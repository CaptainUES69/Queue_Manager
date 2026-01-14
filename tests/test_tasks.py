from unittest.mock import Mock

import pytest
from celery.exceptions import Reject, Retry
from fastapi import status
from requests.exceptions import ConnectTimeout, HTTPError

from src.tasks import (callback_result_to_url, create_pipeline, delete_task,
                       download_file, load_backups, transcribe_file)


class TestCeleryTasks:
    def test_download_file_success(
        self, 
        mock_task_self, 
        mock_requests
    ):
        # Arrange
        test_url = "http://example.com/audio.mp3"
        test_filename = "audio.mp3"
        test_content = b"fake audio data"
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = test_content
        mock_requests.get.return_value = mock_response


    def test_download_file_http_error(
        self, 
        mock_task_self, 
        mock_requests
    ):
        # Arrange
        test_url = "http://example.com/test.mp3"
        
        mock_response = Mock()
        mock_response.status_code = status.HTTP_404_NOT_FOUND
        mock_requests.get.side_effect = HTTPError(
            "Not Found", 
            response=mock_response
        )
        
        # Act & Assert
        with pytest.raises(Retry, match = "Error while download file"):
            download_file(mock_task_self, test_url)
    

    def test_download_file_connect_timeout(
        self, 
        mock_task_self, 
        mock_requests
    ):
        # Arrange
        test_url = "http://example.com/test.mp3"
        mock_requests.get.side_effect = ConnectTimeout("Connection timeout")
        
        # Act & Assert
        with pytest.raises(Retry, match = "Error while download file"):
            download_file(mock_task_self, test_url)


    def test_download_file(
        self,
    ):
        # arrange

        # act

        # assert
        assert ...
    
    
    def test_create_pipeline(
        self,
    ):
        # arrange
        
        # act

        # assert
        assert ...

    
    def test_delete_task(
        self,
    ):
        # arrange
        
        # act

        # assert
        assert ...

    
    def test_callback_result_to_url(
       self,
    ):
        # arrange
        
        # act

        # assert
        assert ...


    def test_transcribe_file(
       self,
    ):
        # arrange
        
        # act

        # assert
        assert ...

    def test_load_backups(
       self,
    ):
        # arrange
        
        # act

        # assert
        assert ...

# Тестируем основные методы важные для выполнения задачи