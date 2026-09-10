from fastapi import APIRouter


router = APIRouter()


@router.get("/")
def root():
    return {
        "message": "Radar backend is running in dev mode"
    }


@router.get("/health")
def health():
    return {
        "status": "ok"
    }
