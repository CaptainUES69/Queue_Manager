import pickle
import shutil
import uuid
from os.path import isfile, splitext
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.conf import ALLOWED_AUDIO_EXTENSIONS, logger
from src.consumer import transcribation, delete_task
from src.db_orm import TableManager, CeleryTasks


app = FastAPI()


class ResponseID(BaseModel):
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

class ResponseResult(BaseModel):
    message: str
    status: str
    result: list[str] | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    'message': 'Result from task wuth id: 123123123123',
                    'status': 'SUCCESS',
                    'result': ['some', 'example', 'text']
                }
            ]
        }
    }

class Payload(BaseModel):
    file_url: str
    callback_url: Optional[str] = None

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


@app.post(path = '/task/produce/url', 
    tags = ['Produce new task'],
    responses = {
        200: {'model': ResponseID, 'description': 'Task created'},
        400: {'model': Error, 'description': 'Trouble with input data (url or file type)'}
    }
)
async def url_to_task(payload: Payload) -> JSONResponse:
    if not any(ext in payload.file_url for ext in ALLOWED_AUDIO_EXTENSIONS):
        logger.warning(f'File type not allowed')
        return JSONResponse(
            content = {
                'Error': f'File type not allowed. Allowed types {ALLOWED_AUDIO_EXTENSIONS}'
                }, 
            status_code = status.HTTP_400_BAD_REQUEST
        ) 
    
    custom_id = str(uuid.uuid4())
    logger.debug(f'Created custom_id {custom_id}')

    _id = TableManager.create_task_backup(custom_id, payload.file_url, callback_url = payload.callback_url)
    if _id:
        return JSONResponse(
            content = {
                'Error': f'URL already tasked with id {_id}'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )
        
    transcribation.apply_async(args = [payload.file_url, payload.callback_url, custom_id], task_id = custom_id)
    logger.info(f'Task: {custom_id} and backup with same id created')

    return JSONResponse(
        content = {
            'task_id': custom_id,
            'status': 'QUEUED'
        }, 
        status_code = status.HTTP_200_OK
    )


@app.post(path = '/task/produce/file', 
    tags = ['Produce new task'],
    responses = {
        200: {'model': ResponseID, 'description': 'Task created'},
        400: {'model': Error, 'description': 'Something about trouble'}
    }
)
async def file_to_task(file: UploadFile = File(...), callback_url: Optional[str] = Form(None)) -> JSONResponse:
    if splitext(file.filename)[1].lower() not in ALLOWED_AUDIO_EXTENSIONS:
        logger.warning('File type not allowed')
        return JSONResponse(
            content = {
                'Error': f'File type not allowed. Allowed types {ALLOWED_AUDIO_EXTENSIONS}'
                }, 
            status_code = status.HTTP_400_BAD_REQUEST
        )

    upload_dir = Path('./src/files')
    upload_dir.mkdir(exist_ok = True)
    custom_id = str(uuid.uuid4())
    file_path = f'{upload_dir}/{file.filename}'
    logger.debug(f'Created custom_id {custom_id}')

    _id = TableManager.create_task_backup(custom_id, file_path = file_path, callback_url = callback_url)
    if _id:
        return JSONResponse(
            content = {
                'Error': f'File already tasked with id {_id}'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )
    
    else:
        logger.info(f'filepath: {file_path}')
        with open(file_path, 'wb') as file_upload:
            shutil.copyfileobj(file.file, file_upload)
            
        if not isfile(file_path):
            logger.critical(f'Unable to save received file: {file_path} with task id: {custom_id}')
            return JSONResponse(
                content = {
                    'Error': f'Unable to save received file {file_path} with task id: {custom_id}'
                },
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    transcribation.apply_async(args = [file_path, callback_url, custom_id], task_id = custom_id)
    logger.info(f'Task: {custom_id} and backup with same id created')

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
        200: {'model': ResponseID, 'description': 'Return data from task'},
        400: {'model': Error, 'description': 'Task_id not implemented'},
        404: {'model': Error, 'description': 'Task doesn`t exists'}
    }
)
async def get_data_from_task(task_id: str, bg: BackgroundTasks) -> JSONResponse:
    if task_id == None:
        return JSONResponse(
            content = {
                'Error': 'Task_id not implemented'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )

    task = TableManager.get_task(task_id, CeleryTasks())
    if not task:
        logger.warning(f'Task with id: {task_id} was not found')
        return JSONResponse(
            content = {
                'Error': f'Task with id: {task_id} not found'
            },
            status_code = status.HTTP_404_NOT_FOUND
        )

    if task.result and task.status == 'SUCCESS':
        bg.add_task(delete_task, task_id)
        bg.add_task(TableManager.delete_task_backup, task_id)

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
