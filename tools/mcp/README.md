# Mock MCP servers

Four read-only stdio MCP servers with invented demonstration data. They stand in for the systems an SI would normally consult (a staff roster, a rate card, a help-desk queue, timesheets) and connect to no real system.

| Server | Data | Tools | Used by |
|---|---|---|---|
| `roster` | `data/roster.json` (Synthetic Engineer 01-12) | `roster_list_people`, `roster_find_by_skill`, `roster_availability` | `/plan`, `/price` |
| `ratecard` | the demonstration SGD rate card in `tools/commercial/server.py` | `ratecard_get`, `ratecard_roles` | `/price` |
| `tickets` | `data/tickets.json` (help-desk reports) | `tickets_search`, `tickets_get`, `incidents_list` | `/assess` |
| `timesheets` | `data/timesheets.json` (Java invoice-preview pilot) | `timesheets_list_entries`, `timesheets_pilot_summary` | `/price` |

`contract.json` declares every tool (there are no write tools). `datasets.json` pins each dataset's SHA-256; a server refuses to start if its data has changed. The data files are kept byte-for-byte with LF line endings (see the root `.gitattributes`); do not reformat them.

## In IBM Bob

`.bob/mcp.json` registers all four servers, switched on (and a fifth, `checks`, that runs the checkers rather than serving data; see `tools/README.md`), so they appear in Bob's MCP settings when you open the repository. Each entry looks like this:

```json
"roster": {
  "command": "python",
  "args": ["${workspaceFolder}/tools/mcp/launch.py", "roster"],
  "alwaysAllow": [],
  "disabled": false
}
```

Bob replaces `${workspaceFolder}` with the folder it has open. `alwaysAllow` is empty, so Bob asks before each tool call. The hook guard in `.bob/hooks/pre_tool_guard.py` refuses every MCP tool that is not one of these ten or the checks tool.

`python` must start Python 3.11 or later. If your Python is called `py` (Windows launcher) or `python3` (macOS, Linux), change `"command"` in each entry; the arguments stay the same. The servers use only the Python standard library.

## Checking by hand

```
python tools/mcp/launch.py roster
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

Paste the two JSON lines; each reply arrives on one line. `launch.py` finds the server, contract and data relative to itself, so it works from any working directory, and it starts only servers declared in `contract.json`.
