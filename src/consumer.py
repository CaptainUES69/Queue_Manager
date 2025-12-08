from os import getenv, remove
from os.path import exists, isfile

import requests
from celery import Celery
from celery.app.task import Task
from celery.exceptions import Reject, Retry
from dotenv import load_dotenv
from miniaudio import DecodeError
from requests.exceptions import RequestException
from tone import StreamingCTCPipeline, TextPhrase, read_audio

from src.conf import logger
from src.db_orm import get_all_celery_tasks, get_all_files_url, get_task

load_dotenv()
app = Celery(
    'consumer',
    # broker = f'amqp://{getenv('RABBIT_LOGIN')}:{getenv('RABBIT_PASSWORD')}@{getenv('RABBIT_HOST')}:{getenv('RABBIT_PORT')}/{getenv('RABBIT_VHOST')}',  # Адрес RabbitMQ
    broker = 'amqp://myadmin:mypassword@127.0.0.1:5672//',
    backend = f'db+{getenv('DBROOT')}'
)


def delete_task(task_id: str) -> None:
    result = app.AsyncResult(task_id)
    result.forget()
    logger.info(f'Delete task with id: {task_id}')


def startup_tasks() -> None:
    files = get_all_files_url()
    tasks = get_all_celery_tasks()

    for file in files:
        if file.task_id in tasks and get_task(file.task_id) == 'SUCCESS':
            logger.info(f'{file.task_id} was already executed')
            continue
        
        if file.file_path != None:
            if isfile(file.file_path) == False:
                logger.warning(f'file on {file.file_path} doesn`t exist')
                continue
            audio_to_text.apply_async(args = [file.file_path], task_id = file.task_id)
            logger.info(f'{file.file_path} was tasked with id: {file.task_id}')
        
        elif file.file_url != None:
            url_to_text.apply_async(args = [file.file_url, file.task_id], task_id = file.task_id)
            logger.info(f'{file.file_url} was tasked with id: {file.task_id}')

        else:
            logger.warning(f'file_path and file_url was None in: {file}')


@app.task(bind = True, track_started = True, max_retries = 3, default_retry_delay = 30)
def url_to_text(self: Task, file_url: str, id: str) -> list[str]:
    try:
        self.update_state(state = 'Downloading file')
        req = requests.get(file_url)

        filepath = f'{getenv("FILES_PATH")}/{id}'
        logger.debug(f'Get on url: {file_url}')
        logger.debug(f'File_path: {filepath}')
        
        self.update_state(state = 'Writing file')
        with open(filepath, "wb") as file:
            file.write(req.content)

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
    
    except RequestException:
        logger.critical('Exception while download data', exc_info = True)
        raise Retry('Error while making request')
    
    except PermissionError:
        logger.critical('Permission troubles check accesability')
        raise Retry('Permission troubles check accesability')
    
    except DecodeError:
        logger.critical(f'{filepath} doesn`t readable')
        if exists(filepath) and isfile(filepath):
            remove(filepath)
        raise Reject('Decoding error', requeue = False)

    # Т.к. могут возникнуть разные ошибки во время транскрибации (чтобы не лезть в библиотеку и не высматривать всевозможные ошибки)
    except Exception:
        logger.critical('Unknown exception', exc_info = True)
        raise Retry('Unknown exception')

    else:
        if exists(filepath) and isfile(filepath):
            remove(filepath)
        return text


@app.task(bind = True, track_started = True, max_retries = 3, default_retry_delay = 30) 
def audio_to_text(self: Task, filepath: str) -> list[str]:
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

        self.update_state(state = 'Creating result')
        text: list[str] = []
        logger.info('Append list with phrases')
        for phrase in phrases:
            text.append(phrase.text)
    
    except DecodeError:
        logger.critical(f'{filepath} doesn`t readable')
        if exists(filepath) and isfile(filepath):
            remove(filepath)
        raise Reject('Decoding error', requeue = False)

    # Т.к. могут возникнуть разные ошибки во время транскрибации (чтобы не лезть в библиотеку и не высматривать всевозможные ошибки)
    except Exception: 
        logger.critical('Unknown exception', exc_info = True)
        raise Retry('Unknown exception')
    
    else:
        if exists(filepath) and isfile(filepath):
            remove(filepath)
        return text


startup_tasks()
