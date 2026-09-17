import json
import sys

import validate_corpus


def entry(name="example/repo"):
    return {"repository": name, "ref": "abc123", "tags": ["test"]}


def operation(ok=True, error_type=None):
    return {
        "status_code": 200 if ok else None,
        "ok": ok,
        "duration_seconds": 0.001,
        "error_type": error_type,
        "body": {"detail": error_type} if error_type else {},
    }


def scan_operation():
    return {
        **operation(),
        "body": {
            "commit_sha": "abc123",
            "files_scanned": 1,
            "facts": [],
            "repository_graph": {"nodes": [{"id": "main.py"}], "relationships": []},
            "component_graph": {"components": [{"id": "root", "type": "unknown"}]},
        },
    }


def test_print_result_handles_none_operations(capsys):
    result = {
        "status": "UNSUPPORTED",
        "repository": "example/repo",
        "file_count": None,
        "fact_count": None,
        "repository_relationship_count": None,
        "component_count": None,
        "unknown_component_count": None,
        "operations": {"scan": operation(), "impact": None, "diff": None},
    }

    validate_corpus._print_result(result)

    output = capsys.readouterr().out
    assert "impact=unsupported" in output
    assert "diff=unsupported" in output


def test_none_impact_result_is_explicitly_unsupported(monkeypatch):
    results = iter([scan_operation(), None, operation()])
    monkeypatch.setattr(validate_corpus, "_operation", lambda *args: next(results))

    result = validate_corpus.validate_entry(entry(), "http://radar", 1)

    assert result["status"] == "UNSUPPORTED"
    assert result["operations"]["impact"]["unsupported"] is True


def test_realistic_successful_scan_produces_counts_and_pass(monkeypatch):
    results = iter([scan_operation(), operation(), operation()])
    monkeypatch.setattr(validate_corpus, "_operation", lambda *args: next(results))

    result = validate_corpus.validate_entry(entry(), "http://radar", 1)

    assert result["status"] == "PASS"
    assert result["scan_success"] is True
    assert result["file_count"] == 1
    assert result["fact_count"] == 0
    assert result["repository_relationship_count"] == 0
    assert result["component_count"] == 1
    assert result["unknown_component_count"] == 1


def test_none_diff_result_is_explicitly_unsupported(monkeypatch):
    results = iter([scan_operation(), operation(), None])
    monkeypatch.setattr(validate_corpus, "_operation", lambda *args: next(results))

    result = validate_corpus.validate_entry(entry(), "http://radar", 1)

    assert result["status"] == "UNSUPPORTED"
    assert result["operations"]["diff"]["unsupported"] is True


def test_operation_exception_is_recorded_as_failure():
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    original = validate_corpus._request
    validate_corpus._request = fail
    try:
        result = validate_corpus._operation("http://radar", "/scan", {}, 1)
    finally:
        validate_corpus._request = original

    assert result["ok"] is False
    assert result["error_type"] == "unexpected_exception"


def test_timeout_is_recorded_as_timeout():
    original = validate_corpus._request
    validate_corpus._request = lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError())
    try:
        result = validate_corpus._operation("http://radar", "/scan", {}, 1)
    finally:
        validate_corpus._request = original

    assert result["ok"] is False
    assert result["error_type"] == "timeout"


def test_failed_repository_does_not_stop_following_repository_and_writes_summary(monkeypatch, tmp_path, capsys):
    corpus_path = tmp_path / "corpus.json"
    report_path = tmp_path / "report.json"
    corpus_path.write_text(json.dumps([entry("failed/repo"), entry("good/repo")]))
    calls = iter([
        RuntimeError("repository exploded"),
        {
            "status": "PASS",
            "repository": "good/repo",
            "operations": {"scan": operation(), "impact": operation(), "diff": operation()},
            "file_count": 1,
            "fact_count": 0,
            "repository_relationship_count": 0,
            "component_count": 1,
            "unknown_component_count": 0,
        },
    ])

    def validate(entry_value, base_url, timeout, mode="deep"):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(validate_corpus, "validate_entry", validate)
    monkeypatch.setattr(validate_corpus, "_preflight", lambda *args: (True, None))
    monkeypatch.setattr(sys, "argv", [
        "validate_corpus.py", "--corpus", str(corpus_path), "--json-out", str(report_path),
    ])

    assert validate_corpus.main() == 1
    output = capsys.readouterr().out
    report = json.loads(report_path.read_text())
    assert "Summary: PASS=1 FAIL=1 UNSUPPORTED=0" in output
    assert report["pass"] == 1
    assert report["fail"] == 1
    assert [item["repository"] for item in report["results"]] == ["failed/repo", "good/repo"]


