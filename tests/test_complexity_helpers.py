"""Two behaviours the shared helpers in `complexity` carry, which nothing pinned (#701)."""

from __future__ import annotations

import pytest

from archy.complexity import (
    compute_function_complexity,
    extract_function_features,
    extract_token_bags,
)

# A latin-1 byte inside a string literal: not valid UTF-8.
UNDECODABLE = b"def f():\n    return 'caf\xe9'\n"


def test_bytes_that_are_not_utf8_are_replaced_not_raised():
    assert [row.name for row in compute_function_complexity(UNDECODABLE)] == ["f"]
    features = extract_function_features(UNDECODABLE)
    assert list(features) == [1]
    assert features[1].concrete_hash
    assert list(extract_token_bags(UNDECODABLE)) == [1]
    # Replaced, not dropped: the bad byte still tells two literals apart.
    without = extract_function_features(b"def f():\n    return 'caf'\n")
    assert features[1].concrete_hash != without[1].concrete_hash


@pytest.mark.parametrize(
    "inner", ["def g():\n        pass", "class C:\n        pass"], ids=["function", "class"]
)
def test_a_body_that_only_defines_something_is_not_trivial(inner: str):
    source = f"def f():\n    {inner}\n".encode()
    # Control: the same function with nothing but `pass` is trivial.
    assert extract_function_features(b"def f():\n    pass\n")[1].is_trivial

    assert not extract_function_features(source)[1].is_trivial
