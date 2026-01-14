import io
import pickle
import uuid
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.conf import StatesTasks
from src.db_orm import BackupTasks, Base, CeleryTasks, TableManager
from src.webserver import app

backups = [
    BackupTasks(
        task_id = str(uuid.uuid4()), 
        file_url = 'https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test_andrei.flac', 
    ),
    BackupTasks(
        task_id = str(uuid.uuid4()), 
        file_path = 'src\\files/test.flac',
    ),
    BackupTasks(
        task_id = str(uuid.uuid4()), 
        file_url = 'https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.mp3', 
        file_path = 'src\\files/test.mp3',
    ),
    BackupTasks(
        task_id = str(uuid.uuid4()), 
        file_url = 'https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.flac', 
        callback_url = 'https://example.com'
    ),
    BackupTasks(
        task_id = str(uuid.uuid4()), 
        file_path = 'src\\files/test.wav',
        callback_url = 'https://example.com'
    )
]
celerys = [
    CeleryTasks(
        task_id = str(uuid.uuid4()), 
        status = StatesTasks.DECODE_EXC.value
    ),
    CeleryTasks(
        task_id = str(uuid.uuid4()), 
        status = StatesTasks.SUCCESS.value,
        result = pickle.dumps(
            '123123frasdasD23ASD'
        )
    ),
    CeleryTasks(
        task_id = str(uuid.uuid4()), 
        status = StatesTasks.DOWNLOAD.value
    )
]

@pytest.fixture(scope = 'session')
def engine() -> Engine:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args = {"check_same_thread": False},
        poolclass = StaticPool,
        echo = False
    )

    return engine


@pytest.fixture(scope = 'session')
def create_tables(engine: Engine) -> Generator[None, Any, None]:
    Base.metadata.create_all(bind = engine)
    connection = engine.connect()
    session_factory = sessionmaker(bind = connection)
    session = session_factory()

    session.add_all(backups)
    session.add_all(celerys)

    session.commit()
    session.close()

    yield

    Base.metadata.drop_all(bind = engine)


@pytest.fixture(scope = 'session')
def session_maker(engine: Engine, create_tables: None) -> Generator[sessionmaker[Session], None, None]:
    session_factory: sessionmaker[Session] = sessionmaker(engine)

    yield session_factory


@pytest.fixture(scope = 'function')
def conf_TB(session_maker) -> None:
    TableManager.session_factory = session_maker


@pytest.fixture(scope = 'session')
def testclient() -> TestClient:
    return TestClient(app)   


@pytest.fixture(scope = 'function')
def mock_TableManager() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.TableManager') as mock:
        yield mock


@pytest.fixture(scope = 'function')
def mock_delete_task_backup() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.TableManager.delete_task_backup') as mock:
        yield mock


@pytest.fixture(scope = 'function')
def mock_transcribation_task() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.transcribation_task') as mock:
        mock.apply_async = MagicMock(return_value = MagicMock(id = 'test-task-id'))
        yield mock


@pytest.fixture(scope = 'function')
def mock_requests() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.requests') as mock:
        yield mock


@pytest.fixture(scope = 'function')
def mock_shutil() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.shutil') as mock:
        mock.copyfileobj = Mock()
        yield mock


@pytest.fixture(scope = 'function')
def mock_open_file():
    with patch('src.webserver.open', mock_open()) as mock_file:
        yield mock_file


@pytest.fixture(scope = 'function')
def mock_pathlib() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.Path') as mock:
        mock_instance = Mock()
        mock_instance.mkdir = Mock()
        mock.return_value = mock_instance
        yield mock


@pytest.fixture(scope = 'function')
def mock_os_path() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch('src.webserver.isfile') as mock:
        yield mock


@pytest.fixture(scope='function')
def audio_file_factory():
    def _create_audio_file(filename = "test.mp3", content = None, mime_type = "audio/mpeg"):
        if content is None:
            content = b"fake audio content" * 100
    
        file_like_object = io.BytesIO(content)
        return (filename, file_like_object, mime_type)
    
    return _create_audio_file



@pytest.fixture(scope = 'function')
def mock_delete_task():
    with patch('src.tasks.delete_task') as mock:
        yield mock

