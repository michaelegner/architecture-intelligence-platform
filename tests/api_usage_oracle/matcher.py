"""The I3 oracle's matching procedure (`docs/specifications/0.7.0/i3-expected-answer-matrix.md` §2):
exact equality, except that the wildcard `{{*}}` matches any non-empty string. Pure: no `app`
import, so it cannot borrow the semantics it checks."""

from typing import Any

WILDCARD = "{{*}}"


def matches(expected: Any, actual: Any) -> bool:
    if expected == WILDCARD:
        return isinstance(actual, str) and actual != ""
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and expected.keys() == actual.keys()
            and all(matches(value, actual[key]) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(matches(e, a) for e, a in zip(expected, actual, strict=True))
        )
    # a bool is not an int, and an int is not a float: type and value must both agree
    return type(expected) is type(actual) and expected == actual


def first_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    """Where the first mismatch is, for a readable failure; `None` when they match."""
    if matches(expected, actual):
        return None
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            if key not in expected or key not in actual:
                return f"{path}.{key}: {'unexpected' if key in actual else 'missing'}"
            found = first_difference(expected[key], actual[key], f"{path}.{key}")
            if found:
                return found
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"{path}: {len(expected)} expected items, {len(actual)} actual"
        for index, (e, a) in enumerate(zip(expected, actual, strict=True)):
            found = first_difference(e, a, f"{path}[{index}]")
            if found:
                return found
    return f"{path}: expected {expected!r}, actual {actual!r}"
