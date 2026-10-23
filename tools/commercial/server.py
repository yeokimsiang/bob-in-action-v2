"""Loopback-only commercial input demonstrator for the Bob business agent."""

from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from export_xlsx import ExportError, build_export_manifest, build_xlsx


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DB_DEFAULT = ROOT / "data" / "commercial.sqlite3"
EFFORT_CSV = REPO_ROOT / "MIGRATION" / "assessment" / "reports" / "effort-model.csv"
KINDS = ("rate_card", "rate", "work_package", "assumption", "pilot_metric", "document")
MONEY = Decimal("0.01")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
EXPORTER_VERSION = "2.0"
EXPORTER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


class InputError(ValueError):
    pass


class ConflictError(ValueError):
    pass


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def field_text(data: dict, key: str, *, required: bool = True, limit: int = 500) -> str:
    value = data.get(key)
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise InputError(f"{key} must be {'nonempty ' if required else ''}text of at most {limit} characters")
    return value.strip()


def identifier(data: dict, key: str) -> str:
    value = field_text(data, key, limit=80)
    if not ID_RE.fullmatch(value):
        raise InputError(f"{key} must use letters, digits, dots, underscores or hyphens")
    return value


def day(data: dict, key: str, *, required: bool = True) -> str:
    value = field_text(data, key, required=required, limit=10)
    if value:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise InputError(f"{key} must be an ISO date") from exc
        if parsed.isoformat() != value:
            raise InputError(f"{key} must use YYYY-MM-DD")
    return value


def decimal_string(data: dict, key: str, *, upper: Decimal, required: bool = True) -> str:
    raw = data.get(key)
    if raw is None and not required:
        return ""
    if not isinstance(raw, str) or not re.fullmatch(r"\d{1,9}(?:\.\d{1,2})?", raw):
        raise InputError(f"{key} must be a nonnegative decimal string with at most two decimal places")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise InputError(f"{key} is invalid") from exc
    if not value.is_finite() or value > upper:
        raise InputError(f"{key} must be at most {upper}")
    return str(value)


def evidence(data: dict) -> list[str]:
    value = data.get("evidence_ids")
    if not isinstance(value, list) or len(value) > 20 or any(not isinstance(v, str) or not ID_RE.fullmatch(v) for v in value):
        raise InputError("evidence_ids must be a list of at most 20 safe identifiers")
    return list(dict.fromkeys(value))


def approved_fields(data: dict) -> dict:
    status = field_text(data, "status", limit=8)
    if status not in ("draft", "approved"):
        raise InputError("status must be draft or approved")
    actor = field_text(data, "approval_actor", required=False, limit=100)
    ev = field_text(data, "approval_evidence_id", required=False, limit=80)
    if ev and not ID_RE.fullmatch(ev):
        raise InputError("approval_evidence_id is invalid")
    if status == "approved" and (not actor or not ev):
        raise InputError("approved status needs approval_actor and approval_evidence_id")
    return {"status": status, "approval_actor": actor, "approval_evidence_id": ev}


