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
        self.connection = self.initalize_database_connection
    
    def initalize_database_connection(self):
        try:
            connection = psycopg2.connect(
                DATABASE_NAME = self.dbname,
                DATABASE_USER = self.user,
                DATABASE_PASSWORD = self.password,
                DATABASE_HOST = self.host,
                DATABASE_PORT = self.port,
            )
            print("Successfully Established Connection to DataBase")
            return connection
        except Exception as e:
            print("Failed To Connect to Database: {e}")
            return None
        
    def change_connection(self, db_name, user, password, host, port):
        try:
            connection = psycopg2.connect(
                DATABASE_NAME = db_name,
                DATABASE_USER = user,
                DATABASE_PASSWORD = password,
                DATABASE_HOST = port,
                DATABASE_PORT = host
            )
            print("Successfully Established Database Connection")
            self.connection = connection
        except Exception as e:
            print("Failed To Connect to Database: {e}")
            return None
        
    def close_connection(self):
        if self.connection:
            self.connection.close()
            print("Database Connection Closed")

