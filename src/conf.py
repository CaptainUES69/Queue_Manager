import logging
from dataclasses import dataclass
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


# Dataclass из библиотеки T-One для выходных данных
@dataclass 
class TextPhrase:
    text: str
    start_time: float
    end_time: float


def create_hash_id(input):
    return hash(input)