def validate(kind: str, source: dict) -> dict:
    if kind not in KINDS or not isinstance(source, dict):
        raise InputError("unknown record kind or invalid JSON object")
    data = dict(source)
    if kind == "rate_card":
        allowed = {"name", "currency", "valid_from", "valid_to", "status", "approval_actor", "approval_evidence_id"}
        out = {"name": field_text(data, "name", limit=120), "currency": field_text(data, "currency", limit=3),
               "valid_from": day(data, "valid_from"), "valid_to": day(data, "valid_to", required=False)}
        if out["currency"] != "SGD":
            raise InputError("this demonstrator supports SGD only")
        if out["valid_to"] and out["valid_to"] < out["valid_from"]:
            raise InputError("valid_to precedes valid_from")
        out.update(approved_fields(data))
    elif kind == "rate":
        allowed = {"card_id", "role", "hourly_rate", "status", "approval_actor", "approval_evidence_id"}
        out = {"card_id": identifier(data, "card_id"), "role": field_text(data, "role", limit=100),
               "hourly_rate": decimal_string(data, "hourly_rate", upper=Decimal("100000"))}
        out.update(approved_fields(data))
    elif kind == "work_package":
        allowed = {"name", "role", "low_hours", "central_hours", "high_hours", "inclusion", "evidence_ids"}
        out = {"name": field_text(data, "name", limit=140), "role": field_text(data, "role", limit=100),
               "inclusion": field_text(data, "inclusion", limit=1000), "evidence_ids": evidence(data)}
        for key in ("low_hours", "central_hours", "high_hours"):
            out[key] = decimal_string(data, key, upper=Decimal("100000"))
        if not (Decimal(out["low_hours"]) <= Decimal(out["central_hours"]) <= Decimal(out["high_hours"])):
            raise InputError("hours must satisfy low <= central <= high")
    elif kind == "assumption":
        allowed = {"name", "value", "unit", "rationale", "evidence_ids"}
        out = {"name": field_text(data, "name", limit=120), "value": decimal_string(data, "value", upper=Decimal("100")),
               "unit": field_text(data, "unit", limit=30), "rationale": field_text(data, "rationale", limit=1000),
               "evidence_ids": evidence(data)}
        if out["name"] != "risk_allowance_percent" or out["unit"] != "percent":
            raise InputError("only risk_allowance_percent in percent is supported")
    elif kind == "pilot_metric":
        allowed = {"name", "value", "unit", "measurement_status", "evidence_ids"}
        status = field_text(data, "measurement_status", limit=7)
        if status not in ("unknown", "actual"):
            raise InputError("measurement_status must be unknown or actual")
        raw_value = data.get("value")
        value = "" if raw_value == "" and status == "unknown" else decimal_string(data, "value", upper=Decimal("100000000"))
        out = {"name": field_text(data, "name", limit=120), "value": value, "unit": field_text(data, "unit", limit=40),
               "measurement_status": status, "evidence_ids": evidence(data)}
        if status == "unknown" and (value or out["evidence_ids"]):
            raise InputError("unknown measurement must have empty value and evidence")
        if status == "actual" and not out["evidence_ids"]:
            raise InputError("actual measurement requires evidence_ids")
    else:
        allowed = {"title", "version", "source", "sha256", "status"}
        status = field_text(data, "status", limit=10)
        if status not in ("reference", "current", "superseded"):
            raise InputError("document status must be reference, current or superseded")
        digest = field_text(data, "sha256", limit=64)
        if not HASH_RE.fullmatch(digest):
            raise InputError("sha256 must be 64 lowercase hex characters")
        out = {"title": field_text(data, "title", limit=140), "version": field_text(data, "version", limit=80),
               "source": field_text(data, "source", limit=500), "sha256": digest, "status": status}
    extra = set(data) - allowed
    if extra:
        raise InputError("unexpected fields: " + ", ".join(sorted(extra)))
    return out


