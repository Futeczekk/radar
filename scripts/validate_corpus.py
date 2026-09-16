#!/usr/bin/env python3
"""Run Radar's API operations against the pinned public validation corpus."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CORPUS = Path(__file__).with_name("radar_validation_corpus.json")
MODES = {"scan", "deep", "smoke"}


def _request(base_url: str, path: str, payload: dict, timeout: float, method="POST"):
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"detail": body[:300]}
        return error.code, detail, "api_error"
    except TimeoutError:
        return None, {"detail": "request timed out"}, "timeout"
    except (URLError, OSError) as error:
        return None, {"detail": str(error)}, "transport_error"


def _error_type(payload: dict):
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        return detail.get("error") or detail.get("type") or "api_error"
    if detail:
        return "api_error"
    return "unknown_error"


def _operation(base_url, path, payload, timeout):
    started = time.monotonic()
    exception = None
    try:
        status, body, request_error_type = _request(base_url, path, payload, timeout)
    except TimeoutError as error:
        status, body, request_error_type = None, {"detail": "request timed out"}, "timeout"
        exception = error
    except Exception as error:
        status, body, request_error_type = None, {"detail": "unexpected operation exception"}, "unexpected_exception"
        exception = error
    exception_info = None if exception is None else {
        "class": type(exception).__name__,
        "message": " ".join(str(exception).split())[:300],
    }
    return {
        "status_code": status,
        "ok": status == 200,
        "duration_seconds": round(time.monotonic() - started, 3),
        "error_type": None if status == 200 else request_error_type or _error_type(body),
        "exception": exception_info,
        "body": body,
    }
def _operation_summary(operation, *, reason="operation unavailable"):
    if operation is None:
        return {
            "status_code": None,
            "ok": False,
            "unsupported": True,
            "duration_seconds": 0.0,
            "error_type": "unsupported",
            "reason": reason,
        }
    return {key: value for key, value in operation.items() if key != "body"}


def _scan_result(entry, scan):
    body = scan.get("body") if isinstance(scan.get("body"), dict) else {}
    graph = body.get("repository_graph", {}) if scan["ok"] else {}
    components = body.get("component_graph", {}).get("components", []) if scan["ok"] else []
    nodes = graph.get("nodes", [])
    target = nodes[0].get("id") if nodes else None
    return {
        "repository": entry["repository"],
        "pinned_ref": entry["ref"],
        "resolved_commit_sha": body.get("commit_sha") if scan["ok"] else None,
        "scan_success": scan["ok"],
        "file_count": body.get("files_scanned") if scan["ok"] else None,
        "fact_count": len(body.get("facts", [])) if scan["ok"] else None,
        "repository_relationship_count": len(graph.get("relationships", [])) if scan["ok"] else None,
        "component_count": len(components) if scan["ok"] else None,
        "unknown_component_count": sum(item.get("type") == "unknown" for item in components) if scan["ok"] else None,
        "source_error_type": scan["error_type"],
        "scan_duration_seconds": scan["duration_seconds"],
        "operations": {
            "scan": _operation_summary(scan),
            "impact": None,
            "diff": None,
        },
        "_impact_target": target,
    }


def validate_entry(entry, base_url: str, timeout: float, mode="deep"):
    url = f"https://github.com/{entry['repository']}"
    scan = _operation(base_url, "/scan", {"url": url}, timeout)
    if not isinstance(scan, dict):
        scan = _operation_summary(None, reason="scan result missing")
    result = _scan_result(entry, scan)

    if not scan["ok"]:
        result["operations"]["impact"] = _operation_summary(None, reason="scan failed")
        result["operations"]["diff"] = _operation_summary(None, reason="scan failed")
        result["status"] = "FAIL"
        result.pop("_impact_target", None)
        return result

    target = result.pop("_impact_target")
    if mode == "scan":
        result["operations"]["impact"] = _operation_summary(None, reason="scan mode")
        result["operations"]["diff"] = _operation_summary(None, reason="scan mode")
        result["status"] = "PASS"
        return result

    if target:
        impact = _operation(base_url, "/impact", {"url": url, "target": target}, timeout)
        result["operations"]["impact"] = _operation_summary(impact)
    else:
        result["operations"]["impact"] = {"ok": False, "unsupported": True, "reason": "no repository graph nodes"}

    diff = _operation(
        base_url,
        "/diff",
        {"url": url, "base_ref": entry["ref"], "target_ref": entry["ref"]},
        timeout,
    )
    result["operations"]["diff"] = _operation_summary(diff)

    operation_failures = [
        operation for operation in (impact if target else None, diff)
        if operation is not None and not operation["ok"]
    ]
    operation_results = [result["operations"]["impact"], result["operations"]["diff"]]
    operation_failures = [operation for operation in operation_results if not operation.get("ok") and not operation.get("unsupported")]
    operation_unsupported = [operation for operation in operation_results if operation.get("unsupported")]
    if operation_failures:
        result["status"] = "FAIL"
    elif operation_unsupported:
        result["status"] = "UNSUPPORTED"
    else:
        result["status"] = "PASS"
    return result


def _preflight(base_url: str, timeout: float):
    health_status, _, health_error = _request(base_url, "/health", {}, timeout, method="GET")
    if health_status != 200:
        return False, f"/health returned {health_status or health_error}"
    controlled = {"repository": "Futii10/radar-test"}
    preflight = _operation(
        base_url,
        "/scan",
        {"url": f"https://github.com/{controlled['repository']}"},
        timeout,
    )
    if not preflight["ok"]:
        return False, f"controlled scan returned {preflight.get('error_type')}"
    return True, None


def _select_corpus(corpus, mode, only=None, limit=None, exclude_tag=None, tag=None):
    selected = corpus
    if only:
        selected = [entry for entry in selected if entry.get("repository") == only]
    if tag:
        selected = [entry for entry in selected if tag in entry.get("tags", [])]
    if exclude_tag:
        selected = [entry for entry in selected if exclude_tag not in entry.get("tags", [])]
    if mode == "smoke":
        smoke_tags = {"controlled", "python", "javascript", "c", "mixed"}
        selected = [entry for entry in selected if smoke_tags.intersection(entry.get("tags", []))][:5]
    if limit is not None:
        selected = selected[:max(limit, 0)]
    return selected


def _print_result(result):
    operations = result.get("operations") or {}
    scan = operations.get("scan") or _operation_summary(None, reason="scan result missing")
    impact = operations.get("impact") or _operation_summary(None, reason="impact result missing")
    diff = operations.get("diff") or _operation_summary(None, reason="diff result missing")
    print(
        f"{result['status']:<11} {result['repository']:<28} "
        f"scan={'ok' if scan.get('ok') else scan.get('error_type', 'unsupported')} "
        f"impact={'ok' if impact.get('ok') else impact.get('error_type', 'unsupported')} "
        f"diff={'ok' if diff.get('ok') else diff.get('error_type', 'unsupported')} "
        f"files={result['file_count'] if result['file_count'] is not None else '-':>5} "
        f"facts={result['fact_count'] if result['fact_count'] is not None else '-':>4} "
        f"rels={result['repository_relationship_count'] if result['repository_relationship_count'] is not None else '-':>4} "
        f"components={result['component_count'] if result['component_count'] is not None else '-':>3} "
        f"unknown={result['unknown_component_count'] if result['unknown_component_count'] is not None else '-':>3}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8001", help="Running Radar API base URL")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="Pinned corpus JSON path")
    parser.add_argument("--timeout", type=float, default=180.0, help="Per-request timeout in seconds")
    parser.add_argument("--json-out", type=Path, help="Optional JSON report path")
    parser.add_argument("--limit", type=int, help="Validate at most N selected corpus entries")
    parser.add_argument("--only", help="Validate only this repository owner/name")
    parser.add_argument("--mode", choices=sorted(MODES), default="scan", help="Validation profile: scan, deep, or smoke")
    parser.add_argument("--resume", type=Path, help="Resume from a prior JSON report")
    parser.add_argument("--exclude-tag", help="Exclude entries containing this corpus tag")
    parser.add_argument("--tag", help="Include only entries containing this corpus tag")
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    corpus = _select_corpus(corpus, args.mode, args.only, args.limit, args.exclude_tag, args.tag)
    if not corpus:
        print("No corpus entries selected", file=sys.stderr)
        return 2

    preflight_ok, preflight_error = _preflight(args.base_url, args.timeout)
    if not preflight_ok:
        print(f"Preflight FAIL: {preflight_error}", file=sys.stderr)
        return 1
    print("Preflight PASS: /health and Futii10/radar-test /scan")
    print(f"Radar corpus validation: mode={args.mode} {len(corpus)} repositories; API {args.base_url}")
    print("STATUS      REPOSITORY                    scan       impact     diff       files facts rels components unknown")
    results = []
    completed = set()
    if args.resume and args.resume.exists():
        prior = json.loads(args.resume.read_text(encoding="utf-8"))
        if prior.get("mode") == args.mode:
            results = prior.get("results", [])
            completed = {item.get("repository") for item in results if item.get("status") == "PASS"}
    if args.json_out:
        _write_report(args.json_out, results, args.mode, len(corpus))
    for entry in corpus:
        if entry.get("repository") in completed:
            print(f"SKIP        {entry['repository']:<28} resume=PASS")
            continue
        try:
            result = validate_entry(entry, args.base_url, args.timeout, args.mode)
        except Exception as error:
            result = {
                "repository": entry.get("repository", "unknown"),
                "pinned_ref": entry.get("ref"),
                "resolved_commit_sha": None,
                "scan_success": False,
                "file_count": None,
                "fact_count": None,
                "repository_relationship_count": None,
                "component_count": None,
                "unknown_component_count": None,
                "source_error_type": "unexpected_repository_exception",
                "scan_duration_seconds": 0.0,
                "operations": {
                    "scan": _operation_summary(None, reason="repository exception"),
                    "impact": _operation_summary(None, reason="repository exception"),
                    "diff": _operation_summary(None, reason="repository exception"),
                },
                "status": "FAIL",
                "error": type(error).__name__,
            }
        results = [item for item in results if item.get("repository") != entry.get("repository")]
        results.append(result)
        _print_result(result)
        if args.json_out:
            _write_report(args.json_out, results, args.mode, len(corpus))

    summary = {
        "mode": args.mode,
        "corpus_size": len(corpus),
        "pass": sum(item["status"] == "PASS" for item in results),
        "fail": sum(item["status"] == "FAIL" for item in results),
        "unsupported": sum(item["status"] == "UNSUPPORTED" for item in results),
        "results": results,
    }
    print(f"Summary: PASS={summary['pass']} FAIL={summary['fail']} UNSUPPORTED={summary['unsupported']}")
    if args.json_out:
        _write_report(args.json_out, results, args.mode, len(corpus))
        print(f"JSON report: {args.json_out}")
    return 1 if summary["fail"] else 0


def _write_report(path: Path, results, mode="deep", selected_count=None):
    summary = {
    "mode": mode,
    "selected_count": selected_count if selected_count is not None else len(results),
        "corpus_size": len(results),
        "pass": sum(item["status"] == "PASS" for item in results),
        "fail": sum(item["status"] == "FAIL" for item in results),
        "unsupported": sum(item["status"] == "UNSUPPORTED" for item in results),
        "results": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
