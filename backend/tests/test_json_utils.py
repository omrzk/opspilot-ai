import pytest

from app.services.llm.json_utils import extract_json_object


def test_plain_json():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_fenced_json():
    text = 'Here is the analysis:\n```json\n{"summary": "ok", "confidence": 0.8}\n```\nDone.'
    assert extract_json_object(text) == {"summary": "ok", "confidence": 0.8}


def test_fence_without_language_tag():
    assert extract_json_object('```\n{"x": [1, 2]}\n```') == {"x": [1, 2]}


def test_prose_around_object():
    text = 'The result is {"root_cause": "disk full", "confidence": 0.9} as shown.'
    assert extract_json_object(text)["root_cause"] == "disk full"


def test_nested_braces_and_strings():
    text = '{"msg": "use {braces} and \\"quotes\\"", "inner": {"k": "}"}}'
    parsed = extract_json_object(text)
    assert parsed["inner"]["k"] == "}"


def test_raw_newline_inside_string_is_repaired():
    text = '{"script": "line1\nline2\tend"}'
    parsed = extract_json_object(text)
    assert parsed["script"] == "line1\nline2\tend"


def test_no_json_raises():
    with pytest.raises(ValueError):
        extract_json_object("I could not produce the analysis, sorry.")


def test_array_only_raises():
    with pytest.raises(ValueError):
        extract_json_object("[1, 2, 3]")
