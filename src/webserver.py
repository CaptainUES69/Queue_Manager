import pickle
import shutil
import uuid
from os.path import isfile, splitext
from pathlib import Path
from typing import Optional

import requests
from fastapi import BackgroundTasks, FastAPI, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, AnyHttpUrl

from src.conf import ALLOWED_AUDIO_EXTENSIONS, StatesAPI, StatesTasks, logger
from src.tasks import delete_task, transcribation_task
from src.db_orm import CeleryTasks, TableManager
from urllib.parse import unquote

app = FastAPI()


class ResponseData(BaseModel):
    status: str
    data: str | list[str]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    'status': StatesAPI.success.value,
                    'data': 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
                },
                {
                    'status': StatesAPI.success.value,
                    'data': [
                        ['text'], 
                        ['from file']
                    ]
                }
            ]
        }
    }

class ResponseError(BaseModel):
    status: str
    message: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    'status': StatesAPI.error.value,
                    'message': 'Something about trouble'
                }
            ]
        }
    }


def audio_file_input(file: UploadFile, callback_url: str = None) -> JSONResponse:
    if splitext(file.filename)[1].lower() not in ALLOWED_AUDIO_EXTENSIONS:
        logger.warning('File type not allowed')
        return JSONResponse(
            content = {
                'status': StatesAPI.fail.value,
                'message': f'File type not allowed, allowed types: {ALLOWED_AUDIO_EXTENSIONS}'
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
                'status': StatesAPI.fail.value,
                'message': f'File already tasked with id: {_id}'
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
                    'status': StatesAPI.error.value,
                    'message': f'Unable to save received file {file_path} with task id: {custom_id}'
                },
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    transcribation_task.apply_async(args = [file_path, callback_url, custom_id], task_id = custom_id)
    logger.info(f'Task: {custom_id} and backup with same id created')

    return ResponseData(
        status = StatesAPI.success.value,
        data = f'Task id: {custom_id}'
    )


def audio_url_input(file_url: str, callback_url: str = None) -> JSONResponse:
    if not any(ext in file_url for ext in ALLOWED_AUDIO_EXTENSIONS):
        logger.warning(f'File type not allowed')
        return JSONResponse(
            content = {
                'status': StatesAPI.fail.value,
                'message': f'File type in url not allowed, allowed types: {ALLOWED_AUDIO_EXTENSIONS}'
            }, 
            status_code = status.HTTP_400_BAD_REQUEST
        ) 
    
    try:
        response = requests.head(file_url)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        if e.response: 
            return JSONResponse(
                content = {
                    'status': StatesAPI.error.value,
                    'message': f'URL doesn`t response correctly. status code: {e.response.status_code}'
                },
                status_code = status.HTTP_400_BAD_REQUEST
            )
        
        return JSONResponse(
            content = {
                'status': StatesAPI.error.value,
                'message': f'URL doesn`t response correctly. status code doesn`t exists'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )

    custom_id = str(uuid.uuid4())
    logger.debug(f'Created custom_id {custom_id}')

    _id = TableManager.create_task_backup(custom_id, file_url, callback_url = callback_url)
    if _id:
        return JSONResponse(
            content = {
                'status': StatesAPI.fail.value,
                'message': f'File already tasked with id: {_id}'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )
        
    transcribation_task.apply_async(args = [file_url, callback_url, custom_id], task_id = custom_id)
    logger.info(f'Task: {custom_id} and backup with same id created')

    return ResponseData(
        status = StatesAPI.success.value,
        data = f'Task id: {custom_id}'
    )


@app.post(
    path = '/transcribe_audio/create',
    tags = ['Produce new task'],
    responses = {
        status.HTTP_201_CREATED: {'model': ResponseData, 'description': 'Task created'},
        status.HTTP_400_BAD_REQUEST: {'model': ResponseError, 'description': 'Something about trouble'}
    },
    status_code = status.HTTP_201_CREATED
)
async def transcribation_task(
    audio_file: Optional[UploadFile] = File(
        None,
        description = "File to transcribe"
    ), 
    audio_url: Optional[str] = Form(
        None, 
        examples = ['https://example.com/audio.mp3'],
        description = 'File download URL'
    ), 
    callback_url: Optional[str] = Form(
        None, 
        examples = ["https://example.com/webhook"],
        description = 'Return data URL'
    )
) -> ResponseData | ResponseError:    
    if (not audio_file and not audio_url) or (audio_file and audio_url):
        return JSONResponse(
            content = {
                'status': StatesAPI.error.value,
                'message': 'Need to specify either the file or the URL'
            },
            status_code = status.HTTP_400_BAD_REQUEST
        )
    
    if callback_url:
        validated = AnyHttpUrl(callback_url) # Если не провалидирует то вернет ошибку 422
        callback_url = unquote(callback_url)

    if audio_file:
        return audio_file_input(audio_file, callback_url)

    else:
        validated = AnyHttpUrl(audio_url) # Если не провалидирует то вернет ошибку 422
        return audio_url_input(unquote(audio_url), callback_url)


@app.get(path = '/transcribe_audio/get_data',
    tags = ['Get data from task'],
    responses = {
        status.HTTP_200_OK: {'model': ResponseData, 'description': 'Return data from task'},
        status.HTTP_404_NOT_FOUND: {'model': ResponseError, 'description': 'Task doesn`t exists'}
    }
)
async def get_data_from_task(task_id: str, bg: BackgroundTasks) -> ResponseData | ResponseError:
    task = TableManager.get_task(task_id, CeleryTasks)
    if not task:
        logger.warning(f'Task with id: {task_id} was not found')
        return JSONResponse(
            content = {
                'status': StatesAPI.error.value,
                'message': f'Task with id: {task_id} was not found'
            },
            status_code = status.HTTP_404_NOT_FOUND
        )

    if task.status == StatesTasks.SUCCESS.value:
        bg.add_task(delete_task, task_id)
        bg.add_task(TableManager.delete_task_backup, task_id)

        logger.info(f'Return result of task with id: {task_id}')
        return ResponseData(
            status = StatesAPI.success.value, 
            data = pickle.loads(task.result)
        )
    
    logger.info(f'Return status of task with id: {task_id}')
    return ResponseData(
            status = StatesAPI.success.value, 
            data = task.status
        )
