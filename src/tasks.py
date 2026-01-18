from os import getenv, remove
from os.path import basename, exists, isfile
from urllib.parse import urlparse

import requests
from celery import Celery
from celery.app.task import Task
from celery.exceptions import Reject, Retry
from celery.signals import after_setup_task_logger
from dotenv import load_dotenv
from miniaudio import DecodeError
from requests.exceptions import ConnectTimeout, HTTPError
from tone import StreamingCTCPipeline, TextPhrase, read_audio

from src.conf import StatesTasks, logger
from src.db_orm import BackupTasks, CeleryTasks, TableManager

load_dotenv(override=True)
app = Celery(
    "tasks",
    broker=f"amqp://{getenv('RABBIT_LOGIN')}:{getenv('RABBIT_PASSWORD')}@{getenv('RABBIT_HOST')}:{getenv('RABBIT_PORT')}/{getenv('RABBIT_VHOST')}",
    # broker = 'amqp://myadmin:mypassword@127.0.0.1:5672//',
    backend=f"db+{getenv('DBROOT')}",
)

app.conf.update(
    worker_concurrency=int(getenv("WORKERS_NUMBER")),
    worker_prefetch_multiplier=int(getenv("TASKS_IN_WORKER")),
)

pipeline = None


def validate_audio_file(file_path: str) -> bool:
    return exists(file_path) and isfile(file_path)


def create_pipeline() -> StreamingCTCPipeline:
    logger.info("Choosing Model type")
    if isfile(f"{getenv('MODEL_PATH')}/kenlm.bin") and isfile(
        f"{getenv('MODEL_PATH')}/model.onnx"
    ):
        logger.info("Preparing local model")
        return StreamingCTCPipeline.from_local(getenv("MODEL_PATH"))

    else:
        logger.info("Preparing HuggingFace model")
        return StreamingCTCPipeline.from_hugging_face()


def load_backups() -> list[str]:
    backups: list[BackupTasks] = TableManager.get_all_tasks(BackupTasks)
    tasks: list[CeleryTasks] = TableManager.get_all_tasks(CeleryTasks)
    task_statuses = {task.task_id: task.status for task in tasks}
    loaded: list[str] = []

    for backup in backups:
        if (
            backup.task_id in task_statuses
            and task_statuses[backup.task_id] == StatesTasks.success.value
        ):
            logger.info(f"{backup.task_id} was already executed")
            continue

        if backup.file_url is None and backup.file_path is None:
            logger.warning(f"file_path and file_url was None in: {backup}")

        if not isfile(backup.file_path):
            logger.warning(f"file on {backup.file_path} doesn`t exist")

            if TableManager.delete_task_backup(backup.task_id):
                continue

            else:
                logger.critical("Strange backup row check table: files")
                continue

        filepath = backup.file_url or backup.file_path

        trancribe.apply_async(
            args=[filepath, backup.callback_url, backup.task_id], task_id=backup.task_id
        )
        logger.info(f"{filepath} was tasked with id: {backup.task_id}")
        loaded.append(backup.task_id)

    return loaded


def delete_task(task_id: str) -> None:
    result = app.AsyncResult(task_id)
    result.forget()
    logger.info(f"Delete task with id: {task_id}")


def download_file(self: Task, audio_url: str, log_id: str = None) -> str:
    try:
        self.update_state(state=StatesTasks.download.value)
        logger.info(f"Try to GET data from url: {audio_url} | {log_id}")
        req = requests.get(audio_url)
        req.raise_for_status()

        parsed = urlparse(audio_url)
        filename = basename(parsed.path)
        filepath = f'{getenv("FILES_PATH")}/{filename}'

        self.update_state(state="Writing file")
        with open(filepath, "wb") as file:
            file.write(req.content)
        logger.info(f"File saved with name: {filename} | {log_id}")

    except HTTPError as e:
        logger.critical(
            f"HTTPError with status code: {e.response.status_code} | {log_id}",
            exc_info=True,
        )
        raise Retry("Error while download file")

    except ConnectTimeout as e:
        logger.critical(f"Connection timeout | {log_id}")
        raise Retry("Error while download file")

    else:
        return filepath


def transcribe_file(self: Task, audiopath: str, log_id: str = None) -> list[str]:
    try:
        audio = read_audio(audiopath)
        logger.info(f"Read audio from path: {audiopath} | {log_id}")

        logger.info(f"Start transcribing | {log_id}")
        self.update_state(state=StatesTasks.decoding.value)

        phrases: list[TextPhrase] = pipeline.forward_offline(audio)
        logger.info(f"Pipeline created succesfully | {log_id}")

        text: list[str] = []
        logger.info(f"Append list with phrases | {log_id}")
        for phrase in phrases:
            text.append(phrase.text)

        return text

    except DecodeError:
        logger.critical(f"{audiopath} doesn`t readable | {log_id}")
        if validate_audio_file(audiopath):
            remove(audiopath)
        self.update_state(state=StatesTasks.decode_exc.value)
        raise Reject("Decoding error")

    # Т.к. могут возникнуть разные ошибки во время транскрибации (чтобы не лезть в библиотеку и не высматривать всевозможные ошибки)
    except Exception:
        logger.critical(f"Unknown exception | {log_id}", exc_info=True)
        self.update_state(state=StatesTasks.unknown.value)
        raise Retry("Unknown exception")


def callback_result_to_url(
    self: Task, callback_url: str, result: list[str], log_id: str = None
) -> None:
    if callback_url:
        response = requests.post(callback_url, json=result)

        try:
            response.raise_for_status()
            logger.info(f"Data was successfully return to: {callback_url} | {log_id}")
            self.update_state(state=StatesTasks.callback.value)

        except HTTPError as e:
            logger.warning(
                f"HTTP Error with status code: {e.response.status_code} | {log_id}",
                exc_info=True,
            )

        except ConnectTimeout:
            logger.warning(f"Connection Timeout | {log_id}")


@app.task(bind=True, track_started=True, max_retries=3, default_retry_delay=30)
def trancribe(
    self: Task, audio_location: str, callback_url: str, log_id: str = None
) -> list[str]:
    if "://" in audio_location:  # т.к. в названии файла символов быть не может
        audio_location = download_file(self, audio_location, log_id)

    result = transcribe_file(self, audio_location, log_id)

    if callback_url != "":
        callback_result_to_url(self, callback_url, result, log_id)

    if validate_audio_file(audio_location):
        logger.info(f"Delete file after get result | {log_id}")
        remove(audio_location)

    return result


@after_setup_task_logger.connect()
def init_pipeline_and_tasks(sender=None, **kwargs):
    logger.info("Startup")
    global pipeline

    if pipeline is None:
        pipeline = create_pipeline()
        logger.info("CTCPipeline initialized")

    logger.info("Startup backup tasks")
    load_backups()
