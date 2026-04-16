"""Feedback model — at most one row per query_id (replace semantics).

The FK target is `query_requests.id`, not `query_responses.id`: feedback
is "how was my question handled" — keyed on the question, so the row
survives even if the response is later rewritten or cleaned up.

`UNIQUE(query_id)` is the conflict target for the `upsert_by_query_id`
classmethod, which implements the atomic replace-on-conflict semantics
frozen in Batch 2b. `created_at` (from `BaseModel`) records when
feedback was first given for this `query_id`; `updated_at` advances on
every replace. Upsert-on-conflict preserves the existing `created_at`
and only touches `rating`, `reason`, and `updated_at`.
"""

from datetime import datetime
from datetime import timezone

from sqlalchemy import TIMESTAMP
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from configs.db import DBConfig
from db import db
from db.models.base import BaseModel
from db.models.base import _generate_random_string


class Feedback(BaseModel):
    __tablename__ = "feedback"

    id = Column(Text, primary_key=True)
    query_id = Column(
        Text,
        ForeignKey(
            f"{DBConfig.SCHEMA_NAME}.query_requests.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )
    rating = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def get_id_prefix(cls) -> str:
        return "fbk_"

    @classmethod
    async def upsert_by_query_id(
        cls,
        query_id: str,
        rating: str,
        reason: str | None,
    ) -> None:
        """Atomically insert or replace the feedback row for a query_id.

        The `id` and `created_at` generated on the first insert are
        preserved on conflict — the upsert updates `rating`, `reason`,
        and `updated_at`, leaving the existing row's PK and first-given
        timestamp alone.
        """
        db_session = await db.get_session()
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(cls)
            .values(
                id=cls.get_id_prefix() + _generate_random_string(10),
                query_id=query_id,
                rating=rating,
                reason=reason,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[cls.query_id],
                set_={
                    "rating": rating,
                    "reason": reason,
                    "updated_at": now,
                },
            )
        )
        await db_session.execute(stmt)
