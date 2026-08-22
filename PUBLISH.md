# Publish checklist — Battery ERP MCP

Repo (org): https://github.com/icohangar-ops/battery-erp  
Repo (personal): https://github.com/Cubiczan/battery-erp  
MCP entry: `python -m battery_erp.mcp` (mcp SDK 2.x `MCPServer`)

| Surface | Status |
|---|---|
| PyPI | https://pypi.org/project/battery-erp/0.1.1/ |
| MCP Registry | `io.github.icohangar-ops/battery-erp` **0.1.1** (active) |
| Glama | https://glama.ai/mcp/servers/@icohangar-ops/battery-erp (`gx5vd3evpn`) |

Packaging files in-repo:

| File | Purpose |
|---|---|
| `glama.json` | Glama maintainers claim |
| `Dockerfile` | Local / reference stdio image |
| `server.json` | Official MCP Registry metadata |
| `pyproject.toml` extras `[mcp]` / `[api]` | Install surface |

## Done

- [x] Landed on `main` (PR #1 merged)
- [x] PyPI `battery-erp==0.1.1` (README includes `mcp-name: io.github.icohangar-ops/battery-erp`)
- [x] Official MCP Registry publish
- [x] Glama listing + release (API 200)
- [x] GitHub topics (`mcp`, `model-context-protocol`, …)
- [x] Handheld demo screenshot in README

## Glama build form (working)

Glama generates its own Dockerfile (`debian:trixie-slim` + `uv` Python). Do **not** use bare `pip` — it is missing. Do **not** use `uv pip install --system` — hits Debian’s externally-managed Python.

**Build steps:**

```json
[
  "uv venv /app/.venv --python /usr/local/bin/python",
  "uv pip install --python /app/.venv/bin/python \".[mcp]\""
]
```

**CMD arguments:**

```json
["/app/.venv/bin/python", "-m", "battery_erp.mcp"]
```

**Placeholder parameters:**

```json
{"BATTERY_ERP_CONFIRM_TOKEN": "glama-introspect-only"}
```

**Env schema:** `BATTERY_ERP_CONFIRM_TOKEN`, `BATTERY_ERP_AUDIT_LOG` (both optional).

Verify:

```bash
curl -s 'https://glama.ai/api/mcp/v1/servers/icohangar-ops/battery-erp' | python3 -m json.tool | head -50
```

If `tools` is still `[]`, wait for post-release introspection or re-check the Glama release logs.

## Sync remotes

```bash
cd ~/Desktop/icohangar-repos/battery-erp
git checkout main && git pull origin main
git push origin main
git push cubiczan main   # https://github.com/Cubiczan/battery-erp
```

## Optional next

- [ ] Related-server cross-links on Glama (codesentinel, chp-mcp, agent-conductor)
- [ ] awesome-mcp-servers PR (blurb below)
- [ ] Smithery Node shim (`@cubiczan/battery-erp-mcp`) if needed
- [ ] Align Glama release `1.0.0` with a future PyPI `1.0.0` bump

### awesome-mcp blurb

```markdown
- [battery-erp](https://github.com/icohangar-ops/battery-erp) - Li-ion inventory MCP (SKU lookup, reorder status, human bin confirmation) — `pip install 'battery-erp[mcp]' && python -m battery_erp.mcp`
```

## Cursor config (PyPI)

```json
{
  "mcpServers": {
    "battery-erp": {
      "command": "python3",
      "args": ["-m", "battery_erp.mcp"],
      "env": {
        "BATTERY_ERP_CONFIRM_TOKEN": "replace-me"
      }
    }
  }
}
```
