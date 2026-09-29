from pathlib import Path

import neo4j
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.analysis.blast_radius import blast_radius
from app.analysis.queues import consumers_of_queue, senders_of_queue
from app.analysis.runtime import default_since, service_runtime_profile
from app.answer_router import LLMNotConfiguredError, answer_question
from app.api.query import QueryResponse
from app.deps import build_question_service, get_read_session, get_settings
from app.graph import read_models
from app.settings import Settings

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _humanize_window_hours(hours: int) -> str:
    if hours % 24 == 0:
        days = hours // 24
        return "1 day" if days == 1 else f"{days} days"
    return f"{hours}h"


@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: neo4j.Session = Depends(get_read_session)):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "services": read_models.index_services(session),
            "queues": read_models.index_queues(session),
        },
    )


@router.get("/services/{service_id}", response_class=HTMLResponse)
def service_explorer(
    request: Request,
    service_id: str,
    environment: str | None = None,
    session: neo4j.Session = Depends(get_read_session),
    settings: Settings = Depends(get_settings),
):
    service = read_models.service_summary(session, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail=f"service not found: {service_id}")

    provides = read_models.service_provides(session, service_id)
    calls = read_models.service_calls(session, service_id)
    sends = read_models.service_sends(session, service_id)
    receives = read_models.service_receives(session, service_id)
    downstream = blast_radius(session, service_id, max_depth=1)

    env = environment or settings.config.runtime_analysis.default_environment
    since = default_since(settings.config.runtime_analysis.default_window_hours)
    observed = service_runtime_profile(session, service_id=service_id, environment=env, since=since)

    return templates.TemplateResponse(
        request,
        "service.html",
        {
            "service": service,
            "provides": provides,
            "calls": calls,
            "sends": sends,
            "receives": receives,
            "downstream": downstream,
            "observed": observed,
            "observed_window_label": _humanize_window_hours(
                settings.config.runtime_analysis.default_window_hours
            ),
        },
    )


@router.get("/queues/{queue_id}", response_class=HTMLResponse)
def queue_explorer(
    request: Request, queue_id: str, session: neo4j.Session = Depends(get_read_session)
):
    queue = read_models.queue_summary(session, queue_id)
    if queue is None:
        raise HTTPException(status_code=404, detail=f"queue not found: {queue_id}")

    messages = read_models.queue_messages(session, queue_id)
    dlq = read_models.queue_dead_letter(session, queue_id)

    return templates.TemplateResponse(
        request,
        "queue.html",
        {
            "queue": queue,
            "senders": senders_of_queue(session, queue_id),
            "consumers": consumers_of_queue(session, queue_id),
            "messages": messages,
            "dlq": dlq,
        },
    )


@router.get("/query", response_class=HTMLResponse)
def query_page(
    request: Request,
    question: str | None = None,
    session: neo4j.Session = Depends(get_read_session),
):
    result = None
    if question:
        settings = get_settings(request)
        question_service = build_question_service(request)
        try:
            routed = answer_question(
                session=session,
                question=question,
                deterministic_threshold=settings.config.intent_router.deterministic_threshold,
                question_service=question_service,
                default_window_hours=settings.config.runtime_analysis.default_window_hours,
                default_environment=settings.config.runtime_analysis.default_environment,
            )
            result = QueryResponse(
                question=routed.question,
                cypher=routed.cypher,
                rows=routed.rows,
                answer=routed.answer,
                execution_mode=routed.execution_mode,
                intent=routed.intent,
            )
        except LLMNotConfiguredError:
            result = QueryResponse(
                question=question,
                cypher=None,
                rows=[],
                answer="Natural language query is not configured (missing OPENAI_API_KEY, or llm.enabled is false in config.yaml).",
            )
    return templates.TemplateResponse(
        request, "query.html", {"question": question, "result": result}
    )
