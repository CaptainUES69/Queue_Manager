from os import getenv

from dotenv import load_dotenv
from fastapi import FastAPI, Response, status
from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from pika.adapters import BlockingConnection

from conf import logger
from db_orm import create_task, get_task_data


load_dotenv()
app = FastAPI()

conn_params = ConnectionParameters(
    host = getenv('RABBIT_HOST'),
    port = getenv('RABBIT_PORT'),
    credentials = PlainCredentials(getenv('RABBIT_LOGIN'), getenv('RABBIT_PASSWORD'))
)


def publish(
    data, 
    queue_name: str = 'messages', 
    routing_key: str = 'message'
) -> None:
    with BlockingConnection(conn_params) as conn:
        with conn.channel() as ch:
            ch.queue_declare(queue = queue_name)
            ch.basic_publish(
                exchange = '',
                routing_key = routing_key,
                body = f'{data}',
            )
            logger.info('Message delivered')


@app.post(path = '/task', tags = ['Produce new task'])
async def produce_task(url: str):
    try:
        if not url:
            logger.warning(f'Url is empty')
            return Response(content = 'Url is empty', status_code = status.HTTP_400_BAD_REQUEST)
        
        publish(url)
        create_task(url)
        return Response(content = 'Task produced', status_code = status.HTTP_201_CREATED)

    except Exception:
        logger.critical('Critical error while producing_task', exc_info = True)


@app.get(path = '/status/', tags = ['Get process status'])
async def process_status(process_ID: int):
    if not process_ID:
        return Response(content = 'process_id = None', status_code = status.HTTP_400_BAD_REQUEST)
        
    data = get_task_data(process_ID)
    if data[1] != None:
        return Response(
            content = {
                'data': f'{data[1]}'
            }, 
            status_code = status.HTTP_200_OK
        )

    return Response(
            content = {
                'data': f'{data[0]}'
            }, 
            status_code = status.HTTP_200_OK
        )
