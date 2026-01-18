# Queue_Manager
Сервис по транскрибации аудио файлов с помощью библиотеки [T-One](https://github.com/voicekit-team/T-one).


## Как запускать?
1) Создать .env в корневой директории, настроить переменные.
   ```
   # Пример данных из .env.example
   # Настройки rabbit_mq
   RABBIT_LOGIN = 'quest'
   RABBIT_PASSWORD = 'quest'
   RABBIT_HOST = 'rabbitmq'
   RABBIT_PORT = '5672'
   RABBIT_VHOST = '/'

   # Настройки базы данных
   DBROOT = 'sqlite:///example.db'

   # Настройки Celery
   WORKERS_NUMBER = '5'
   TASKS_IN_WORKER = '2'

   # Настройки путей
   MODEL_PATH = './models'
   FILES_PATH = './src/files'
   ```
2) Сделать docker image:
   
   ```cmd
   docker build -t queue --no-cache .
   ```
   - Опционально можно скачать файлы [kenlm.bin](https://huggingface.co/t-tech/T-one/resolve/main/kenlm.bin), [model.onnx](https://huggingface.co/t-tech/T-one/resolve/main/model.onnx) и поместить их в папку указанную в MODEL_PATH для локального использования.
   
4) Запустить контейнер.
   ```cmd
   docker-compose up
   ```
5) Дождаться полной инициализации всех сервисов.
   
   Celery может долго запускаться из-за инициализации CTCPipeline, который отвечает за преобразование аудио в текст, но т.к. вебсервер запускается одновременно с celery может возникнуть проблема, что задача уже отправилась на сервис, а сам сервис еще полноценно не [включен](#известные-ошибки).


## Как открыть swagger`ы?
1) Для FastAPI перейти по адресу: http://localhost:8000/docs#.
2) Для RabbitMQ: http://localhost:15672.


## Как можно протестировать транскрибацию вручную?
1) Воспользоваться swagger.

   Перейти на http://localhost:8000/docs# или ваш домен, на котором находится сервис и ручкой /docs#, далее в swagger можно потестировать отправку данных, через интерфейс, добавить нужный файл или ссылку на него, а также [протестировать отправку](https://requestcatcher.com) callback`ов.

2) С помощью CURL запросов на домен на котором находится сервис.

   Отправка аудиофайла
   ```bash
   curl -X POST "http://localhost:8000/transcribe_audio/create" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "audio_file=@/path/to/your/audio.wav" \
     -F "callback_url=https://your-webhook-url.com"
   ```

   Отправка URL на аудиофайл
   ```bash
   curl -X POST "http://localhost:8000/transcribe_audio/create" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "audio_url=https://example.com/audio.wav" \
     -F "callback_url=https://your-webhook-url.com"
   ```

   Получение результата задачи
   ```bash
   curl -X GET "http://localhost:8000/transcribe_audio/get_data?task_id=ваш_task_id" \
     -H "accept: application/json"
   ```
   

## Известные ошибки
1) Бесконечная инициализация pipeline при скачивании с HuggingFace.

   Возможная причина это ошибка на стороне HuggingFace т.к. скачивание больших файлов без VPN из России, почему-то вызывает ошибку которая понижает скорость скачивания до 0 bit/s, рекомендуется либо использовать VPN или скачать модель заранее и положить в ```./models``` файлы ```kenlm.bin``` и ```model.onxx```.

2) ERROR: failed to build: did not complete successfully: exit code: 100.

   Такое иногда возникает при построении образа, зачастую обычный повторный запуск сборки образа помогает решить проблему.

3) 500 код ошибки при отправке любых данных на endpoint.

   Может быть вызвано тем, что celery не до конца запустился, данные будут обработаны сразу после полного запуска celery. Планируется изменение, для запуска веб-приложения только после полной инициализации celery, во избежания этой проблемы в будущем.
