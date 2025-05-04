from backend.db.db_manager import DatabaseManager
import os
import asyncio

# Success
def test_connection():
    db = DatabaseManager(os.getenv('DATABASE_URL_TEST'))
    asyncio.run(db.connect())

# Success
async def test_disconnect():
    db = DatabaseManager(os.getenv('DATABASE_URL_TEST'))
    await db.connect()
    await db.disconnect()

# Success
async def test_input_data():
    db = DatabaseManager(os.getenv('DATABASE_URL_TEST'))
    await db.connect()
    await db.input_data(table="profile", data={"username": "biguy", "displayname": "notBigGuy", "email" : "thatbigguuy@aol.com", "password_hash" : "SuperSecurePassword"})

# Success
async def test_modify_data():
    db = DatabaseManager(os.getenv('DATABASE_URL_TEST'))
    await db.connect()
    await db.modify_data(table="profile", data={"username": "updated_bigguy", "email": "notsosecureanymore@garbage.com"}, condition="username = $3", params=["biguy"])

# Success
async def test_fetch_data():
    db = DatabaseManager(os.getenv('DATABASE_URL_TEST'))
    await db.connect()
    await db.fetch("SELECT username, email FROM profile WHERE username = $1", "updated_bigguy")

# Success
async def test_remove_data():
    db = DatabaseManager(os.getenv('DATABASE_URL_TEST'))
    await db.connect()
    await db.remove_data(table="profile", condition="username = $1", params=["updated_bigguy"])

#asyncio.run(test_connection())
#asyncio.run(test_disconnect())
#asyncio.run(test_input_data())
#asyncio.run(test_modify_data())
#asyncio.run(test_fetch_data())
#asyncio.run(test_remove_data())