from os import remove
from os.path import basename, exists
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, Mock
from urllib.parse import urlparse

import pytest

from src.tasks import (callback_result_to_url, download_file)


# class TestCeleryTasks:
#     @pytest.mark.parametrize(
#         ('audio_url'),
#         [
#             ('https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.flac'),
#             ('https://raw.githubusercontent.com/CaptainUES69/test/refs/heads/main/test.mp3')
#         ]
#     )
#     def test_download_file_success(
#         self,
#         mock_task_self: Mock,
#         audio_url: str
#     ):
#         try:
#             # arrange
#             parsed = urlparse(audio_url)
#             filename = basename(parsed.path)

#             # act
#             filepath = download_file(mock_task_self, audio_url = audio_url)

#             # assert
#             assert filename in filepath
#             assert exists(filepath)

#         finally:
#             if exists(filepath):
#                 remove(filepath)


#     def test_callback_result_to_url(
#         self,
#         mock_task_self: Mock,

#     ):
#         # arrange

#         # act

#         # assert
#         assert ...

# Тестируем основные методы важные для выполнения задачи
