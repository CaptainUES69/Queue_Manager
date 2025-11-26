from os import getenv

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from conf import logger


load_dotenv()
class Base(DeclarativeBase):
    pass


class Tasks(Base):
    __tablename__ = 'tasks'
    
    id: Mapped[str] = mapped_column(primary_key = True) # Хеш в качестве ID
    status: Mapped[str] = mapped_column(nullable = True) # Текущий статус задачи
    result: Mapped[str] = mapped_column(nullable = True) # Выходные данные


engine = create_engine(
    getenv('DBROOT'), 
    echo = True,
    pool_size = int(getenv('TASKS_NUMBER')),
    max_overflow = int(getenv('TASKS_NUMBER')) + 5 # 5 дополнительных операций вдруг что
)

Base.metadata.create_all(engine)

session_factory = sessionmaker(engine)


def id_in_table(hash_id: str) -> bool:
    with session_factory() as session:
        result = session.get(Tasks, hash_id)
        if result:
            return True
        
        logger.warning(f'Hash_ID: {hash_id} not found')
        return False


def create_task(hash_id: str) -> None:
    with session_factory() as session:
        if id_in_table(hash_id):
            logger.warning(f'{hash_id} already in table.')
            raise IntegrityError
        
        task = Tasks(id = hash_id, status = 'InRabbit')
        session.add(task)
        
        session.commit()


def change_task_data(hash_id: str, status: str = None, result: str = None) -> None:
    with session_factory() as session:
        if id_in_table(hash_id) == False:
            raise NoResultFound
        
        if status:
            task = session.get(Tasks, hash_id)
            if task == None:
                raise NoResultFound
            
            task.status = status
            session.commit()

        elif result:
            task = session.get(Tasks, hash_id)
            if task == None:
                raise NoResultFound

            task.result = result
            session.commit()

        else:
            raise ValueError


def get_task_data(hash_id: str) -> tuple[str, str | None]:
    with session_factory() as session:
        if id_in_table(hash_id) == False:
            raise NoResultFound
        
        task = session.get(Tasks, hash_id)
        return (task.status, task.result)


def delete_task() -> None:
    
    ...