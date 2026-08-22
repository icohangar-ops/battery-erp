# Glama MCP introspection reference
# Glama's hosted builder uses debian:trixie-slim + uv (see PUBLISH.md).
# Working Glama form build steps:
#   uv venv /app/.venv --python /usr/local/bin/python
#   uv pip install --python /app/.venv/bin/python ".[mcp]"
# CMD: ["/app/.venv/bin/python", "-m", "battery_erp.mcp"]

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY docs ./docs

RUN pip install --no-cache-dir -e '.[mcp]' \
  && pip cache purge || true

ENV BATTERY_ERP_CONFIRM_TOKEN=glama-introspect-only
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "battery_erp.mcp"]
