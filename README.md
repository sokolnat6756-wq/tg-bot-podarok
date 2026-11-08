# Подбери идеальный подарок

Telegram-бот: подбор подарков по кнопкам + персональные поздравительные открытки через OpenAI. Регистрация пользователей не нужна.

## Что умеет бот

1. `/start` — приветствие и кнопки
2. Опрос: кому, пол, возраст, повод, бюджет, интересы → 3 идеи подарков
3. После выбора **пола, возраста и повода** — предложение создать открытку
4. Пожелание бот пишет сам; у пользователя спрашивается только **имя**
5. Фон через OpenAI Images (по умолчанию `gpt-image-2`), текст имени и поздравления накладывается отдельно (кириллица, переносы)
6. «Другие варианты» подарков без повторов; сессии пользователей изолированы
7. Свободный текст — ответ через текстовую модель OpenAI

## Быстрый старт на компьютере

1. Создайте бота у [@BotFather](https://t.me/BotFather) и скопируйте токен
2. Создайте ключ на [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
3. Подготовьте окружение:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

4. В локальный файл **`.env`** добавьте (значения не публикуйте):

```
BOT_TOKEN=ваш_токен_от_BotFather
OPENAI_API_KEY=ваш_ключ_openai
```

По желанию:

```
OPENAI_MODEL=gpt-6-luna
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_SIZE=1024x1536
OPENAI_IMAGE_QUALITY=medium
CARD_HOURLY_LIMIT=5
CARD_OUTPUT_WIDTH=1080
CARD_OUTPUT_HEIGHT=1920
```

5. Запуск:

```powershell
python run.py
```

Файл `.env` в `.gitignore` — в GitHub не попадёт.

## Открытки: как это устроено

- Запрос к Images API идёт в вертикальном размере `1024x1536` (поддерживаемый портрет API; точные 9:16 у API обычно нет)
- Готовый фон **без текста** вписывается в холст **1080×1920 (9:16)** без обрезки (поля + мягкий фон)
- Имя и поздравление рисуются поверх через Pillow и шрифт с кириллицей
- Одновременно у одного пользователя не может идти две генерации
- `CARD_HOURLY_LIMIT` — сколько открыток на пользователя за скользящий час; счётчик **в памяти** и **сбрасывается при перезапуске** бота

Доступ модели `gpt-image-2` к вашему аккаунту из этого проекта **не проверялся**. Если API вернёт ошибку модели — смените `OPENAI_IMAGE_MODEL` на доступную вам (например `gpt-image-2.5-flare`).

## Деплой на VPS (Timeweb, Амстердам)

Подробная инструкция: **[DEPLOY_TIMEWEB.md](DEPLOY_TIMEWEB.md)**.

Кратко:
1. VPS Ubuntu + Docker
2. Загрузить проект **без** `.env`
3. На сервере создать `.env` (`BOT_TOKEN`, `OPENAI_API_KEY`)
4. `docker compose up -d --build`
5. Локального бота на ПК остановить

Сессии и лимиты открыток в памяти: после перезапуска контейнера сбрасываются.

## Структура

```
Dockerfile / docker-compose.yml / .dockerignore / requirements.txt / .env.example / run.py
DEPLOY_TIMEWEB.md        — деплой на облачный сервер Timeweb (VPS, Нидерланды)
bot/
  main.py, handlers.py, keyboards.py, gifts.py, session.py
  config.py, ai.py, images.py, card_compose.py, limits.py
tests/check_readiness.py
```

## Проверка

```powershell
python tests\check_readiness.py
```

В Telegram: `/start` → «Подобрать подарок» → до повода → согласие на открытку → имя → получить картинку → продолжить бюджет/интересы.

## Секреты

Не публикуйте `.env`, токены и ключи. При утечке — перевыпустите в BotFather и в кабинете OpenAI.
