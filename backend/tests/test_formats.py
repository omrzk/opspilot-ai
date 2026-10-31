import json

import pytest

from app.services.parsers.formats import read_file
from app.services.parsers.service import parse_file


def test_json_array(tmp_path):
    p = tmp_path / "events.json"
    p.write_text(json.dumps([{"a": 1}, {"a": 2}]))
    fmt, records = read_file(p, "events.json")
    assert fmt == "json"
    assert records == [{"a": 1}, {"a": 2}]


def test_json_envelope_records(tmp_path):
    p = tmp_path / "trail.json"
    p.write_text(json.dumps({"Records": [{"eventName": "RunInstances"}]}))
    _, records = read_file(p, "trail.json")
    assert records == [{"eventName": "RunInstances"}]


def test_ndjson(tmp_path):
    p = tmp_path / "stream.json"
    p.write_text('{"n": 1}\n{"n": 2}\nnot json\n{"n": 3}\n')
    _, records = read_file(p, "stream.json")
    assert [r["n"] for r in records] == [1, 2, 3]


def test_csv_with_sniffed_delimiter(tmp_path):
    p = tmp_path / "log.csv"
    p.write_text("time;level;message\n2026-01-01T00:00:00;error;disk full\n")
    fmt, records = read_file(p, "log.csv")
    assert fmt == "csv"
    assert records[0]["message"] == "disk full"


def test_xml_repeated_children(tmp_path):
    p = tmp_path / "events.xml"
    p.write_text(
        "<Events><Event id='1'><Msg>a</Msg></Event><Event id='2'><Msg>b</Msg></Event></Events>"
    )
    fmt, records = read_file(p, "events.xml")
    assert fmt == "xml"
    assert len(records) == 2
    assert records[0]["@id"] == "1"


def test_text_lines(tmp_path):
    p = tmp_path / "app.log"
    p.write_text("line one\n\nline two\n")
    fmt, records = read_file(p, "app.log")
    assert fmt == "text"
    assert [r["line"] for r in records] == ["line one", "line two"]


def test_sniff_json_named_txt(tmp_path):
    p = tmp_path / "data.txt"
    p.write_text('[{"kind": "Event"}]')
    fmt, records = read_file(p, "data.txt")
    assert fmt == "json"
    assert records == [{"kind": "Event"}]


def test_unsupported_extension(tmp_path):
    p = tmp_path / "image.png"
    p.write_bytes(b"\x89PNG")
    try:
        read_file(p, "image.png")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


@pytest.mark.parametrize("key", ["Records", "records", "items", "events", "value"])
def test_json_envelopes_skip_non_object_entries(tmp_path, key):
    first = {"eventVersion": "1.08", "eventSource": "ec2.amazonaws.com",
             "eventName": "RunInstances"}
    second = {"eventVersion": "1.08", "eventSource": "ec2.amazonaws.com",
              "eventName": "StopInstances"}
    path = tmp_path / "mixed.json"
    path.write_text(json.dumps({key: [first, None, 42, True, "noise", [], second]}))

    fmt, records = read_file(path, path.name)
    assert fmt == "json"
    assert records == [first, second]
    result = parse_file(path, path.name)
    assert result.source_type == "cloudtrail"
    assert [event.raw for event in result.events] == [first, second]
    assert result.warnings == []


@pytest.mark.parametrize("records", [[], [None], [None, {"message": "ok"}], [42], ["noise"]])
def test_unrecognized_json_envelope_keeps_generic_object(tmp_path, records):
    data = {"Records": records, "message": "metadata"}
    path = tmp_path / "generic.json"
    path.write_text(json.dumps(data))
    assert read_file(path, path.name)[1] == [data]


@pytest.mark.parametrize("wrapped", [False, True])
def test_json_record_limit_applies_before_filtering(tmp_path, monkeypatch, wrapped):
    monkeypatch.setattr("app.services.parsers.formats.MAX_RECORDS", 3)
    records = [{"message": "first"}, None, {"message": "second"}, {"message": "beyond cap"}]
    data = {"Records": records} if wrapped else records
    path = tmp_path / "capped.json"
    path.write_text(json.dumps(data))
    assert read_file(path, path.name)[1] == [records[0], records[2]]
