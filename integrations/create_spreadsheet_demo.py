"""
Тестовый скрипт: создание Google Таблицы от имени пользователя (OAuth2).

При первом запуске откроется браузер для входа в Google-аккаунт.
Токен сохранится в token.json (файл в git не попадает).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from integrations.google_drive import GoogleDrive

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    credentials_path = PROJECT_ROOT / os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        "service-account.json",
    )
    oauth_secrets = PROJECT_ROOT / os.getenv(
        "GOOGLE_OAUTH_CLIENT_SECRETS_PATH",
        "client_secret.json",
    )
    token_path = PROJECT_ROOT / os.getenv("GOOGLE_OAUTH_TOKEN_PATH", "token.json")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None

    if not oauth_secrets.is_file():
        raise SystemExit(
            f"Не найден OAuth client secret: {oauth_secrets}\n"
            "Проверьте GOOGLE_OAUTH_CLIENT_SECRETS_PATH в .env"
        )

    drive = GoogleDrive(
        credentials_path=credentials_path,
        oauth_client_secrets_path=oauth_secrets,
        token_path=token_path,
    )

    name = f"Тестовая таблица {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"Создаю таблицу: «{name}»…")
    if folder_id:
        print(f"Папка: {folder_id}")
    else:
        print("Папка не указана (GOOGLE_DRIVE_FOLDER_ID пуст) — файл попадёт в «Мой диск».")

    created = drive.create_spreadsheet(name=name, folder_id=folder_id)

    print("\nГотово!")
    print(f"  name:  {created.get('name')}")
    print(f"  id:    {created.get('id')}")
    print(f"  link:  {created.get('webViewLink')}")


if __name__ == "__main__":
    main()
