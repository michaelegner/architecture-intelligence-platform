"""The I3 oracle's matching procedure (`docs/specifications/0.6.0/i3-expected-answer-matrix.md` §2),
for every harness that executes `i3-vectors/expected-answers.json`.

Pure: no Neo4j and no `app` import, so it cannot borrow the semantics it checks.

- **Literals** are compared exactly.
- **Scalar symbols** `{{NAME}}` bind on first use, and every later use must be equal.
- **Spreads** `{{...NAME}}` stand for one or more list elements, bound as a set.
- **Wildcard** `{{*}}` matches any non-empty string.
- **Injective binding:** distinct names bind distinct values.
- **Pre-bound symbols** (`SOURCE:*`, `REF:*`) are substituted before matching.
- **Lists that contain a symbol** may be matched as sets after binding, so an order chosen for
  stand-in symbols cannot decide the result. Their actual order is enforced by the contract
  validators, which every actual answer must also pass. Every other list is positional.

A match is accepted only if some binding makes the whole expected value equal the actual one.
Property cases are evaluated by `check_property`.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import permutations
from typing import Any

_SYMBOL = re.compile(r"^\{\{(?P<spread>\.\.\.)?(?P<name>[^{}]+)\}\}$")
WILDCARD = "*"


@dataclass
class Bindings:
    """Scalar and spread bindings, with the reverse maps that keep them injective."""

    scalars: dict[str, Any] = field(default_factory=dict)
    spreads: dict[str, frozenset] = field(default_factory=dict)

    def copy(self) -> Bindings:
        return Bindings(dict(self.scalars), dict(self.spreads))

    def bind_scalar(self, name: str, value: Any) -> Bindings | None:
        if name in self.scalars:
            return self if self.scalars[name] == value else None
        if any(bound == value for bound in self.scalars.values()):
            return None  # distinct names bind distinct values
        result = self.copy()
        result.scalars[name] = value
        return result

    def bind_spread(self, name: str, values: frozenset) -> Bindings | None:
        if not values:
            return None  # a spread stands for one or more values
        if name in self.spreads:
            return self if self.spreads[name] == values else None
        if any(bound == values for bound in self.spreads.values()):
            return None
        result = self.copy()
        result.spreads[name] = values
        return result


def symbol(value: Any) -> tuple[bool, str] | None:
    """`(is_spread, name)` for a symbol string, else None."""
    if not isinstance(value, str):
        return None
    found = _SYMBOL.match(value)
    if found is None:
        return None
    return bool(found["spread"]), found["name"]


def substitute(value: Any, prebound: Mapping[str, Any]) -> Any:
    """Replaces every pre-bound scalar symbol (rule 2: `SOURCE:*`, `REF:*`) by its value."""
    if isinstance(value, dict):
        return {key: substitute(item, prebound) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, prebound) for item in value]
    found = symbol(value)
    if found is not None and not found[0] and found[1] in prebound:
        return prebound[found[1]]
    return value


def has_symbol(value: Any) -> bool:
    if isinstance(value, dict):
        return any(has_symbol(item) for item in value.values())
    if isinstance(value, list):
        return any(has_symbol(item) for item in value)
    return symbol(value) is not None


def _match(expected: Any, actual: Any, bindings: Bindings) -> Iterator[Bindings]:
    found = symbol(expected)
    if found is not None:
        is_spread, name = found
        if is_spread:
            return  # a spread is only meaningful as a list element
        if name == WILDCARD:
            if isinstance(actual, str) and actual:
                yield bindings
            return
        bound = bindings.bind_scalar(name, actual)
        if bound is not None:
            yield bound
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            return
        yield from _match_items(
            [expected[key] for key in sorted(expected)],
            [actual[key] for key in sorted(expected)],
            bindings,
        )
        return
    if isinstance(expected, list):
        if isinstance(actual, list):
            yield from _match_list(expected, actual, bindings)
        return
    if type(expected) is type(actual) and expected == actual:
        yield bindings


def _match_items(
    expected: Sequence[Any], actual: Sequence[Any], bindings: Bindings
) -> Iterator[Bindings]:
    if not expected:
        yield bindings
        return
    for bound in _match(expected[0], actual[0], bindings):
        yield from _match_items(expected[1:], actual[1:], bound)


def _match_list(expected: list, actual: list, bindings: Bindings) -> Iterator[Bindings]:
    spreads = [item for item in expected if (found := symbol(item)) is not None and found[0]]
    if len(spreads) > 1:
        raise ValueError(f"at most one spread per list is supported: {expected!r}")
    if spreads:
        [spread] = spreads
        name = _SYMBOL.match(spread)["name"]  # pyright: ignore[reportOptionalSubscript]
        others = [item for item in expected if item is not spread]
        if not all(isinstance(item, str) for item in [*others, *actual]):
            raise ValueError(f"a spread list holds strings only: {expected!r}")
        if len(set(actual)) != len(actual):
            return
        yield from _match_spread(others, set(actual), name, bindings)
        return
    if len(expected) != len(actual):
        return
    yield from _match_items(expected, actual, bindings)
    if not has_symbol(expected) or len(expected) > 7:
        return
    # Rule 3: a list whose order depends on symbols is compared as a set after binding. Every
    # alternative is yielded, not only the first local one, so a binding that a later field
    # contradicts can still be replaced by another (rule 5: *some* injective binding).
    identity = tuple(range(len(actual)))
    for order in permutations(identity):
        if order != identity:
            yield from _match_items(expected, [actual[index] for index in order], bindings)


def _match_spread(
    others: list[str], remaining: set[str], name: str, bindings: Bindings
) -> Iterator[Bindings]:
    """Each non-spread element takes one distinct actual element (a literal exactly, a scalar
    symbol by binding); the remaining one or more elements are the spread's set."""
    if not others:
        bound = bindings.bind_spread(name, frozenset(remaining))
        if bound is not None:
            yield bound
        return
    head, rest = others[0], others[1:]
    for value in sorted(remaining):
        for bound in _match(head, value, bindings):
            yield from _match_spread(rest, remaining - {value}, name, bound)


