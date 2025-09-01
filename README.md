# MangaRecon (WIP)

> Work-in-progress service for manga discovery, collections, ratings, and personalized recommendations.  
> This repository is primarily for documentation and code review while development continues.

## Project Status

- Active development; APIs and data models may change.
- Back-end foundations are in place (auth, profiles, collections, ratings, metadata, recommendations).
- Test suite is being expanded (pytest + httpx ASGI).
- Frontend integration will come after back-end tests.

---

## Architecture (High-Level)

- **API**: FastAPI (async), Pydantic **v2** (`pydantic-settings` for configuration)
- **Data**: PostgreSQL via SQLAlchemy **2.x async** (`asyncpg`)
- **Cache / RL store**: Redis (`redis.asyncio`)
- **Auth**: `fastapi-users` + `fastapi-users-db-sqlalchemy`
- **Rate limiting**: `slowapi`
  - Global default limit covers third-party handlers (e.g., fastapi-users routes)
  - Per-route limits
- **Testing**: `pytest`, `pytest-asyncio`, `httpx`, `asgi-lifespan`

---
