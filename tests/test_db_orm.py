import uuid
from typing import Type

import pytest
from sqlalchemy.orm import Session, sessionmaker

from src.db_orm import BackupTasks, CeleryTasks, T, TableManager
from tests.conftest import backups, celerys


class TestDataBaseORM:
    @pytest.mark.parametrize(
        ("_id", "table"),
        [
            (backups[0].task_id, BackupTasks),
            (backups[1].task_id, BackupTasks),
            (backups[2].task_id, BackupTasks),
            (backups[3].task_id, BackupTasks),
            (backups[4].task_id, BackupTasks),
            (celerys[0].task_id, CeleryTasks),
            (celerys[1].task_id, CeleryTasks),
            (celerys[2].task_id, CeleryTasks),
        ],
    )
    def test_get_task(self, _id: str, conf_TB: None, table: Type[T]) -> T | None:
        result = TableManager.get_task(_id, table)

        assert result.task_id == _id

    @pytest.mark.parametrize(("table"), [(BackupTasks), (CeleryTasks)])
    def test_get_all_task(self, conf_TB: None, table: Type[T]) -> list[T] | None:
        task_list = TableManager.get_all_tasks(table)

        assert task_list == backups or celerys

    @pytest.mark.parametrize(
        ("_id", "file_url", "file_path", "callback_url"),
        [
            (str(uuid.uuid4()), "http://site.ru", "/flow.mp3", "http://example.com"),
            (
                str(uuid.uuid4()),
                "http://free_flac.com",
                "tests/files/testfile.flac",
                None,
            ),
            (str(uuid.uuid4()), "https://example.com", None, "https://example.com"),
            (str(uuid.uuid4()), "http://free_mp3.kz", None, None),
            (str(uuid.uuid4()), None, "tests/files/music.wav", "https://example.com"),
            (str(uuid.uuid4()), None, "something/in/the/directory/file.flac", None),
        ],
    )
    def test_create_task_backup(
        self,
        session_maker: sessionmaker[Session],
        _id: str,
        file_url: str | None,
        file_path: str | None,
        callback_url: str | None,
    ) -> str | None:
        TableManager.create_task_backup(_id, file_url, file_path, callback_url)
        task = (
            session_maker()
            .query(BackupTasks)
            .filter(BackupTasks.task_id == _id)
            .first()
        )

        assert task != None

    @pytest.mark.parametrize(
        ("_id"),
        [
            (backups[0].task_id),
            (backups[1].task_id),
            (backups[2].task_id),
            (backups[3].task_id),
            (backups[4].task_id),
        ],
    )
    def test_delete_task_backup(
        self, session_maker: sessionmaker[Session], _id: str
    ) -> str | None:
        deleted: str = TableManager.delete_task_backup(_id)
        task = (
            session_maker()
            .query(BackupTasks)
            .filter(BackupTasks.task_id == _id)
            .first()
        )

        assert deleted == _id
        assert task == None
