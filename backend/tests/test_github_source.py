import pytest

from app.sources.github import GitHubError, get_commit, get_repository, github_headers


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


def test_github_headers_are_unauthenticated_by_default(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    headers = github_headers()

    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["User-Agent"] == "radar-core"
    assert "Authorization" not in headers


def test_github_headers_use_optional_bearer_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    assert github_headers()["Authorization"] == "Bearer test-token"


def test_github_request_preserves_repository_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.sources.github.httpx.get",
        lambda *args, **kwargs: FakeResponse(404),
    )

    with pytest.raises(GitHubError) as error:
        get_repository("missing/repository")

    assert error.value.status_code == 404
    assert error.value.error_type == "repository_not_found"
    assert str(error.value) == "GitHub repository not found"


def test_github_request_distinguishes_invalid_ref(monkeypatch):
    monkeypatch.setattr(
        "app.sources.github.httpx.get",
        lambda *args, **kwargs: FakeResponse(404),
    )

    with pytest.raises(GitHubError) as error:
        get_commit("owner/repository", "missing-ref")

    assert error.value.status_code == 404
    assert error.value.error_type == "ref_not_found"
    assert str(error.value) == "GitHub repository ref not found"


def test_github_request_distinguishes_authentication_failure(monkeypatch):
    monkeypatch.setattr(
        "app.sources.github.httpx.get",
        lambda *args, **kwargs: FakeResponse(401),
    )

    with pytest.raises(GitHubError) as error:
        get_repository("owner/repository")

    assert error.value.status_code == 401
    assert error.value.error_type == "github_auth_failed"
    assert str(error.value) == "GitHub authentication failed"


def test_github_request_distinguishes_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "app.sources.github.httpx.get",
        lambda *args, **kwargs: FakeResponse(403, headers={"x-ratelimit-remaining": "0"}),
    )

    with pytest.raises(GitHubError) as error:
        get_repository("owner/repository")

    assert error.value.status_code == 403
    assert error.value.error_type == "github_rate_limited"
    assert str(error.value) == "GitHub API rate limit exceeded"


def test_github_request_passes_auth_headers_to_httpx(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    captured = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse(200, {"sha": "abc"})

    monkeypatch.setattr("app.sources.github.httpx.get", fake_get)

    assert get_commit("owner/repository", "abc")["sha"] == "abc"
    assert captured["headers"]["Authorization"] == "Bearer test-token"
