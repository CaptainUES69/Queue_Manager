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

from src.conf import logger
from src.db_orm import get_all_celery_tasks, get_all_files_url, get_task, delete_task_backup, NoResultFound

load_dotenv()
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
        
        if backup.file_path != None:
            if isfile(backup.file_path) == False:
                logger.warning(f'file on {backup.file_path} doesn`t exist')
                try:
                    delete_task_backup(backup.task_id)
                    continue

                except NoResultFound:
                    logger.critical('Strange backup row check table: files')
                    continue

            audio_to_text.apply_async(args = [backup.file_path, backup.callback_url], task_id = backup.task_id)
            logger.info(f'{backup.file_path} was tasked with id: {backup.task_id}')
        
        elif backup.file_url != None:
            url_to_text.apply_async(args = [backup.file_url, backup.task_id, backup.callback_url], task_id = backup.task_id)
            logger.info(f'{backup.file_url} was tasked with id: {backup.task_id}')

        else:
            logger.warning(f'file_path and file_url was None in: {backup}')


def create_pipeline(self: Task, filepath: str) -> list[str]:
    try:
        audio = read_audio(filepath)
        logger.info(f'Read audio from path: {filepath}')

        # Ссылка на файлы моделей
        if isfile(f'{getenv('MODEL_PATH')}/kenlm.bin') == False or isfile(f'{getenv('MODEL_PATH')}/model.onnx') == False: 
            logger.critical('Models files doesn`t exists')
            raise Retry('Models files doesn`t exists')
        
        logger.info('Start creating pipeline')
        self.update_state(state = 'Starting decode file')
        pipeline = StreamingCTCPipeline.from_local(getenv('MODEL_PATH'))
        logger.info('Pipeline created succesfully')
        phrases: list[TextPhrase] = pipeline.forward_offline(audio)
        
        text: list[str] = []
        logger.info('Append list with phrases')
        self.update_state(state = 'Creating result')
        for phrase in phrases:
            text.append(phrase.text)
        
        return text
    
    except DecodeError:
        logger.critical(f'{filepath} doesn`t readable')
        if exists(filepath) and isfile(filepath):
            remove(filepath)
        self.update_state(state = 'Decoding error')
        raise Reject('Decoding error')
    
    # Т.к. могут возникнуть разные ошибки во время транскрибации (чтобы не лезть в библиотеку и не высматривать всевозможные ошибки)
    except Exception:
        logger.critical('Unknown exception', exc_info = True)
        self.update_state(state = 'Unknown internal error')
        raise Retry('Unknown exception')


def return_data(self: Task, text: list[str], filepath: str, callback_url: str | None) -> list[str]:
    if callback_url != None:
        response = requests.post(
            callback_url,
            json = text 
        )
        try:
            response.raise_for_status()
            self.update_state(state = 'Callback_url')

        except HTTPError as e:
            logger.warning(f'HTTPError with status code: {e.response.status_code}', exc_info = True)
            self.update_state(state = f'HTTPError with status code: {e.response.status_code}')

    if exists(filepath) and isfile(filepath):
        remove(filepath)
    return text


@app.task(bind = True, track_started = True, max_retries = 3, default_retry_delay = 30)
def url_to_text(self: Task, file_url: str, id: str, callback_url: str | None = None) -> list[str]:
    try:
        self.update_state(state = 'Downloading file')
        req = requests.get(file_url)
        req.raise_for_status()

    except HTTPError as e:
        logger.critical(f'HTTPError with status code: {e.response.status_code}', exc_info = True)
        self.update_state(state = f'HTTPError with status code: {e.response.status_code}')
        raise Retry('Error while processing request')
    
    try:
        filepath = f'{getenv("FILES_PATH")}/{id}'
        logger.debug(f'Get on url: {file_url}')
        logger.debug(f'File_path: {filepath}')
        
        self.update_state(state = 'Writing file')
        with open(filepath, "wb") as file:
            file.write(req.content)

        text = create_pipeline(self, filepath)
        
    except PermissionError:
        logger.critical('Permission troubles check accesability')
        self.update_state(state = 'Permission error')
        raise Reject('Permission troubles check accesability')

    else:
        return return_data(self, text, filepath, callback_url)


@app.task(bind = True, track_started = True, max_retries = 3, default_retry_delay = 30) 
def audio_to_text(self: Task, filepath: str, callback_url: str | None = None) -> list[str]:
    text = create_pipeline(self, filepath)

    return return_data(self, text, filepath, callback_url)


startup_tasks()