def test_scan_mode_does_not_call_impact_or_diff(monkeypatch):
    calls = []

    def operation(base_url, path, payload, timeout):
        calls.append(path)
        return scan_operation() if path == "/scan" else operation()

    monkeypatch.setattr(validate_corpus, "_operation", operation)
    result = validate_corpus.validate_entry(entry(), "http://radar", 1, "scan")

    assert result["status"] == "PASS"
    assert calls == ["/scan"]


def test_scan_payload_includes_the_exact_pinned_ref(monkeypatch):
    captured = {}

    def operation(base_url, path, payload, timeout):
        captured.update(payload)
        return scan_operation()

    monkeypatch.setattr(validate_corpus, "_operation", operation)

    validate_corpus.validate_entry(entry(), "http://radar", 1, "scan")

    assert captured == {"url": "https://github.com/example/repo", "ref": "abc123"}


def test_full_sha_pinned_ref_mismatch_fails_clearly(monkeypatch):
    pinned = "f1021eb25d0f4cfbd0d3f8fc37caeaeab0f31b95"
    mismatched_scan = scan_operation()
    mismatched_scan["body"]["commit_sha"] = "d893460cc40474cd605a75ae08c7ca83e722b5e6"
    monkeypatch.setattr(validate_corpus, "_operation", lambda *args: mismatched_scan)

    result = validate_corpus.validate_entry(
        {"repository": "example/repo", "ref": pinned, "tags": []},
        "http://radar",
        1,
        "scan",
    )

    assert result["status"] == "FAIL"
    assert result["failure_reason"] == (
        f"pinned ref mismatch: requested {pinned}, "
        "returned d893460cc40474cd605a75ae08c7ca83e722b5e6"
    )


def test_deep_mode_calls_scan_impact_and_diff(monkeypatch):
    calls = []
    results = iter([scan_operation(), operation(), operation()])

    def operation_call(base_url, path, payload, timeout):
        calls.append(path)
        return next(results)

    monkeypatch.setattr(validate_corpus, "_operation", operation_call)
    result = validate_corpus.validate_entry(entry(), "http://radar", 1, "deep")

    assert result["status"] == "PASS"
    assert calls == ["/scan", "/impact", "/diff"]


def test_resume_skips_successful_and_retries_failed_entries(monkeypatch, tmp_path):
    corpus_path = tmp_path / "corpus.json"
    report_path = tmp_path / "report.json"
    corpus_path.write_text(json.dumps([entry("done/repo"), entry("retry/repo")]))
    report_path.write_text(json.dumps({
        "mode": "scan",
        "results": [{"repository": "done/repo", "status": "PASS"}, {"repository": "retry/repo", "status": "FAIL"}],
    }))
    monkeypatch.setattr(validate_corpus, "_preflight", lambda *args: (True, None))
    monkeypatch.setattr(validate_corpus, "validate_entry", lambda item, *args: {
        "repository": item["repository"], "status": "PASS", "operations": {
            "scan": operation(), "impact": validate_corpus._operation_summary(None), "diff": validate_corpus._operation_summary(None),
        }, "file_count": 1, "fact_count": 0, "repository_relationship_count": 0, "component_count": 1, "unknown_component_count": 0,
    })
    monkeypatch.setattr(sys, "argv", ["validate_corpus.py", "--mode", "scan", "--corpus", str(corpus_path), "--resume", str(report_path), "--json-out", str(report_path)])

    assert validate_corpus.main() == 0
    output = capsys.readouterr().out if False else ""
    report = json.loads(report_path.read_text())
    assert [item["repository"] for item in report["results"]] == ["done/repo", "retry/repo"]


def test_tag_filtering_and_smoke_selection():
    corpus = [
        {"repository": "a", "tags": ["python", "large"]},
        {"repository": "b", "tags": ["javascript"]},
        {"repository": "c", "tags": ["c"]},
    ]

    assert [item["repository"] for item in validate_corpus._select_corpus(corpus, "scan", exclude_tag="large")] == ["b", "c"]
    assert [item["repository"] for item in validate_corpus._select_corpus(corpus, "scan", tag="javascript")] == ["b"]
    assert [item["repository"] for item in validate_corpus._select_corpus(corpus, "smoke")] == ["a", "b", "c"]
