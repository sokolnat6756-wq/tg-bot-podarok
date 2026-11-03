# Деплой на облачный сервер Timeweb (VPS)

Этот бот рассчитан на **облачный сервер** (виртуальную машину), а не на App Platform.  
Для доступа к Telegram/OpenAI удобно выбрать локацию **Нидерланды** (или другой зарубежный регион) в панели Timeweb Cloud → Облачные серверы.

Режим работы бота: **polling** (сам опрашивает Telegram). Отдельный домен и webhook не нужны.

## Что понадобится

1. Облачный сервер Timeweb (Ubuntu 22.04/24.04), регион **Netherlands** / Нидерланды
2. Файл проекта на сервере (`Dockerfile`, `docker-compose.yml`, папка `bot/`, `run.py`, `requirements.txt`)
3. Файл **`.env` только на сервере** с секретами (не в GitHub)

## Секреты в `.env` на сервере

Создайте на сервере файл `.env` рядом с `docker-compose.yml`:

```
BOT_TOKEN=ваш_токен_бота
OPENAI_API_KEY=ваш_ключ_openai
```

По желанию:

```
OPENAI_MODEL=gpt-6-luna
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_SIZE=1024x1536
OPENAI_IMAGE_QUALITY=medium
CARD_HOURLY_LIMIT=5
PORT=8080
```

Файл `.env` уже в `.gitignore` — в репозиторий он не должен попадать.

## Установка на сервер (Docker)

На чистом Ubuntu обычно достаточно:

1. Подключиться к серверу по SSH
2. Установить Docker и Docker Compose (по документации Docker / Timeweb)
3. Скопировать проект на сервер (git clone или загрузка архива **без** локального `.env` из Windows, либо создать `.env` заново на сервере)
4. В папке проекта создать `.env` с `BOT_TOKEN` и `OPENAI_API_KEY`
5. Запустить:

```bash
docker compose up -d --build
```

6. Смотреть логи:

```bash
docker compose logs -f bot
```

Должно появиться сообщение вроде: `Бот запущен (polling)`.

7. В Telegram написать боту `/start`

Остановить:

```bash
docker compose down
```

Обновить код и перезапустить:

```bash
git pull
docker compose up -d --build
```

## Важно

- Перед запуском в облаке **остановите бота на своём компьютере**. Иначе будет ошибка Conflict (два polling с одним токеном).
- Нужен исходящий интернет с сервера до `api.telegram.org` и `api.openai.com`.
- Сессии пользователей и лимит открыток хранятся в памяти контейнера: после `restart` / нового деплоя сбрасываются.
- Если модель `gpt-image-2` недоступна аккаунту OpenAI — смените `OPENAI_IMAGE_MODEL` (например на `gpt-image-2.5-flare`).

## Проверка

- `docker compose ps` — контейнер в статусе running
- В браузере или через curl на сервере: `http://127.0.0.1:8080/health` → ответ `ok`
- В Telegram: подбор подарка и создание открытки

## Если без Docker

Можно вручную: Python 3.12, `pip install -r requirements.txt`, systemd-сервис с `python -u run.py` и переменными из `.env`. Для простоты на Timeweb VPS рекомендуется вариант с **Docker Compose** выше.