SEEDS = (
    ("rate_card", "sample-sgd-2026", {"name": "Synthetic SGD demonstration rate card", "currency": "SGD", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "status": "draft", "approval_actor": "", "approval_evidence_id": ""}),
    ("rate", "sample-architect", {"card_id": "sample-sgd-2026", "role": "Solution architect", "hourly_rate": "180", "status": "draft", "approval_actor": "", "approval_evidence_id": ""}),
    ("rate", "sample-engineer", {"card_id": "sample-sgd-2026", "role": "Migration engineer", "hourly_rate": "140", "status": "draft", "approval_actor": "", "approval_evidence_id": ""}),
    ("work_package", "sample-assessment", {"name": "Estate assessment", "role": "Solution architect", "low_hours": "16", "central_hours": "24", "high_hours": "40", "inclusion": "Review supplied inventory and produce a migration assessment with assumptions and open questions.", "evidence_ids": ["DEMO-SCOPE-1"]}),
    ("work_package", "sample-migration", {"name": "Migration preparation", "role": "Migration engineer", "low_hours": "40", "central_hours": "64", "high_hours": "96", "inclusion": "Prepare a sample migration plan and validation checklist for the agreed application boundary.", "evidence_ids": ["DEMO-SCOPE-1"]}),
    ("assumption", "risk-allowance", {"name": "risk_allowance_percent", "value": "15", "unit": "percent", "rationale": "Synthetic additive allowance for uncertainty; replace with an agreed figure.", "evidence_ids": ["DEMO-ASSUMPTION-1"]}),
    ("pilot_metric", "pilot-throughput", {"name": "Pilot throughput", "value": "", "unit": "applications/week", "measurement_status": "unknown", "evidence_ids": []}),
    ("pilot_metric", "pilot-rework", {"name": "Pilot rework", "value": "", "unit": "person-hours", "measurement_status": "unknown", "evidence_ids": []}),
    ("document", "DEMO-SCOPE-1", {"title": "Synthetic sample scope", "version": "1", "source": "samples/synthetic-scope.txt", "sha256": sha256((ROOT / "samples" / "synthetic-scope.txt").read_bytes()).hexdigest(), "status": "reference"}),
    ("document", "DEMO-ASSUMPTION-1", {"title": "Synthetic risk allowance note", "version": "1", "source": "samples/synthetic-assumption.txt", "sha256": sha256((ROOT / "samples" / "synthetic-assumption.txt").read_bytes()).hexdigest(), "status": "reference"}),
)


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init(self):
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                    revision INTEGER NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    record_id TEXT NOT NULL, revision INTEGER NOT NULL, actor TEXT NOT NULL,
                    action TEXT NOT NULL, before_json TEXT, after_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, payload TEXT NOT NULL, sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON snapshots
                    BEGIN SELECT RAISE(ABORT, 'snapshots are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON snapshots
                    BEGIN SELECT RAISE(ABORT, 'snapshots are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS snapshots_no_replace BEFORE INSERT ON snapshots
                    WHEN EXISTS(SELECT 1 FROM snapshots WHERE id=NEW.id)
                    BEGIN SELECT RAISE(ABORT, 'snapshots are immutable'); END;
            """)
            # Serialize the empty-check and all seed/audit inserts across first-start callers.
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0:
                for kind, rid, source in SEEDS:
                    data = validate(kind, source)
                    stamp = now()
                    con.execute("INSERT INTO records VALUES(?,?,?,?,?)", (kind, rid, canonical(data), 1, stamp))
                    con.execute("INSERT INTO audit(kind,record_id,revision,actor,action,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                (kind, rid, 1, "system-seed", "create", None, canonical(data), stamp))

    def list(self) -> list[dict]:
        with self.connect() as con:
            return self._list(con)

    @staticmethod
    def _list(con) -> list[dict]:
        rows = con.execute("SELECT kind,id,data,revision,updated_at FROM records ORDER BY kind,id").fetchall()
        return [{"kind": row["kind"], "id": row["id"], "data": json.loads(row["data"]),
                 "revision": row["revision"], "updated_at": row["updated_at"]} for row in rows]

    def save(self, kind: str, rid: str, source: dict, revision: int, actor: str) -> dict:
        if kind not in KINDS or not ID_RE.fullmatch(rid):
            raise InputError("invalid kind or record id")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise InputError("revision must be a nonnegative integer")
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 100:
            raise InputError("actor is required (self-asserted; no authentication)")
        data = validate(kind, source)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT data,revision FROM records WHERE kind=? AND id=?", (kind, rid)).fetchone()
            if old and old["revision"] != revision:
                raise ConflictError(f"stale revision: current is {old['revision']}")
            if not old and revision != 0:
                raise ConflictError("new records require revision 0")
            new_revision = revision + 1
            stamp = now()
            con.execute("INSERT INTO records(kind,id,data,revision,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data, revision=excluded.revision, updated_at=excluded.updated_at",
                        (kind, rid, canonical(data), new_revision, stamp))
            con.execute("INSERT INTO audit(kind,record_id,revision,actor,action,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        (kind, rid, new_revision, actor.strip(), "update" if old else "create",
                         old["data"] if old else None, canonical(data), stamp))
            return {"kind": kind, "id": rid, "data": data, "revision": new_revision, "updated_at": stamp}

    def audit(self, limit: int = 100) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT id,kind,record_id,revision,actor,action,created_at FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]

    def snapshot(self) -> dict:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            payload = build_bob_input(self._list(con))
            payload["created_at"] = now()
            raw = canonical(payload)
            digest = sha256(raw.encode("utf-8")).hexdigest()
            sid = str(uuid4())
            con.execute("INSERT INTO snapshots VALUES(?,?,?,?)", (sid, raw, digest, payload["created_at"]))
            return {"snapshot_id": sid, "sha256": digest, "payload": payload}

    def get_snapshot(self, sid: str) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT id,payload,sha256 FROM snapshots WHERE id=?", (sid,)).fetchone()
            return {"snapshot_id": row["id"], "sha256": row["sha256"], "payload": json.loads(row["payload"])} if row else None


def money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def build_snapshot_export(snapshot: dict, effort_csv: Path = EFFORT_CSV) -> tuple[bytes, dict]:
    try:
        effort_bytes = effort_csv.read_bytes()
    except OSError as exc:
        raise ExportError(f"effort CSV is unavailable: {effort_csv}") from exc
    try:
        rows = [
            row for row in csv.DictReader(effort_bytes.decode("utf-8-sig").splitlines())
            if row.get("deliverable_id") and row.get("wbs_id")
        ]
    except UnicodeDecodeError as exc:
        raise ExportError("effort CSV must be UTF-8") from exc
    workbook = bytes(build_xlsx(snapshot=snapshot, effort_rows=rows))
    try:
        effort_source = effort_csv.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        effort_source = effort_csv.name
    manifest = build_export_manifest(snapshot, effort_bytes, workbook, effort_source=effort_source)
    return workbook, manifest


def build_bob_input(records: list[dict], *, as_of: date | None = None, illustrative: bool = False) -> dict:
    today = as_of or date.today()
    grouped = {kind: [r for r in records if r["kind"] == kind] for kind in KINDS}
    diagnostics = []
    registered_evidence = {d["id"] for d in grouped["document"] if d["data"]["status"] in ("reference", "current")}
    cards = grouped["rate_card"]
    eligible = ([c for c in cards if c["id"] == "sample-sgd-2026"] or cards) if illustrative else [c for c in cards if c["data"]["status"] == "approved"]
    card = eligible[0] if len(eligible) == 1 else None
    if not card:
        diagnostics.append("Exactly one " + ("rate card" if illustrative else "locally approved rate card") + " is required for this calculation.")
    elif not (card["data"]["valid_from"] <= today.isoformat() <= (card["data"]["valid_to"] or "9999-12-31")):
        diagnostics.append("Rate card is outside its validity dates.")
    if card and not illustrative and card["data"]["status"] != "approved":
        diagnostics.append("Rate card is not approved with recorded approval evidence.")
    if card and not illustrative and card["data"]["approval_evidence_id"] not in registered_evidence:
        diagnostics.append("Rate card approval evidence is absent from the active document register.")
    matching_rates = [r for r in grouped["rate"] if card and r["data"]["card_id"] == card["id"]]
    rates = {r["data"]["role"]: r for r in matching_rates}
    if len(rates) != len(matching_rates):
        diagnostics.append("Duplicate role rates exist on the selected card.")
    packages = grouped["work_package"]
    if not packages:
        diagnostics.append("At least one work package is required.")
    for package in packages:
        role = package["data"]["role"]
        rate = rates.get(role)
        if not rate:
            diagnostics.append(f"Missing rate for role: {role}.")
        elif not illustrative and rate["data"]["status"] != "approved":
            diagnostics.append(f"Rate is not approved for role: {role}.")
        elif not illustrative and rate["data"]["approval_evidence_id"] not in registered_evidence:
            diagnostics.append(f"Rate approval evidence is absent from the active document register: {role}.")
        if not package["data"]["evidence_ids"]:
            diagnostics.append(f"Work package has no evidence: {package['id']}.")
    assumptions = grouped["assumption"]
    if len(assumptions) != 1:
        diagnostics.append("Exactly one risk allowance assumption is required.")
    risk = next((a for a in assumptions if a["data"]["name"] == "risk_allowance_percent"), None)
    if not risk:
        diagnostics.append("Explicit risk allowance assumption is missing.")
    elif not risk["data"]["evidence_ids"]:
        diagnostics.append("Risk allowance assumption has no evidence.")
    for package in packages:
        for evidence_id in package["data"]["evidence_ids"]:
            if evidence_id not in registered_evidence:
                diagnostics.append(f"Work package evidence is absent from the active document register: {evidence_id}.")
    if risk:
        for evidence_id in risk["data"]["evidence_ids"]:
            if evidence_id not in registered_evidence:
                diagnostics.append(f"Risk allowance evidence is absent from the active document register: {evidence_id}.")
    calculation_blockers = list(diagnostics)
    can_calculate = not calculation_blockers
    diagnostics.append("SYNTHETIC / NONBINDING: local approval labels and registered hashes do not establish human authority or source authenticity.")
    diagnostics.append("Client pricing remains unauthorized; actual human approval and tax/expense decisions must be verified outside this simulator.")
    diagnostics.append("WBS input is incomplete: quantities, estimate method, phase, inclusion state, uncertainty and plan/acceptance links require assessment evidence.")
    diagnostics.append("Risk overlap review NOT PERFORMED: ranges and additive allowance may cover the same uncertainty; totals are conditional arithmetic only.")
    pilot_metrics = []
    for metric in grouped["pilot_metric"]:
        data = metric["data"]
        missing = [eid for eid in data["evidence_ids"] if eid not in registered_evidence]
        if data["measurement_status"] == "unknown":
            status, evidence_status = "unknown", "not_provided"
            diagnostics.append(f"Pilot metric remains UNKNOWN: {data['name']}.")
        elif missing:
            status, evidence_status = "unverified_actual", "missing_or_inactive"
            diagnostics.append(f"Pilot actual is unverified: {data['name']}; evidence absent from the active document register: {', '.join(missing)}.")
        else:
            status, evidence_status = "asserted_actual", "registered_unverified"
            diagnostics.append(f"Pilot actual is locally asserted, with source authenticity unverified: {data['name']}.")
        pilot_metrics.append({"id": metric["id"], "name": data["name"], "value": data["value"] or None,
                              "unit": data["unit"], "status": status, "reported_status": data["measurement_status"],
                              "evidence_status": evidence_status, "evidence_ids": data["evidence_ids"],
                              "revision": metric["revision"]})
    bands = ("low", "central", "high")
    effort = {band: Decimal("0") for band in bands}
    effort_by_role = {}
    for package in packages:
        data = package["data"]
        role_effort = effort_by_role.setdefault(data["role"], {band: Decimal("0") for band in bands})
        for band in bands:
            hours = Decimal(data[f"{band}_hours"])
            effort[band] += hours
            role_effort[band] += hours
    lines = []
    totals = None
    if can_calculate:
        subtotals = {band: Decimal("0") for band in bands}
        for package in packages:
            p = package["data"]
            rate = Decimal(rates[p["role"]]["data"]["hourly_rate"])
            line = {"package_id": package["id"], "name": p["name"], "role": p["role"],
                    "rate_sgd_per_hour": money(rate), "rate_revision": rates[p["role"]]["revision"],
                    "rate_approval_evidence_id": rates[p["role"]]["data"]["approval_evidence_id"],
                    "hours": {}, "subtotals_sgd": {}, "inclusion": p["inclusion"],
                    "evidence_ids": p["evidence_ids"], "package_revision": package["revision"]}
            for band in subtotals:
                hours = Decimal(p[f"{band}_hours"])
                amount = (hours * rate).quantize(MONEY, rounding=ROUND_HALF_UP)
                line["hours"][band] = str(hours)
                line["subtotals_sgd"][band] = money(amount)
                subtotals[band] += amount
            lines.append(line)
        pct = Decimal(risk["data"]["value"])
        totals = {band: {"subtotal_sgd": money(base), "risk_allowance_percent": str(pct),
                         "risk_allowance_sgd": money(base * pct / Decimal("100")),
                         "total_excluding_tax_sgd": money(base + (base * pct / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP))}
                  for band, base in subtotals.items()}
    return {"schema_version": 2, "exporter_version": EXPORTER_VERSION, "exporter_sha256": EXPORTER_SHA256,
            "as_of": today.isoformat(), "currency": "SGD", "synthetic_demo": True, "nonbinding": True,
            "scenario": "SYNTHETIC ILLUSTRATION" if illustrative else "SYNTHETIC CONDITIONAL INPUT",
            "pricing_status": "illustrative" if can_calculate and illustrative else "conditional" if can_calculate else "blocked",
            "calculation_status": "calculated" if can_calculate else "blocked",
            "calculation_blockers": calculation_blockers, "approval_trust": "local_assertion_only",
            "commercial_authorization": {"status": "not_authorized", "client_quote_allowed": False,
                "human_approval": "required_outside_simulator", "tax_and_expenses": "not_authorized"},
            "calculation_method": "Decimal: round each package hours x role rate to cents HALF_UP; sum rounded packages; round subtotal x allowance percent to cents HALF_UP; add once. Tax and expenses are not added.",
            "record_revisions": [{"kind": r["kind"], "id": r["id"], "revision": r["revision"]} for r in records],
            "diagnostics": diagnostics, "rate_card": ({"id": card["id"], "name": card["data"]["name"],
                "valid_from": card["data"]["valid_from"], "valid_to": card["data"]["valid_to"],
                "status": card["data"]["status"], "approval_evidence_id": card["data"]["approval_evidence_id"],
                "revision": card["revision"]} if card else None),
            "work_packages": lines if can_calculate else [{"id": p["id"], "name": p["data"]["name"], "role": p["data"]["role"],
                "low_hours": p["data"]["low_hours"], "central_hours": p["data"]["central_hours"],
                "high_hours": p["data"]["high_hours"], "inclusion": p["data"]["inclusion"],
                "evidence_ids": p["data"]["evidence_ids"], "revision": p["revision"]} for p in packages],
            "effort_totals_hours": {band: str(value) for band, value in effort.items()},
            "effort_by_role_hours": {role: {band: str(value) for band, value in values.items()} for role, values in effort_by_role.items()},
            "effort_basis": "entered_forecast_ranges_not_observed_actuals",
            "wbs_readiness": {"status": "incomplete", "missing_fields": ["scoped_quantity", "scope_unit",
                "estimate_method", "uncertainty_driver", "inclusion_state", "phase", "deliverable_id", "plan_id", "acceptance_id"],
                "required_action": "Complete the assessment WBS and reconcile each entered forecast; package names do not establish actual effort or accepted scope."},
            "totals": totals, "risk_assumption": ({"id": risk["id"], "value_percent": risk["data"]["value"], "rationale": risk["data"]["rationale"],
                "double_counting_review": "not_performed", "application_basis": "conditional_additive_arithmetic_only",
                "evidence_ids": risk["data"]["evidence_ids"], "revision": risk["revision"]} if risk else None),
            "pilot_metrics": pilot_metrics,
            "documents": [{"id": d["id"], "title": d["data"]["title"], "version": d["data"]["version"],
                "sha256": d["data"]["sha256"], "hash_verification": "not_performed",
                "status": d["data"]["status"], "revision": d["revision"]} for d in grouped["document"]],
            "tax_treatment": "UNSPECIFIED — no tax added", "expense_treatment": "UNSPECIFIED — no expenses added",
            "bobcoins": "SEPARATE — excluded from SI price"}


def handler_factory(store: Store, port: int):
    token = secrets.token_urlsafe(32)
    permitted_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "BobCommercialDemo/1.0"

        def _safe_host(self):
            return self.headers.get("Host", "") in permitted_hosts

        def _send(self, status: int, value: object, *, content_type: str = "application/json", headers: dict | None = None):
            raw = canonical(value).encode("utf-8") if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'")
            for name, header_value in (headers or {}).items():
                self.send_header(name, header_value)
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self._safe_host():
                return self._send(400, {"error": "unexpected Host"})
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/bootstrap":
                return self._send(200, {"csrf_token": token, "local_demo": True})
            if path == "/api/records":
                return self._send(200, {"records": store.list()})
            if path == "/api/audit":
                return self._send(200, {"audit": store.audit()})
            if path == "/api/bob-input":
                return self._send(200, build_bob_input(store.list()))
            if path == "/api/illustration":
                return self._send(200, build_bob_input(store.list(), illustrative=True))
            if path.startswith("/api/snapshots/"):
                sid = path.rsplit("/", 1)[-1]
                value = store.get_snapshot(sid)
                return self._send(200, value) if value else self._send(404, {"error": "snapshot not found"})
            if path == "/api/export/xlsx":
                query = parse_qs(parsed.query, keep_blank_values=True)
                if set(query) != {"snapshot_id"} or len(query["snapshot_id"]) != 1 or not query["snapshot_id"][0]:
                    return self._send(400, {"error": "exactly one snapshot_id query parameter is required"})
                snapshot = store.get_snapshot(query["snapshot_id"][0])
                if not snapshot:
                    return self._send(404, {"error": "snapshot not found"})
                try:
                    workbook, _manifest = build_snapshot_export(snapshot)
                except ExportError as exc:
                    return self._send(409, {"error": str(exc)})
                return self._send(
                    200,
                    workbook,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="bob-commercial-{snapshot["snapshot_id"]}.xlsx"'},
                )
            static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
            if path in static:
                name, mime = static[path]
                return self._send(200, (ROOT / name).read_bytes(), content_type=mime)
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._safe_host():
                return self._send(400, {"error": "unexpected Host"})
            origin = self.headers.get("Origin", "")
            if origin not in {f"http://{host}" for host in permitted_hosts} or self.headers.get("X-CSRF-Token") != token:
                # Consume a bounded request body before replying. On Windows,
                # closing a response while request bytes remain unread can
                # surface as WSAECONNABORTED in the client instead of the 403.
                try:
                    rejected_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    rejected_length = 0
                if 0 < rejected_length <= 100_000:
                    self.rfile.read(rejected_length)
                else:
                    self.close_connection = True
                return self._send(403, {"error": "same-origin and CSRF token required"})
            if self.headers.get_content_type() != "application/json":
                return self._send(415, {"error": "application/json required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100_000:
                    raise InputError("JSON body must be 1 to 100000 bytes")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise InputError("JSON object required")
                path = urlparse(self.path).path
                if path == "/api/records":
                    if set(body) != {"kind", "id", "data", "revision", "actor"}:
                        raise InputError("kind, id, data, revision and actor are required")
                    result = store.save(body["kind"], body["id"], body["data"], body["revision"], body["actor"])
                    return self._send(200, result)
                if path == "/api/snapshots":
                    if body:
                        raise InputError("snapshot request body must be empty")
                    return self._send(201, store.snapshot())
                if path == "/api/export-manifest":
                    if set(body) != {"snapshot_id"} or not isinstance(body["snapshot_id"], str) or not body["snapshot_id"]:
                        raise InputError("snapshot_id is required")
                    snapshot = store.get_snapshot(body["snapshot_id"])
                    if not snapshot:
                        return self._send(404, {"error": "snapshot not found"})
                    try:
                        _workbook, manifest = build_snapshot_export(snapshot)
                    except ExportError as exc:
                        return self._send(409, {"error": str(exc)})
                    return self._send(200, manifest)
                return self._send(404, {"error": "not found"})
            except ConflictError as exc:
                return self._send(409, {"error": str(exc)})
            except (InputError, ValueError, TypeError, json.JSONDecodeError) as exc:
                return self._send(400, {"error": str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=DB_DEFAULT)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024-65535")
    store = Store(args.db)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(store, args.port))
    print(f"Bob commercial demo: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
