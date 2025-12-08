from datetime import datetime
from os import getenv

from dotenv import load_dotenv
from sqlalchemy import DateTime, LargeBinary, String, Text, create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

from src.conf import logger

load_dotenv()
class Base(DeclarativeBase):
    pass


class CeleryTasks(Base):
    __tablename__ = 'celery_taskmeta'
    
    ID: Mapped[int] = mapped_column(primary_key = True)
    task_id: Mapped[str] = mapped_column(String(155), unique = True, nullable = True)
    status: Mapped[str] = mapped_column(String(50), nullable = True)
    result: Mapped[bytes] = mapped_column(LargeBinary, nullable = True)
    date_done: Mapped[datetime] = mapped_column(DateTime, nullable = True)
    traceback: Mapped[str] = mapped_column(Text, nullable = True)
    name: Mapped[str] = mapped_column(String(155), nullable = True)
    args: Mapped[bytes] = mapped_column(LargeBinary, nullable = True)
    kwargs: Mapped[bytes] = mapped_column(LargeBinary, nullable = True)
    worker: Mapped[str] = mapped_column(String(155), nullable = True)
    retries: Mapped[int] = mapped_column(nullable = True)
    queue: Mapped[str] = mapped_column(String(155), nullable = True)

class FilesAndURL(Base):
    __tablename__ = 'files'

    ID: Mapped[int] = mapped_column(primary_key = True)
    task_id: Mapped[str] = mapped_column(String(155), unique = True, nullable = True)
    file_url: Mapped[str] = mapped_column(nullable = True)
    file_path: Mapped[str] = mapped_column(nullable = True)
    
    
engine = create_engine(
    getenv('DBROOT'), 
    echo = False
)

Base.metadata.create_all(engine)
session_factory = sessionmaker(engine)


def id_in_table_celery(_id: str, session: Session) -> bool:
    result = session.query(CeleryTasks).filter(CeleryTasks.task_id == _id).first()
    if result:
        return True
    
    logger.warning(f'Hash_ID: {_id} not found')
    return False
    

def get_task(_id: str) -> CeleryTasks | None:
    with session_factory() as session:
        if id_in_table_celery(_id, session) == False:
            logger.warning(f'{_id} not found in table - tasks')
            raise NoResultFound
        
        task = session.query(CeleryTasks).filter(CeleryTasks.task_id == _id).first()
        logger.info(f'Get celery task: {task.task_id=}')

        return task
    

def get_all_celery_tasks() -> list[CeleryTasks]:
    with session_factory() as session:
        tasks = session.query(CeleryTasks).all()
        logger.info('Get all tasks from celery')
        filetasks: list[CeleryTasks] = []
        for task in tasks:
            logger.debug(f'Celery task_id = {task.task_id}')
            filetasks.append(task)
        
        return tasks


def id_in_table_files(_id: str, session: Session) -> bool:
    result = session.query(FilesAndURL).filter(FilesAndURL.task_id == _id).first()
    if result:
        return True
    
    logger.warning(f'Hash_ID: {_id} not found')
    return False


def get_all_files_url() -> list[FilesAndURL]:
    with session_factory() as session:
        tasks = session.query(FilesAndURL).all()
        logger.info('Get all tasks from backup')
        files: list[FilesAndURL] = []
        for task in tasks:
            logger.debug(f'Backup task_id = {task.task_id}')
            files.append(task)
        
        return files


def create_task_backup(_id: str, file_url: str = None, file_path: str = None) -> None:
    with session_factory() as session:
        if id_in_table_files(_id, session):
            logger.warning(f'ID: {_id} was already in backup table')
            raise IntegrityError
        
        file = FilesAndURL(task_id = _id, file_url = file_url, file_path = file_path)
        logger.debug(f'Backup task created: {file}')
        session.add(file)
        session.commit()
        logger.info(f'Backup task {_id} created')


def delete_task_backup(_id: str) -> None:
    with session_factory() as session:
        if id_in_table_files(_id, session) == False:
            logger.warning(f'Task_id: {_id} was not found in backup')
            raise NoResultFound
        
        file = session.query(FilesAndURL).filter(FilesAndURL.task_id == _id).first()
        logger.debug(f'Backup task deleted {file=}')
        session.delete(file)
        session.commit()
        logger.info(f'Backup task: {_id} deleted')
