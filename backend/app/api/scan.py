from fastapi import APIRouter, HTTPException

from app.models.repository import DiffRequest, ImpactRequest, RepositoryRequest
from app.services.diff import SnapshotMismatchError, diff_snapshots
from app.services.impact import build_component_impact, build_file_impact
from app.services.scanner import scan_repository
from app.sources.github import GitHubError


router = APIRouter()


@router.post("/scan")
def scan(request: RepositoryRequest):
    try:
        return scan_repository(request.url)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except GitHubError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error)
        )


@router.post("/impact")
def impact(request: ImpactRequest):
    if (request.target is None) == (request.component is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of target or component")

    try:
        scanned = scan_repository(request.url)
        if request.target is not None:
            return build_file_impact(scanned["repository_graph"], request.target)
        return build_component_impact(scanned["component_graph"], request.component)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except GitHubError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error)
        )


@router.post("/diff")
def diff(request: DiffRequest):
    try:
        base = scan_repository(request.url, request.base_ref)
        target = scan_repository(request.url, request.target_ref)
        return diff_snapshots(base["snapshot"], target["snapshot"])

    except SnapshotMismatchError as error:
        raise HTTPException(status_code=409, detail=str(error))

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except GitHubError as error:
        detail = {
            "error": error.error_type,
            "message": str(error),
        }
        raise HTTPException(status_code=error.status_code, detail=detail)
