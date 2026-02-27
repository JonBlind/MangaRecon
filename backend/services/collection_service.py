from __future__ import annotations

from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.cache.invalidation import invalidate_collection_recommendations
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.db.models.collection import Collection
from backend.repositories.collections_repo import (
    count_collection_manga,
    get_owned_collection_id,
    page_collection_manga_ids,
)
from backend.repositories.manga_repo import attach_genres_to_base, fetch_manga_list_base
from backend.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
)
from backend.schemas.manga import MangaListItem
from backend.utils.domain_exceptions import NotFoundError, ConflictError


async def list_user_collections_page(
    *,
    user_id,
    page: int,
    size: int,
    order: Literal["asc", "desc"],
    user_db: ClientReadDatabase,
) -> dict:
    """
    Return a paginated list of collections for the given user.
    """
    offset = (page - 1) * size

    base = select(Collection).where(Collection.user_id == user_id)

    count_stmt = base.with_only_columns(func.count(Collection.collection_id)).order_by(None)
    total = (await user_db.execute(count_stmt)).scalar_one()

    order_by = Collection.collection_id.asc() if order == "asc" else Collection.collection_id.desc()
    stmt = base.order_by(order_by).offset(offset).limit(size)

    res = await user_db.execute(stmt)
    rows = res.scalars().all()

    items = [CollectionRead.model_validate(c) for c in rows]
    return {"total_results": total, "page": page, "size": size, "items": items}


async def get_user_collection_by_id(
    *,
    user_id,
    collection_id: int,
    user_db: ClientReadDatabase,
) -> CollectionRead:
    """
    Return a single collection by id for the given user.
    """
    stmt = select(Collection).where(
        Collection.collection_id == collection_id,
        Collection.user_id == user_id,
    )
    res = await user_db.execute(stmt)
    collection = res.scalar_one_or_none()

    if collection is None:
        raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

    return CollectionRead.model_validate(collection)


async def create_user_collection(
    *,
    user_id,
    payload: CollectionCreate,
    user_db: ClientWriteDatabase,
) -> CollectionRead:
    """
    Create a new collection for the given user.
    """
    try:
        new_collection = Collection(
            user_id=user_id,
            collection_name=payload.collection_name,
            description=payload.description,
        )
        user_db.add(new_collection)
        await user_db.commit()
        await user_db.refresh(new_collection)

        return CollectionRead.model_validate(new_collection)

    except IntegrityError:
        await user_db.rollback()
        raise ConflictError(code="COLLECTION_NAME_CONFLICT", message="A collection with this name already exists.")

    except Exception:
        await user_db.rollback()
        raise


async def update_user_collection(
    *,
    user_id,
    collection_id: int,
    payload: CollectionUpdate,
    user_db: ClientWriteDatabase,
) -> CollectionRead:
    """
    Update a user's collection by id.
    """
    try:
        res = await user_db.execute(
            select(Collection).where(
                Collection.collection_id == collection_id,
                Collection.user_id == user_id,
            )
        )
        collection = res.scalar_one_or_none()
        if collection is None:
            raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

        update_fields = payload.model_dump(exclude_unset=True)

        if "collection_name" in update_fields:
            exists = await user_db.execute(
                select(Collection.collection_id).where(
                    Collection.user_id == user_id,
                    Collection.collection_name == update_fields["collection_name"],
                    Collection.collection_id != collection_id,
                )
            )
            if exists.scalar_one_or_none() is not None:
                raise ConflictError(code="COLLECTION_NAME_CONFLICT", message="A collection with this name already exists.")

        for k, v in update_fields.items():
            setattr(collection, k, v)

        await user_db.commit()
        await user_db.refresh(collection)

        await invalidate_collection_recommendations(user_id, collection_id)

        return CollectionRead.model_validate(collection)

    except IntegrityError:
        await user_db.rollback()
        raise ConflictError(code="COLLECTION_NAME_CONFLICT", message="A collection with this name already exists.")

    except Exception:
        await user_db.rollback()
        raise


async def delete_user_collection(
    *,
    user_id,
    collection_id: int,
    user_db: ClientWriteDatabase,
) -> dict:
    """
    Delete a user's collection by id.
    """
    try:
        res = await user_db.execute(
            select(Collection).where(
                Collection.collection_id == collection_id,
                Collection.user_id == user_id,
            )
        )
        collection = res.scalar_one_or_none()
        if collection is None:
            raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

        await user_db.delete(collection)
        await user_db.commit()

        await invalidate_collection_recommendations(user_id, collection_id)

        return {"collection_id": collection_id}

    except Exception:
        await user_db.rollback()
        raise


async def get_collection_manga_page(
    *,
    user_id,
    collection_id: int,
    page: int,
    size: int,
    order: Literal["asc", "desc"],
    user_db: ClientReadDatabase,
    manga_db: ClientReadDatabase,
) -> dict:
    """
    Return paginated MangaListItem objects for a user's collection.
    """
    offset = (page - 1) * size

    owned = await get_owned_collection_id(user_db, user_id=user_id, collection_id=collection_id)
    if owned is None:
        raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

    total = await count_collection_manga(user_db, collection_id=collection_id)

    manga_ids = await page_collection_manga_ids(
        user_db,
        collection_id=collection_id,
        offset=offset,
        limit=size,
        order=order,
    )

    if not manga_ids:
        return {"total_results": total, "page": page, "size": size, "items": []}

    base_by_id = await fetch_manga_list_base(manga_db, manga_ids=manga_ids)
    await attach_genres_to_base(manga_db, manga_ids=manga_ids, base_by_id=base_by_id)

    ordered_payloads = [base_by_id[mid] for mid in manga_ids if mid in base_by_id]
    items = [MangaListItem.model_validate(p) for p in ordered_payloads]

    return {"total_results": total, "page": page, "size": size, "items": items}


async def add_manga_to_user_collection(
    *,
    user_id,
    collection_id: int,
    manga_id: int,
    user_db: ClientWriteDatabase,
) -> dict:
    """
    Add a manga to a user's collection.
    """
    await user_db.add_manga_to_collection(user_id, collection_id, manga_id)
    await invalidate_collection_recommendations(user_id, collection_id)
    return {"collection_id": collection_id, "manga_id": manga_id}


async def remove_manga_from_user_collection(
    *,
    user_id,
    collection_id: int,
    manga_id: int,
    user_db: ClientWriteDatabase,
) -> dict:
    """
    Remove a manga from a user's collection.
    """
    await user_db.remove_manga_from_collection(user_id, collection_id, manga_id)
    await invalidate_collection_recommendations(user_id, collection_id)
    return {"collection_id": collection_id, "manga_id": manga_id}