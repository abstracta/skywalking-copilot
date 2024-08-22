import os

from psycopg import AsyncConnection
from sqlalchemy import select, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

from skywalking_copilot import domain

db_url = os.getenv("DB_URL")
engine = create_async_engine(db_url)
async_session = async_sessionmaker(engine, autoflush=True, autocommit=False)
Base = declarative_base()
CHAT_HISTORY_TABLE = 'chat_history'


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_raw_connection(db: AsyncSession) -> AsyncConnection:
    conn = await db.connection()
    raw_conn = await conn.get_raw_connection()
    return raw_conn.driver_connection


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(primary_key=True)
    locales: Mapped[str] = mapped_column()

    @staticmethod
    def from_domain(session: domain.Session) -> 'Session':
        return Session(id=str(session.id), locales=','.join(session.locales))

    def to_domain(self) -> domain.Session:
        return domain.Session(id=self.id, locales=self.locales.split(','))


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey(Session.id))
    question: Mapped[str] = mapped_column()
    answer: Mapped[str] = mapped_column()

    @staticmethod
    def from_domain(question: domain.Question) -> 'Question':
        return Question(id=str(question.id), session_id=str(question.session.id), question=question.question,
                        answer=question.answer)


class SessionsRepository:

    def __init__(self, db: AsyncSession):
        self._db = db

    async def save(self, session: domain.Session) -> None:
        self._db.add(Session.from_domain(session))
        await self._db.commit()

    async def find_session(self, session_id: str) -> domain.Session:
        stmt = select(Session).filter(Session.id == session_id)
        result = await self._db.execute(stmt)
        ret = result.scalar()
        return ret.to_domain() if ret else None


class QuestionsRepository:

    def __init__(self, db: AsyncSession):
        self._db = db

    async def save_question(self, question: domain.Question):
        self._db.add(Question.from_domain(question))
        await self._db.commit()
