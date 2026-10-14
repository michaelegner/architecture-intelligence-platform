"""Closed REST request bodies derived from a published MCP request model (v0.6.0 I3.3b, v0.7.0 I3.3).

A route that mirrors an MCP tool with a `mode`-discriminated request takes the request model's own
fields as its body, minus the ones the path or the route supplies, rather than restating them. The
body is closed. Only a body that cannot form a valid published request is a 422; every evaluated or
refused answer is a 200 envelope."""

from typing import Any

import pydantic
from fastapi import HTTPException


def closed_body(
    request_type: type[pydantic.BaseModel], name: str, supplied: frozenset[str]
) -> type[pydantic.BaseModel]:
    fields: dict[str, Any] = {
        field: (info.annotation, info)
        for field, info in request_type.model_fields.items()
        if field not in supplied
    }
    return pydantic.create_model(
        name, __config__=pydantic.ConfigDict(extra="forbid", frozen=True), **fields
    )


def published_request[R: pydantic.BaseModel](
    request_type: type[R], body: pydantic.BaseModel, **supplied: Any
) -> R:
    """The full published request: the body's own fields plus what the path and the route supply.
    The request model's validators (sorted lists, cursor form, cross-field rules) run here, so a body
    that fails them is a 422 like a malformed one."""
    try:
        return request_type.model_validate({**body.model_dump(exclude_unset=True), **supplied})
    except pydantic.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
