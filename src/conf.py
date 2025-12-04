import logging
import os
from logging.handlers import RotatingFileHandler


# Настройки логгирования
logger = logging.getLogger("App")
logger.level = logging.INFO # Уровень логирования

handler = RotatingFileHandler(
    filename = 'app.log',
    maxBytes = 5 * 1024 * 1024,
    backupCount = 5,
    encoding = 'utf-8'
)

formatter = logging.Formatter('%(asctime)s %(levelname)s -- %(funcName)s(%(lineno)d) - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)


def delete_file(file_path: str):
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f'file from: {file_path}. deleted correctly')

    else:
        logger.warning(f'file path: {file_path}. doesn`t exist')
        raise FileNotFoundError
    