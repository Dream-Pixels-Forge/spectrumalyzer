"""End-to-end CLI tests."""

from __future__ import annotations

import json

from spectrumalyzer.cli import main


def test_analyze_json(click_120, tmp_path, capsys):
    out = tmp_path / "beats.json"
    rc = main(["analyze", str(click_120), "-o", str(out), "--fps", "30", "--quiet"])
    assert rc == 0
    data = json.loads(out.read_text())
    assert 117 <= data["bpm"] <= 123
    assert data["fps"] == 30
    assert data["beats"][0]["frame"] >= 0


def test_analyze_multi_format(click_120, tmp_path):
    out = tmp_path / "beats"
    rc = main([
        "analyze", str(click_120), "-o", str(out), "--fps", "30",
        "--format", "json,csv,remotion,ae,fcpxml,hyperframes", "--quiet",
    ])
    assert rc == 0
    base = tmp_path / "beats"
    assert (tmp_path / "beats.json").exists()
    assert (tmp_path / "beats.markers.csv").exists()
    assert (tmp_path / "beats.remotion.json").exists()
    assert (base.parent / "beats.useBeats.ts").exists()
    assert (tmp_path / "beats.markers.jsx").exists()
    assert (tmp_path / "beats.fcpxml").exists()
    assert (tmp_path / "beats.hyperframes.json").exists()


def test_analyze_stdout(click_120, capsys):
    rc = main(["analyze", str(click_120), "--stdout", "--quiet"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["bpm"] > 0


def test_report_command(click_120, tmp_path):
    out = tmp_path / "report.html"
    rc = main(["report", str(click_120), "-o", str(out), "--fps", "30", "--quiet"])
    assert rc == 0
    html = out.read_text()
    assert "<canvas" in html


def test_formats_command(capsys):
    rc = main(["formats"])
    assert rc == 0
    out = capsys.readouterr().out
    for fmt in ("json", "remotion", "hyperframes", "ae", "csv", "fcpxml"):
        assert fmt in out


def test_missing_file_exits_nonzero(tmp_path):
    rc = main(["analyze", str(tmp_path / "nope.mp3")])
    assert rc != 0
