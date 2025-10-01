'''
Declarative base for SQLAlchemy ORM models.

All tables should inherit from `Base`.
'''

from sqlalchemy.orm import declarative_base

Base = declarative_base()