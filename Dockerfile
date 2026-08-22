# Glama MCP introspection (https://glama.ai/mcp/servers)
# Stdio inventory tools — no ports. Paste into Glama Dockerfile admin
# if the crawler does not auto-detect this file on main.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY docs ./docs

RUN pip install --no-cache-dir -e '.[mcp]' \
  && pip cache purge || true

# Read tools work without a real confirm token; mutating tool stays gated.
ENV BATTERY_ERP_CONFIRM_TOKEN=glama-introspect-only
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "battery_erp.mcp"]
