from typing import Any, Generator, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from tone import StreamingCTCPipeline

from src.conf import StatesTasks
from src.db_orm import BackupTasks, CeleryTasks
from src.tasks import (callback_result_to_url, create_pipeline, delete_task,
                       download_file, load_backups, transcribe_file,
                       validate_audio_file)


class TestTasksFunctions:
    def test_validate_audio_file_exists(
        self, 
        mock_tasks_exists: Generator[MagicMock, Any, None], 
        mock_tasks_os_path: Generator[MagicMock | AsyncMock, Any, None]
    ):
        mock_tasks_exists.return_value = True
        mock_tasks_os_path.return_value = True
        
        result = validate_audio_file("/path/to/valid/file.mp3")
        
        assert result is True

    
    def test_validate_audio_file_not_exists(
        self, 
        mock_tasks_exists: Generator[MagicMock, Any, None], 
        mock_tasks_os_path: Generator[MagicMock | AsyncMock, Any, None]
    ):
        mock_tasks_exists.return_value = False
        mock_tasks_os_path.return_value = False
        
        result = validate_audio_file("/path/to/invalid/file.mp3")
        
        assert result is False


    @pytest.mark.skip(reason='Slow test')
    def test_create_pipeline_local_model(
        self
    ):
        result = create_pipeline()
        
        assert type(result) == StreamingCTCPipeline
    

    @pytest.mark.skip(reason='Really slow test + need to download large files')
    def test_create_pipeline_huggingface_model(
        self, 
        mock_tasks_os_path: Generator[MagicMock | AsyncMock, Any, None]
    ):
        mock_tasks_os_path.return_value = False
        result = create_pipeline()
        
        assert type(result) == type(StreamingCTCPipeline)


    def test_download_file_success(
        self, 
        mock_tasks_getenv: Generator[MagicMock, Any, None],
        mock_tasks_open_file: Generator[Any, Any, None],
        mock_tasks_requests: Generator[MagicMock, Any, None],
        mock_tasks_urlparse: Generator[MagicMock, Any, None],
        mock_tasks_basename: Generator[MagicMock, Any, None],
        mock_self_task: MagicMock
    ):
        # Arrange
        mock_tasks_getenv.return_value = "/download/path"
        
        mock_response = MagicMock()
        mock_response.content = b"test audio content"
        mock_tasks_requests.get.return_value = mock_response
        
        mock_parsed = MagicMock()
        mock_parsed.path = "/audio.mp3"
        mock_tasks_urlparse.return_value = mock_parsed
        mock_tasks_basename.return_value = "audio.mp3"
        
        # Act
        result = download_file(mock_self_task, "http://example.com/audio.mp3", "test-log-id")
        
        # Assert
        assert result == "/download/path/audio.mp3"


    def test_transcribe_file_success(
        self, 
        mock_tasks_read_audio: Generator[MagicMock, Any, None],
        mock_tasks_pipeline_global: Generator[MagicMock, Any, None],
        mock_tasks_pipeline_instance: MagicMock,
        mock_text_phrase: MagicMock,
        mock_self_task: MagicMock
    ):
        # Arrange
        mock_tasks_pipeline_global.forward_offline.return_value = [mock_text_phrase]
        
        mock_audio = MagicMock()
        mock_tasks_read_audio.return_value = mock_audio
        
        # Act
        result = transcribe_file(mock_self_task, "/path/to/audio.mp3", "test-log-id")
        
        # Assert
        assert result == ["test phrase"]


    def test_callback_success(
        self, 
        mock_tasks_requests: Generator[MagicMock, Any, None], 
        mock_self_task: MagicMock
    ):
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_tasks_requests.post.return_value = mock_response
        
        result_data = ["Hello", "World"]
        
        # Act
        callback_result_to_url(mock_self_task, "http://callback.example.com", result_data, "test-log-id")
        
        # Assert
        mock_tasks_requests.post.assert_called_once_with(
            "http://callback.example.com",
            json=result_data
        )
        mock_self_task.update_state.assert_called_once_with(state=StatesTasks.callback.value)
    
    
    def test_callback_with_empty_url(
        self, 
        mock_tasks_requests: Generator[MagicMock, Any, None], 
        mock_self_task: MagicMock
    ):
        callback_result_to_url(mock_self_task, "", ["test"], "test-log-id")
        
        mock_tasks_requests.post.assert_not_called()
        mock_self_task.update_state.assert_not_called()


    def test_delete_task_success(
        self, 
        mock_tasks_app: Generator[MagicMock, Any, None], 
        mock_celery_task_result: MagicMock
    ):
        # Arrange
        mock_tasks_app.AsyncResult.return_value = mock_celery_task_result
        
        # Act
        delete_task("test-task-id")
        
        # Assert
        mock_tasks_app.AsyncResult.assert_called_once_with("test-task-id")
        mock_celery_task_result.forget.assert_called_once()


    def test_load_backups_success(
        self,
        mock_tasks_TableManager: Generator[MagicMock | AsyncMock, Any, None],
        mock_tasks_transcribation_task: Generator[MagicMock | AsyncMock, Any, None],
        mock_tasks_os_path: Generator[MagicMock | AsyncMock, Any, None],
        backup_task_factory: Callable[..., BackupTasks],
        celery_task_factory: Callable[..., CeleryTasks]
    ):
        # Arrange
        backup1 = backup_task_factory(
            task_id="backup-1",
            file_path="/path/to/file1.mp3"
        )
        
        backup2 = backup_task_factory(
            task_id="backup-2",
            file_url="http://example.com/audio.mp3",
            callback_url="http://callback.com"
        )
        
        celery_task_success = celery_task_factory(
            task_id="celery-success",
            status=StatesTasks.success.value
        )
        
        celery_task_failed = celery_task_factory(
            task_id="celery-failed",
            status=StatesTasks.decode_exc.value
        )
        
        mock_tasks_TableManager.get_all_tasks.side_effect = [
            [backup1, backup2],  # BackupTasks
            [celery_task_success, celery_task_failed]  # CeleryTasks
        ]
        
        mock_tasks_os_path.return_value = True  # Файл существует
        
        mock_async_result = MagicMock()
        mock_async_result.id = "async-task-id"
        mock_tasks_transcribation_task.apply_async.return_value = mock_async_result
        
        # Act
        result = load_backups()
        
        # Assert
        assert len(result) == 2
        assert "backup-1" in result
        assert "backup-2" in result
        
        assert mock_tasks_transcribation_task.apply_async.call_count == 2
    

    def test_load_backups_already_executed(
        self,
        mock_tasks_TableManager: Generator[MagicMock | AsyncMock, Any, None],
        mock_tasks_transcribation_task: Generator[MagicMock | AsyncMock, Any, None],
        mock_tasks_os_path: Generator[MagicMock | AsyncMock, Any, None],
        backup_task_factory: Callable[..., BackupTasks],
        celery_task_factory: Callable[..., CeleryTasks]
    ):
        # Arrange
        backup = backup_task_factory(
            task_id="backup-1",
            file_path="/path/to/file.mp3"
        )
        
        celery_task = celery_task_factory(
            task_id="backup-1",
            status=StatesTasks.success.value
        )
        
        mock_tasks_TableManager.get_all_tasks.side_effect = [
            [backup],  # BackupTasks
            [celery_task]  # CeleryTasks
        ]
        
        mock_tasks_os_path.return_value = True  # Файл существует
        
        # Act
        result = load_backups()
        
        # Assert
        assert result == []  # Задача не должна быть запущена
        mock_tasks_transcribation_task.apply_async.assert_not_called()
