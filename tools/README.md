# Tools

Small tools that sit beside IBM Bob. None of them calls Bob, costs Bob credits or needs a network connection. All need Python 3.11 or later and only its standard library. Run every command from the repository root.

| Folder | What it holds |
|---|---|
| `mcp/` | Four synthetic, read-only MCP servers (roster, rate card, help-desk tickets, timesheets) that `.bob/mcp.json` registers. See `mcp/README.md`. |
| `checkers/` | Checkers you run on Bob's `/price` output (the illustrative price table and the effort and SOW cross-check), and the read-only `checks` MCP server Bob uses to run a stage's checkers on its own files before it stops. |
| `metrics/` | The complexity-metrics measurement `/assess` reads. |
| `commercial/` | The SI commercial engine: a synthetic SGD rate card and the pricing views the checkers and the `ratecard` server use. |

The checkers that belong to one Bob skill (evidence, findings, plan, effort and report-quality checks) live with that skill under `.bob/skills/*/scripts/`. The root `README.md` lists every checker command in the order you run them.

## metrics

```
python tools/metrics/complexity_metrics.py --out runs/<name>/inputs/complexity-metrics.json
```

Measures every Java file under `app/src` (line counts, methods, branch counts per method) and writes deterministic JSON. `/assess` uses it as SI-measured evidence; Bob does not compute metrics itself. `--root` measures another source folder.

## checkers

After `/price`, render the effort model first (`.bob/skills/si-business/scripts/validate_effort.py`, see the root `README.md`), then:

```
python tools/checkers/illustrative_price.py --csv runs/<name>/reports/effort-model.csv --output runs/<name>/checks/illustrative-price.json
python tools/checkers/check_effort_numbers.py --csv runs/<name>/reports/effort-model.csv --sow runs/<name>/reports/sow.md --price-table runs/<name>/checks/illustrative-price.json --output runs/<name>/checks/effort-check.json
```

- `illustrative_price.py` prices the effort model with the engine in `commercial/`: low, central and high bands, plus the pricing views (fixed price, capped time and materials, pilot then programme, risk-driver contingency from the SOW's `## Risk drivers` table, and a calibration factor from the synthetic pilot timesheets). Bob does no price arithmetic; this tool does it. The result is illustrative, not a quote. It refuses to overwrite an existing file.
- `check_effort_numbers.py` reconciles the CSV's summary rows and checks that every figure in the SOW's commercial sections, and every currency amount anywhere in it, is a value the price table holds. Exit 0 means it passed.
- `effort_model.py` is the CSV formatter `validate_effort.py` calls; you do not run it directly.
- `checks_server.py` is a stdio MCP server with one read-only tool, `run_stage_checks(run, stage)`, registered in `.bob/mcp.json` as `checks`. It runs the root `README.md`'s checker commands for that stage, unchanged, and returns each exit code and its errors; for `price` it writes the CSV, price table and check file to a temporary folder, so it writes nothing under `runs/`. Each command calls it before stopping. It does not replace your own run of the checkers.

## commercial

`server.py` holds the synthetic rate card (`SEEDS`), its validation and `build_bob_input`, the arithmetic the checkers call. `pricing_views.py` with `pricing-views.json` adds the pricing views, and `commercial-illustration.json` maps the effort model's roles to rate-card roles. `samples/` holds two synthetic reference notes the rate card cites by hash. Every figure is invented demonstration data.

`server.py` can also run as a small loopback web form for editing rate-card inputs (`python tools/commercial/server.py --port 8765`); the Bob kit does not need it.
