"""
Простое Tkinter-приложение: симуляция отчёта и запись в Google Таблицу.

Использует CRUD-модуль google_sheets.GoogleSheet.
Оформление «как документ» реализовано здесь через Sheets API batchUpdate.
"""

from __future__ import annotations

import os
import random
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from dotenv import load_dotenv

from integrations.google_sheets import GoogleSheet

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SPREADSHEET_ID = os.getenv("REPORT_SPREADSHEET_ID", "").strip()
CREDENTIALS_PATH = PROJECT_ROOT / os.getenv(
    "GOOGLE_CREDENTIALS_PATH",
    "service-account.json",
)

REPORT_TYPES = ("Электроэнергия", "Тепло", "Вода", "Сводный")
OBJECTS = ("Квартира 12", "Квартира 45", "Офис 3", "Склад А")


class ReportSheet(GoogleSheet):
    """Расширение CRUD-клиента: лист под отчёт + оформление ячеек."""

    def ensure_sheet(self, title: str) -> int:
        """Создаёт лист с именем title (если нет) и переключает клиент на него."""
        meta = (
            self._service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id)
            .execute()
        )
        for sheet in meta.get("sheets", []):
            props = sheet["properties"]
            if props["title"] == title:
                self.sheet_name = title
                return props["sheetId"]

        response = (
            self._service.spreadsheets()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
            )
            .execute()
        )
        sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
        self.sheet_name = title
        return sheet_id

    def batch_format(self, requests: list[dict[str, Any]]) -> None:
        if not requests:
            return
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        ).execute()


def _rgb(r: float, g: float, b: float) -> dict[str, float]:
    return {"red": r, "green": g, "blue": b}


def _text_format(
    bold: bool = False,
    size: int = 11,
    color: dict[str, float] | None = None,
) -> dict[str, Any]:
    fmt: dict[str, Any] = {
        "fontFamily": "Arial",
        "fontSize": size,
        "bold": bold,
    }
    if color:
        fmt["foregroundColor"] = color
    return fmt


