# Queue_Manager
## Как запускать?
1) Скачать файлы (kenlm.bin и model.onnx) с https://huggingface.co/t-tech/T-one и положить их в папку models
2) Сделать docker image:
   ```cmd
   docker build -t queue --no-cache .
   ```
3) Запустить контейнер
   ```cmd
   docker-compose up
   ```

## Как открыть отладку?
1) Для FastAPI перейти по адресу: http://localhost:8000/docs#
2) Для RabbitMQ: http://localhost:33
