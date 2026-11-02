# Telegram-бот «Подбери идеальный подарок» (polling)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY run.py .

# Токен задаётся только через переменную окружения BOT_TOKEN в панели Timeweb
CMD ["python", "-u", "run.py"]
