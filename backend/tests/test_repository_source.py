from app.sources.repository import get_repository_file_contents


class FakeResponse:
    status_code = 200
    text = "file contents"


def test_repository_file_paths_are_url_encoded_by_segment(monkeypatch):
    requests = []

    def fake_request(url, **kwargs):
        requests.append(url)
        return FakeResponse()

    monkeypatch.setattr("app.sources.repository.github_request", fake_request)

    paths = [
        "plain/file.py",
        "directory/file with spaces.py",
        "test/fixtures/% of dogs.txt",
        "directory/file#name.py",
        "directory/file?query.py",
    ]
    contents = get_repository_file_contents("owner/repo", "abc123", paths)

    assert contents == {path: "file contents" for path in paths}
    assert requests == [
        "https://raw.githubusercontent.com/owner/repo/abc123/plain/file.py",
        "https://raw.githubusercontent.com/owner/repo/abc123/directory/file%20with%20spaces.py",
        "https://raw.githubusercontent.com/owner/repo/abc123/test/fixtures/%25%20of%20dogs.txt",
        "https://raw.githubusercontent.com/owner/repo/abc123/directory/file%23name.py",
        "https://raw.githubusercontent.com/owner/repo/abc123/directory/file%3Fquery.py",
    ]


def test_express_fixture_path_can_be_fetched(monkeypatch):
    requests = []

    def fake_request(url, **kwargs):
        requests.append(url)
        return FakeResponse()

    monkeypatch.setattr("app.sources.repository.github_request", fake_request)

    contents = get_repository_file_contents(
        "expressjs/express",
        "9a34acf03cb818ff3f8bc40e44176e277a25cbb9",
        ["test/fixtures/% of dogs.txt"],
    )

    assert contents["test/fixtures/% of dogs.txt"] == "file contents"
    assert requests == [
        "https://raw.githubusercontent.com/expressjs/express/9a34acf03cb818ff3f8bc40e44176e277a25cbb9/test/fixtures/%25%20of%20dogs.txt"
    ]