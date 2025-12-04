import time
from os import getenv

from celery import Celery
from dotenv import load_dotenv
from tone import StreamingCTCPipeline, TextPhrase, read_audio
import requests

from src.db_orm import get_all_celery_tasks, get_all_files_url, get_task


load_dotenv()
app = Celery(
    'consumer',
    broker = f'amqp://{getenv('RABBIT_LOGIN')}:{getenv('RABBIT_PASSWORD')}@{getenv('RABBIT_HOST')}:{getenv('RABBIT_PORT')}/{getenv('RABBIT_VHOST')}',  # Адрес RabbitMQ
    backend = f'db+{getenv('DBROOT')}'
)


def delete_task(task_id: str) -> None:
    result = app.AsyncResult(task_id)
    result.forget()
    return True


def startup_tasks():
    files = get_all_files_url()
    tasks = get_all_celery_tasks()

    for file in files:
        if file.task_id in tasks and get_task(file.task_id) == 'SUCCESS':
            continue
        
        if file.file_path != None:
           audio_to_text.apply_async(args = [file.file_path], task_id = file.task_id)
        
        elif file.file_url != None:
            url_to_text.apply_async(args = [file.file_path, file.task_id], task_id = file.task_id)
        

@app.task(track_started = True)
def url_to_text(file_url: str, id: str):
    req = requests.get(file_url)
    path = f'{getenv("FILES_PATH")}/{id}'
    
    with open(path, "wb") as file:
        file.write(req.content)

    audio = read_audio(path)
    # pipeline = StreamingCTCPipeline.from_hugging_face()
    pipeline = StreamingCTCPipeline.from_local(getenv('MODEL_PATH'))
    phrases: list[TextPhrase] = pipeline.forward_offline(audio)
    text = []
    for phrase in phrases:
        text.append(phrase.text)

    return text


@app.task(track_started = True)
def audio_to_text(filepath: str):
    audio = read_audio(filepath)
    # pipeline = StreamingCTCPipeline.from_hugging_face()
    pipeline = StreamingCTCPipeline.from_local(getenv('MODEL_PATH'))
    phrases: list[TextPhrase] = pipeline.forward_offline(audio)
    text = []
    for phrase in phrases:
        text.append(phrase.text)

    return text


startup_tasks()
