"""Dependency-free XLSX export for immutable synthetic commercial snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import re
from typing import Iterable
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


EXPORTER_VERSION = "1.0"
RATE_CARD_NAME = "Synthetic SGD demonstration rate card"
SHEET_NAMES = ("Rate card (SGD)", "Effort WBS", "Assumptions", "Summary")


class ExportError(ValueError):
    """Raised when the snapshot cannot safely be exported."""


@dataclass(frozen=True)
class XlsxPackage:
    content: bytes

    def __bytes__(self) -> bytes:
        return self.content

    def namelist(self) -> list[str]:
        with ZipFile(BytesIO(self.content)) as archive:
            return archive.namelist()

    def shared_strings(self) -> str:
        with ZipFile(BytesIO(self.content)) as archive:
            return archive.read("xl/sharedStrings.xml").decode("utf-8")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def validate_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict) or set(("snapshot_id", "sha256", "payload")) - set(snapshot):
        raise ExportError("immutable snapshot identity, hash and payload are required")
    payload = snapshot["payload"]
    if not isinstance(payload, dict):
        raise ExportError("snapshot payload must be an object")
    if payload.get("synthetic_demo") is not True or payload.get("nonbinding") is not True:
        raise ExportError("only synthetic, nonbinding input may be exported")
    authorization = payload.get("commercial_authorization")
    if not isinstance(authorization, dict) or authorization.get("client_quote_allowed") is not False:
        raise ExportError("client quote authority must remain false")
    if payload.get("currency") != "SGD":
        raise ExportError("only SGD snapshots are supported")
    if payload.get("calculation_status") != "calculated" or payload.get("calculation_blockers"):
        raise ExportError("blocked commercial snapshots cannot be exported")
    rate_card = payload.get("rate_card")
    if not isinstance(rate_card, dict) or rate_card.get("name") != RATE_CARD_NAME:
        raise ExportError(f"rate card must be named {RATE_CARD_NAME}")
    actual_hash = sha256(canonical(payload)).hexdigest()
    if snapshot.get("sha256") != actual_hash:
        raise ExportError("snapshot hash is stale or invalid")
    return payload


def validate_effort_rows(rows: Iterable[dict]) -> list[dict]:
    rows = list(rows)
    required = {"deliverable_id", "wbs_id", "task_name", "role", "low_hours", "central_hours", "high_hours", "status", "notes"}
    if not rows:
        raise ExportError("effort WBS is empty")
    for index, row in enumerate(rows, start=2):
        if not isinstance(row, dict) or required - set(row):
            raise ExportError(f"effort WBS row {index} is missing required fields")
        if not row["deliverable_id"] or not row["wbs_id"]:
            raise ExportError(f"effort WBS row {index} lacks an identity")
    return rows


def build_tables(snapshot: dict, effort_rows: list[dict]) -> list[list[list[str]]]:
    payload = snapshot["payload"]
    rate_card = payload["rate_card"]
    rate_table = [
        ["Rate card (SGD)"],
        ["Synthetic and non-binding — not a client quote"],
        ["Snapshot ID", snapshot["snapshot_id"]],
        ["Snapshot SHA-256", snapshot["sha256"]],
        ["Rate card", rate_card["name"]],
        ["Rate card ID", str(rate_card["id"])],
        ["Revision", str(rate_card["revision"])],
        [],
        ["Work package", "Role", "Rate SGD/hour", "Low hours", "Central hours", "High hours"],
    ]
    for package in payload.get("work_packages", []):
        hours = package.get("hours", {})
        rate_table.append([
            str(package.get("name", "")),
            str(package.get("role", "")),
            str(package.get("rate_sgd_per_hour", "")),
            str(hours.get("low", "")),
            str(hours.get("central", "")),
            str(hours.get("high", "")),
        ])

    effort_headers = ["deliverable_id", "wbs_id", "task_name", "role", "low_hours", "central_hours", "high_hours", "status", "notes"]
    effort_table = [["Effort WBS"], ["Assessment forecast — not observed actual effort"], effort_headers]
    effort_table.extend([[str(row.get(key, "")) for key in effort_headers] for row in effort_rows])

    risk = payload.get("risk_assumption") or {}
    assumptions_table = [
        ["Assumptions"],
        ["Synthetic and non-binding — verify all terms outside this demonstrator"],
        ["Risk allowance percent", str(risk.get("value_percent", ""))],
        ["Risk rationale", str(risk.get("rationale", ""))],
        ["Tax", "Unspecified; not added"],
        ["Expenses", "Unspecified; not added"],
        ["Security scanning", "Not performed"],
    ]
    for diagnostic in payload.get("diagnostics", []):
        assumptions_table.append(["Diagnostic", str(diagnostic)])

    summary_table = [
        ["Summary"],
        ["Synthetic SGD commercial illustration — non-binding and not a client quote"],
        ["Band", "Subtotal SGD", "Allowance %", "Allowance SGD", "Total excluding tax SGD"],
    ]
    for band in ("low", "central", "high"):
        values = payload["totals"][band]
        summary_table.append([
            band.title(), values["subtotal_sgd"], values["risk_allowance_percent"],
            values["risk_allowance_sgd"], values["total_excluding_tax_sgd"],
        ])
    summary_table.extend([
        [],
        ["Client quote allowed", "false"],
        ["Human commercial approval", "Required outside simulator"],
        ["Bobcoins", "Separate from SI price"],
    ])
    return [rate_table, effort_table, assumptions_table, summary_table]


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xml_text(value: object) -> str:
    return escape(str(value), {'"': "&quot;"})


def make_shared_strings(tables: list[list[list[str]]]) -> tuple[list[str], dict[str, int]]:
    values: list[str] = []
    indexes: dict[str, int] = {}
    for table in tables:
        for row in table:
            for value in row:
                text = str(value)
                if text not in indexes:
                    indexes[text] = len(values)
                    values.append(text)
    return values, indexes


def worksheet_xml(table: list[list[str]], indexes: dict[str, int]) -> bytes:
    rows = []
    for row_number, row in enumerate(table, start=1):
        cells = []
        for column, value in enumerate(row, start=1):
            reference = f"{column_name(column)}{row_number}"
            cells.append(f'<c r="{reference}" t="s"><v>{indexes[str(value)]}</v></c>')
        rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(rows)}</sheetData></worksheet>').encode("utf-8")


def zip_write(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, content)


def build_xlsx(*, snapshot: dict, effort_rows: Iterable[dict]) -> XlsxPackage:
    validate_snapshot(snapshot)
    effort_rows = validate_effort_rows(effort_rows)
    tables = build_tables(snapshot, effort_rows)
    strings, indexes = make_shared_strings(tables)
    shared_xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                  f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{sum(len(row) for table in tables for row in table)}" uniqueCount="{len(strings)}">'
                  + "".join(f'<si><t xml:space="preserve">{xml_text(value)}</t></si>' for value in strings)
                  + "</sst>").encode("utf-8")
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, 5)
    )
    content_types = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'{sheet_overrides}'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>').encode("utf-8")
    root_rels = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>').encode("utf-8")
    sheets = "".join(f'<sheet name="{xml_text(name)}" sheetId="{index}" r:id="rId{index}"/>' for index, name in enumerate(SHEET_NAMES, 1))
    workbook = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheets}</sheets></workbook>').encode("utf-8")
    relationships = [
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, 5)
    ]
    relationships.extend([
        '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>',
        '<Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
    ])
    workbook_rels = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(relationships) + "</Relationships>").encode("utf-8")
    styles = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Aptos"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="1"><xf xfId="0"/></cellXfs></styleSheet>').encode("utf-8")

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        zip_write(archive, "[Content_Types].xml", content_types)
        zip_write(archive, "_rels/.rels", root_rels)
        zip_write(archive, "xl/workbook.xml", workbook)
        zip_write(archive, "xl/_rels/workbook.xml.rels", workbook_rels)
        zip_write(archive, "xl/sharedStrings.xml", shared_xml)
        zip_write(archive, "xl/styles.xml", styles)
        for index, table in enumerate(tables, start=1):
            zip_write(archive, f"xl/worksheets/sheet{index}.xml", worksheet_xml(table, indexes))
    return XlsxPackage(buffer.getvalue())


def build_export_manifest(snapshot: dict, effort_csv: bytes, workbook: bytes, *, effort_source: str = "effort-model.csv") -> dict:
    payload = validate_snapshot(snapshot)
    return {
        "schema_version": 1,
        "status": "passed",
        "exporter_version": EXPORTER_VERSION,
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_sha256": snapshot["sha256"],
        "effort_csv_sha256": sha256(effort_csv).hexdigest(),
        "effort_csv_source": effort_source,
        "workbook_sha256": sha256(workbook).hexdigest(),
        "currency": "SGD",
        "rate_card_name": payload["rate_card"]["name"],
        "synthetic_demo": True,
        "nonbinding": True,
        "client_quote_allowed": False,
        "warnings": [
            "Synthetic demonstration only; not a client quote.",
            "Human commercial approval, tax, expenses and terms require verification outside the simulator.",
            "Effort WBS rows are assessment forecasts, not observed actual delivery effort.",
        ],
    }
