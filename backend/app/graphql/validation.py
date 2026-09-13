from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Optional

from graphql import GraphQLError
from strawberry.extensions import SchemaExtension
from strawberry.extensions.base_extension import AsyncIteratorOrIterator

logger = logging.getLogger(__name__)

MAX_QUERY_DEPTH = 10
MAX_QUERY_COMPLEXITY = 1000
DEFAULT_FIELD_COST = 1
NESTED_FIELD_MULTIPLIER = 2


class DepthValidationExtension(SchemaExtension):
    """Strawberry extension to enforce query depth/complexity limits."""

    async def on_operation(self) -> AsyncIteratorOrIterator[None]:
        # Access parsed operation from execution context
        # Strawberry provides `self.execution_context` in newer versions
        try:
            ctx = self.execution_context
            if ctx and ctx.graphql_document:
                doc = ctx.graphql_document
                fragments = _fragment_definitions(doc.definitions)
                for definition in doc.definitions:
                    if not hasattr(definition, "selection_set") or not definition.selection_set:
                        continue
                    depth = calculate_depth(
                        definition.selection_set.selections, fragments=fragments
                    )
                    if depth > MAX_QUERY_DEPTH:
                        raise GraphQLError(
                            f"Query depth {depth} exceeds maximum allowed depth of {MAX_QUERY_DEPTH}",
                            extensions={
                                "code": "QUERY_TOO_DEEP",
                                "depth": depth,
                                "max_depth": MAX_QUERY_DEPTH,
                            },
                        )
                    complexity = calculate_complexity(
                        definition.selection_set.selections, fragments=fragments
                    )
                    if complexity > MAX_QUERY_COMPLEXITY:
                        raise GraphQLError(
                            f"Query complexity {complexity} exceeds maximum allowed complexity of {MAX_QUERY_COMPLEXITY}",
                            extensions={
                                "code": "QUERY_TOO_COMPLEX",
                                "complexity": complexity,
                                "max_complexity": MAX_QUERY_COMPLEXITY,
                            },
                        )
        except GraphQLError:
            raise
        except Exception as e:
            logger.error("Depth validation failed closed: %s", type(e).__name__)
            raise GraphQLError(
                "GraphQL query validation is unavailable",
                extensions={"code": "GRAPHQL_VALIDATION_FAILED"},
            ) from e
        yield


# Backwards compat aliases
QueryDepthExtension = DepthValidationExtension


class DisableIntrospection(SchemaExtension):
    """Extension that blocks GraphQL introspection in production."""

    async def on_operation(self) -> AsyncIteratorOrIterator[None]:
        try:
            ctx = self.execution_context
            if ctx and ctx.graphql_document:
                doc = ctx.graphql_document
                fragments = _fragment_definitions(doc.definitions)
                for definition in doc.definitions:
                    if not hasattr(definition, "selection_set") or not definition.selection_set:
                        continue
                    if _has_introspection_field(
                        definition.selection_set.selections, fragments=fragments
                    ):
                        raise GraphQLError(
                            "Introspection is disabled in production.",
                            extensions={"code": "GRAPHQL_VALIDATION_FAILED"},
                        )
        except GraphQLError:
            raise
        except Exception as e:
            logger.error("Introspection validation failed closed: %s", type(e).__name__)
            raise GraphQLError(
                "GraphQL query validation is unavailable",
                extensions={"code": "GRAPHQL_VALIDATION_FAILED"},
            ) from e
        yield


def _has_introspection_field(
    selections: list,
    *,
    fragments: Optional[dict[str, object]] = None,
    fragment_stack: frozenset[str] = frozenset(),
) -> bool:
    """Return True if any selection is a built-in introspection field."""
    # __typename is a standard response meta-field, not schema introspection;
    # Apollo and fragment-based clients commonly request it in production.
    introspection_fields = {"__schema", "__type"}
    for selection in selections:
        if getattr(selection, "kind", None) == "fragment_spread":
            fragment_name = selection.name.value
            fragment = (fragments or {}).get(fragment_name)
            fragment_selection_set = getattr(fragment, "selection_set", None)
            if (
                fragment_selection_set
                and fragment_name not in fragment_stack
                and _has_introspection_field(
                    fragment_selection_set.selections,
                    fragments=fragments,
                    fragment_stack=fragment_stack | {fragment_name},
                )
            ):
                return True
            continue
        name = getattr(selection, "name", None)
        name_value = getattr(name, "value", name)
        if isinstance(name_value, str) and name_value in introspection_fields:
            if name_value == "__typename":
                continue
            return True
        if hasattr(selection, "selection_set") and selection.selection_set:
            if _has_introspection_field(
                selection.selection_set.selections,
                fragments=fragments,
                fragment_stack=fragment_stack,
            ):
                return True
    return False


