from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_repository_identity(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("git+"):
        text = text[4:]
    if text.startswith("git@") and ":" in text:
        host, path = text[4:].split(":", 1)
        text = f"https://{host}/{path}"
    if not text.startswith(("https://", "http://", "ssh://")):
        return None
    parsed = urlsplit(text)
    if not parsed.netloc or parsed.query or parsed.fragment:
        return None
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path or path == "/" or "//" in path:
        return None
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    return urlunsplit((scheme, parsed.netloc.lower(), path, "", ""))