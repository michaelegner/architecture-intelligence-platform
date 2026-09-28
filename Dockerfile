FROM python:3.14.7-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/

# Non-root runtime user (12G container verification: the image must not run as root).
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY --chown=app:app app ./app
COPY --chown=app:app config.yaml ./
COPY --chown=app:app examples ./examples

RUN uv sync --frozen --no-dev

# v0.4.0 I2.2: this image has no git binary and no .git directory, so app/mcp/wiring.py cannot
# resolve Producer.build_revision from `git rev-parse HEAD` - the build step supplies it explicitly
# instead. Defaults to empty (app.mcp.wiring falls back to a logged "unknown" placeholder rather than
# crashing startup) so a plain `docker build .` with no --build-arg still works.
ARG AIP_BUILD_REVISION=""
ENV AIP_BUILD_REVISION=${AIP_BUILD_REVISION}

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
