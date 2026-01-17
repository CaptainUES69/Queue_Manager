import pickle
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Generator, Any
import pytest
from fastapi import status
from fastapi.responses import Response
from fastapi.testclient import TestClient

from src.conf import StatesAPI
from tests.conftest import celerys
from src.db_orm import TableManager, CeleryTasks


class TestTranscribationTask:
    @pytest.mark.parametrize(
        ("filename", "audio_url", "callback_url"),
        [
            ("test.mp3", None, "https://example.com/callback"),
            ("test.wav", None, None),
            ("test.flac", None, None),
            (None, "https://example.com/test.mp3", "https://example.com/callback"),
            (None, "https://example.com/test.wav", None),
            (None, "https://example.com/test.flac", None),
        ],
    )
    def test_post_success(
        self,
        testclient: TestClient,
        mock_webserver_TableManager: MagicMock | AsyncMock,
        mock_webserver_os_path: MagicMock | AsyncMock,
        mock_webserver_transcribation_task: MagicMock | AsyncMock,
        mock_webserver_shutil: MagicMock | AsyncMock,
        mock_webserver_open_file: MagicMock | AsyncMock,
        mock_webserver_requests: MagicMock | AsyncMock,
        audio_file_factory: tuple,
        filename: str | None,
        audio_url: str | None,
        callback_url: str | None,
    ) -> None:
        # arrange
        mock_webserver_TableManager.create_task_backup.return_value = None
        mock_webserver_os_path.return_value = True
        mock_webserver_transcribation_task.return_value = None
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_webserver_requests.head.return_value = mock_response

        files = {}
        data = {}
        if filename:
            files["audio_file"] = audio_file_factory(filename=filename)
            if callback_url:
                files["callback_url"] = (None, callback_url, None)

        else:
            data = {"audio_url": audio_url, "callback_url": callback_url}

        # act
        response: Response = testclient.post(
            "/transcribe_audio/create", data=data, files=files
        )

        # assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["status"] == StatesAPI.success.value
        assert response.json()["data"] != None
        print(response.json()["data"])

    def test_post_both_exception(
        self, testclient: TestClient, audio_file_factory: tuple
    ):
        # arrange
        data = {"audio_url": "https://example.com/test.mp3"}
        files = {"audio_file": audio_file_factory()}

        # act
        response: Response = testclient.post(
            "/transcribe_audio/create", data=data, files=files
        )

        # assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["status"] == StatesAPI.error.value
        assert response.json()["message"] != None
        print(response.json()["message"])

    @pytest.mark.parametrize(
        ("filename", "audio_url"),
        [
            ("test.csv", None),
            ("test.mp3asd", None),
            ("test.wa", None),
            ("test.FLACdasd", None),
            (None, "https://example.com/test.mp4"),
            (None, "https://example.com/test.jpeg"),
            (None, "https://example.com/test.fla"),
            (None, "https://example.com/test.MP3"),
        ],
    )
    def test_post_extension_exception(
        self,
        testclient: TestClient,
        audio_file_factory: tuple,
        mock_webserver_TableManager: MagicMock | AsyncMock,
        mock_webserver_os_path: MagicMock | AsyncMock,
        mock_webserver_transcribation_task: MagicMock | AsyncMock,
        mock_webserver_requests: MagicMock | AsyncMock,
        filename: str | None,
        audio_url: str | None,
    ):
        # arrange
        mock_webserver_TableManager.create_task_backup.return_value = None
        mock_webserver_os_path.return_value = True
        mock_webserver_transcribation_task.return_value = None
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_webserver_requests.head.return_value = mock_response

        files = {}
        data = {}
        if filename:
            files["audio_file"] = audio_file_factory(filename=filename)

        else:
            data = {
                "audio_url": audio_url,
            }

        # act
        response: Response = testclient.post(
            "/transcribe_audio/create", data=data, files=files
        )

        # assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["status"] == StatesAPI.fail.value
        assert response.json()["message"] != None
        print(response.json()["message"])

    @pytest.mark.parametrize(
        ("filename", "audio_url"),
        [
            ("test.mp3", None),
            (
                None,
                "https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.mp3",
            ),
        ],
    )
    def test_post_overlap_exception(
        self,
        testclient: TestClient,
        audio_file_factory: tuple,
        mock_webserver_os_path: MagicMock | AsyncMock,
        mock_webserver_transcribation_task: MagicMock | AsyncMock,
        mock_webserver_requests: MagicMock | AsyncMock,
        mock_webserver_TableManager: Generator[MagicMock | AsyncMock, Any, None],
        filename: str | None,
        audio_url: str | None,
    ):
        # arrange
        mock_webserver_TableManager.create_task_backup.return_value = "exists"
        mock_webserver_os_path.return_value = True
        mock_webserver_transcribation_task.return_value = None
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_webserver_requests.head.return_value = mock_response

        files = {}
        data = {}
        if filename:
            files["audio_file"] = audio_file_factory(filename=filename)

        else:
            data = {
                "audio_url": audio_url,
            }

        # act
        response: Response = testclient.post(
            "/transcribe_audio/create", data=data, files=files
        )

        # assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["status"] == StatesAPI.fail.value
        assert response.json()["message"] != None
        print(response.json()["message"])

    def test_post_url_no_response(
        self,
        testclient: TestClient,
        mock_webserver_TableManager: MagicMock | AsyncMock,
        mock_webserver_os_path: MagicMock | AsyncMock,
        mock_webserver_transcribation_task: MagicMock | AsyncMock,
    ):
        # arrange
        mock_webserver_TableManager.create_task_backup.return_value = None
        mock_webserver_os_path.return_value = True
        mock_webserver_transcribation_task.return_value = None

        data = {"audio_url": "https://example.com/test.mp3"}

        # act
        response: Response = testclient.post("/transcribe_audio/create", data=data)

        # arrange
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["status"] == StatesAPI.error.value
        assert response.json()["message"] != None
        print(response.json()["message"])


class TestGetDataFromTask:
    @pytest.mark.parametrize(
        ("task_id", "expected"),
        [
            (celerys[0].task_id, celerys[0].status),
            (celerys[1].task_id, pickle.loads(celerys[1].result)),
            (celerys[2].task_id, celerys[2].status),
        ],
    )
    def test_get_success(
        self,
        testclient: TestClient,
        mock_webserver_delete_task: MagicMock | AsyncMock,
        mock_webserver_delete_task_backup: MagicMock | AsyncMock,
        conf_TB,
        task_id: str,
        expected: str | list[str],
    ) -> None:
        # arrange

        # act
        response: Response = testclient.get(
            "/transcribe_audio/get_data", params={"task_id": task_id}
        )

        # assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == StatesAPI.success.value
        assert response.json()["data"] == expected
        print(response.json()["data"])

    def test_get_task_not_found(
        self,
        testclient: TestClient,
        mock_webserver_delete_task: MagicMock | AsyncMock,
        mock_webserver_delete_task_backup: MagicMock | AsyncMock,
        conf_TB,
    ):
        # arrange
        task_id = str(uuid.uuid4())

        # act
        response: Response = testclient.get(
            "/transcribe_audio/get_data", params={"task_id": task_id}
        )

        # assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["status"] == StatesAPI.error.value
        assert response.json()["message"] != None
        print(response.json()["message"])
