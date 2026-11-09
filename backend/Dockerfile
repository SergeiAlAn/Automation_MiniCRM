FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt watchdog

# Код backend монтируется volume'ом в compose;
# копирование нужно, чтобы образ мог стартовать и без mount.
COPY backend /app/backend

EXPOSE 8000

# Watchdog следит за файлами и перезапускает uvicorn при изменениях
CMD ["watchmedo", "auto-restart", \
     "--directory=/app/backend", \
     "--pattern=*.py", \
     "--recursive", \
     "--debug-force-polling", \
     "--", \
     "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
