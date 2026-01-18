import logging
from logging.handlers import RotatingFileHandler
from enum import Enum

# Настройки логгирования
logger = logging.getLogger("App")
logger.level = logging.INFO  # Уровень логирования

handler = RotatingFileHandler(
    filename="app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s %(levelname)s -- %(funcName)s(%(lineno)d) - %(message)s"
)
handler.setFormatter(formatter)

logger.addHandler(handler)


# Разрешеные форматы данных
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac"}


class StatesAPI(Enum):
    success = "Success"
    fail = "Fail"
    error = "Error"


class StatesTasks(Enum):
    download = "Download file from URL"
    decoding = "Start decode file"
    callback = "Result was callbacked"
    success = "SUCCESS"

    decode_exc = "Decoding error"
    unknown = "Unknown error while decoding"
