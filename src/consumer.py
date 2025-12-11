from os import getenv, remove
from os.path import exists, isfile

import requests
from celery import Celery
from celery.app.task import Task
from celery.exceptions import Reject, Retry
from dotenv import load_dotenv
from miniaudio import DecodeError
from requests.exceptions import HTTPError
from tone import StreamingCTCPipeline, TextPhrase, read_audio

from src.conf import logger, States
from src.db_orm import get_all_celery_tasks, get_all_files_url, get_task, delete_task_backup, NoResultFound


load_dotenv(override = True)
app = Celery(
    'consumer',
    broker = f'amqp://{getenv('RABBIT_LOGIN')}:{getenv('RABBIT_PASSWORD')}@{getenv('RABBIT_HOST')}:{getenv('RABBIT_PORT')}/{getenv('RABBIT_VHOST')}',
    # broker = 'amqp://myadmin:mypassword@127.0.0.1:5672//',
    backend = f'db+{getenv('DBROOT')}'
)

app.conf.update(
    worker_concurrency = int(getenv('WORKERS_NUMBER')),
    worker_prefetch_multiplier = int(getenv('TASKS_IN_WORKER'))
)


def delete_task(task_id: str) -> None:
    result = app.AsyncResult(task_id)
    result.forget()
    logger.info(f'Delete task with id: {task_id}')


def startup_tasks() -> None:
    backups = get_all_files_url()
    tasks = get_all_celery_tasks()

    for backup in backups:
        if backup.task_id in tasks and get_task(backup.task_id) == 'SUCCESS':
            logger.info(f'{backup.task_id} was already executed')
            continue
        
        if (backup.file_url is None and backup.file_path is None):
            logger.warning(f'file_path and file_url was None in: {backup}')
            
        if isfile(backup.file_path) == False:
            logger.warning(f'file on {backup.file_path} doesn`t exist')
            try:
                delete_task_backup(backup.task_id)
                continue

            except NoResultFound:
                logger.critical('Strange backup row check table: files')
                continue
        
        filepath = backup.file_url or backup.file_path

        transcribation.apply_async(args = [filepath, backup.task_id, backup.callback_url], task_id = backup.task_id)
        logger.info(f'{filepath} was tasked with id: {backup.task_id}')


def download_file(self: Task, file_url: str, hash_id: str) -> str:
    try:
        self.update_state(state = States.DOWNLOAD)
        req = requests.get(file_url)
        req.raise_for_status()

        filepath = f'{getenv("FILES_PATH")}/{hash_id}'
        logger.debug(f'Get on url: {file_url}')
        logger.debug(f'File_path: {filepath}')
        
        self.update_state(state = 'Writing file')
        with open(filepath, "wb") as file:
            file.write(req.content)

    except HTTPError as e:
        logger.critical(f'HTTPError with status code: {e.response.status_code}', exc_info = True)
        self.update_state(state = f'{States.HTTP}: {e.response.status_code}')
        raise Retry('Error while processing request')
    
    else:
        return filepath


def file_to_text(self: Task, filepath: str) -> list[str]:
    try:
        audio = read_audio(filepath)
        logger.info(f'Read audio from path: {filepath}')
        
        logger.info('Start transcribing')
        self.update_state(state = States.DECODING)
        pipeline = StreamingCTCPipeline.from_local(getenv('MODEL_PATH'))
        logger.info('Pipeline created succesfully')
        phrases: list[TextPhrase] = pipeline.forward_offline(audio)
        
        text: list[str] = []
        logger.info('Append list with phrases')
        self.update_state(state = States.WRITE_RES)
        for phrase in phrases:
            text.append(phrase.text)
        
        return text
    
    except DecodeError:
        logger.critical(f'{filepath} doesn`t readable')
        if exists(filepath) and isfile(filepath):
            remove(filepath)
        self.update_state(state = States.DECODE_EXC)
        raise Reject('Decoding error')
    
    # Т.к. могут возникнуть разные ошибки во время транскрибации (чтобы не лезть в библиотеку и не высматривать всевозможные ошибки)
    except Exception:
        logger.critical('Unknown exception', exc_info = True)
        self.update_state(state = States.UNKNOWN)
        raise Retry('Unknown exception')


def callback_to_url(self: Task, callback_url: str, result: list[str]) -> None:
    if callback_url:
        response = requests.post(
            callback_url,
            json = result 
        )

        try:
            response.raise_for_status()
            self.update_state(state = States.CALLBACK)
            logger.info(f'Data was successfully return to: {callback_url}')

        except HTTPError as e:
            logger.warning(f'HTTPError with status code: {e.response.status_code}', exc_info = True)
            self.update_state(state = f'{States.HTTP}: {e.response.status_code}')


@app.task(bind = True, track_started = True, max_retries = 3, default_retry_delay = 30) 
def transcribation(self: Task, filepath: str, hash_id: str, callback_url: str) -> list[str]:
    if 'http' in filepath:
        filepath = download_file(self, filepath, hash_id) 

    result = file_to_text(self, filepath)
    
    if callback_url != '':
        callback_to_url(self, callback_url, result)
    
    if exists(filepath) and isfile(filepath):
        remove(filepath)

    return result


startup_tasks()
