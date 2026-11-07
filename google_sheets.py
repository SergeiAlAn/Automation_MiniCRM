"""
Модуль CRUD-операций для Google Таблиц через Google Sheets API.

Подключение — сервисный аккаунт (JSON-ключ).
Можно импортировать класс GoogleSheet в любое приложение:

    from google_sheets import GoogleSheet

    sheet = GoogleSheet(
        spreadsheet_id="...",
        credentials_path="path/to/key.json",
        sheet_name="Лист1",
    )
    rows = sheet.read_all()
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv(Path(__file__).resolve().parent / ".env")

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
PROJECT_ROOT = Path(__file__).resolve().parent


class GoogleSheet:
    """Клиент для CRUD-работы с одним листом Google Таблицы."""

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str | Path,
        sheet_name: str = "Sheet1",
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.credentials_path = Path(credentials_path)

        if not self.credentials_path.is_file():
            raise FileNotFoundError(
                f"JSON-ключ сервисного аккаунта не найден: {self.credentials_path}"
            )

        credentials = Credentials.from_service_account_file(
            str(self.credentials_path),
            scopes=SCOPES,
        )
        self._service = build("sheets", "v4", credentials=credentials)
        self._values = self._service.spreadsheets().values()

    def _a1(self, range_name: str | None = None) -> str:
        """Собирает A1-диапазон с именем листа."""
        if not range_name:
            return self.sheet_name
        if "!" in range_name:
            return range_name
        return f"{self.sheet_name}!{range_name}"

    # --- CREATE ---

    def create(
        self,
        values: Sequence[Sequence[Any]],
        range_name: str = "A1",
    ) -> dict[str, Any]:
        """
        Добавляет новые строки в конец таблицы (append).

        :param values: двумерный список значений, например [["Аня", 25], ["Борис", 30]]
        :param range_name: стартовая ячейка / колонки для append (по умолчанию A1)
        :return: ответ Google Sheets API
        """
        body = {"values": [list(row) for row in values]}
        try:
            return (
                self._values.append(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._a1(range_name),
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                ).execute()
            )
        except HttpError as error:
            raise RuntimeError(f"Ошибка create: {error}") from error

    # --- READ ---

    def read(self, range_name: str | None = None) -> list[list[Any]]:
        """
        Читает значения из диапазона.

        :param range_name: A1-диапазон (например "A1:C10") или None — весь лист
        :return: список строк
        """
        try:
            result = self._values.get(
                spreadsheetId=self.spreadsheet_id,
                range=self._a1(range_name),
            ).execute()
        except HttpError as error:
            raise RuntimeError(f"Ошибка read: {error}") from error

        return result.get("values", [])

    def read_all(self) -> list[list[Any]]:
        """Читает все заполненные ячейки текущего листа."""
        return self.read()

    # --- UPDATE ---

    def update(
        self,
        range_name: str,
        values: Sequence[Sequence[Any]],
    ) -> dict[str, Any]:
        """
        Перезаписывает значения в указанном диапазоне.

        :param range_name: A1-диапазон, например "B2" или "A2:C2"
        :param values: двумерный список новых значений
        :return: ответ Google Sheets API
        """
        body = {"values": [list(row) for row in values]}
        try:
            return (
                self._values.update(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._a1(range_name),
                    valueInputOption="USER_ENTERED",
                    body=body,
                ).execute()
            )
        except HttpError as error:
            raise RuntimeError(f"Ошибка update: {error}") from error

    # --- DELETE ---

    def delete(self, range_name: str) -> dict[str, Any]:
        """
        Очищает значения в диапазоне (ячейки остаются, содержимое удаляется).

        :param range_name: A1-диапазон, например "A5:Z5" или "C3"
        :return: ответ Google Sheets API
        """
        try:
            return (
                self._values.clear(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._a1(range_name),
                    body={},
                ).execute()
            )
        except HttpError as error:
            raise RuntimeError(f"Ошибка delete: {error}") from error


def print_sheet(title: str, rows: list[list[Any]]) -> None:
    """Печатает лист в консоль в виде выровненной таблицы."""
    print()
    print("=" * 80)
    print(f"  Лист: {title}")
    print("=" * 80)

    if not rows:
        print("  (пусто)")
        return

    width = max(len(row) for row in rows)
    normalized = [[str(cell) for cell in row] + [""] * (width - len(row)) for row in rows]
    col_widths = [
        max(len(normalized[r][c]) for r in range(len(normalized)))
        for c in range(width)
    ]

    for row_index, row in enumerate(normalized):
        line = " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))
        print(line)
        if row_index == 0:
            print("-+-".join("-" * w for w in col_widths))

    print(f"\nВсего строк: {len(rows)}")


if __name__ == "__main__":
    spreadsheet_id = os.getenv("METERS_SPREADSHEET_ID", "").strip()
    credentials_path = PROJECT_ROOT / os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        "service-account.json",
    )
    sheet_names = ("ЭЭ", "Тепло", "Вода (гв хв)")

    if not spreadsheet_id:
        raise SystemExit("Заполните METERS_SPREADSHEET_ID в файле .env")

    for sheet_name in sheet_names:
        client = GoogleSheet(
            spreadsheet_id=spreadsheet_id,
            credentials_path=credentials_path,
            sheet_name=sheet_name,
        )
        print_sheet(sheet_name, client.read_all())
