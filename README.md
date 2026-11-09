# Automation Google Spreadsheets Report — Mini CRM

Учебный проект: мини-CRM для личного бизнеса с REST API (FastAPI + SQLite), Tkinter-клиентом и выгрузкой отчётов в Google Drive / Google Sheets.

Пользователь работает в GUI, данные хранятся локально через API, а отчёты по клиентам, сделкам и задачам создаются в Google от имени личного аккаунта (OAuth2) и заполняются через сервисный аккаунт.

## Что делает проект

1. **CRM-бэкенд** (`backend/`) — клиенты, сделки, задачи: CRUD, архивация, поиск, статусы.
2. **HTTP API** (FastAPI) — эндпоинты для каждой операции, документация Swagger.
3. **Tkinter GUI** (`ui/crm_app.py`) — таблицы, формы, поиск; все действия идут запросами на локальный API.
4. **Google-интеграция** (`integrations/`)
   - `google_drive.py` — Drive API: список/чтение/удаление (сервисный аккаунт), создание Docs/Sheets (OAuth2 пользователя);
   - `google_sheets.py` — Sheets API: CRUD значений + оформление отчёта.
5. **Выгрузка отчётов из GUI** — кнопка «Выгрузить отчёт» на каждой вкладке: анализ видимых данных → создание таблицы в Drive → запись и форматирование → ссылка с кнопкой «Открыть».
6. **Сидер** (`seed_crm_data.py`) — заполняет API ~1000 реалистичных клиентов, сделок и задач.
7. **Docker Compose** — запуск API с монтированием кода и автоперезапуском через Watchdog.

## Структура репозитория

```
backend/            # models.py, crm.py (SQLite CRUD), api.py (FastAPI), Dockerfile
integrations/       # google_sheets.py, google_drive.py, report_generator.py
ui/                 # crm_app.py, google_export.py
credentials/        # service account + OAuth client secret + token (не в git)
data/               # crm.db, google_gui_settings.txt (не в git / локально)
docker-compose.yml
seed_crm_data.py
.env.example
requirements.txt
```

## Как проект закрывает домашнее задание

### 1. Подготовка окружения

| Требование | Как закрыто |
|------------|-------------|
| Проект в Google Cloud с **Google Drive API** и **Google Sheets API** | Настраивается в Cloud Console (проект Excel Factory / аналог); в коде используются оба API |
| Корректная **OAuth2**-аутентификация (личный аккаунт, тестировщики) | `credentials/client_secret_….json`, токен `credentials/token.json`; вход из GUI при создании таблицы (`GoogleDrive.create_spreadsheet`) |

Сервисный аккаунт (JSON в `credentials/`) используется для записи в Sheets и для операций Drive, где нужен SA. Папка отчётов в Drive должна быть выдана сервисному аккаунту как **Редактор**.

### 2. Разработка и запуск проекта

| Требование | Как закрыто |
|------------|-------------|
| Модули Google Drive и Google Sheets (создание, чтение, запись) | `integrations/google_drive.py`, `integrations/google_sheets.py` |
| Мини-CRM через **Docker Compose** | `docker-compose.yml` + `backend/Dockerfile`; сервис `crm-api`, порт `8000`, volume на код + Watchdog |
| Проверка API (клиенты, сделки, задачи) | Swagger: `http://127.0.0.1:8000/docs` или GUI `python -m ui.crm_app` |

Основные сущности CRM:

- **clients** — создание / правка / удаление / архив (`active` / `archived`), поиск;
- **deals** — опциональная привязка к клиенту, статусы, поиск;
- **tasks** — связь с клиентом и/или сделкой, отметка выполнено / не выполнено.

### 3. Генерация и выгрузка данных

| Требование | Как закрыто |
|------------|-------------|
| Тестовый скрипт с рандомными, но реалистичными данными | `seed_crm_data.py` → HTTP `requests` к API, ~1000 записей в каждую сущность |
| Отчёты по клиентам, сделкам и задачам в Google Drive | В GUI: «Выгрузить отчёт» на каждой вкладке (`ui/google_export.py`) |
| Отчёты создаются корректно и открываются по ссылке | Создание файла (OAuth) → запись + оформление (Sheets) → диалог со ссылкой и кнопкой **«Открыть»** |

## Быстрый старт

### 1. Окружение Python (для GUI и сидера)

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Секреты

1. Положите в `credentials/`:
   - JSON сервисного аккаунта;
   - OAuth client secret.
2. Скопируйте `.env.example` → `.env` и заполните пути / ID.
3. Выдайте сервисному аккаунту доступ **Редактор** на рабочую папку Drive.
4. В GUI → **Google…** укажите пути к JSON и ID папки (кнопка **Вставить**). Настройки сохраняются в `data/google_gui_settings.txt`.

Пример `.env`:

```env
GOOGLE_CREDENTIALS_PATH=credentials/your-service-account.json
GOOGLE_OAUTH_CLIENT_SECRETS_PATH=credentials/your-client-secret.json
GOOGLE_OAUTH_TOKEN_PATH=credentials/token.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
CRM_API_URL=http://127.0.0.1:8000
```

### 3. Запуск API (Docker Compose)

```powershell
docker compose up --build -d
```

- API: http://127.0.0.1:8000  
- Swagger: http://127.0.0.1:8000/docs  
- Код `backend/` смонтирован в контейнер; Watchdog перезапускает uvicorn при изменении `.py`.

Альтернатива без Docker:

```powershell
.\venv\Scripts\uvicorn.exe backend.api:app --reload
```

### 4. GUI

```powershell
.\venv\Scripts\python.exe -m ui.crm_app
```

### 5. Сидер тестовых данных

```powershell
.\venv\Scripts\python.exe seed_crm_data.py
```

### 6. Выгрузка отчёта

В GUI откройте вкладку Клиенты / Сделки / Задачи → **Выгрузить отчёт** → дождитесь диалога → **Открыть**.

## Безопасность при сдаче на GitHub

**Не коммитить:**

- `.env`
- `credentials/*.json` (и любой `*.json` с ключами — см. `.gitignore`)
- `data/*.db`, локальные настройки с секретами

**Можно коммитить:**

- исходники (`backend/`, `integrations/`, `ui/`, `seed_crm_data.py`)
- `docker-compose.yml`, `backend/Dockerfile`
- `.env.example`, `.gitignore`, `requirements.txt`, `README.md`

Перед коммитом:

```powershell
git status
```

В staged не должно быть `.env` и JSON-ключей.

## Зависимости

- `fastapi` / `uvicorn` — API  
- `google-api-python-client`, `google-auth`, `google-auth-oauthlib` — Google APIs + OAuth  
- `python-dotenv` — `.env`  
- `requests` — GUI и сидер к API  
- `watchdog` — автоперезапуск в Docker  
- `tkinter` — стандартная библиотека Python на Windows  
