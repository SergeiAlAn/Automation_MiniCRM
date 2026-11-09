"""
Модуль CRUD-операций для Google Drive через Google Drive API.

- Чтение / удаление / список файлов — сервисный аккаунт (как в google_sheets.py).
- Создание Google Документов и Таблиц — OAuth2 от имени пользователя,
  чтобы файлы принадлежали личному аккаунту, а не сервисному.

Пример:

    from integrations.google_drive import GoogleDrive

    drive = GoogleDrive(
        credentials_path="service-account.json",
        oauth_client_secrets_path="client_secret.json",
    )
    files = drive.read_all()
    doc = drive.create_document("Отчёт", folder_id="...")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Сервисный аккаунт: список / чтение / удаление
SA_SCOPES = ("https://www.googleapis.com/auth/drive",)

# Личный аккаунт: создание Docs / Sheets от имени пользователя
OAUTH_SCOPES = ("https://www.googleapis.com/auth/drive",)

MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
MIME_GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"


class GoogleDrive:
    """Клиент CRUD для файлов Google Drive."""

    def __init__(
        self,
        credentials_path: str | Path,
        oauth_client_secrets_path: str | Path | None = None,
        token_path: str | Path | None = None,
    ) -> None:
        self.credentials_path = Path(credentials_path)
        if not self.credentials_path.is_file():
            raise FileNotFoundError(
                f"JSON-ключ сервисного аккаунта не найден: {self.credentials_path}"
            )

        sa_credentials = ServiceCredentials.from_service_account_file(
            str(self.credentials_path),
            scopes=SA_SCOPES,
        )
        self._sa_service = build("drive", "v3", credentials=sa_credentials)

        self.oauth_client_secrets_path = (
            Path(oauth_client_secrets_path) if oauth_client_secrets_path else None
        )
        self.token_path = Path(token_path) if token_path else PROJECT_ROOT / "token.json"
        self._user_service = None

    def _get_user_service(self):
        """Drive API от имени пользователя (OAuth2). При первом вызове откроет браузер."""
        if self._user_service is not None:
            return self._user_service

        if self.oauth_client_secrets_path is None:
            raise ValueError(
                "Для операций от имени пользователя укажите oauth_client_secrets_path"
            )
        if not self.oauth_client_secrets_path.is_file():
            raise FileNotFoundError(
                f"OAuth client secret не найден: {self.oauth_client_secrets_path}"
            )

        creds: UserCredentials | None = None
        if self.token_path.is_file():
            creds = UserCredentials.from_authorized_user_file(
                str(self.token_path),
                list(OAUTH_SCOPES),
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.oauth_client_secrets_path),
                    list(OAUTH_SCOPES),
                )
                creds = flow.run_local_server(port=0)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        self._user_service = build("drive", "v3", credentials=creds)
        return self._user_service

    # --- READ ---

    def read(self, file_id: str) -> dict[str, Any]:
        """Читает метаданные файла по ID (сервисный аккаунт)."""
        try:
            return (
                self._sa_service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, parents, webViewLink, createdTime, modifiedTime, owners",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as error:
            raise RuntimeError(f"Ошибка read: {error}") from error

    def read_all(
        self,
        folder_id: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Список файлов, доступных сервисному аккаунту.

        :param folder_id: если задан — только файлы внутри этой папки
        :param page_size: размер страницы API (до 1000)
        """
        query_parts = ["trashed = false"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        query = " and ".join(query_parts)

        files: list[dict[str, Any]] = []
        page_token: str | None = None
        try:
            while True:
                response = (
                    self._sa_service.files()
                    .list(
                        q=query,
                        pageSize=min(page_size, 1000),
                        fields="nextPageToken, files(id, name, mimeType, parents, webViewLink, modifiedTime)",
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                files.extend(response.get("files", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as error:
            raise RuntimeError(f"Ошибка read_all: {error}") from error

        return files

    # --- CREATE (OAuth2 — от имени пользователя) ---

    def create_document(
        self,
        name: str,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """Создаёт Google Документ в личном аккаунте пользователя."""
        return self._create_google_file(name, MIME_GOOGLE_DOC, folder_id)

    def create_spreadsheet(
        self,
        name: str,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """Создаёт Google Таблицу в личном аккаунте пользователя."""
        return self._create_google_file(name, MIME_GOOGLE_SHEET, folder_id)

    def _create_google_file(
        self,
        name: str,
        mime_type: str,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name, "mimeType": mime_type}
        if folder_id:
            body["parents"] = [folder_id]

        try:
            return (
                self._get_user_service()
                .files()
                .create(
                    body=body,
                    fields="id, name, mimeType, parents, webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as error:
            raise RuntimeError(f"Ошибка create: {error}") from error

    # --- DELETE ---

    def delete(self, file_id: str) -> None:
        """Удаляет файл по ID (сервисный аккаунт; файл должен быть ему доступен)."""
        try:
            self._sa_service.files().delete(
                fileId=file_id,
                supportsAllDrives=True,
            ).execute()
        except HttpError as error:
            raise RuntimeError(f"Ошибка delete: {error}") from error


def print_files(title: str, files: list[dict[str, Any]]) -> None:
    """Печатает список файлов Drive в консоль."""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)

    if not files:
        print("  (файлов не найдено)")
        print(
            "  Подсказка: выдайте сервисному аккаунту доступ к папке/файлам "
            "или укажите GOOGLE_DRIVE_FOLDER_ID в .env"
        )
        return

    for index, item in enumerate(files, start=1):
        print(f"{index}. {item.get('name')}")
        print(f"   id:        {item.get('id')}")
        print(f"   mimeType:  {item.get('mimeType')}")
        print(f"   modified:  {item.get('modifiedTime')}")
        if item.get("webViewLink"):
            print(f"   link:      {item.get('webViewLink')}")
        print()

    print(f"Всего файлов: {len(files)}")


if __name__ == "__main__":
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

    drive = GoogleDrive(
        credentials_path=credentials_path,
        oauth_client_secrets_path=oauth_secrets if oauth_secrets.is_file() else None,
        token_path=token_path,
    )

    scope = f"папка {folder_id}" if folder_id else "все доступные сервисному аккаунту"
    print(f"Чтение файлов Google Drive ({scope})…")
    print_files("Файлы Google Drive (сервисный аккаунт)", drive.read_all(folder_id=folder_id))
