# Обзор системы

Сервис предоставляет API для распознавания объектов на фотографиях и видео. Система состоит из следующих компонентов:

* **API Gateway:** принимает запросы от пользователей на анализ фотографий или видео.


* **FFmpeg Worker:** обрабатывает загруженные видео, разбивает их на сцены и извлекает кадры для распознавания.


* **Recognition Worker:** выполняет распознавание объектов на изображениях (как на загруженных фотографиях, так и на кадрах из видео).


* **Хранилище S3:** сохраняет входные файлы, промежуточные и итоговые результаты.


* **Очереди RabbitMQ:** координируют обработку задач между компонентами системы.


* **База данных Postgres:** хранит информацию о задачах, сегментах и результатах распознавания.

## Запуск системы

Выполнить команду 
`docker-compose up -d`

Все необходимые таблицы, бакеты и очереди будут созданы автоматически.

Сервис работает как с GPU через CUDA, так и с CPU.

Swagger доступен по адресу 
[http://localhost:8000/docs/](http://localhost:8000/docs/)

Minio S3
[http://localhost:9001/browser](http://localhost:9001/browser)
`minioadmin` / `minioadmin`

RabbitMQ
[http://127.0.0.1:15672/#/queues](http://127.0.0.1:15672/#/queues)
`guest` / `guest`

Тестовые фото и видео в папке `_samples`

## Взаимодействие компонентов

**Загрузка файла:**

Пользователь отправляет фотографию или видео на эндпоинт `/analysis` API Gateway.
Файл сохраняется в S3, и создаётся задача в базе данных.
В зависимости от типа файла, задача отправляется либо в `video_processing_queue`, либо напрямую в `recognition_queue`.

**Обработка фотографии:**

* Если загружена фотография, API Gateway отправляет сообщение в `recognition_queue`.
* Recognition Worker получает сообщение, скачивает фотографию из S3 и выполняет распознавание.
* Результаты сохраняются в базе данных и S3.

**Обработка видео:**

* Если загружено видео, API Gateway отправляет сообщение в `video_processing_queue`.
* FFmpeg Worker получает сообщение, скачивает видео из S3 и разбивает его на сцены.
* Из каждой сцены извлекается кадр (средний по времени), который сохраняется в S3.
* Для каждого кадра создаётся задача и сообщение отправляется в `recognition_queue`.
* Recognition Worker обрабатывает кадры аналогично фотографиям.

**Получение результатов:**

Пользователь может получить статус задачи и результаты распознавания через API Gateway:
* GET `/analysis/{task_id}`: информация о задаче.
* GET `/analysis/{task_id}/segments`: список сегментов (кадров или сцен).
* GET `/analysis/{task_id}/segments/{segment_id}`: детали сегмента и результаты распознавания.

**Удаление результатов:**

Пользователь может удалить задачи, файлы и результаты распознавания через API Gateway:
* DELETE `/analysis/{task_id}`
 
### Хранилище S3

**Структура хранения:**

* `input-files/{task_id}/{filename}`: исходные файлы.
* `scene-images/{task_id}/image_{segment_id}.jpg`: извлечённые кадры.
* `recognition-results/{task_id}/{segment_id}_result.jpg`: изображения с результатами распознавания.

### Очереди RabbitMQ

**Очереди:**

* `video_processing_queue`: для задач по обработке видео.
* `recognition_queue`: для задач по распознаванию изображений.

### Таблицы базы данных

* `tasks`: список всех задач.
* `recognition_results`: результаты распознавания.
* `task_segments`: список сегментов.

### TODO

* Разделение логики между фото и видео
* Вынести из инференса ресайз изображений. Для фото в отдельный сервис, для кадров видео в сервис нарезки на сцены.
* Структуризация модулей сервисов
* Вынос routs в API в отдельные модули, версионирование методов
* Подумать над финальным статусом в Tasks, как собирать информацию о готовности всех сегментов
* Убрать весь хардкод, вынести все в переменные
* Подумать над более удачным методом удаления из S3
* Подобрать оптимальное значение в детектор сцен
* Улучшить обработку ошибок, включая HTTP коды
* Валидация входящих данных
* Добавить ретраи и подтверждения обработки
* Добавить подробное логирование и метрики 
* Вынос сервисов взаимодействия с S3/RMQ/DB в пакеты
* Система версионирования моделей
* Добавить пользователей и приоритезацию сообщений в очереди в зависимости от уровня
* Написать тесты и в целом потестировать, делал быстро, могут быть проблемы :)
