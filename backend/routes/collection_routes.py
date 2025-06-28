from fastapi import APIRouter, Depends
from sqlalchemy.future import select
from backend.db.client_db import ClientDatabase
from backend.db.models.user import User
from backend.db.models.collection import Collection
from backend.dependencies import get_user_write_db, get_user_read_db
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
)
from utils.response import success, error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])

@router.get("/", response_model=dict)
async def get_users_collection(
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    try:
        logger.info(f"Fetching all collections of {user.id}")
        result = await db.session.execute(
            select(Collection).where(Collection.user_id == user.id)
        )

        collections = result.scalars().all()
        validated = [CollectionRead.model_validate(c) for c in collections]

        return success("Collections Successfully Retrieved", data=validated)
    
    except Exception as e:
        logger.error(f"Failed to Fetch all collections of {user.id}: {e}")
        return error("Failed to retrieve collections", detail=str(e))
    

@router.get("/{collection_id}", response_class=dict)
async def get_collection_by_id(
    collection_id: int,
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    try:
        logger.info(f"Fetching Collection_id: {collection_id} for user: {user.id}")
        result = await db.session.execute(
            select(Collection).where(Collection.collection_id == collection_id, Collection.user_id == user.id)
        )
        collection = result.scalar_one_or_none()
        validated = CollectionRead.model_validate(collection)

        if not collection:
            return error("Collection Not Found", detail=f"No Collection found with the ID: {collection_id}")
        
        return success("Collection retrieved successfully", data=validated)
    
    except Exception as e:
        logger.error(f"Failed to fetch collection {collection_id} for user {user.id}: {e}")
        return error("Failed to retrieve collection", detail=str(e))
    
@router.post("/", response_model=dict)
async def create_collection(
    collection_data: CollectionCreate,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        logger.info(f"Creating New Collection for user: {user.id} with title: {collection_data.collection_name}")
        new_collection = Collection(user_id=user.id, collection_name = collection_data.collection_name, description=collection_data.description)
        db.session.add(new_collection)
        await db.session.commit()
        await db.session.refresh(new_collection)
        
        validated = CollectionRead.model_validate(new_collection)

        return success("Collection Created Successfully", data=validated)
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to create collection: {e}")
        return error("Failed To Create Collection", detail=str(e))
    
@router.put("/{collection_id}", response_class=dict)
async def update_collection(
    collection_id: int,
    collection_update: CollectionUpdate,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        result = await db.session.execute(
            select(Collection).where(Collection.collection_id == collection_id, Collection.user_id == user.id))
        
        collection = result.scalar_one_or_none()

        if not collection:
            return error("Collection not found", detail="Cannot locate collection or improper user permissions.")

        for field, value in collection_update.model_dump(exclude_unset=True).items():
            setattr(collection, field, value)

        await db.session.commit()
        await db.session.refresh(collection)

        validated = CollectionRead.model_validate(collection)

        return success("Collection updated successfully", validated)
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to update collection {collection_id}: {e}")
        return error("Failed to update collection", str(e))
    
# I ideally would want to give this to a role that isn't write. But that might be pushed off to the future since It's too much multitasking currently for a solo work.
@router.delete("/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: int,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        result = await db.session.execute(
            select(Collection).where(Collection.collection_id == collection_id,Collection.user_id == user.id))
        
        collection = result.scalar_one_or_none()

        if not collection:
            return error("Collection not found", detail="Cannot locate collection or improper user permissions.")

        await db.session.delete(collection)
        await db.session.commit()

        return success("Collection deleted successfully", data={"collection_id": collection_id})
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to delete collection {collection_id}: {e}")
        return error("Failed to delete collection", str(e))