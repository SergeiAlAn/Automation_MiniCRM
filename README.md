# Google Sheets Report — Excel Factory

Учебный проект: CRUD-модуль для Google Таблиц через Google Sheets API и Tkinter-приложение, которое генерирует случайные отчёты и записывает их в таблицу с оформлением «как документ».

## Состав проекта

| Файл | Назначение |
|------|------------|
| `google_sheets.py` | Переиспользуемый OOP-модуль CRUD (`create`, `read`, `update`, `delete`) |
| `report_generator.py` | GUI на tkinter: ввод параметров, симуляция данных, запись отчёта |
| `.env` | Локальные секреты (не коммитится) |
| `.env.example` | Шаблон переменных окружения без секретов |
| `requirements.txt` | Зависимости Python |

## Как закрывает домашнее задание

### 1. Настройка Google Cloud
Выполнено вручную: проект в Google Cloud Console (например, «Excel Factory»), подключены Google Sheets API, создан сервисный аккаунт с ролью Editor/Owner, скачан JSON-ключ.

### 2. Интеграция с таблицей
Созданы Google Таблицы, сервисному аккаунту выдан доступ «Редактор» по `client_email` из JSON-ключа.

### 3. Разработка в Cursor — CRUD-модуль
- JSON-ключ лежит в корне проекта **локально** (в git не попадает, см. `.gitignore`).
- Модуль `google_sheets.py` реализует класс `GoogleSheet` с CRUD-операциями через Google Sheets API и сервисный аккаунт.
- Модуль можно импортировать в любое приложение:

```python
from google_sheets import GoogleSheet

sheet = GoogleSheet(
    spreadsheet_id="...",
    credentials_path="path/to/key.json",
    sheet_name="Лист1",
)
rows = sheet.read_all()
```

### 4. Симулятор отчётов
- Приложение `report_generator.py` на tkinter принимает период, тип отчёта, объект, составителя и комментарий.
- Генерирует случайные строки отчёта и записывает их в Google Таблицу через модуль `google_sheets.py`.
- Автоматическое форматирование: цвета, шрифты, объединение ячеек, границы таблицы, чередование строк, блоки итогов и подписи.

## Быстрый старт

### 1. Окружение

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Секреты

1. Положите JSON-ключ сервисного аккаунта в корень проекта.
2. Скопируйте шаблон окружения:

```powershell
copy .env.example .env
```

3. Заполните `.env`:

```env
GOOGLE_CREDENTIALS_PATH=your-service-account.json
REPORT_SPREADSHEET_ID=id_таблицы_для_отчётов
METERS_SPREADSHEET_ID=id_таблицы_с_показаниями
```

ID таблицы берётся из URL:  
`https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`

Не забудьте выдать сервисному аккаунту права **Редактор** на обе таблицы.

### 3. Проверка CRUD

```powershell
.\venv\Scripts\python.exe google_sheets.py
```

Читает листы `ЭЭ`, `Тепло`, `Вода (гв хв)` из таблицы `METERS_SPREADSHEET_ID` и печатает их в консоль.

### 4. Генератор отчётов

```powershell
.\venv\Scripts\python.exe report_generator.py
```

После нажатия «Сформировать отчёт» в таблице `REPORT_SPREADSHEET_ID` появится новый лист с оформленным документом.

## Безопасность при сдаче / публикации на GitHub

В репозиторий **не** должны попадать:

- JSON-ключ сервисного аккаунта (`*.json` в `.gitignore`)
- файл `.env` с ID таблиц и путём к ключу

В репозиторий **можно** класть:

- исходники `.py`
- `requirements.txt`
- `.env.example`
- `README.md`
- `.gitignore`

Перед первым `git add` убедитесь:

```powershell
git status
```

В списке staged не должно быть `.env` и `*.json` с ключом.

## Структура отчёта в таблице

На новом листе формируются:

1. Заголовок документа (объединённые ячейки)
2. Метаданные: период, тип, объект, составитель, дата, комментарий
3. Таблица случайных показаний с границами и чередованием строк
4. Итоги по расходу и сумме
5. Блок подписи

## Зависимости

- `google-api-python-client` / `google-auth` — Google Sheets API
- `python-dotenv` — загрузка `.env`
- `tkinter` — входит в стандартную поставку Python на Windows
