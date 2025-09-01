from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.cache.invalidation import invalidate_collection_recommendations
from backend.db.client_db import ClientDatabase
from backend.db.models.user import User
from backend.db.models.collection import Collection
from backend.db.models.manga import Manga
from backend.db.models.manga_collection import MangaCollection
from backend.dependencies import get_user_write_db, get_user_read_db
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
    MangaInCollectionRequest
)
from backend.schemas.manga import MangaListItem
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])

@router.get("/", response_model=dict)
@limiter.limit("120/minute")    
async def get_users_collection(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user),
):
    try:
        logger.info(f"Fetching collections of {user.id} page={page} size={size}")
        offset = (page - 1) * size

        base = select(Collection).where(Collection.user_id == user.id)

        count_stmt = base.with_only_columns(func.count(Collection.collection_id)).order_by(None)
        total = (await db.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Collection.collection_id.desc()).offset(offset).limit(size)
        result = await db.session.execute(stmt)
        collections = result.scalars().all()

        validated = [CollectionRead.model_validate(c) for c in collections]
        return success("Collections retrieved", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": validated
        })
    except Exception as e:
        logger.error(f"Failed to fetch collections of {user.id}: {e}", exc_info=True)
        return error("Failed to retrieve collections", detail=str(e))
    

@router.get("/{collection_id}", response_model=dict)
@limiter.limit("120/minute")  
async def get_collection_by_id(
    request: Request,
    collection_id: int,
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    try:
        logger.info(f"Fetching Collection_id: {collection_id} for user: {user.id}")
        result = await db.session.execute(
            select(Collection).where(Collection.collection_id == collection_id, 
                                     Collection.user_id == user.id))
        collection = result.scalar_one_or_none()

        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        
        validated = CollectionRead.model_validate(collection)
        
        return success("Collection retrieved successfully", data=validated)
    except Exception as e:
        logger.error(f"Failed to fetch collection {collection_id} for user {user.id}: {e}")
        return error("Failed to retrieve collection", detail=str(e))
    
@router.post("/", response_model=dict)
@limiter.limit("60/minute")   
async def create_collection(
    request: Request,
    collection_data: CollectionCreate,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        exists = await db.session.execute(
            select(Collection.collection_id).where(Collection.user_id == user.id, 
                                                   Collection.collection_name == collection_data.collection_name))
        
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")
        
        logger.info(f"Creating New Collection for user: {user.id} with title: {collection_data.collection_name}")
        new_collection = Collection(user_id=user.id, collection_name = collection_data.collection_name, description=collection_data.description)
        db.session.add(new_collection)
        await db.session.commit()
        await db.session.refresh(new_collection)
        
        validated = CollectionRead.model_validate(new_collection)

        return success("Collection Created Successfully", data=validated)
    
    except IntegrityError:
        await db.session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to create collection: {e}")
        return error("Failed To Create Collection", detail=str(e))
    
@router.put("/{collection_id}", response_model=dict)
@limiter.limit("60/minute")
async def update_collection(
    request: Request,
    collection_id: int,
    collection_update: CollectionUpdate,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        result = await db.session.execute(
            select(Collection).where(Collection.collection_id == collection_id, 
                                     Collection.user_id == user.id))
        
        collection = result.scalar_one_or_none()

        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        
        update_fields = collection_update.model_dump(exclude_unset=True)

        if "collection_name" in update_fields:
            exists = await db.session.execute(
                select(Collection.collection_id).where(
                    Collection.user_id == user.id,
                    Collection.collection_name == update_fields["collection_name"],
                    Collection.collection_id != collection_id))
            
            if exists.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")

        for field, value in update_fields.items():
            setattr(collection, field, value)

        await db.session.commit()
        await db.session.refresh(collection)

        # Remove cache since old data will interfere with new actions
        await invalidate_collection_recommendations(user.id, collection_id)

        validated = CollectionRead.model_validate(collection)

        return success("Collection updated successfully", data=validated)
    
    except IntegrityError:
        await db.session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to update collection {collection_id}: {e}")
        return error("Failed to update collection", detail=str(e))
    
# I ideally would want to give this to a role that isn't write. But that might be pushed off to the future since It's too much multitasking currently for a solo work.
@router.delete("/{collection_id}", response_model=dict)
@limiter.limit("60/minute")
async def delete_collection(
    request: Request,
    collection_id: int,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        result = await db.session.execute(
            select(Collection).where(Collection.collection_id == collection_id,Collection.user_id == user.id))
        
        collection = result.scalar_one_or_none()

        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        await db.session.delete(collection)
        await db.session.commit()
        await invalidate_collection_recommendations(user.id, collection_id)

        return success("Collection deleted successfully", data={"collection_id": collection_id})
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to delete collection {collection_id}: {e}")
        return error("Failed to delete collection", detail=str(e))
    
@router.get("/{collection_id}/mangas", response_model=dict)
@limiter.shared_limit("120/minute", scope="collections-read-ip-min")
@limiter.shared_limit("3000/hour", scope="collections-read-ip-hour")
async def get_manga_in_collection(
    request: Request,
    collection_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    """
    Paginated manga from a user-owned collection.
    """
    try:
        logger.info(f"User {user.id} fetching manga from collection {collection_id} page={page} size={size}")
        offset = (page - 1) * size

        # ownership check (fast fail)
        exists_q = await db.session.execute(
            select(Collection.collection_id).where(
                Collection.collection_id == collection_id,
                Collection.user_id == user.id
            )
        )
        if exists_q.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        base = (
            select(Manga)
            .join(MangaCollection, MangaCollection.manga_id == Manga.manga_id)
            .where(MangaCollection.collection_id == collection_id)
        )

        count_stmt = base.with_only_columns(func.count(Manga.manga_id)).order_by(None)
        total = (await db.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Manga.manga_id.desc()).offset(offset).limit(size)
        result = await db.session.execute(stmt)
        manga_list = result.scalars().all()

        items = [MangaListItem.model_validate(m) for m in manga_list]
        return success("Manga retrieved successfully", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": items
        })

    except Exception as e:
        logger.error(f"Failed to retrieve manga from collection {collection_id}: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.delete("/{collection_id}/mangas", response_model=dict)
@limiter.limit("60/minute") 
async def remove_manga_from_collection(
    request: Request,
    collection_id: int,
    data: MangaInCollectionRequest,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    '''
    Remove a manga from a collection owned by the user.

    Args:
        collection_id (int): ID of the collection to remove from
        manga_id (int): ID of the manga to remove (via request body)

    Returns:
        dict: Success or error response
    '''
    try:
        logger.info(f"User {user.id} attempting to remove manga {data.manga_id} from collection {collection_id}")

        await db.remove_manga_from_collection(user.id, collection_id, data.manga_id)

        # Remove cache since state of collection is now diff.
        await invalidate_collection_recommendations(user.id, collection_id)

        logger.info(f"Successfully removed manga {data.manga_id} from collection {collection_id}")
        return success("Manga removed from collection", data={"collection_id": collection_id, "manga_id": data.manga_id})

    except ValueError as ve:
        logger.warning(f"Remove failed for collection {collection_id}: {ve}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    except Exception as e:
        logger.error(f"Failed to remove manga {data.manga_id} from collection {collection_id}: {e}", exc_info=True)
        return error("Failed to remove manga from collection", detail=str(e))

@router.post("/{collection_id}/mangas", response_model=dict)
@limiter.limit("60/minute")      
async def add_manga_to_collection(
    request: Request,
    collection_id: int,
    data: MangaInCollectionRequest,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    """
    Add a manga to a collection owned by the user.

    Args:
        collection_id (int): ID of the collection to add to
        manga_id (int): ID of the manga to add (via request body)

    Returns:
        dict: Success or error response
    """
    try:
        logger.info(f"User {user.id} attempting to add manga {data.manga_id} to collection {collection_id}")

        # Add manga to collection
        await db.add_manga_to_collection(user.id, collection_id, data.manga_id)

        # Delete any cache_version since collection is now different.
        await invalidate_collection_recommendations(user.id, collection_id)

        logger.info(f"Successfully added manga {data.manga_id} to collection {collection_id}")
        return success("Manga added to collection", data={"collection_id": collection_id, "manga_id": data.manga_id})

    except ValueError as ve:
        logger.warning(f"Add failed for collection {collection_id}: {ve}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    
    except Exception as e:
        logger.error(f"Failed to add manga {data.manga_id} to collection {collection_id}: {e}", exc_info=True)
        return error("Failed to add manga to collection", detail=str(e))