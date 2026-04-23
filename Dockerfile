FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV PYTHONPATH=/app

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY . .

EXPOSE 8080

CMD ["uv", "run", "--no-dev", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]
