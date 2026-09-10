from fastapi import APIRouter, HTTPException

from app.models.repository import RepositoryRequest
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
