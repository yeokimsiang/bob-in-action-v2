"""Read-only checks MCP server (stdio): Bob runs a stage's README checkers on its own run.

One tool, run_stage_checks(run, stage), runs the same checker commands the README tells
the user to run after that stage, unchanged, as separate processes, on runs/<run>/ and
returns each checker's exit code and errors. Files a checker would write (the effort
CSV, the illustrative price table, the effort check) go to a temporary folder that is
deleted afterwards, so the tool writes nothing under runs/ and the user's own checker
run afterwards starts clean. It changes no rule: the user still runs the README
checkers as the gate. No environment variables, no network, no Bob credits.

.bob/mcp.json starts it as: python ${workspaceFolder}/tools/checkers/checks_server.py
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import BinaryIO, Iterable

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools" / "mcp"))

from mcp_common import ToolError, serve  # noqa: E402

SERVER = "checks"
RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
STAGES = ("discover", "assess", "plan", "price")
TIMEOUT_SECONDS = 120
MAX_ERRORS = 60
TOOLS = [{
    "name": "run_stage_checks",
    "description": (
        "Run the README checkers for one stage (discover, assess, plan or price) on runs/<run>/ and return "
        "every checker's exit code and errors. Read-only: writes nothing under runs/. Call it after writing "
        "the stage's files; passed true means every checker for that stage exits 0."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "run": {"type": "string", "description": "the run name, the folder under runs/"},
            "stage": {"type": "string", "enum": list(STAGES)},
        },
        "required": ["run", "stage"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True},
}]


def _script(relative: str) -> str:
    return str(KIT / relative)


def _run_folder(run: str, runs: Path) -> Path:
    if not isinstance(run, str) or not RUN_NAME.fullmatch(run):
        raise ToolError("run must match [A-Za-z0-9][A-Za-z0-9._-]* (the folder name under runs/)")
    folder = runs / run
    if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != runs.resolve():
        raise ToolError(f"runs/{run}/ does not exist in this workspace")
    return folder


def _errors(stdout: str, stderr: str, report: Path | None) -> list[str]:
    texts = [report.read_text(encoding="utf-8-sig")] if report is not None and report.is_file() else []
    texts.append(stdout)
    for text in texts:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("errors"), list):
            return [str(item) for item in payload["errors"]]
    output = (stderr.strip() or stdout.strip())[-2000:]
    return [output] if output else []


def _check(name: str, command: list[str], report: Path | None = None) -> dict:
    try:
        done = subprocess.run(command, cwd=KIT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return {"check": name, "exit_code": None, "errors": [f"timed out after {TIMEOUT_SECONDS} seconds"]}
    errors = [] if done.returncode == 0 else _errors(done.stdout, done.stderr, report)
    if done.returncode != 0 and not errors:
        errors = [f"exited {done.returncode} with no output"]
    return {"check": name, "exit_code": done.returncode, "errors": errors[:MAX_ERRORS]}


def _not_run(name: str, needs: str) -> dict:
    return {"check": name, "exit_code": None, "errors": [f"not run: needs {needs} to pass first"]}


def run_stage_checks(run: str, stage: str, runs: Path | None = None) -> dict:
    """Run one stage's README checkers on runs/<run>/; nothing is written under runs/."""
    if stage not in STAGES:
        raise ToolError(f"stage must be one of {', '.join(STAGES)}")
    runs = runs if runs is not None else KIT / "runs"
    folder = _run_folder(run, runs)
    data, reports = folder / "data", folder / "reports"
    python = sys.executable
    quality = _script(".bob/skills/si-collate/scripts/validate_report_quality.py")
    rubric = str(KIT / ".bob" / "standards" / "report-quality-rubric.json")
    checks: list[dict] = []
    if stage == "discover":
        checks.append(_check("normalize_evidence.py", [
            python, _script(".bob/skills/si-discover/scripts/normalize_evidence.py"),
            "--input", str(data / "discovery-evidence.json"), "--source-root", str(KIT)]))
    elif stage == "assess":
        checks.append(_check("validate_findings.py", [
            python, _script(".bob/skills/si-assess/scripts/validate_findings.py"),
            "--input", str(data / "findings.json"), "--run-id", run,
            "--evidence-map", str(data / "discovery-evidence.json")]))
        checks.append(_check("validate_report_quality.py --partial-stage assess", [
            python, quality, "--partial-stage", "assess", "--pack", str(reports),
            "--findings", str(data / "findings.json")]))
    elif stage == "plan":
        checks.append(_check("validate_dag.py", [
            python, _script(".bob/skills/si-plan/scripts/validate_dag.py"),
            "--input", str(data / "plan-tasks.json"), "--run-id", run, "--findings", str(data / "findings.json")]))
        checks.append(_check("validate_report_quality.py --partial-stage plan", [
            python, quality, "--partial-stage", "plan", "--pack", str(reports),
            "--findings", str(data / "findings.json"), "--plan-tasks", str(data / "plan-tasks.json"),
            "--rubric", rubric]))
    else:
        with tempfile.TemporaryDirectory(prefix="si-checks-") as scratch:
            work = Path(scratch)
            pack = work / "reports"
            shutil.copytree(reports, pack, ignore=shutil.ignore_patterns("effort-model.csv"))
            csv_path, price_path, effort_path = pack / "effort-model.csv", work / "illustrative-price.json", work / "effort-check.json"
            effort = _check("validate_effort.py", [
                python, _script(".bob/skills/si-business/scripts/validate_effort.py"),
                "--input", str(data / "effort-rows.json"), "--run-id", run,
                "--plan-tasks", str(data / "plan-tasks.json"), "--csv-output", str(csv_path)])
            checks.append(effort)
            if effort["exit_code"] != 0:
                checks.append(_not_run("illustrative_price.py", "validate_effort.py"))
                checks.append(_not_run("check_effort_numbers.py", "validate_effort.py"))
                checks.append(_not_run("validate_report_quality.py", "validate_effort.py"))
            else:
                price = _check("illustrative_price.py", [
                    python, _script("tools/checkers/illustrative_price.py"), "--csv", str(csv_path),
                    "--sow", str(reports / "sow.md"), "--run-id", run, "--output", str(price_path)])
                checks.append(price)
                if price["exit_code"] != 0:
                    checks.append(_not_run("check_effort_numbers.py", "illustrative_price.py"))
                else:
                    checks.append(_check("check_effort_numbers.py", [
                        python, _script("tools/checkers/check_effort_numbers.py"), "--csv", str(csv_path),
                        "--sow", str(reports / "sow.md"), "--price-table", str(price_path),
                        "--output", str(effort_path)], report=effort_path))
                checks.append(_check("validate_report_quality.py", [
                    python, quality, "--pack", str(pack), "--rubric", rubric,
                    "--findings", str(data / "findings.json"), "--plan-tasks", str(data / "plan-tasks.json"),
                    "--effort-rows", str(data / "effort-rows.json")]))
    return {
        "run": run,
        "stage": stage,
        "passed": all(check["exit_code"] == 0 for check in checks),
        "checks": checks,
        "note": "The user still runs the README checkers as the gate; this tool wrote nothing under runs/.",
    }


def serve_checks(stream_in: Iterable[bytes] | None = None, stream_out: BinaryIO | None = None,
                 runs: Path | None = None) -> None:
    def invoke(name: str, args: dict) -> object:
        if name != "run_stage_checks":
            raise KeyError(name)
        return run_stage_checks(args["run"], args["stage"], runs=runs)

    serve(SERVER, invoke, stream_in, stream_out, tools=TOOLS)


if __name__ == "__main__":
    serve_checks()
