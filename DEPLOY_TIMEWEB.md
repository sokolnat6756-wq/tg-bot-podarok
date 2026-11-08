# Деплой бота на VPS (Timeweb, Амстердам)

Бот работает в режиме **polling**. Домен и webhook не нужны.

## Перед началом

1. Сервер уже создан (Ubuntu 24.04, 1 GB RAM — достаточно).
2. В панели есть: **IPv4**, команда `ssh root@ВАШ_IP`, root-пароль.
3. На компьютере **остановите** локальный `python run.py` (иначе Conflict).
4. Пароль и токены **не присылайте** в чат Cursor.

## Шаг 1. Подключитесь к серверу

На своём ПК (PowerShell или терминал):

```bash
ssh root@ВАШ_IP
```

Вставьте root-пароль из панели Timeweb (символы при вводе не отображаются — это нормально).

## Шаг 2. Установите Docker

На сервере:

```bash
curl -fsSL https://get.docker.com | sh
docker --version
docker compose version
```

Либо скопируйте и выполните `scripts/server-bootstrap.sh` из проекта.

## Шаг 3. Загрузите проект на сервер

### Вариант А — через GitHub (удобнее)

1. Закоммитьте и запушьте проект в GitHub **без** файла `.env`.
2. На сервере:

```bash
apt-get update && apt-get install -y git
mkdir -p /opt && cd /opt
git clone https://github.com/ВАШ_АККАУНТ/ВАШ_РЕПО.git tg-bot-podarok
cd tg-bot-podarok
```

### Вариант Б — архивом с компьютера

На **своём ПК** в папке проекта (PowerShell):

```powershell
# Создать архив без .env и .venv
tar --exclude=".env" --exclude=".venv" --exclude="__pycache__" -czf bot-deploy.tgz .
scp bot-deploy.tgz root@ВАШ_IP:/root/
```

На **сервере**:

```bash
mkdir -p /opt/tg-bot-podarok
tar -xzf /root/bot-deploy.tgz -C /opt/tg-bot-podarok
cd /opt/tg-bot-podarok
```

## Шаг 4. Секреты только на сервере

```bash
cd /opt/tg-bot-podarok
nano .env
```

Вставьте (свои значения):

```
BOT_TOKEN=токен_от_BotFather
OPENAI_API_KEY=ключ_openai
```

Сохраните: `Ctrl+O`, Enter, `Ctrl+X`.

Проверьте права:

```bash
chmod 600 .env
```

## Шаг 5. Запуск

```bash
cd /opt/tg-bot-podarok
docker compose up -d --build
docker compose logs -f bot
```

Должно быть: `Бот запущен (polling)`. Выход из логов: `Ctrl+C` (контейнер продолжит работать).

Проверка:

```bash
docker compose ps
curl -s http://127.0.0.1:8080/health
```

Ответ: `ok`. Затем в Telegram: `/start`.

## Обновление кода позже

```bash
cd /opt/tg-bot-podarok
git pull
docker compose up -d --build
```

Или снова залить архив и пересобрать.

Остановка:

```bash
docker compose down
```

## Важно

- Одновременно работает **одна** копия бота с этим токеном.
- `.env` не должен попасть в GitHub.
- Сессии и лимиты открыток в памяти — после редеплоя сбрасываются.
- Если модель картинок недоступна: в `.env` добавьте  
  `OPENAI_IMAGE_MODEL=gpt-image-2.5-flare`

## Файлы проекта для деплоя

- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `run.py`
- `bot/` (включая `bot/fonts/`)
- `.env.example` (образец, без реальных секретов)
