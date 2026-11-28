FROM python:3.15.1-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51

# The runtime never uses the system pip (uv installs into /app/.venv, which has no pip); removing it
# drops pip's bundled certifi/urllib3/setuptools/msgpack from the image and its scan.
RUN /usr/local/bin/python -m pip uninstall --yes pip

COPY --from=ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f /uv /uvx /bin/

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