def match(expected: Any, actual: Any, prebound: Mapping[str, Any] | None = None) -> Bindings | None:
    """The first binding under which `actual` equals `expected` (rule 5), or None. Pre-bound
    symbols start out bound rather than being substituted, so a list ordered by a pre-bound
    symbol (e.g. pairs sorted by `{{SOURCE:A}}`) is still matched as a set (rule 3)."""
    start = Bindings(scalars=dict(prebound or {}))
    if len(set(start.scalars.values())) != len(start.scalars):
        raise ValueError("pre-bound symbols must bind distinct values")
    for bindings in _match(expected, actual, start):
        if _same_digest(bindings):
            return bindings
    return None


def _same_digest(bindings: Bindings) -> bool:
    """Rule 2: `SNAPSHOT_ID` and `MODEL_REVISION` carry the same digest."""
    snapshot, revision = bindings.scalars.get("SNAPSHOT_ID"), bindings.scalars.get("MODEL_REVISION")
    if snapshot is None or revision is None:
        return True
    return str(snapshot).rsplit(":", 1)[-1] == str(revision).rsplit(":", 1)[-1]


def explain_mismatch(expected: Any, actual: Any, path: str = "$") -> str | None:
    """A best-effort first difference, ignoring symbols, for a readable failure message."""
    if symbol(expected) is not None:
        return None
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            return f"{path}: keys {sorted(expected)} != {sorted(actual)}"
        for key in sorted(expected):
            found = explain_mismatch(expected[key], actual[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if has_symbol(expected):
            return None if len(expected) == len(actual) else f"{path}: length differs"
        if len(expected) != len(actual):
            return f"{path}: length {len(expected)} != {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            found = explain_mismatch(left, right, f"{path}[{index}]")
            if found:
                return found
        return None
    if expected != actual:
        return f"{path}: {json.dumps(expected)} != {json.dumps(actual)}"
    return None


# --- Property cases (matrix §1 `property`) -------------------------------------------------------


class PathError(LookupError):
    pass


def _decode_cursor(value: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def resolve(path: str, document: Any) -> Any:
    """`a.b[0].c`, `a[*].b` (fans out), `len(<path>)` and `cursor(<path>).field`."""
    if path.startswith("len(") and path.endswith(")"):
        value = resolve(path[4:-1], document)
        if not isinstance(value, list):
            raise PathError(f"len() of a non-list at {path}")
        return len(value)
    if path.startswith("cursor("):
        inner, _, rest = path[len("cursor(") :].partition(")")
        cursor = resolve(inner, document)
        if not isinstance(cursor, str):
            raise PathError(f"no cursor at {inner}")
        decoded = _decode_cursor(cursor)
        return resolve(rest.lstrip("."), decoded) if rest else decoded
    values: list[Any] = [document]
    fanned = False
    for part in path.split("."):
        name, _, index = part.partition("[")
        values = [_field(value, name, path) for value in values]
        if index:
            index = index.rstrip("]")
            if index == "*":
                fanned = True
                values = [item for value in values for item in _list(value, path)]
            else:
                values = [_list(value, path)[int(index)] for value in values]
    return values if fanned else values[0]


def _field(value: Any, name: str, path: str) -> Any:
    if not isinstance(value, dict) or name not in value:
        raise PathError(f"{name!r} not found on the way to {path}")
    return value[name]


def _list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise PathError(f"not a list on the way to {path}")
    return value


def check_property(
    item: Mapping[str, Any], steps: Mapping[int, Any], custom: Mapping[str, bool] | None = None
) -> None:
    """Asserts one `assert` item against the step results (1-based). `equals_expr` items are
    prose; the harness decides them per case and passes the verdict in `custom`, keyed by path."""
    if "equals_expr" in item:
        if custom is None or item["path"] not in custom:
            raise AssertionError(f"no harness check for equals_expr at {item['path']!r}")
        assert custom[item["path"]], f"{item['path']}: {item['equals_expr']}"
        return
    step = item.get("step", 1)
    value = resolve(item["path"], steps[step])
    where = f"step {step} {item['path']}"
    if "equals" in item:
        assert value == item["equals"], f"{where}: {value!r} != {item['equals']!r}"
    elif "all_equal" in item:
        assert isinstance(value, list) and value, f"{where}: empty, so not checked"
        assert all(v == item["all_equal"] for v in value), f"{where}: {value!r}"
    elif "contains" in item:
        assert isinstance(value, list) and item["contains"] in value, f"{where}: {value!r}"
    elif "subset_of" in item:
        assert isinstance(value, list) and value, f"{where}: empty, so not checked"
        assert set(value) <= set(item["subset_of"]), f"{where}: {value!r}"
    elif "at_least" in item:
        assert value >= item["at_least"], f"{where}: {value!r}"
    elif "at_most" in item:
        assert value <= item["at_most"], f"{where}: {value!r}"
    elif "equals_step" in item:
        other = resolve(item["path"], steps[item["equals_step"]])
        assert value == other, f"{where}: {value!r} != step {item['equals_step']} {other!r}"
    elif "not_equals_step" in item:
        other = resolve(item["path"], steps[item["not_equals_step"]])
        assert value != other, f"{where}: equals step {item['not_equals_step']}"
    else:
        raise AssertionError(f"unknown assert operator in {item!r}")
