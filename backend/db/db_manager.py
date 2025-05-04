import asyncpg
import asyncio
import os
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager():
    '''
    Class that acts as a foundation for Database interaction via Python Scripts.
    Enables one to connect to the database and conduct interactions such as:
    inputting data, update data, delete data, and execute custom queries with data.
    When initialized, will automatically attempt to connect to the database described in the environment.
    Utilizes asyncpg.

    Not to be used by the actual user, only admin/owner use.
    '''

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None


    async def connect(self, attempt_limit:int = 10, retry_delay:float = 3.0):
        """
        Initializes the connection pool.

        Args:
            attempt_limit (int, optional): Number of times to attempt a connection, default is 10 times. Does not accept Values over 50.
            retry_delay   (float, optional): Time in seconds to wait between connection attempts.

        Raises:
            ValueError: If attempt_limit is greater than 50.

        Returns:
            None
        """
        if attempt_limit > 50:
            raise ValueError(f"Attempt Limit Exceed Maximum Attempts Allowed! ({attempt_limit} > 50)")
        
        if self.pool:
            logger.error("Connection already exists!")
            return
        
        attempts = 0
        while(attempts < attempt_limit):
            try:
                self.pool = await asyncpg.create_pool(dsn=self.db_url, max_size=50)
                logger.info("Database Connection Pool Established")
                return
            except Exception as e:
                attempts += 1
                logger.error(f"Connection attempt {attempts} failed: {e}")

                if attempts < attempt_limit:
                    await asyncio.sleep(retry_delay)

        logger.error("Failed to initialize Database Connection Pool after max attempts")

    async def disconnect(self):
        """
        Closes the connection pool.

        Returns:
            None
        """
        if self.pool:
            try:
                await self.pool.close()
                self.pool = None
                logger.info("Database Connection Pool Closed!")
            except Exception as e:
                logger.error(f"Connection Failed to Close: {e}")
        else:
            logger.warning("No Connection Open to Close!")

    def _validate_table_name(self, table: str) -> bool:
        """
        Prevents SQL Injection via table names.

        Args:
            table (str): Table name.

        Returns:
            bool: True if table name is valid, False otherwise.
        """
        return table.isidentifier()

    async def execute(self, query: str, *args):
        """
        Executes a query (INSERT, UPDATE, DELETE).

        Args:
            query (str): SQL query string WITH PLACEHOLDERS, ($1, $2, etc.).
            *args: values to substitute into the query placeholders. (SO THE ACTUAL VALUES YOU WANT TO INPUT)

        Returns:
            str or None: Command completion string returns if successful; otherwise, will return None if it fails.
        """
        if not self.pool:
            logger.error("No Database Connection Found!")
            return
        
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    result = await connection.execute(query, *args)
                    logger.info(f"Query Successful: {result}")
                    return result
        except Exception as e:
            logger.error(f"Failed to perform 'execute'!: {e}")
            return None

    
    async def fetch(self, query: str, *args) -> List[dict]:
        """
        Executes a SELECT query and returns results as a list of dictionaries.
        """
        if not self.pool:
            logger.error("No Database Connection Found!")
            return None
        
        try:
            async with self.pool.acquire() as connection:
                results = await connection.fetch(query, *args)
                logger.info(f"Query Successful: {results}")
                return [dict(record) for record in results]
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return None
        

    async def input_data(self, table: str, data: Dict[str, Any]):
        """
        Inserts data into the specified table.

        Args:
            table (str): String matching the name of the table to input data into
            data (dict): Dictionary of data, where the key is the column name, and the value is the corresponding value to input.

        Returns:
            bool: True if the query is successful, False otherwise.
        """
        if not self._validate_table_name(table):
            logger.error(f"Invalid table name: {table}")
            return

        columns = ", ".join(data.keys())
        values_placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        query = f"INSERT INTO {table} ({columns}) VALUES ({values_placeholders})"
        result = await self.execute(query, *data.values())
        return (result is not None)

    async def modify_data(self, table: str, data: Dict[str, Any], condition: str, params: List[Any]):
        '''
        Modify existing data in the postgres table.
        A Placeholeder is a dollar sign + number. The number must match the placement of the corresponding param in the list PLUS how much data is passed.

        Args:
            table (str): String matching the name of the table to update data
            data (dict): Dictionary of data, where the key is the column name, and the value is the corresponding value to input.
            condition (str): WHERE clause, condition, WITH PLACEHOLDERS, defining which rows to directly update.
            params (List[Any]): List of values that correspond to the placeholders in the WHERE clause.

        Returns:
            bool: True if the query is successful, False otherwise.
        '''
        if not self._validate_table_name(table):
            logger.error(f"Invalid table name: {table}")
            return

        set_clause = ", ".join(f"{col} = ${i+1}" for i, col in enumerate(data.keys()))
        query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        result = await self.execute(query, *data.values(), *params)
        return (result is not None)

    async def remove_data(self, table: str, condition: str, params: List[Any]):
        '''
        Remove data using 'DELETE' based on the specific conditions.
        A Placeholeder is a dollar sign + number. The number must match the placement of the corresponding param in the list PLUS how much data is passed.

        Args:
            table (str): String matching the name of the table to remove data from
            condition (str): WHERE clause, condition, WITH PLACEHOLDERS, defining which rows to delete.
            params (List[Any]): List of values that correspond to the placeholders in the WHERE clause.

        Returns:
            bool: True if the query is successful, False otherwise.

        '''
        if not self._validate_table_name(table):
            logger.error(f"Invalid table name: {table}")
            return

        query = f"DELETE FROM {table} WHERE {condition}"
        result = await self.execute(query, *params)
        return (result is not None)
