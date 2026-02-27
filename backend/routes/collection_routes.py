'''
FastAPI routes for CRUD operations over user-owned collections.

Endpoints include list/create/update/delete, and membership management for manga
(add/remove). All handlers enforce ownership via the authenticated user.
'''

from typing import Literal
import logging

from fastapi import APIRouter, Depends, Query, Request
from backend.auth.dependencies import current_active_user as current_user
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.db.models.user import User
from backend.dependencies import (
    get_user_read_db,
    get_user_write_db,
    get_manga_read_db,
)
from backend.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
    MangaInCollectionRequest,
)
from backend.services.collection_service import (
    list_user_collections_page,
    get_user_collection_by_id,
    create_user_collection,
    update_user_collection,
    delete_user_collection,
    get_collection_manga_page,
    add_manga_to_user_collection,
    remove_manga_from_user_collection,
)
from backend.utils.rate_limit import limiter
from backend.utils.response import success


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=dict)
@limiter.limit("120/minute")
async def get_users_collection(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    order: Literal["asc", "desc"] = Query("desc"),
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user),
):
    '''
    List the current user's collections (paginated).

    Args:
        request (Request): FastAPI request (required by rate limiting).
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        order (str): Sort order for collection_id ("asc" or "desc").
        user_db (ClientDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' containing total_results, page, size, and items (CollectionRead).
    '''
    try:
        data = await list_user_collections_page(
            user_id=user.id,
            page=page,
            size=size,
            order=order,
            user_db=db,
        )
        return success("Collections retrieved", data=data)

    except Exception as e:
        logger.error("Failed to fetch collections for user %s: %s", user.id, e, exc_info=True)
        raise


@router.get("/{collection_id}", response_model=dict)
@limiter.limit("120/minute")
async def get_collection_by_id(
    request: Request,
    collection_id: int,
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user),
):
    '''
    Retrieve a single collection by ID for the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier.
        user_db (ClientDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' with the collection (CollectionRead), or 404 if not found/owned.
    '''
    try:
        data = await get_user_collection_by_id(
            user_id=user.id,
            collection_id=collection_id,
            user_db=db,
        )
        return success("Collection retrieved successfully", data=data)

    except Exception as e:
        logger.error("Failed to fetch collection %s for user %s: %s", collection_id, user.id, e, exc_info=True)
        raise


@router.post("", response_model=dict)
@limiter.limit("60/minute")
async def create_collection(
    request: Request,
    collection_data: CollectionCreate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    '''
    Create a new collection owned by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_data (CollectionCreate): New collection payload.
        user_db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' with the created collection (CollectionRead).
    '''
    try:
        data = await create_user_collection(
            user_id=user.id,
            payload=collection_data,
            user_db=db,
        )
        return success("Collection created successfully", data=data)

    except Exception as e:
        logger.error("Failed to create collection for user %s: %s", user.id, e, exc_info=True)
        raise


@router.put("/{collection_id}", response_model=dict)
@limiter.limit("60/minute")
async def update_collection(
    request: Request,
    collection_id: int,
    collection_update: CollectionUpdate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    '''
    Update a collection's attributes (name/description).

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier to update.
        collection_update (CollectionUpdate): Patch payload.
        user_db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' with the updated collection (CollectionRead).
    '''
    try:
        data = await update_user_collection(
            user_id=user.id,
            collection_id=collection_id,
            payload=collection_update,
            user_db=db,
        )
        return success("Collection updated successfully", data=data)

    except Exception as e:
        logger.error("Failed to update collection %s for user %s: %s", collection_id, user.id, e, exc_info=True)
        raise


@router.delete("/{collection_id}", response_model=dict)
@limiter.limit("60/minute")
async def delete_collection(
    request: Request,
    collection_id: int,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    '''
    Delete a collection owned by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier to delete.
        user_db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' with the deleted collection_id.
    '''
    try:
        data = await delete_user_collection(
            user_id=user.id,
            collection_id=collection_id,
            user_db=db,
        )
        return success("Collection deleted successfully", data=data)

    except Exception as e:
        logger.error("Failed to delete collection %s for user %s: %s", collection_id, user.id, e, exc_info=True)
        raise


@router.get("/{collection_id}/mangas", response_model=dict)
@limiter.shared_limit("120/minute", scope="collections-read-ip-min")
@limiter.shared_limit("3000/hour", scope="collections-read-ip-hour")
async def get_manga_in_collection(
    request: Request,
    collection_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    order: Literal["asc", "desc"] = Query("desc"),
    user_db: ClientReadDatabase = Depends(get_user_read_db),
    manga_db: ClientReadDatabase = Depends(get_manga_read_db),
    user: User = Depends(current_user),
):
    '''
    List manga in a specified collection (paginated).

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier.
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        order (str): Sort order for manga_id ("asc" or "desc").
        user_db (ClientDatabase): User-domain read database client.
        manga_db (ClientDatabase): Manga-domain read database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' containing total_results, page, size, and items (MangaListItem).
    '''
    try:
        data = await get_collection_manga_page(
            user_id=user.id,
            collection_id=collection_id,
            page=page,
            size=size,
            order=order,
            user_db=user_db,
            manga_db=manga_db,
        )
        return success("Manga retrieved successfully", data=data)

    except Exception as e:
        logger.error("Failed to retrieve manga from collection %s: %s", collection_id, e, exc_info=True)
        raise


@router.post("/{collection_id}/mangas", response_model=dict)
@limiter.limit("60/minute")
async def add_manga_to_collection(
    request: Request,
    collection_id: int,
    data: MangaInCollectionRequest,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    '''
    Add a manga to a collection owned by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier to add to.
        data (MangaInCollectionRequest): Payload containing the manga ID to add.
        user_db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized 'Response' with the added manga_id and collection_id.
    '''
    try:
        out = await add_manga_to_user_collection(
            user_id=user.id,
            collection_id=collection_id,
            manga_id=data.manga_id,
            user_db=db,
        )
        return success("Manga added to collection", data=out)

    except Exception as e:
        logger.error(
            "Failed to add manga %s to collection %s for user %s: %s",
            data.manga_id,
            collection_id,
            user.id,
            e,
            exc_info=True,
        )
        raise


@router.delete("/{collection_id}/mangas", response_model=dict)
@limiter.limit("60/minute")
async def remove_manga_from_collection(
    request: Request,
    collection_id: int,
    data: MangaInCollectionRequest,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    '''
    Remove a manga from a collection owned by the current user.
    
    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier to remove from.
        data (MangaInCollectionRequest): Payload containing the manga ID to remove.
        user_db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.
    
    Returns:
       dict: Standardized 'Response' with the removed manga_id and collection_id.
    '''
    try:
        out = await remove_manga_from_user_collection(
            user_id=user.id,
            collection_id=collection_id,
            manga_id=data.manga_id,
            user_db=db,
        )
        return success("Manga removed from collection", data=out)

    except Exception as e:
        logger.error(
            "Failed to remove manga %s from collection %s for user %s: %s",
            data.manga_id,
            collection_id,
            user.id,
            e,
            exc_info=True,
        )
        raise