def build_simulated_rows(date_from: date, date_to: date, report_type: str) -> list[list[Any]]:
    """Случайные строки отчёта за выбранный период."""
    days = max((date_to - date_from).days, 0) + 1
    sample_days = min(days, 12)
    step = max(days // sample_days, 1)

    rows: list[list[Any]] = []
    for i in range(sample_days):
        day = date_from + timedelta(days=min(i * step, days - 1))
        consumption = round(random.uniform(8, 95), 2)
        tariff = {
            "Электроэнергия": round(random.uniform(6.5, 11.5), 2),
            "Тепло": round(random.uniform(2200, 2400), 2),
            "Вода": round(random.uniform(45, 320), 2),
            "Сводный": round(random.uniform(50, 500), 2),
        }[report_type]
        amount = round(consumption * (tariff if report_type != "Тепло" else tariff / 100), 2)
        note = random.choice(("норма", "норма", "пик", "ниже среднего", "выше среднего"))
        rows.append(
            [
                day.strftime("%d.%m.%Y"),
                report_type,
                consumption,
                tariff,
                amount,
                note,
            ]
        )
    return rows


def write_document_report(
    sheet: ReportSheet,
    *,
    date_from: date,
    date_to: date,
    report_type: str,
    object_name: str,
    author: str,
    comment: str,
) -> str:
    """Собирает «документный» отчёт на новом листе и возвращает имя листа."""
    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    sheet_title = f"Отчёт {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}"
    sheet_id = sheet.ensure_sheet(sheet_title)

    data_rows = build_simulated_rows(date_from, date_to, report_type)
    total_amount = round(sum(float(row[4]) for row in data_rows), 2)
    total_consumption = round(sum(float(row[2]) for row in data_rows), 2)

    header = [
        "Дата",
        "Категория",
        "Расход",
        "Тариф",
        "Сумма, руб.",
        "Примечание",
    ]

    values: list[list[Any]] = [
        ["ОТЧЁТ О ПОТРЕБЛЕНИИ РЕСУРСОВ"],
        [""],
        ["Период:", f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"],
        ["Тип отчёта:", report_type],
        ["Объект:", object_name],
        ["Составил:", author],
        ["Сформирован:", stamp],
        ["Комментарий:", comment or "—"],
        [""],
        ["1. Сводная таблица показаний"],
        header,
        *data_rows,
        [""],
        ["2. Итоги"],
        ["Всего расход:", total_consumption],
        ["Итого к оплате, руб.:", total_amount],
        [""],
        ["Подпись ответственного:", "________________ / " + (author or "__________")],
        ["Дата подписания:", datetime.now().strftime("%d.%m.%Y")],
    ]

    # Очистка и запись значений через CRUD-методы базового класса
    sheet.delete("A1:F60")
    sheet.update("A1", values)

    table_start = 10  # 0-based row index of header (строка 11 в Sheets)
    table_end = table_start + len(data_rows)  # last data row index
    summary_title_row = table_end + 2
    totals_row_1 = summary_title_row + 1
    totals_row_2 = summary_title_row + 2

    requests: list[dict[str, Any]] = [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 6,
                },
                "properties": {"pixelSize": 140},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 170},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 5,
                    "endIndex": 6,
                },
                "properties": {"pixelSize": 150},
                "fields": "pixelSize",
            }
        },
        {
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "mergeType": "MERGE_ALL",
            }
        },
        {
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 9,
                    "endRowIndex": 10,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "mergeType": "MERGE_ALL",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.18, 0.32, 0.48),
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "textFormat": _text_format(bold=True, size=16, color=_rgb(1, 1, 1)),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 42},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 2,
                    "endRowIndex": 8,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": _text_format(bold=True, size=11),
                        "backgroundColor": _rgb(0.93, 0.95, 0.97),
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 9,
                    "endRowIndex": 10,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": _text_format(bold=True, size=12),
                        "backgroundColor": _rgb(0.88, 0.92, 0.96),
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": table_start,
                    "endRowIndex": table_start + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.25, 0.45, 0.62),
                        "horizontalAlignment": "CENTER",
                        "textFormat": _text_format(bold=True, size=10, color=_rgb(1, 1, 1)),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": table_start,
                    "endRowIndex": table_end + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "top": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                "bottom": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                "left": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                "right": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                "innerHorizontal": {
                    "style": "SOLID",
                    "width": 1,
                    "color": _rgb(0.75, 0.75, 0.75),
                },
                "innerVertical": {
                    "style": "SOLID",
                    "width": 1,
                    "color": _rgb(0.75, 0.75, 0.75),
                },
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": summary_title_row,
                    "endRowIndex": summary_title_row + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 2,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": _text_format(bold=True, size=12),
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": totals_row_1,
                    "endRowIndex": totals_row_2 + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 2,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.95, 0.97, 0.90),
                        "textFormat": _text_format(bold=True, size=11),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
    ]

    # Чередование строк таблицы
    for row_index in range(table_start + 1, table_end + 1):
        if (row_index - table_start) % 2 == 0:
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_index,
                            "endRowIndex": row_index + 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 6,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": _rgb(0.96, 0.97, 0.99),
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor)",
                    }
                }
            )

    sheet.batch_format(requests)
    return sheet_title


class ReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Генератор отчётов → Google Sheets")
        self.geometry("520x420")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Симуляция отчёта для Google Таблицы",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        today = date.today()
        self.date_from = tk.StringVar(value=(today - timedelta(days=30)).strftime("%d.%m.%Y"))
        self.date_to = tk.StringVar(value=today.strftime("%d.%m.%Y"))
        self.report_type = tk.StringVar(value=REPORT_TYPES[0])
        self.object_name = tk.StringVar(value=OBJECTS[0])
        self.author = tk.StringVar(value="Иванов И.И.")
        self.comment = tk.StringVar(value="")

        fields = [
            ("Дата с (ДД.ММ.ГГГГ)", self.date_from),
            ("Дата по (ДД.ММ.ГГГГ)", self.date_to),
            ("Тип отчёта", self.report_type),
            ("Объект", self.object_name),
            ("Составил", self.author),
            ("Комментарий", self.comment),
        ]

        for row_index, (label, variable) in enumerate(fields, start=1):
            ttk.Label(frame, text=label).grid(row=row_index, column=0, sticky="w", **pad)
            if label == "Тип отчёта":
                widget: ttk.Widget = ttk.Combobox(
                    frame,
                    textvariable=variable,
                    values=REPORT_TYPES,
                    state="readonly",
                    width=36,
                )
            elif label == "Объект":
                widget = ttk.Combobox(
                    frame,
                    textvariable=variable,
                    values=OBJECTS,
                    width=36,
                )
            else:
                widget = ttk.Entry(frame, textvariable=variable, width=38)
            widget.grid(row=row_index, column=1, sticky="ew", **pad)

        self.status = tk.StringVar(value="Заполните поля и нажмите «Сформировать отчёт».")
        ttk.Label(frame, textvariable=self.status, wraplength=460).grid(
            row=len(fields) + 1,
            column=0,
            columnspan=2,
            sticky="w",
            **pad,
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="e", **pad)
        ttk.Button(buttons, text="Случайные поля", command=self._fill_random).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(buttons, text="Сформировать отчёт", command=self._generate).pack(
            side=tk.LEFT
        )

    def _parse_date(self, value: str) -> date:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()

    def _fill_random(self) -> None:
        end = date.today() - timedelta(days=random.randint(0, 10))
        start = end - timedelta(days=random.randint(14, 60))
        self.date_from.set(start.strftime("%d.%m.%Y"))
        self.date_to.set(end.strftime("%d.%m.%Y"))
        self.report_type.set(random.choice(REPORT_TYPES))
        self.object_name.set(random.choice(OBJECTS))
        self.author.set(random.choice(("Иванов И.И.", "Петрова А.С.", "Сидоров К.В.")))
        self.comment.set(random.choice(("", "Плановая проверка", "По заявке жильца", "Аудит")))
        self.status.set("Поля заполнены случайными значениями.")

    def _generate(self) -> None:
        try:
            date_from = self._parse_date(self.date_from.get())
            date_to = self._parse_date(self.date_to.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Даты должны быть в формате ДД.ММ.ГГГГ")
            return

        if date_from > date_to:
            messagebox.showerror("Ошибка", "Дата «с» не может быть позже даты «по».")
            return

        if not self.author.get().strip():
            messagebox.showerror("Ошибка", "Укажите составителя отчёта.")
            return

        if not SPREADSHEET_ID:
            messagebox.showerror(
                "Ошибка конфигурации",
                "Заполните REPORT_SPREADSHEET_ID в файле .env",
            )
            return

        self.status.set("Формирую отчёт и записываю в Google Таблицу…")
        self.update_idletasks()

        try:
            client = ReportSheet(
                spreadsheet_id=SPREADSHEET_ID,
                credentials_path=CREDENTIALS_PATH,
                sheet_name="Отчёты",
            )
            sheet_title = write_document_report(
                client,
                date_from=date_from,
                date_to=date_to,
                report_type=self.report_type.get(),
                object_name=self.object_name.get().strip() or "—",
                author=self.author.get().strip(),
                comment=self.comment.get().strip(),
            )
        except Exception as error:
            self.status.set("Ошибка при записи отчёта.")
            hint = (
                f"{error}\n\n"
                "Если это ошибка доступа (403): откройте таблицу и выдайте "
                "права «Редактор» email сервисного аккаунта из JSON-ключа."
            )
            messagebox.showerror("Ошибка Google Sheets", hint)
            return

        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        self.status.set(f"Готово: лист «{sheet_title}».")
        messagebox.showinfo(
            "Отчёт создан",
            f"Отчёт записан на лист:\n{sheet_title}\n\nОткройте таблицу:\n{url}",
        )


if __name__ == "__main__":
    app = ReportApp()
    app.mainloop()
