"""Hardened YAML loading shared by the Kubernetes envelope (v0.6 I2 §4.3) and the EventCatalog
loader (v0.8 I1 §5.5): no anchors or aliases, bounded nesting, no duplicate mapping keys. Custom
tags are already rejected by `yaml.SafeLoader` itself (`yaml.constructor.ConstructorError`), which
is left to the caller to classify. Messages never echo document content."""

from typing import Any

import yaml


class BoundedYamlLimitExceeded(ValueError):
    """An alias/anchor or nesting beyond the bound."""


class BoundedYamlMalformed(ValueError):
    """A duplicate or unhashable mapping key."""


def _loader_class(max_depth: int) -> type[yaml.SafeLoader]:
    class _BoundedSafeLoader(yaml.SafeLoader):
        def __init__(self, stream: Any) -> None:
            super().__init__(stream)
            self._compose_depth = 0

        def compose_node(self, parent: Any, index: Any) -> Any:
            # `compose_node` is the single recursive entry point the Composer uses for every node
            # (scalar, sequence, or mapping), including alias resolution - checking here, before
            # delegating, catches an alias regardless of where it appears.
            if self.check_event(yaml.events.AliasEvent):
                raise BoundedYamlLimitExceeded("YAML aliases/anchors are not supported")
            self._compose_depth += 1
            try:
                if self._compose_depth > max_depth:
                    raise BoundedYamlLimitExceeded(
                        f"YAML/JSON nesting exceeds the {max_depth}-level bound"
                    )
                return super().compose_node(parent, index)
            finally:
                self._compose_depth -= 1

        def construct_mapping(self, node: Any, deep: bool = False) -> dict:
            # Duplicate-key rejection: by the time `construct_mapping` returns a plain dict, a
            # repeated key has already silently overwritten its earlier value. `node.value` is the
            # raw ordered (key_node, value_node) pair list *before* that collapse happens.
            seen_keys: set[Any] = set()
            for key_node, _value_node in node.value:
                key = self.construct_object(key_node, deep=True)
                # YAML permits complex (unhashable) mapping keys; reject them cleanly instead of
                # letting the membership check raise a raw TypeError.
                try:
                    is_duplicate = key in seen_keys
                except TypeError as exc:
                    raise BoundedYamlMalformed("unhashable YAML mapping key") from exc
                if is_duplicate:
                    raise BoundedYamlMalformed("duplicate mapping key")
                seen_keys.add(key)
            return super().construct_mapping(node, deep=deep)

    return _BoundedSafeLoader


def load_bounded_yaml_documents(raw_bytes: bytes | str, *, max_depth: int) -> list[Any]:
    """Every document of a YAML stream (JSON is a YAML subset). Raises `BoundedYamlLimitExceeded`
    or `BoundedYamlMalformed` for a hardening violation; `yaml.YAMLError` (including the
    `ConstructorError` of a custom tag) propagates unchanged."""
    return list(yaml.load_all(raw_bytes, Loader=_loader_class(max_depth)))