def _fragment_definitions(definitions: Sequence[object]) -> dict[str, object]:
    fragments: dict[str, object] = {}
    for definition in definitions:
        if getattr(definition, "kind", None) != "fragment_definition":
            continue
        name = getattr(getattr(definition, "name", None), "value", None)
        if isinstance(name, str):
            fragments[name] = definition
    return fragments


def calculate_depth(
    selections: list,
    current_depth: int = 0,
    *,
    fragments: Optional[dict[str, object]] = None,
    fragment_stack: frozenset[str] = frozenset(),
) -> int:
    """Calculate the maximum depth of a GraphQL query."""
    if not selections:
        return current_depth

    max_depth = current_depth
    for selection in selections:
        if getattr(selection, "kind", None) == "fragment_spread":
            fragment_name = selection.name.value
            fragment = (fragments or {}).get(fragment_name)
            if fragment is not None and fragment_name not in fragment_stack:
                fragment_selection_set = getattr(fragment, "selection_set", None)
                if fragment_selection_set:
                    max_depth = max(
                        max_depth,
                        calculate_depth(
                            fragment_selection_set.selections,
                            current_depth,
                            fragments=fragments,
                            fragment_stack=fragment_stack | {fragment_name},
                        ),
                    )
            continue
        if hasattr(selection, "selection_set") and selection.selection_set:
            nested_depth = calculate_depth(
                selection.selection_set.selections,
                current_depth + 1,
                fragments=fragments,
                fragment_stack=fragment_stack,
            )
            max_depth = max(max_depth, nested_depth)
    return max_depth


def calculate_complexity(
    selections: list,
    depth: int = 0,
    field_cost: int = DEFAULT_FIELD_COST,
    *,
    fragments: Optional[dict[str, object]] = None,
    fragment_stack: frozenset[str] = frozenset(),
) -> int:
    """Calculate the complexity score of a GraphQL query."""
    if not selections:
        return 0

    total = 0
    for selection in selections:
        if getattr(selection, "kind", None) == "fragment_spread":
            fragment_name = selection.name.value
            fragment = (fragments or {}).get(fragment_name)
            total += field_cost * (NESTED_FIELD_MULTIPLIER**depth)
            if fragment is not None and fragment_name not in fragment_stack:
                fragment_selection_set = getattr(fragment, "selection_set", None)
                if fragment_selection_set:
                    total += calculate_complexity(
                        fragment_selection_set.selections,
                        depth,
                        field_cost,
                        fragments=fragments,
                        fragment_stack=fragment_stack | {fragment_name},
                    )
            continue
        cost = field_cost * (NESTED_FIELD_MULTIPLIER**depth)
        total += cost

        if hasattr(selection, "selection_set") and selection.selection_set:
            total += calculate_complexity(
                selection.selection_set.selections,
                depth + 1,
                field_cost,
                fragments=fragments,
                fragment_stack=fragment_stack,
            )
    return total


def validate_query_depth(query: str) -> Optional[GraphQLError]:
    """Validate query depth. Returns GraphQLError if invalid."""
    from graphql import parse

    try:
        document = parse(query)
    except GraphQLError as e:
        return e

    if not document.definitions:
        return None
    fragments = _fragment_definitions(document.definitions)
    for definition in document.definitions:
        if not hasattr(definition, "selection_set") or not definition.selection_set:
            continue
        depth = calculate_depth(definition.selection_set.selections, fragments=fragments)
        if depth > MAX_QUERY_DEPTH:
            return GraphQLError(
                f"Query depth {depth} exceeds maximum allowed depth of {MAX_QUERY_DEPTH}",
                extensions={
                    "code": "QUERY_TOO_DEEP",
                    "depth": depth,
                    "max_depth": MAX_QUERY_DEPTH,
                },
            )

        complexity = calculate_complexity(definition.selection_set.selections, fragments=fragments)
        if complexity > MAX_QUERY_COMPLEXITY:
            return GraphQLError(
                f"Query complexity {complexity} exceeds maximum allowed complexity of {MAX_QUERY_COMPLEXITY}",
                extensions={
                    "code": "QUERY_TOO_COMPLEX",
                    "complexity": complexity,
                    "max_complexity": MAX_QUERY_COMPLEXITY,
                },
            )

    return None
