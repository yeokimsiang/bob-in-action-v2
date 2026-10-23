# The SI kit for IBM Bob

This folder configures vanilla IBM Bob to do an SI's assessment work on the legacy app in `../app/`: four slash commands, nine persona modes, rules, skills with their checkers, a hook guard, four synthetic MCP servers and a read-only checks server. It is custom SI configuration, not an IBM premium package. Kit version: see `kit-version.json`.

The root `README.md` walks through a run. This file explains the pieces.

## Commands

| Command | Mode | Bob writes (under `runs/<name>/`) | You then run |
|---|---|---|---|
| `/discover <name> [source-revision]` | `si-architect` | `data/discovery-evidence.json` | `normalize_evidence.py` and the metrics tool |
| `/assess <name>` | `si-architect` | `reports/assessment.md`, `reports/target-annexes.md`, `data/findings.json` | `validate_findings.py`, report check (assess) |
| `/plan <name>` | `si-pm` | `reports/implementation-plan.md`, `reports/validation-ledger.md`, `data/plan-tasks.json` | `validate_dag.py`, report check (plan) |
| `/price <name>` | `si-commercial` | `reports/sow.md`, `data/effort-rows.json` | `validate_effort.py`, `illustrative_price.py`, `check_effort_numbers.py`, full report check |

A command cannot switch modes, so switch first (`/mode si-architect`, and so on); each command's text tells Bob to stop if the mode is wrong. That is an instruction, not enforcement: what enforces writes is the mode's `fileRegex` and the guard hook. Before it stops, each command checks its own files with the `checks` MCP tool (see [MCP](#mcp)), corrects only what the errors name for at most three rounds, and tells you whether its last check passed; you still run the checkers. Each command has a wrapper skill of the same name in `skills/` with identical text, for Bob versions that load commands as skills. `<name>` must match `[A-Za-z0-9][A-Za-z0-9._-]*`.

## Modes

`custom_modes.yaml` defines nine personas. Writers get an `edit` group whose `fileRegex` accepts only their own stage's files under `runs/<name>/`, as a relative path or an absolute path ending in `runs/<name>/...`, and refuses any path containing `..` or an evaluator folder name.

| Mode | Groups | May write |
|---|---|---|
| `si-orchestrator` | read, skill, subagent (explore, general) | nothing |
| `si-architect` | read, edit, skill, mcp (tickets, checks) | Discover and Assess files |
| `si-pm` | read, edit, skill, mcp (roster, checks) | Plan files |
| `si-commercial` | read, edit, skill, mcp (rate card, roster, timesheets, checks) | Price files |
| `si-collator` | read, skill | nothing |
| `si-developer` | read, edit, skill | `pilot/pilot-plan.json`, `pilot/candidate/**` (no `.git`, no scripts) |
| `si-senior-reviewer` | read, edit, skill | `pilot/pilot-review.json` |
| `si-qa` | read, edit, skill | `pilot/pilot-verification.json` |
| `si-tech-lead` | read, skill | nothing |

No mode has a shell (`command` group). Bob writes and checks its own files through the read-only checks tool; you run the checkers as the gate and paste any failures back.

## Rules

Bob loads `rules/` for every mode and `rules-<slug>/` for the active mode only; the folder name must match the mode's slug exactly, or Bob ignores it without warning. The root `AGENTS.md` is loaded in every mode too.

- `rules/00-governance.md`: goal, workspace boundaries, hooks, conduct.
- `rules/10-evidence.md`: evidence, IDs and provenance.
- `rules/20-runs-and-stopping.md`: the run folder layout, stage order and when to stop.
- `rules-si-*/AGENTS.md`: each persona's scope, tools, writable files, inputs, outputs and stop conditions.

## Skills

| Skill | Used by | Holds |
|---|---|---|
| `discover`, `assess`, `plan`, `price` | the commands | wrapper copies of the four commands |
| `si-discover` | architect | discovery contract, evidence template, `normalize_evidence.py`, `build_source_inventory.py` |
| `si-document` | architect | documentation guidance |
| `si-assess` | architect | assessment contract, three templates, `validate_findings.py` |
| `si-plan` | PM | dependency contract, two templates, `validate_dag.py` |
| `si-business` | commercial | effort/SOW contract, evidence hierarchy, three templates, `validate_effort.py` |
| `si-collate` | collator | `validate_report_quality.py` (partial and full report checks) |
| `si-code-review` | senior reviewer | review guidance and the pilot review template |
| `si-delivery-control` | orchestrator, tech lead | traceability guidance |

`standards/` holds the report-quality standard and the machine-readable rubric that `/plan`'s ledger and the full report check use. `schemas/` holds the finding and handoff schemas.

## Hooks

`settings.json` wires three scripts in `hooks/`, each started as `python .bob/hooks/<script>.py` from the folder Bob has open (Bob runs hook commands through `cmd /c` on Windows and `sh -c` elsewhere). Bob loads workspace hooks only for a trusted folder.

- `preflight.py` (SessionStart, UserPromptSubmit): checks the kit files exist and no evaluator folder sits at the top of the workspace; at session start it prints `SI kit hooks active`, which the rules tell Bob to look for. A failure blocks the prompt.
- `pre_tool_guard.py` (PreToolUse, every tool): reads only inside the workspace (evaluator folders, internal working folders and secret-looking files refused); writes, edits, patches and mkdir only inside `runs/<name>/`, refusing `..`, symlink or junction escapes and everything else (`app/`, `tools/`, `targets/`, `.bob/`); shell commands and delete, move or rename always refused; MCP only for the ten read-only tools of the four mock servers and the checks tool. Exit 2 blocks the call. It needs no environment variables.
- `log_event.py` (PostToolUse, Stop): appends a content-free line (time, event, tool, run, path) to `runs/hook-events.jsonl` once `runs/` exists. It never blocks.

The guard is a backstop for mistakes, not a security sandbox: it sees only the paths a tool call declares.

**Python.** The hooks and the MCP servers start with `python`, which must be Python 3.11 or later. If yours is called `py` (Windows launcher) or `python3` (macOS, Linux), change `"command"` in `settings.json` and `mcp.json`. If a hook cannot start, Bob ignores it and the guard is off; the missing `SI kit hooks active` line is how you notice.

## MCP

`mcp.json` registers `roster`, `ratecard`, `tickets` and `timesheets`, switched on, each started as `python ${workspaceFolder}/tools/mcp/launch.py <server>`. `alwaysAllow` is empty, so Bob asks before every call. The data is invented demonstration data; see `../tools/mcp/README.md`.

It also registers `checks`, started as `python ${workspaceFolder}/tools/checkers/checks_server.py`. Its one tool, `run_stage_checks(run, stage)`, runs that stage's checker commands from the root `README.md`, unchanged, on `runs/<run>/` and returns each one's exit code and errors. It writes nothing under `runs/`: the price stage's generated CSV, price table and check file go to a temporary folder that is then deleted. The commands call it before they stop so that Bob corrects its own files first; it does not replace your run of the checkers.

## Checking the kit without Bob

The kit's own tests do not ship in this folder. Everything here can be exercised at zero Bob credits: start the MCP servers by hand (see `../tools/mcp/README.md`), feed the guard a JSON payload on stdin (in PowerShell or a POSIX shell, `echo '{"tool_name":"execute_command","tool_input":{}}' | python .bob/hooks/pre_tool_guard.py` prints the refusal and exits 2), and run each checker on a finished run.
