# Publish checklist — Battery ERP MCP

Repo: https://github.com/icohangar-ops/battery-erp  
MCP entry: `python -m battery_erp.mcp` (mcp SDK 2.x `MCPServer`)

Packaging files in-repo:

| File | Purpose |
|---|---|
| `glama.json` | Glama maintainers claim |
| `Dockerfile` | Glama stdio tool introspection |
| `server.json` | Official MCP Registry metadata |
| `pyproject.toml` extras `[mcp]` / `[api]` | Install surface |

## 1) Land on `main`

Glama crawls the default branch. Merge PR #1 (or cherry-pick packaging) first:

```bash
gh pr merge 1 --merge
git checkout main && git pull
```

## 2) Glama

1. Confirm `glama.json` + `Dockerfile` are on `main`.
2. Open https://glama.ai/mcp/servers and add / claim  
   `https://github.com/icohangar-ops/battery-erp`  
   (or wait for crawl — other icohangar-ops servers appear under `@icohangar-ops/...`).
3. If introspection fails, paste the repo `Dockerfile` into Glama’s Dockerfile admin field.
4. Expected listing:  
   `https://glama.ai/mcp/servers/@icohangar-ops/battery-erp`
5. Optional: set related servers to codesentinel / chp-mcp / agent-conductor for cross-links.

Verify API:

```bash
curl -s 'https://glama.ai/api/mcp/v1/servers/icohangar-ops/battery-erp' | python3 -m json.tool
```

## 3) PyPI (needed for official registry + one-liner installs)

```bash
cd ~/Desktop/icohangar-repos/battery-erp
python3 -m pip install build twine
python3 -m build
# Use a PyPI API token (never commit it):
twine upload dist/*
python3 -m pip index versions battery-erp
```

Install check:

```bash
python3 -m pip install 'battery-erp[mcp]'
BATTERY_ERP_CONFIRM_TOKEN=dev-secret python3 -m battery_erp.mcp
```

## 4) Official MCP Registry

```bash
# ~/.local/bin/mcp-publisher
mcp-publisher login github   # device flow as icohangar-ops
cd ~/Desktop/icohangar-repos/battery-erp
mcp-publisher validate
mcp-publisher publish
# → io.github.icohangar-ops/battery-erp@0.1.0

curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=battery-erp'
```

## 5) Smithery

Your other servers publish **Node MCPB** bundles (`smithery mcp publish …mcpb`).  
This repo is Python-first. Options:

**A (recommended short-term):** list on Glama + MCP Registry only; document Cursor stdio config.

**B:** add a thin `@cubiczan/battery-erp-mcp` Node shim that `spawn`s `python3 -m battery_erp.mcp`, then reuse the mcpb + `scripts/smithery-publish-mcpb.sh` pattern from codesentinel / chp-mcp.

**C:** if/when Smithery supports native Python stdio packages, publish from PyPI identifier.

## 6) awesome-mcp-servers PR (paste)

Against https://github.com/punkpeye/awesome-mcp-servers (e.g. **Finance** / **Data** / **Productivity**):

```markdown
- [battery-erp](https://github.com/icohangar-ops/battery-erp) - Li-ion inventory MCP (SKU lookup, reorder status, human bin confirmation) — `pip install 'battery-erp[mcp]' && python -m battery_erp.mcp`
```

Optional: https://github.com/appcypher/awesome-mcp-servers · https://github.com/wong2/awesome-mcp-servers

## 7) GitHub topics

```bash
gh repo edit icohangar-ops/battery-erp \
  --add-topic mcp \
  --add-topic model-context-protocol \
  --add-topic inventory \
  --add-topic battery \
  --add-topic fastapi \
  --add-topic cursor
```

## Cursor config (after publish)

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

From source (pre-PyPI):

```json
{
  "mcpServers": {
    "battery-erp": {
      "command": "python3",
      "args": ["-m", "battery_erp.mcp"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/battery-erp/src",
        "BATTERY_ERP_CONFIRM_TOKEN": "replace-me"
      }
    }
  }
}
```

## Already done in-repo

- [x] Shared `InventoryService` + REST + MCP tools
- [x] `glama.json`, `Dockerfile`, `server.json`, this checklist
- [x] README / `docs/INTEGRATION.md` wiring
- [ ] Merge to `main`
- [ ] Glama claim / introspection green
- [ ] PyPI `battery-erp`
- [ ] `mcp-publisher publish`
- [ ] awesome-mcp PR(s)
- [ ] Optional Smithery Node shim
