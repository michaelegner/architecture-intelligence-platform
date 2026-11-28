"""v0.8.1 I1 - the MCP Skills extension (SEP-2640; spec `docs/specifications/0.8.1/
specification.md` §4).

`AipSkillsExtension` serves the static `SKILL.md` files in this package through the SDK
`Extension` hook (D2). A client finds them with `skills/list` and `skills/get` and reads them with
`resources/read`. The skill files are static package data, never generated from the graph, so each
manifest is complete and never `"dynamic"` (D5: one file per skill).

- **Era (D3, ADR 0018).** `skills/list` and `skills/get` are bound for `2026-07-28` only. On a
  `2025-11-25` session the SDK returns `METHOD_NOT_FOUND` for them.
- **Legacy path unchanged (D8).** SDK resources are not gated by era, so
  `legacy_skill_resource_middleware` hides the `skill://` resources on every non-modern request:
  `resources/list` leaves them out, and `resources/read` of a skill URI gets the same `-32602`
  error as any unknown resource.
- **Skill set follows the tool set (D4).** `aip-binding-picture` exists only when the
  `experimental.binding-picture` flag is on.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from mcp.server import CacheHint
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.extension import Extension, MethodBinding, ResourceBinding
from mcp.server.mcpserver.resources import TextResource
from mcp.shared.exceptions import MCPError
from mcp_types import PaginatedRequestParams, RequestParams
from mcp_types.jsonrpc import INVALID_PARAMS

SKILLS_EXTENSION_ID = "io.modelcontextprotocol/skills"
SKILLS_PROTOCOL_VERSIONS = frozenset({"2026-07-28"})
"""D3: the era the skills methods are served on (ADR 0018)."""

SKILL_URI_PREFIX = "skill://aip/"
READING_ANSWERS_SKILL = "aip-reading-answers"
BINDING_PICTURE_SKILL = "aip-binding-picture"

_SKILLS_DIR = Path(__file__).parent
_SKILL_FILE = "SKILL.md"
_FRONTMATTER_DELIMITER = "---"


def skill_names(*, binding_picture: bool) -> tuple[str, ...]:
    """The served skill names, in listing order."""
    if binding_picture:
        return (READING_ANSWERS_SKILL, BINDING_PICTURE_SKILL)
    return (READING_ANSWERS_SKILL,)


def skill_uri(name: str) -> str:
    return f"{SKILL_URI_PREFIX}{name}/{_SKILL_FILE}"


def parse_frontmatter(text: str) -> dict[str, Any]:
    """The YAML frontmatter of a `SKILL.md`, as the object that the file declares."""
    lines = text.split("\n")
    if lines[0] != _FRONTMATTER_DELIMITER:
        raise ValueError("a SKILL.md must start with a YAML frontmatter block")
    end = lines.index(_FRONTMATTER_DELIMITER, 1)
    frontmatter = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(frontmatter, dict):
        raise TypeError("the SKILL.md frontmatter must be a mapping")
    return frontmatter


@dataclass(frozen=True)
class _Skill:
    name: str
    uri: str
    text: str
    frontmatter: dict[str, Any]
    digest: str
    size: int

    @classmethod
    def load(cls, name: str) -> _Skill:
        raw = (_SKILLS_DIR / name / _SKILL_FILE).read_bytes()
        text = raw.decode("utf-8")
        frontmatter = parse_frontmatter(text)
        # SEP-2640: the last segment of the skill path equals the frontmatter `name`.
        if frontmatter.get("name") != name:
            raise ValueError(f"the frontmatter name of skill {name!r} must equal its directory")
        return cls(
            name=name,
            uri=skill_uri(name),
            text=text,
            frontmatter=frontmatter,
            digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
            size=len(raw),
        )

    def entry(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "frontmatter": self.frontmatter,
            "resources": [{"uri": self.uri, "digest": self.digest, "size": self.size}],
        }


class SkillsGetParams(RequestParams):
    uri: str


class AipSkillsExtension(Extension):
    """The SEP-2640 Skills extension over AIP's static skill files. See the module docstring."""

    identifier = SKILLS_EXTENSION_ID

    def __init__(self, *, binding_picture: bool, cache_hint: CacheHint) -> None:
        self._skills = {
            skill.uri: skill
            for skill in (
                _Skill.load(name) for name in skill_names(binding_picture=binding_picture)
            )
        }
        self._cache_fields = {"ttlMs": cache_hint.ttl_ms, "cacheScope": cache_hint.scope}

    def resources(self) -> list[ResourceBinding]:
        return [
            ResourceBinding(
                TextResource(
                    uri=skill.uri, name=skill.name, mime_type="text/markdown", text=skill.text
                )
            )
            for skill in self._skills.values()
        ]

    def methods(self) -> list[MethodBinding]:
        return [
            MethodBinding(
                method="skills/list",
                params_type=PaginatedRequestParams,
                handler=self._list,
                protocol_versions=SKILLS_PROTOCOL_VERSIONS,
            ),
            MethodBinding(
                method="skills/get",
                params_type=SkillsGetParams,
                handler=self._get,
                protocol_versions=SKILLS_PROTOCOL_VERSIONS,
            ),
        ]

    async def _list(
        self, _ctx: ServerRequestContext[Any, Any], _params: PaginatedRequestParams
    ) -> dict[str, Any]:
        # Two static skills fit one page, so the result never carries a cursor.
        skills = [skill.entry() for skill in self._skills.values()]
        return {"resultType": "complete", "skills": skills, **self._cache_fields}

    async def _get(
        self, _ctx: ServerRequestContext[Any, Any], params: SkillsGetParams
    ) -> dict[str, Any]:
        skill = self._skills.get(params.uri)
        if skill is None:
            raise MCPError(code=INVALID_PARAMS, message="Unknown skill")
        return {"resultType": "complete", "skill": skill.entry(), **self._cache_fields}


def _is_skill_uri(uri: object) -> bool:
    return isinstance(uri, str) and uri.startswith(SKILL_URI_PREFIX)


async def legacy_skill_resource_middleware(
    ctx: ServerRequestContext[Any, Any], call_next: CallNext
) -> HandlerResult:
    """D8: hide the skill resources on every request outside `SKILLS_PROTOCOL_VERSIONS`, so that
    the `2025-11-25` path serves exactly what v0.8.0 served. A modern request passes through."""
    if ctx.protocol_version in SKILLS_PROTOCOL_VERSIONS:
        return await call_next(ctx)
    uri = (ctx.params or {}).get("uri")
    if ctx.method == "resources/read" and _is_skill_uri(uri):
        # Exactly the SDK's own error for an unknown resource, as v0.8.0 returned for this URI.
        raise MCPError(code=INVALID_PARAMS, message=f"Unknown resource: {uri}", data={"uri": uri})
    result = await call_next(ctx)
    if ctx.method != "resources/list":
        return result
    # The handler result reaches the middleware already serialized as a dict.
    if isinstance(result, dict):
        resources = [r for r in result.get("resources", ()) if not _is_skill_uri(r.get("uri"))]
        return {**result, "resources": resources}
    return result
