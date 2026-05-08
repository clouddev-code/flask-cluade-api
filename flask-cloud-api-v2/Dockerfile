FROM python:3.13.13-slim-bookworm AS base

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_NODE=copy

WORKDIR /app

COPY uv.lock pyproject.toml /app/
RUN --mount=type=cache,target=/root/.cache/uv \ 
   uv sync --frozen --no-install-project --no-dev 

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \ 
   uv sync --frozen --no-dev

FROM base
WORKDIR /app

COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 実行コマンド指定
ENTRYPOINT ["gunicorn", "-w", "2", "-b", "0.0.0.0", "src.app:app","--timeout", "120"]
