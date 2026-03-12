from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from backend.utils.response import error

router = APIRouter(tags=["system"])

@router.get("/healthz")
def health():
    '''Simple probe used for uptime check.'''
    return {"message": "MangaRecon API is running."}

@router.get("/readyz")
def readyz(request: Request):
    ready = getattr(request.app.state, "rate_limit_storage_ready", False)
    if ready:
        return {"message": "MangaRecon API is ready."}
    return JSONResponse(status_code=503, content=error("Service unavailable", detail="TEMPORARILY_UNAVAILABLE"), headers={"Retry-After": "15"})


