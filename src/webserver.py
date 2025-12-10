import pickle
import shutil
import uuid
from os.path import isfile, splitext
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, NoResultFound

from src.conf import ALLOWED_AUDIO_EXTENSIONS, logger
from src.consumer import audio_to_text, delete_task, url_to_text
from src.db_orm import create_task_backup, delete_task_backup, get_task


app = FastAPI()


class UrlInput(BaseModel):
    task_id: str
    status: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    'task_id': 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
                    'status': 'QUEUED'
                }
            ]
        }
    }

class Error(BaseModel):
    error: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    'error': 'Something about trouble'
                }
            ]
        }
    }

class Payload(BaseModel):
    file_url: str
    callback_url: str | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    'file_url': 'http://download/link/file.mp3',
                    'callback_url': 'http://return_data_here'
                }
            ]
        }
    }

class GetInfo(BaseModel):
    message: str
    status: str
    result: list[str] | None


@app.post(path = '/task/produce/url', 
    tags = ['Produce new task'],
    responses = {
        200: {'model': UrlInput, 'description': 'Task created'},
        400: {'model': Error, 'description': 'Trouble with input data (url or file type)'}
    }
)
async def url_to_task(payload: Payload) -> JSONResponse:
    if not payload.file_url:
        logger.warning(f'Url is empty')
        return JSONResponse(
            content = {
                'Error': 'Url is empty'
                }, 
            status_code = status.HTTP_400_BAD_REQUEST
        )
    
    can = False
    for ext in ALLOWED_AUDIO_EXTENSIONS:
        if ext in payload.file_url:
            can = True
            break
        continue

    if can == False:
        logger.warning(f'File type not allowed')
        return JSONResponse(
            content = {
                'Error': f'File type not allowed. Allowed types {ALLOWED_AUDIO_EXTENSIONS}'
                }, 
            status_code = status.HTTP_400_BAD_REQUEST
        )

    try:
        custom_id = str(uuid.uuid4())
        logger.debug(f'Created custom_id {custom_id}')
        create_task_backup(custom_id, 
            file_url = payload.file_url,
            callback_url = payload.callback_url
        )

    except IntegrityError:
        logger.info(f'Create custom_id again')
        custom_id = str(uuid.uuid4())
        create_task_backup(custom_id, 
            file_url = payload.file_url, 
            callback_url = payload.callback_url
        )
        
    url_to_text.apply_async(args = [payload.file_url, custom_id, payload.callback_url], task_id = custom_id)
    logger.info(f'Task and backup created')

    return JSONResponse(
        content = {
            'task_id': f'{custom_id}',
            'status': 'QUEUED'
        }, 
        status_code = status.HTTP_200_OK
    )


@app.post(path = '/task/produce/file', 
    tags = ['Produce new task'],
    responses = {
        200: {'model': UrlInput, 'description': 'Task created'},
        400: {'model': Error, 'description': 'Trouble with file type'}
    }
)
async def file_to_task(file: UploadFile = File(...), callback_url: Optional[str] = Form(None)) -> JSONResponse:
    if splitext(file.filename)[1].lower() not in ALLOWED_AUDIO_EXTENSIONS:
        logger.warning(f'File type not allowed')
        return JSONResponse(
            content = {
                'Error': f'File type not allowed. Allowed types {ALLOWED_AUDIO_EXTENSIONS}'
                }, 
            status_code = status.HTTP_400_BAD_REQUEST
        )

    upload_dir = Path('./src/files')
    upload_dir.mkdir(exist_ok = True)
    custom_id = str(uuid.uuid4())
    logger.debug(f'Created custom_id {custom_id}')

    file_path = f'{upload_dir}/{custom_id}'
    logger.info(f'filepath: {file_path}')
    with open(file_path, 'wb') as file_upload:
        shutil.copyfileobj(file.file, file_upload)
        logger.info('Created file backup')
    if isfile(file_path) == False:
        logger.critical(f'File doesn`t exist on path: {file_path}')
        return JSONResponse(
            content = {
                'Error': f'File doesn`t created {file_path} is None'
            },
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        if callback_url == None or callback_url == '':
            create_task_backup(custom_id, file_path = file_path)

        else:
            create_task_backup(custom_id, 
                file_path = file_path, 
                callback_url = callback_url
            )

    except IntegrityError:
        logger.info(f'Create custom_id again')
        custom_id = str(uuid.uuid4())
        if callback_url == None or callback_url == '':
            create_task_backup(custom_id, file_path = file_path)

        else:
            create_task_backup(custom_id, 
                file_path = file_path, 
                callback_url = callback_url
            )

    audio_to_text.apply_async(args = [file_path, callback_url], task_id = custom_id)
    
    logger.info(f'Task and backup created')

    return JSONResponse(
        content = {
            'task_id': f'{custom_id}',
            'status': 'QUEUED'
        },
        status_code = status.HTTP_200_OK
    )


@app.get(path = '/task/get',
    tags = ['Get data from task'],
    responses = {
        200: {'model': GetInfo, 'description': 'Return data from task'},
        400: {'model': Error, 'description': 'Task_id not implemented'},
        404: {'model': Error, 'description': 'Task doesn`t exists'}
    }
)
async def get_data_from_task(task_id: str, bg: BackgroundTasks) -> JSONResponse:
    if task_id == None:
        logger.warning('Task_id not implemented')
        return JSONResponse(
            content = {
                'Error': 'Task_id not implemented'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )

    try:
        task = get_task(task_id)

        if task.result != None and task.status == 'SUCCESS':
            bg.add_task(delete_task, task_id)
            bg.add_task(delete_task_backup, task_id)
    
            logger.info(f'Return result of task with id: {task_id}')
            return JSONResponse(
                content = {
                    'message': f'Result from task {task_id}',
                    'status': task.status,
                    'result': pickle.loads(task.result)
                },
                status_code = status.HTTP_200_OK
            )
        
        logger.info(f'Return status of task with id: {task_id}')
        return JSONResponse(
            content = {
                'message': f'Status of task with id: {task_id}',
                'status': task.status,
                'result': None
            },
            status_code = status.HTTP_200_OK
        )

    except NoResultFound:
        logger.warning('Task was not found')
        return JSONResponse(
            content = {
                'Error': f'Task with id: {task_id} not found'
            },
            status_code = status.HTTP_404_NOT_FOUND
        )
