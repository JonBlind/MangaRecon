import redis.asyncio as redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

class RedisCache:
    def __init__(self, host=None, port=None, db=None, ttl=600):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT"))
        self.db = db or int(os.getenv("REDIS_DB"))
        self.ttl = ttl
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True
        )

    async def set(self, key: str, value: dict, ttl: int = None):
        try:
            await self.client.setex(key, ttl or self.ttl, json.dumps(value))
        except Exception as e:
            print(f"Redis SET error for {key}: {e}")

    async def get(self, key: str):
        try:
            result = await self.client.get(key)
            return json.loads(result) if result else None
        except Exception as e:
            print(f"Redis GET error for {key}: {e}")
            return None

    async def delete(self, key: str):
        try:
            await self.client.delete(key)
        except Exception as e:
            print(f"Redis DELETE error for {key}: {e}")

redis_cache = RedisCache()