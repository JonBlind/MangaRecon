import psycopg2
from psycopg2 import sql
import os

class database_manager():
    def __init__(self):
        self.dbname =   os.getenv("DB_NAME")
        self.user =     os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.host =     os.getenv("DB_HOST", "localhost")
        self.port =     os.getenv("DB_PORT", "5432")
        self.connection = self.initalize_database_connection()
    
    def _initalize_database_connection(self):
        try:
            connection = psycopg2.connect(
                dbname = self.dbname,
                user = self.user,
                password = self.password,
                host = self.host,
                port = self.port,
            )
            print("Successfully Established Connection to DataBase")
            return connection
        except Exception as e:
            print("Failed To Connect to Database: {e}")
            return None
        
    def change_connection(self, db_name, db_user, db_password, db_host, db_port):
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
        new_connection = self._initalize_database_connection()
        if new_connection:
            self.connection = new_connection
        else:
            print("Failed to reset the database connection.")
        
    def close_connection(self):
        if self.connection:
            self.connection.close()
            print("Database Connection Closed")

    def _build_insert_query(self, table, data):

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

        query, params = self._build_insert_query(table, data)
        if not query:
            print("Failed to build insert query.")
            return False
        return self.execute_query(query, params)

    def modify_data(self, data, table, condition):

        query, params = self._build_update_query(table, data, condition)
        if not query:
            print("Failed to build update query.")
            return False
        return self.execute_query(query, params)

    def remove_data(self, table, condition):
        
        query, params = self._build_delete_query(table, condition)
        if not query:
            print("Failed to build delete query.")
            return False
        return self.execute_query(query, params)