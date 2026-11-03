# Telegram-бот «Подбери идеальный подарок»
# Для облачного сервера Timeweb (VPS): polling + необязательный HTTP /health
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Кириллица для текста на открытках
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin botuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY run.py .
# bot/fonts — Cormorant Garamond, Marck Script, Manrope (SIL OFL)

RUN chown -R botuser:botuser /app
USER botuser

EXPOSE 8080

# Секреты НЕ вшивать в образ. Задайте в панели Timeweb:
# BOT_TOKEN, OPENAI_API_KEY
# Опционально: OPENAI_MODEL, OPENAI_IMAGE_MODEL, OPENAI_IMAGE_SIZE,
# OPENAI_IMAGE_QUALITY, CARD_HOURLY_LIMIT, CARD_OUTPUT_WIDTH,
# CARD_OUTPUT_HEIGHT, PORT
CMD ["python", "-u", "run.py"]
