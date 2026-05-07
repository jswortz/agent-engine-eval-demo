FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy the MCP server package with the required parent structure
COPY . /app/src/mcp_server/
RUN touch /app/src/__init__.py

RUN uv pip install --system \
    "fastmcp>=3.2.4" \
    "cryptography>=41.0.0" \
    "PyJWT>=2.8.0" \
    "mcp>=1.9.0" \
    "pydantic>=2.0.0"

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "src.mcp_server.server", "--transport", "streamable-http", "--port", "8080"]
