import json

from app.services.parsers.formats import read_file


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
