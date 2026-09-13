from __future__ import annotations

from graphql import parse

from app.graphql.validation import _has_introspection_field, validate_query_depth


def test_query_limits_check_non_first_operation() -> None:
    deep_operation = """
        query Deep {
            a { b { c { d { e { f { g { h { i { j { k { l { m } } } } } } } } } } } }
        }
    """
    error = validate_query_depth(f"query Cheap {{ x }} {deep_operation}")

    assert error is not None
    assert error.extensions["code"] == "QUERY_TOO_DEEP"


def test_query_limits_allow_a_shallow_single_operation() -> None:
    assert validate_query_depth("query Cheap { x { y } }") is None


def test_query_limits_check_fields_hidden_in_fragments() -> None:
    error = validate_query_depth(
        """
        query Deep { ...DeepFields }
        fragment DeepFields on Query {
            a { b { c { d { e { f { g { h { i { j { k { l } } } } } } } } } } }
        }
        """
    )

    assert error is not None
    assert error.extensions["code"] == "QUERY_TOO_DEEP"


def test_introspection_guard_checks_fields_hidden_in_fragments() -> None:
    document = parse(
        """
        query Introspection { ...Fields }
        fragment Fields on Query { __schema { queryType { name } } }
        """
    )
    fragments = {
        definition.name.value: definition
        for definition in document.definitions
        if definition.kind == "fragment_definition"
    }

    operation = document.definitions[0]
    assert _has_introspection_field(operation.selection_set.selections, fragments=fragments)


def test_introspection_guard_checks_direct_fields() -> None:
    document = parse('query Introspection { __type(name: "Query") { name } }')
    operation = document.definitions[0]

    assert _has_introspection_field(operation.selection_set.selections)


def test_introspection_guard_allows_typename_meta_field() -> None:
    document = parse("query CachedType { __typename }")
    operation = document.definitions[0]

    assert not _has_introspection_field(operation.selection_set.selections)
