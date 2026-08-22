import asyncio

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from backend.cache.redis import get_redis_cache
from backend.config.settings import ENV
from backend.dependencies import database_connections_ready
from backend.rate_limit.middleware import limiter, rate_limit_storage_ready
from backend.utils.response import error

router = APIRouter(tags=["system"])

@router.get("/healthz")
@limiter.exempt
def health():
    '''Simple probe used for uptime check.'''
    return {"message": "MangaRecon API is running."}

@router.get("/readyz")
@limiter.exempt
async def readyz(request: Request):
    if ENV == "prod":
        database_ready, cache_ready, limiter_ready = await asyncio.gather(
            database_connections_ready(),
            get_redis_cache().ping(),
            rate_limit_storage_ready(),
        )
        request.app.state.rate_limit_storage_ready = limiter_ready
        ready = database_ready and cache_ready and limiter_ready
    else:
        ready = True

    if ready:
        return {"message": "MangaRecon API is ready."}
    return JSONResponse(status_code=503, content=error("Service unavailable.", detail="TEMPORARILY_UNAVAILABLE"), headers={"Retry-After": "15"})
