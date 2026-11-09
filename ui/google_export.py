"""
Выгрузка таблиц CRM в Google Sheets через готовые модули integrations.

OAuth (создание файла) — в GUI от имени пользователя.
Запись данных — GoogleSheet (сервисный аккаунт) по ID созданной таблицы.
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv

from integrations.google_drive import GoogleDrive
from integrations.google_sheets import GoogleSheet

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SETTINGS_PATH = PROJECT_ROOT / "data" / "google_gui_settings.txt"

DEFAULT_KEYS = (
    "GOOGLE_CREDENTIALS_PATH",
    "GOOGLE_OAUTH_CLIENT_SECRETS_PATH",
    "GOOGLE_OAUTH_TOKEN_PATH",
    "GOOGLE_DRIVE_FOLDER_ID",
)


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def load_google_settings() -> dict[str, str]:
    settings = {
        "GOOGLE_CREDENTIALS_PATH": os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            "credentials/service-account.json",
        ),
        "GOOGLE_OAUTH_CLIENT_SECRETS_PATH": os.getenv(
            "GOOGLE_OAUTH_CLIENT_SECRETS_PATH",
            "credentials/client_secret.json",
        ),
        "GOOGLE_OAUTH_TOKEN_PATH": os.getenv(
            "GOOGLE_OAUTH_TOKEN_PATH",
            "credentials/token.json",
        ),
        "GOOGLE_DRIVE_FOLDER_ID": os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
    }
    if not SETTINGS_PATH.is_file():
        return settings

    for line in SETTINGS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in settings:
            settings[key] = value.strip()
    return settings


def save_google_settings(settings: dict[str, str]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={settings.get(key, '')}" for key in DEFAULT_KEYS]
    SETTINGS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _rgb(r: float, g: float, b: float) -> dict[str, float]:
    return {"red": r, "green": g, "blue": b}


def _text(bold: bool = False, size: int = 11, color: dict[str, float] | None = None) -> dict[str, Any]:
    fmt: dict[str, Any] = {"fontFamily": "Arial", "fontSize": size, "bold": bold}
    if color:
        fmt["foregroundColor"] = color
    return fmt


def analyze_rows(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[list[Any]]:
    """Простой анализ видимой таблицы для блока отчёта."""
    block: list[list[Any]] = [
        ["Анализ"],
        ["Всего строк", len(rows)],
    ]
    if not rows or not headers:
        return block

    header_list = [str(h) for h in headers]
    lower_map = {name.lower(): index for index, name in enumerate(header_list)}

    status_idx = None
    for key in ("status", "статус", "is_done", "готово"):
        if key in lower_map:
            status_idx = lower_map[key]
            break

    if status_idx is not None:
        counter = Counter(str(row[status_idx]) if status_idx < len(row) else "" for row in rows)
        block.append([""])
        block.append(["Распределение по статусу / флагу"])
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
            block.append([value or "(пусто)", count])

    amount_idx = None
    for key in ("amount", "сумма"):
        if key in lower_map:
            amount_idx = lower_map[key]
            break
    if amount_idx is not None:
        total = 0.0
        for row in rows:
            raw = row[amount_idx] if amount_idx < len(row) else ""
            try:
                total += float(str(raw).replace(",", ".") or 0)
            except ValueError:
                continue
        block.append([""])
        block.append(["Итого по сумме", round(total, 2)])

    return block


def build_report_matrix(
    title: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> dict[str, Any]:
    stamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    analysis = analyze_rows(headers, rows)

    matrix: list[list[Any]] = [
        [title],
        ["Сформирован", stamp],
        [""],
    ]
    analysis_start = len(matrix)
    matrix.extend(analysis)
    matrix.append([""])
    matrix.append(["Данные"])
    header_row = len(matrix)
    matrix.append(list(headers))
    data_start = len(matrix)
    for row in rows:
        matrix.append([("" if cell is None else cell) for cell in row])
    data_end = len(matrix) - 1
    num_cols = max(len(headers), 2)

    return {
        "values": matrix,
        "num_cols": num_cols,
        "analysis_start": analysis_start,
        "header_row": header_row,
        "data_start": data_start,
        "data_end": data_end,
        "row_count": len(rows),
    }


def _format_requests(sheet_id: int, layout: dict[str, Any]) -> list[dict[str, Any]]:
    cols = int(layout["num_cols"])
    header_row = int(layout["header_row"])
    data_start = int(layout["data_start"])
    data_end = int(layout["data_end"])
    analysis_start = int(layout["analysis_start"])

    requests: list[dict[str, Any]] = [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": cols,
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
                "properties": {"pixelSize": 180},
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
                    "endColumnIndex": cols,
                },
                "mergeType": "MERGE_ALL",
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
                "properties": {"pixelSize": 40},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.16, 0.31, 0.47),
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "textFormat": _text(bold=True, size=16, color=_rgb(1, 1, 1)),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": 2,
                    "startColumnIndex": 0,
                    "endColumnIndex": 2,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": _text(size=10, color=_rgb(0.35, 0.35, 0.35)),
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": analysis_start,
                    "endRowIndex": analysis_start + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 2,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.90, 0.94, 0.98),
                        "textFormat": _text(bold=True, size=12),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row - 1,
                    "endRowIndex": header_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.88, 0.92, 0.96),
                        "textFormat": _text(bold=True, size=12),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row,
                    "endRowIndex": header_row + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _rgb(0.22, 0.42, 0.60),
                        "horizontalAlignment": "CENTER",
                        "textFormat": _text(bold=True, size=10, color=_rgb(1, 1, 1)),
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
    ]

    if data_end >= data_start:
        requests.append(
            {
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": header_row,
                        "endRowIndex": data_end + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": cols,
                    },
                    "top": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                    "bottom": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                    "left": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                    "right": {"style": "SOLID", "width": 1, "color": _rgb(0.6, 0.6, 0.6)},
                    "innerHorizontal": {
                        "style": "SOLID",
                        "width": 1,
                        "color": _rgb(0.78, 0.78, 0.78),
                    },
                    "innerVertical": {
                        "style": "SOLID",
                        "width": 1,
                        "color": _rgb(0.78, 0.78, 0.78),
                    },
                }
            }
        )
        for row_index in range(data_start, data_end + 1):
            if (row_index - data_start) % 2 == 1:
                requests.append(
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_index,
                                "endRowIndex": row_index + 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": cols,
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

    return requests


def export_visible_table(
    report_title: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    settings: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    1) create_spreadsheet (OAuth, личный аккаунт)
    2) GoogleSheet.update + batch_format по ID (сервисный аккаунт)
    """
    cfg = settings or load_google_settings()
    sa_path = _resolve(cfg["GOOGLE_CREDENTIALS_PATH"])
    oauth_path = _resolve(cfg["GOOGLE_OAUTH_CLIENT_SECRETS_PATH"])
    token_path = _resolve(cfg["GOOGLE_OAUTH_TOKEN_PATH"])
    folder_id = (cfg.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip() or None

    if not sa_path.is_file():
        raise FileNotFoundError(f"JSON сервисного аккаунта не найден: {sa_path}")
    if not oauth_path.is_file():
        raise FileNotFoundError(f"OAuth client secret не найден: {oauth_path}")

    stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    spreadsheet_name = f"{report_title} {stamp}"

    drive = GoogleDrive(
        credentials_path=sa_path,
        oauth_client_secrets_path=oauth_path,
        token_path=token_path,
    )
    created = drive.create_spreadsheet(name=spreadsheet_name, folder_id=folder_id)
    spreadsheet_id = created["id"]

    layout = build_report_matrix(report_title, headers, rows)
    sheet = GoogleSheet(
        spreadsheet_id=spreadsheet_id,
        credentials_path=sa_path,
        sheet_name=None,
    )
    sheet.update("A1", layout["values"])
    sheet.batch_format(_format_requests(sheet.sheet_id(), layout))

    link = created.get("webViewLink") or (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    )

    return {
        "id": spreadsheet_id,
        "name": created.get("name", spreadsheet_name),
        "webViewLink": link,
        "rows": len(rows),
    }
