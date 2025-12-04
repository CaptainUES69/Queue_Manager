import pickle
import shutil
import uuid
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound

from src.conf import logger
from src.consumer import audio_to_text, delete_task, url_to_text
from src.db_orm import create_task_backup, delete_task_backup, get_task


load_dotenv()
app = FastAPI()

class Payload(BaseModel):
    file_url: str
    optional: str


@app.post(path = '/task/produce/url', tags = ['Produce new task'])
async def produce_task_with_url(payload: Payload):
    if not payload.file_url:
        logger.warning(f'Url is empty')
        return JSONResponse(
            content = {
                'Error':'Url is empty'
                }, 
            status_code = status.HTTP_400_BAD_REQUEST
        )
    
    custom_id = str(uuid.uuid4())
    create_task_backup(custom_id, file_url = payload.file_url, file_path = f'{getenv("FILES_PATH")}/{custom_id}')
    url_to_text.apply_async(args = [payload.file_url, custom_id], task_id = custom_id)
    
    return JSONResponse(
        content = {
            'task_id': f'{custom_id}',
            'status': 'queued'
        }, 
        status_code = status.HTTP_201_CREATED
    )


@app.post(path = '/task/produce/file', tags = ['Produce new task'])
async def produce_task_with_file(file: UploadFile = File(...)):
    upload_dir = Path('./src/files')
    upload_dir.mkdir(exist_ok = True)\
    
    file_path = f'{upload_dir}/{file.filename}'
    with open (file_path, 'wb') as file_upload:
        shutil.copyfileobj(file.file, file_upload)

    custom_id = str(uuid.uuid4())
    create_task_backup(custom_id, file_path = file_path)
    audio_to_text.apply_async(args = [file_path], task_id = custom_id)

    return JSONResponse(
        content = {
            'task_id': f'{custom_id}',
            'status': 'queued'
        },
        status_code = status.HTTP_201_CREATED
    )


@app.get(path = '/task/get', tags = ['Get data from task'])
async def get_data_from_task(task_id: str, bg: BackgroundTasks):
    if task_id == None:
        return JSONResponse(
            content = {
                'message': 'task_id == None, please input task_id in url',
                'status': None,
                'result': None
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )

    try:
        task = get_task(task_id)

        if task.result != None:
            bg.add_task(delete_task, task_id)
            bg.add_task(delete_task_backup, task_id)

            return JSONResponse(
                content = {
                    'message': f'Result from task {task_id}',
                    'status': None,
                    'result': pickle.loads(task.result)
                },
                status_code = status.HTTP_200_OK
            )
        
        return JSONResponse(
            content = {
                'message': f'Status of task {task_id}',
                'status': task.status,
                'result': None
            },
            status_code = status.HTTP_200_OK
        )

    except NoResultFound:
        return JSONResponse(
            content = {
                'message': f'Task with id: {task_id} not found',
                'status': None,
                'result': None
            },
            status_code = status.HTTP_404_NOT_FOUND
        )


