import psycopg2
from psycopg2 import sql
import os

class database_manager():
    '''
    Class that acts as a foundation for Database interaction via Python Scripts.\n
    Enables one to connect to the database and conduct interactions such as:\n
    inputting data, update data, delete data, and execute custom queries with data.\n
    When initialized, will automatically attempt to connect to the database described in the environment.\n
    '''

    def __init__(self):
        '''
        Initalization method of the database_manager class. Calls the _initalizae_database_connection() method to initalize connection.
        This creates and intializes the following varaibles based on the environment:\n
        -self.dbname
        -self.user
        -self.host
        -self.port
        -self.connection

        Arguments:
            self
        
        Returns:
            Creates a database_manager object. Each object has a database name, username, password, host address, port number, and a conneciton variable.
        
        '''
        self.dbname =   os.getenv("DB_NAME")
        self.user =     os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.host =     os.getenv("DB_HOST", "localhost")
        self.port =     os.getenv("DB_PORT", "5432")
        self.connection = self._initalize_database_connection()
    
    def _initalize_database_connection(self):
        '''
        Method to create a database connection to the PostgreSQL server defined in the environment.
        '''
        try:
            connection = psycopg2.connect(
                dbname = self.dbname,
                user = self.user,
                password = self.password,
                host = self.host,
                port = self.port,
            )
            print("Successfully Established Connection to Database")
            return connection
        except Exception as e:
            print("Failed To Connect to Database: {e}")
            return None
        
    def change_connection(self, db_name, db_user, db_password, db_host, db_port):
        '''
        Forcefully change a connection to another database based on the given parameters.
        Respectfully, I dont even know why this is here but I thought why not. This is probably stupid and a vulnerability.
        '''
        try:
            connection = psycopg2.connect(
                dbname = db_name,
                user = db_user,
                password = db_password,
                host = db_host,
                port = db_port
            )
            print("Successfully Established Database Connection")
            self.connection = connection
            self.dbname = db_name
            self.user = db_user
            self.password = db_password
            self.host = db_host
            self.port = db_port
        except Exception as e:
            print("Failed To Connect to Database: {e}")
            return None

    def reset_connection(self):
        '''
        Method to force re-initalize the database connection from outside the module.
        '''
        new_connection = self._initalize_database_connection()
        if new_connection:
            self.connection = new_connection
        else:
            print("Failed to reset the database connection.")
        
    def close_connection(self):
        '''
        Close the connection to the database.
        '''
        if self.connection:
            self.connection.close()
            print("Database Connection Closed")

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
                placeholders=sql.SQL(', ').join(sql.Placeholder() for _ in columns)
            )

            return query, tuple(data.values())   
        
        except Exception as e:
            print(f"Error building Insert Query: {e}")
            return None, ()

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
            print(f"Error building Update Query: {e}")
            return None, ()

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
            print(f"Error building delete query: {e}")
            return None, ()


    def execute_query(self, query, params):
        '''
        method to execute a custom query.
        '''

        if not self.connection:
            print(f"Database connection not established!")
            return False

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return True

        except psycopg2.Error as e:
            print(f"Database error during execution: {e}")
            self.connection.rollback()
            return False

        except Exception as e:
            print(f"Unexpected error during query execution: {e}")
            self.connection.rollback()
            return False


    def input_data(self, data, table):
        '''
        Method to facilitate inputting data into a specified table for the connected postgresql database.
        '''

        query, params = self._build_insert_query(table, data)
        if not query:
            print("Failed to build insert query.")
            return False
        return self.execute_query(query, params)

    def modify_data(self, data, table, condition):
        '''
        Method to facilitate modifying data in a specified table for the connected postgresql database.
        '''

        query, params = self._build_update_query(table, data, condition)
        if not query:
            print("Failed to build update query.")
            return False
        return self.execute_query(query, params)

    def remove_data(self, table, condition):
        '''
        Method to facilitate removing data from a specified table for the connected postgresql database.
        '''
        
        query, params = self._build_delete_query(table, condition)
        if not query:
            print("Failed to build delete query.")
            return False
        return self.execute_query(query, params)