import psycopg2
from psycopg2 import sql
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



class DatabaseManager():
    '''
    Class that acts as a foundation for Database interaction via Python Scripts.\n
    Enables one to connect to the database and conduct interactions such as:\n
    inputting data, update data, delete data, and execute custom queries with data.\n
    When initialized, will automatically attempt to connect to the database described in the environment.\n
    '''

    def __init__(self, db_name, db_user, db_password, db_host, db_port):
        '''
        Initalization method of the database_manager class. Calls the _initalizae_database_connection() method to initalize connection.
        This creates and intializes the following variables based on the environment:\n
        -self.dbname
        -self.user
        -self.host
        -self.port
        -self.connection

        Arguments:
            self
        
        Returns:
            Creates a database_manager object. Each object has a database name, username, password, host address, port number, and a connection variable.
        
        '''
        if not all((db_name, db_user, db_password, db_host, db_port)):
            raise ValueError(f"Cannot Connect to DB w/o all Fields!")
        
        self.dbname =   db_name
        self.user =     db_user
        self.password = db_password
        self.host =     db_host
        self.port =     db_port
        self.connection = self._initialize_database_connection()
    
    def _initialize_database_connection(self, conn_limit=20):
        '''
        Method to create a database connection to the PostgreSQL server defined in the environment.
        '''
        conn_attempts = 0

        try:
            connection = psycopg2.connect(
                dbname = self.dbname,
                user = self.user,
                password = self.password,
                host = self.host,
                port = self.port,
            )
            logger.info("Successfully Established Connection to Database")
            return connection
        except psycopg2.OperationalError as err:
            conn_attempts += 1
            logger.error(f"Error Initializing Connection: {err}")
        except:
            conn_attempts += 1
            if conn_attempts > conn_limit:
                logger.error(f"Error Initializing Connection after {conn_limit} attempts!")
                raise Exception(f"Failed To Connect To DB After {conn_limit} attempts. Exiting!")
        
    def close_connection(self):
        if self.connection:
            try:
                self.connection.close()
                logger.info("Database connection closed.")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        else:
            logger.error("No connection initialized; cannot close connection.")
            raise ValueError("No connection to close.")
        
    def __del__(self):
        if self.connection:
            self.close_connection()
    
    def __exit__(self):
        if self.connection:
            self.close_connection()
            
    def reset_connection(self):
        '''
        Method to force re-initalize the database connection from outside the module.
        '''
        self.close_connection()
        new_connection = self._initialize_database_connection()
        if new_connection:
            self.connection = new_connection
            logger.info("Database connection reset successfully.")
        else:
            logger.error(f"Failed to reset the database connection!")



    def _build_insert_query(self, table, data):
        '''
        builder for the insert query
        '''
        try:
            columns = data.keys()
            placeholders = [sql.Placeholder() for _ in columns]

            query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders})").format(
                table=sql.Identifier(table),
                fields=sql.SQL(', ').join(map(sql.Identifier, columns)),
                placeholders=sql.SQL(", ").join(placeholders)
            )

            return query, tuple(data.values())   
        
        except Exception as e:
            logger.error(f"Error building INSERT Query: {e}")
            raise ValueError(f"Error building INSERT Query: {e}")

    def _build_update_query(self, table, data, condition):
        '''
        builder for the update query
        '''
        try:
            columns = data.keys()
            set_clause = [
                sql.SQL("{field} = {placeholder}").format(
                    field=sql.Identifier(column),
                    placeholder=sql.Placeholder()
                ) for column in columns
            ]

            query = sql.SQL("UPDATE {table} SET {set_clause} WHERE {condition}").format(
                table=sql.Identifier(table),
                set_clause=sql.SQL(', ').join(set_clause),
                condition=sql.SQL(condition)
            )

            return query, tuple(data.values())

        except Exception as e:
            logger.error(f"Error building UPDATE Query: {e}")
            raise ValueError(f"Error building UPDATE Query: {e}")

    def _build_delete_query(self, table, condition):
        '''
        builder for the delete query
        '''

        try:
            query = sql.SQL("DELETE FROM {table} WHERE {condition}").format(
                table=sql.Identifier(table),
                condition=sql.SQL(condition)
            )
            return query, ()

        except Exception as e:
            logger.error(f"Error building DELETE query: {e}")
            raise ValueError(f"Error building DELETE Query: {e}")


    def execute_query(self, query, params):
        '''
        method to execute a custom query.
        '''
        if not self.connection:
            logger.error(f"Database connection not established!")
            raise ConnectionError("Database connection not established.")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()

        except psycopg2.Error as e:
            logger.error(f"Database error during execution: {e}")
            self.connection.rollback()
            raise

        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            self.connection.rollback()
            raise
        
    def fetch_data(self, query, params=()):
        '''
        Method to execute a query and fetch results.
        '''
        if not self.connection:
            logger.error("Database connection not established!")
            raise ConnectionError("Database connection not established!")
    
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
            
        except psycopg2.Error as e:
            logger.error(f"Database error during fetch: {e}")
            self.connection.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error during fetch: {e}")
            self.connection.rollback()
            raise


    def input_data(self, data, table):
        '''
        Method to facilitate inputting data into a specified table for the connected postgresql database.
        '''

        query, params = self._build_insert_query(table, data)
        self.execute_query(query, params)

    def modify_data(self, data, table, condition):
        '''
        Method to facilitate modifying data in a specified table for the connected postgresql database.
        '''

        query, params = self._build_update_query(table, data, condition)
        self.execute_query(query, params)

    def remove_data(self, table, condition):
        '''
        Method to facilitate removing data from a specified table for the connected postgresql database.
        '''
        
        query, params = self._build_delete_query(table, condition)
        self.execute_query(query, params)