"""Declarative base + small async query helpers shared by every model."""

import secrets
import string
from abc import abstractmethod
from datetime import datetime
from datetime import timezone

from sqlalchemy import TIMESTAMP
from sqlalchemy import Column
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import BinaryExpression

from configs.db import DBConfig
from db import db


def _generate_random_string(string_length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(string_length))


class Base(DeclarativeBase):
    __table_args__ = {"schema": DBConfig.SCHEMA_NAME}

    def __repr__(self) -> str:
        return "%s" % (self.__dict__)

    def to_dict(self) -> dict:
        return {key: value for key, value in self.__dict__.items() if not key.startswith("_")}

    @classmethod
    async def filter_first(cls, *criterion: BinaryExpression):
        db_session = await db.get_session()
        stmt = select(cls).filter(*criterion).limit(1).offset(0)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_id(cls, model_object_id):
        db_session = await db.get_session()
        stmt = select(cls).filter(cls.id == model_object_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()


class BaseModel(Base):
    __abstract__ = True

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    async def create(cls, model_object: "BaseModel"):
        db_session = await db.get_session()
        if getattr(model_object, "id", None) is None:
            model_object.id = cls.get_id_prefix() + _generate_random_string(10)
        model_object.created_at = datetime.now(timezone.utc)
        db_session.add(model_object)
        await db_session.flush([model_object])
        return await cls.get_by_id(model_object.id)

    @classmethod
    @abstractmethod
    def get_id_prefix(cls) -> str:
        pass
