from datetime import datetime
from os import getenv

from dotenv import load_dotenv
from sqlalchemy import DateTime, LargeBinary, String, Text, create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.conf import delete_file, logger

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


def id_in_table_celery(_id: str) -> bool:
    with session_factory() as session:
        result = session.query(CeleryTasks).filter(CeleryTasks.task_id == _id).first()
        if result:
            return True
        
        logger.warning(f'Hash_ID: {_id} not found')
        return False
    

def get_task(_id: str) -> CeleryTasks | None:
    with session_factory() as session:
        if id_in_table_celery(_id) == False:
            logger.warning(f'{_id} not found in table - tasks')
            raise NoResultFound
        
        task = session.query(CeleryTasks).filter(CeleryTasks.task_id == _id).first()

        return task
    

def get_all_celery_tasks() -> list[CeleryTasks]:
    with session_factory() as session:
        tasks = session.query(CeleryTasks).all()
        filetasks: list[CeleryTasks] = []
        for task in tasks:
            filetasks.append(task)
        
        return tasks


def id_in_table_files(_id: str) -> bool:
    with session_factory() as session:
        result = session.query(FilesAndURL).filter(FilesAndURL.task_id == _id).first()
        if result:
            return True
        
        logger.warning(f'Hash_ID: {_id} not found')
        return False


def get_all_files_url() -> list[FilesAndURL]:
    with session_factory() as session:
        tasks = session.query(FilesAndURL).all()
        files: list[FilesAndURL] = []
        for task in tasks:
            files.append(task)
        
        return files


def create_task_backup(_id: str, file_url: str = None, file_path: str = None) -> None:
    with session_factory() as session:
        if id_in_table_files(_id):
            return IntegrityError
        
        file = FilesAndURL(task_id = _id, file_url = file_url, file_path = file_path)
        session.add(file)
        session.commit()


def delete_task_backup(_id: str):
    with session_factory() as session:
        try:
            if id_in_table_files(_id) == False:
                raise NoResultFound
            
            file = session.query(FilesAndURL).filter(FilesAndURL.task_id == _id).first()
            session.delete(file)
            session.commit()
            
            delete_file(file.file_path)

        except FileNotFoundError:
            logger.info('File not deleted from files')
            
