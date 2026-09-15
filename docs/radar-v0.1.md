docs/radar-v0.1.md

# Radar Core v0.1

Status: COMPLETED

Goal:
Detect what technologies exist in a repository
using deterministic evidence-backed scanning.

Implemented:
- Repository tree retrieval from GitHub
- Entity / Fact / Evidence models
- CMake detection
- Docker detection
- Docker Compose detection
- Python detection
- Node.js detection
- Jenkins detection
- GitHub Actions detection
- Maven detection
- Gradle detection
- Yocto / BitBake detection
- technology fact deduplication
- false-positive protection for weak-path evidence
- /scan response extended with technology findings
- SQLite persistence for release tracking without removing prior functionality

Tests:
25 passed (including v0.1 coverage)

Known limitations:
- no deep file parsing
- no configuration version extraction
- no configuration comparison
- no GitLab/local repository support
- no advanced repository graph modeling