from __future__ import annotations

import logging
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
                if doc.definitions:
                    first = doc.definitions[0]
                    if hasattr(first, "selection_set") and first.selection_set:
                        depth = calculate_depth(first.selection_set.selections)
                        if depth > MAX_QUERY_DEPTH:
                            raise GraphQLError(
                                f"Query depth {depth} exceeds maximum allowed depth of {MAX_QUERY_DEPTH}",
                                extensions={
                                    "code": "QUERY_TOO_DEEP",
                                    "depth": depth,
                                    "max_depth": MAX_QUERY_DEPTH,
                                },
                            )
                        complexity = calculate_complexity(first.selection_set.selections)
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
            logger.debug("Depth validation check skipped: %s", e)
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
                for definition in doc.definitions:
                    if not hasattr(definition, "selection_set") or not definition.selection_set:
                        continue
                    if _has_introspection_field(definition.selection_set.selections):
                        raise GraphQLError(
                            "Introspection is disabled in production.",
                            extensions={"code": "GRAPHQL_VALIDATION_FAILED"},
                        )
        except GraphQLError:
            raise
        except Exception as e:
            logger.debug("Introspection check skipped: %s", e)
        yield


def _has_introspection_field(selections: list) -> bool:
    """Return True if any selection is a built-in introspection field."""
    introspection_fields = {"__schema", "__type", "__typename"}
    for selection in selections:
        name = getattr(selection, "name", None)
        if name and str(name) in introspection_fields:
            if str(name) == "__typename":
                continue
            return True
        if hasattr(selection, "selection_set") and selection.selection_set:
            if _has_introspection_field(selection.selection_set.selections):
                return True
    return False


def calculate_depth(selections: list, current_depth: int = 0) -> int:
    """Calculate the maximum depth of a GraphQL query."""
    if not selections:
        return current_depth

    max_depth = current_depth
    for selection in selections:
        if hasattr(selection, "selection_set") and selection.selection_set:
            nested_depth = calculate_depth(selection.selection_set.selections, current_depth + 1)
            max_depth = max(max_depth, nested_depth)
    return max_depth


def calculate_complexity(
    selections: list, depth: int = 0, field_cost: int = DEFAULT_FIELD_COST
) -> int:
    """Calculate the complexity score of a GraphQL query."""
    if not selections:
        return 0

    total = 0
    for selection in selections:
        cost = field_cost * (NESTED_FIELD_MULTIPLIER**depth)
        total += cost

        if hasattr(selection, "selection_set") and selection.selection_set:
            total += calculate_complexity(
                selection.selection_set.selections,
                depth + 1,
                field_cost,
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
    first = document.definitions[0]
    if not hasattr(first, "selection_set") or not first.selection_set:
        return None
    depth = calculate_depth(first.selection_set.selections)
    if depth > MAX_QUERY_DEPTH:
        return GraphQLError(
            f"Query depth {depth} exceeds maximum allowed depth of {MAX_QUERY_DEPTH}",
            extensions={
                "code": "QUERY_TOO_DEEP",
                "depth": depth,
                "max_depth": MAX_QUERY_DEPTH,
            },
        )

    complexity = calculate_complexity(first.selection_set.selections)
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
