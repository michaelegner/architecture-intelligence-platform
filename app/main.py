import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.ai.provider import OpenAIProvider
from app.ai.semantic_query_validator import SemanticValidationError
from app.api import (
    analysis,
    evidence,
    import_api,
    messages,
    query,
    queues,
    runtime,
    services,
    telemetry,
    ui,
)
from app.deps import get_driver, get_settings
from app.graph.repository import build_driver, open_session
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.settings import MCPConfig, Settings, load_settings
from app.telemetry.correlation_buffer import HttpCorrelationBuffer

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.yaml"))
logger = logging.getLogger("architecture_intelligence.health")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings(CONFIG_PATH)
    app.state.settings = settings
    app.state.driver = build_driver(
        settings.config.graph.uri, settings.secrets.neo4j_user, settings.secrets.neo4j_password
    )
    if settings.config.llm.enabled and settings.secrets.openai_api_key:
        app.state.llm_provider = OpenAIProvider(api_key=settings.secrets.openai_api_key)
    else:
        app.state.llm_provider = None
    http_correlation = settings.config.telemetry.http_correlation
    app.state.http_correlation_buffer = (
        HttpCorrelationBuffer(
            ttl_seconds=http_correlation.ttl_seconds,
            max_pending_spans=http_correlation.max_pending_spans,
        )
        if http_correlation.enabled
        else None
    )
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp_session_manager_lifespan())
        yield
    app.state.driver.close()


def create_app() -> FastAPI:
    """Builds the FastAPI app without touching env vars/Neo4j - real settings/driver only load on lifespan startup."""
    app = FastAPI(title="Architecture Intelligence PoC", lifespan=lifespan)

    app.include_router(services.router)
    app.include_router(queues.router)
    app.include_router(messages.router)
    app.include_router(analysis.router)
    app.include_router(import_api.router)
    app.include_router(query.router)
    app.include_router(evidence.router)
    app.include_router(telemetry.router)
    app.include_router(runtime.runtime_router)
    app.include_router(runtime.runtime_analysis_router)
    app.include_router(ui.router)

    @app.exception_handler(SemanticValidationError)
    def handle_semantic_validation_error(request: Request, exc: SemanticValidationError):
        """Spec §5.10: structurally invalid generated Cypher (e.g. wrong relationship direction)
        never reaches Neo4j and is reported as 422 with the violated relation's domain/range."""
        return JSONResponse(
            status_code=422,
            content={
                "code": "SEMANTIC_QUERY_INVALID",
                "message": str(exc),
                "relation": exc.relation,
                "expectedSource": sorted(exc.expected_source),
                "expectedTarget": sorted(exc.expected_target),
            },
        )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/neo4j")
    def health_neo4j(settings: Settings = Depends(get_settings), driver=Depends(get_driver)):
        try:
            with open_session(
                driver, database=settings.config.graph.database, read_only=True
            ) as session:
                session.run("RETURN 1").consume()
        except Exception:
            # CodeQL py/stack-trace-exposure: the exception (which for a Neo4j driver error can
            # include the bolt URI/hostname) is logged server-side only - an unauthenticated caller
            # of a health endpoint must never see internal connection detail in the response body.
            logger.exception("Neo4j health check failed")
            return JSONResponse(status_code=503, content={"status": "error"})
        return {"status": "ok"}

    # v0.4.0 I2.1 - mounted at "/" (not "/mcp") and registered last, so it only ever receives
    # requests no route above already claimed - in practice exactly `POST /mcp`, which is the
    # mounted sub-app's own route path (see app.mcp.app.build_mcp_app's docstring for why mounting
    # at an outer "/mcp" prefix instead 307-redirects a bare `POST /mcp`, confirmed live). Built
    # ahead of settings/driver being available (create_app() itself must stay env/Neo4j-free), so
    # origin/host allow-listing uses MCPConfig's own defaults rather than the loaded config.yaml -
    # revisit if a deployment needs non-default origins (spec §15: local/trusted-network only).
    mcp_config = MCPConfig()
    app.mount(
        "/",
        build_mcp_app(
            allowed_origins=mcp_config.allowed_origins, allowed_hosts=mcp_config.allowed_hosts
        ),
    )

    return app


app = create_app()
