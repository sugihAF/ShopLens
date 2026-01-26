"""SQLAlchemy declarative base class."""

import uuid as uuid_module
import json

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator, Text, CHAR
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID


class JSONB(TypeDecorator):
    """
    Platform-agnostic JSONB type.

    Uses JSONB on PostgreSQL and Text with JSON serialization on other databases.
    This allows tests to run with SQLite while production uses PostgreSQL JSONB.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is not None:
            if dialect.name != 'postgresql':
                return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if dialect.name != 'postgresql' and isinstance(value, str):
                return json.loads(value)
        return value


class UUID(TypeDecorator):
    """
    Platform-agnostic UUID type.

    Uses native UUID on PostgreSQL and CHAR(36) on other databases.
    This allows tests to run with SQLite while production uses PostgreSQL UUID.
    """
    impl = CHAR(36)
    cache_ok = True

    def __init__(self, as_uuid: bool = True):
        super().__init__()
        self.as_uuid = as_uuid

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is not None:
            if dialect.name != 'postgresql':
                if isinstance(value, uuid_module.UUID):
                    return str(value)
                return value
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if dialect.name != 'postgresql' and self.as_uuid:
                if isinstance(value, str):
                    return uuid_module.UUID(value)
        return value


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass
