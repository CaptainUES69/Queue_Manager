import io
import pickle
import uuid
from typing import Any, Generator, Callable
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
        task_id=str(uuid.uuid4()),
        file_url="https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test_andrei.flac",
    ),
    BackupTasks(
        task_id=str(uuid.uuid4()),
        file_path="src\\files/test.flac",
    ),
    BackupTasks(
        task_id=str(uuid.uuid4()),
        file_url="https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.mp3",
        file_path="src\\files/test.mp3",
    ),
    BackupTasks(
        task_id=str(uuid.uuid4()),
        file_url="https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.flac",
        callback_url="https://example.com",
    ),
    BackupTasks(
        task_id=str(uuid.uuid4()),
        file_path="src\\files/test.wav",
        callback_url="https://example.com",
    ),
]
celerys = [
    CeleryTasks(task_id=str(uuid.uuid4()), status=StatesTasks.decode_exc.value),
    CeleryTasks(
        task_id=str(uuid.uuid4()),
        status=StatesTasks.success.value,
        result=pickle.dumps("123123frasdasD23ASD"),
    ),
    CeleryTasks(task_id=str(uuid.uuid4()), status=StatesTasks.download.value),
]


@pytest.fixture(scope="session")
def engine() -> Engine:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    return engine


@pytest.fixture(scope="session")
def create_tables(engine: Engine) -> Generator[None, Any, None]:
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    session.add_all(backups)
    session.add_all(celerys)

    session.commit()
    session.close()

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="class")
def session_maker(
    engine: Engine, create_tables: None
) -> Generator[sessionmaker[Session], None, None]:
    session_factory: sessionmaker[Session] = sessionmaker(engine)

    yield session_factory


@pytest.fixture(scope="class")
def conf_TB(session_maker) -> None:
    TableManager.session_factory = session_maker


@pytest.fixture(scope="class")
def testclient() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
def mock_webserver_TableManager() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.TableManager") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_TableManager() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.tasks.TableManager") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_delete_task_backup() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.TableManager.delete_task_backup") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_transcribation_task() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.transcribation_task") as mock:
        mock.apply_async = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_transcribation_task() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.tasks.transcribation_task") as mock:
        mock.apply_async = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_requests() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.requests") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_shutil() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.shutil") as mock:
        mock.copyfileobj = Mock()
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_open_file() -> Generator[Any, Any, None]:
    with patch("src.webserver.open", mock_open()) as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_pathlib() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.Path") as mock:
        mock_instance = Mock()
        mock_instance.mkdir = Mock()
        mock.return_value = mock_instance
        yield mock


@pytest.fixture(scope="function")
def mock_webserver_os_path() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.isfile") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_os_path() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.tasks.isfile") as mock:
        yield mock


@pytest.fixture(scope="function")
def audio_file_factory() -> tuple[str, io.BytesIO, str]:
    def _create_audio_file(filename="test.mp3", content=None, mime_type="audio/mpeg"):
        if content is None:
            content = b"fake audio content" * 100

        file_like_object = io.BytesIO(content)
        return (filename, file_like_object, mime_type)

    return _create_audio_file


@pytest.fixture(scope="function")
def mock_webserver_delete_task() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.webserver.delete_task") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_task_self() -> Mock:
    mock = Mock()
    mock.update_state = Mock()
    return mock


@pytest.fixture(scope="function")
def mock_tasks_celery_app() -> Generator[MagicMock | AsyncMock, Any, None]:
    with patch("src.tasks.app") as mock:
        mock.AsyncResult = Mock()
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_getenv() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.getenv") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_streaming_pipeline() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.StreamingCTCPipeline") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_read_audio() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.read_audio") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_remove() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.remove") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_exists() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.exists") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_basename() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.basename") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_urlparse() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.urlparse") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_requests() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.requests") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_open_file() -> Generator[Any, Any, None]:
    with patch("src.tasks.open", mock_open()) as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_app() -> Generator[MagicMock, Any, None]:
    with patch("src.tasks.app") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_tasks_pipeline_global() -> Generator[MagicMock, Any, None]:
    import src.tasks as tasks_module

    original_pipeline = tasks_module.pipeline
    mock_pipeline = MagicMock()
    tasks_module.pipeline = mock_pipeline

    yield mock_pipeline

    # Восстанавливаем оригинальный pipeline
    tasks_module.pipeline = original_pipeline


@pytest.fixture(scope="function")
def mock_tasks_pipeline_instance() -> MagicMock:
    mock = MagicMock()
    mock.forward_offline = MagicMock(return_value=[])
    return mock


@pytest.fixture(scope="function")
def mock_text_phrase() -> MagicMock:
    mock = MagicMock()
    mock.text = "test phrase"
    return mock


@pytest.fixture(scope="function")
def mock_celery_task_result() -> MagicMock:
    mock = MagicMock()
    mock.forget = MagicMock()
    return mock


@pytest.fixture(scope="function")
def backup_task_factory() -> Callable[..., BackupTasks]:
    def _create_backup_task(
        task_id: str = None,
        file_url: str = None,
        file_path: str = None,
        callback_url: str = None,
    ) -> BackupTasks:
        return BackupTasks(
            task_id=task_id or str(uuid.uuid4()),
            file_url=file_url,
            file_path=file_path,
            callback_url=callback_url,
        )

    return _create_backup_task


@pytest.fixture(scope="function")
def celery_task_factory() -> Callable[..., CeleryTasks]:
    def _create_celery_task(
        task_id: str = None, status: str = None, result: bytes = None
    ) -> CeleryTasks:
        return CeleryTasks(
            task_id=task_id or str(uuid.uuid4()),
            status=status or StatesTasks.download.value,
            result=result,
        )

    return _create_celery_task


@pytest.fixture(scope="function")
def mock_self_task() -> MagicMock:
    mock = MagicMock()
    mock.update_state = MagicMock()
    return mock
