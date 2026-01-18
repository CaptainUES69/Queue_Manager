from datetime import datetime
from os import getenv
from typing import Type, TypeVar

from dotenv import load_dotenv
from sqlalchemy import DateTime, LargeBinary, String, Text, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.conf import logger

load_dotenv(override=True)


def get_engine():
    return create_engine(getenv("DBROOT"), echo=False)


class Base(DeclarativeBase):
    pass


class CeleryTasks(Base):
    __tablename__ = "celery_taskmeta"

    ID: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(155), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=True)
    result: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    date_done: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    traceback: Mapped[str] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(String(155), nullable=True)
    args: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    kwargs: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    worker: Mapped[str] = mapped_column(String(155), nullable=True)
    retries: Mapped[int] = mapped_column(nullable=True)
    queue: Mapped[str] = mapped_column(String(155), nullable=True)


class BackupTasks(Base):
    __tablename__ = "files"

    ID: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(155), unique=True)
    file_url: Mapped[str] = mapped_column(nullable=True, unique=True)
    file_path: Mapped[str] = mapped_column(nullable=True, unique=True)
    callback_url: Mapped[str] = mapped_column(nullable=True)


T = TypeVar("T", CeleryTasks, BackupTasks)


class TableManager:
    session_factory: sessionmaker[Session] = sessionmaker(get_engine())
    Base.metadata.create_all(get_engine())

    @classmethod
    def get_task(cls, _id: str, table: Type[T]) -> T | None:
        with cls.session_factory() as session:
            task = session.query(table).filter(table.task_id == _id).first()
            if not task:
                return None

        logger.info(f"Get task {table.__name__} with task id: {task.task_id=}")
        return task

    @classmethod
    def get_all_tasks(cls, table: Type[T]) -> list[T] | None:
        with cls.session_factory() as session:
            tasks = session.query(table).all()

            logger.info(f"Get all tasks for: {table.__name__}")
            return tasks

    @classmethod
    def create_task_backup(
        cls,
        _id: str,
        file_url: str = None,
        file_path: str = None,
        callback_url: str = None,
    ) -> str | None:
        with cls.session_factory() as session:
            try:
                file = BackupTasks(
                    task_id=_id,
                    file_url=file_url,
                    file_path=file_path,
                    callback_url=callback_url,
                )

                logger.debug(f"Backup task created: {file}")
                session.add(file)
                session.commit()
                logger.info(f"Backup task {_id} created")

            except IntegrityError:
                session.rollback()
                logger.warning(
                    f"Duplicate entry detected for URL/Path: {file_url or file_path}"
                )

                with cls.session_factory() as new_session:
                    if file_path:
                        task = (
                            new_session.query(BackupTasks)
                            .filter(BackupTasks.file_path.contains(file_path))
                            .first()
                        )

                    elif file_url:
                        task = (
                            new_session.query(BackupTasks)
                            .filter(BackupTasks.file_url.contains(file_url))
                            .first()
                        )

                    return task.task_id

    @classmethod
    def delete_task_backup(cls, _id: str) -> str | None:
        with cls.session_factory() as session:
            file = session.query(BackupTasks).filter(BackupTasks.task_id == _id).first()
            logger.debug(f"Backup task deleted {file=}")
            session.delete(file)
            session.commit()
            logger.info(f"Backup task with id: {_id} deleted")

            return _id
