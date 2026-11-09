"""
Tkinter-клиент мини-CRM.

Работает через HTTP с локальным FastAPI-бэкендом (как с сервером).

Запуск (из корня проекта, бэкенд уже должен быть запущен):
    python -m ui.crm_app

Бэкенд:
    uvicorn backend.api:app --reload
"""

from __future__ import annotations

import os
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable

import requests
from dotenv import load_dotenv

from ui.google_export import (
    export_visible_table,
    load_google_settings,
    save_google_settings,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_URL = os.getenv("CRM_API_URL", "http://127.0.0.1:8000").rstrip("/")

CLIENT_STATUSES = ("active", "archived")
DEAL_STATUSES = ("new", "in_progress", "won", "lost", "cancelled")


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.session = requests.Session()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)
        except requests.RequestException as error:
            raise ApiError(f"Нет связи с сервером ({self.base_url}): {error}") from error

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise ApiError(f"{response.status_code}: {detail}")

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, json: dict[str, Any] | None = None, **params: Any) -> Any:
        return self.request(
            "POST",
            path,
            json=json,
            params={k: v for k, v in params.items() if v is not None},
        )

    def patch(self, path: str, json: dict[str, Any]) -> Any:
        return self.request("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)


class FormDialog(tk.Toplevel):
    """Универсальное модальное окно с полями ввода."""

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        fields: list[tuple[str, str, Any, str]],
    ) -> None:
        """
        fields: (key, label, initial_value, kind)
        kind: entry | text | combo:<a,b,c> | check
        """
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result: dict[str, Any] | None = None
        self.vars: dict[str, tk.Variable] = {}
        self.widgets: dict[str, tk.Widget] = {}

        body = ttk.Frame(self, padding=12)
        body.grid(row=0, column=0, sticky="nsew")

        for row, (key, label, initial, kind) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            if kind.startswith("combo:"):
                values = kind.split(":", 1)[1].split(",")
                var = tk.StringVar(value=str(initial if initial is not None else values[0]))
                widget: tk.Widget = ttk.Combobox(
                    body, textvariable=var, values=values, state="readonly", width=36
                )
            elif kind == "check":
                var = tk.BooleanVar(value=bool(initial))
                widget = ttk.Checkbutton(body, variable=var)
            elif kind == "text":
                var = tk.StringVar(value="" if initial is None else str(initial))
                widget = tk.Text(body, width=38, height=4)
                widget.insert("1.0", var.get())
                self.widgets[key] = widget
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars[key] = var
                continue
            else:
                var = tk.StringVar(value="" if initial is None else str(initial))
                widget = ttk.Entry(body, textvariable=var, width=38)

            self.vars[key] = var
            widget.grid(row=row, column=1, sticky="ew", pady=4)

        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Отмена", command=self._cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text="Сохранить", command=self._ok).pack(side=tk.RIGHT)

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.wait_visibility()
        self.focus_set()

    def _ok(self) -> None:
        data: dict[str, Any] = {}
        for key, var in self.vars.items():
            widget = self.widgets.get(key)
            if isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", "end").strip()
            elif isinstance(var, tk.BooleanVar):
                data[key] = bool(var.get())
            else:
                value = var.get().strip()
                data[key] = value
        self.result = data
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class GoogleSettingsDialog(tk.Toplevel):
    """Настройки Google: пути JSON и ID папки (с кнопкой «Вставить»)."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("Настройки Google")
        self.resizable(False, False)
        self.result: dict[str, str] | None = None

        cfg = load_google_settings()
        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        self.vars = {
            "GOOGLE_CREDENTIALS_PATH": tk.StringVar(value=cfg.get("GOOGLE_CREDENTIALS_PATH", "")),
            "GOOGLE_OAUTH_CLIENT_SECRETS_PATH": tk.StringVar(
                value=cfg.get("GOOGLE_OAUTH_CLIENT_SECRETS_PATH", "")
            ),
            "GOOGLE_OAUTH_TOKEN_PATH": tk.StringVar(value=cfg.get("GOOGLE_OAUTH_TOKEN_PATH", "")),
            "GOOGLE_DRIVE_FOLDER_ID": tk.StringVar(value=cfg.get("GOOGLE_DRIVE_FOLDER_ID", "")),
        }

        rows = [
            ("GOOGLE_CREDENTIALS_PATH", "Service Account JSON", True),
            ("GOOGLE_OAUTH_CLIENT_SECRETS_PATH", "OAuth client secret JSON", True),
            ("GOOGLE_OAUTH_TOKEN_PATH", "OAuth token.json", True),
            ("GOOGLE_DRIVE_FOLDER_ID", "ID папки Drive", False),
        ]

        for index, (key, label, is_file) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=index, column=0, sticky="w", pady=4, padx=(0, 8))
            entry = ttk.Entry(body, textvariable=self.vars[key], width=56)
            entry.grid(row=index, column=1, sticky="ew", pady=4)
            if is_file:
                ttk.Button(
                    body,
                    text="Обзор…",
                    command=lambda k=key: self._browse_json(k),
                ).grid(row=index, column=2, padx=4)
            else:
                ttk.Button(
                    body,
                    text="Вставить",
                    command=lambda k=key: self._paste(k),
                ).grid(row=index, column=2, padx=4)

        hint = (
            "Папка Drive должна быть доступна сервисному аккаунту (Редактор),\n"
            "иначе запись в созданную таблицу через GoogleSheet не пройдёт."
        )
        ttk.Label(body, text=hint, foreground="#555").grid(
            row=len(rows), column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        buttons = ttk.Frame(body)
        buttons.grid(row=len(rows) + 1, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Отмена", command=self._cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text="Сохранить", command=self._save).pack(side=tk.RIGHT)

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _browse_json(self, key: str) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Выберите JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.vars[key].set(path)

    def _paste(self, key: str) -> None:
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            messagebox.showwarning("Буфер", "Буфер обмена пуст.", parent=self)
            return
        self.vars[key].set(text)

    def _save(self) -> None:
        self.result = {key: var.get().strip() for key, var in self.vars.items()}
        save_google_settings(self.result)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class CrmApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mini CRM")
        self.geometry("1100x640")
        self.minsize(900, 520)

        self.api = ApiClient(API_URL)
        self.status = tk.StringVar(value=f"API: {API_URL}")
        self._client_headers = ("ID", "Имя", "Телефон", "Email", "Компания", "Статус")
        self._deal_headers = ("ID", "Название", "Клиент ID", "Сумма", "Валюта", "Статус")
        self._task_headers = ("ID", "Задача", "Срок", "Готово", "Клиент", "Сделка")

        self._build()
        self.after(200, self.refresh_all)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Mini CRM", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(top, text="Google…", command=self.open_google_settings).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="Обновить всё", command=self.refresh_all).pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.clients_tab = self._make_clients_tab()
        self.deals_tab = self._make_deals_tab()
        self.tasks_tab = self._make_tasks_tab()
        self.notebook.add(self.clients_tab, text="Клиенты")
        self.notebook.add(self.deals_tab, text="Сделки")
        self.notebook.add(self.tasks_tab, text="Задачи")

        ttk.Label(self, textvariable=self.status, anchor="w", padding=8).pack(fill=tk.X)

    def _toolbar(self, parent: ttk.Frame, buttons: list[tuple[str, Callable[[], None]]]) -> ttk.Frame:
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, pady=(0, 6))
        for text, command in buttons:
            ttk.Button(bar, text=text, command=command).pack(side=tk.LEFT, padx=3)
        return bar

    def _tree(
        self,
        parent: ttk.Frame,
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=widths.get(col, 120), anchor="w")
        return tree

    def _selected_id(self, tree: ttk.Treeview) -> int | None:
        selected = tree.selection()
        if not selected:
            return None
        values = tree.item(selected[0], "values")
        return int(values[0])

    def _fill(self, tree: ttk.Treeview, rows: list[tuple[Any, ...]]) -> None:
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", tk.END, values=row)

    def _handle(self, action: Callable[[], None]) -> None:
        try:
            action()
        except ApiError as error:
            self.status.set(str(error))
            messagebox.showerror("Ошибка API", str(error), parent=self)
        except Exception as error:
            self.status.set(str(error))
            messagebox.showerror("Ошибка", str(error), parent=self)

    def _tree_rows(self, tree: ttk.Treeview) -> list[list[Any]]:
        return [list(tree.item(item_id, "values")) for item_id in tree.get_children()]

    def open_google_settings(self) -> None:
        dialog = GoogleSettingsDialog(self)
        self.wait_window(dialog)
        if dialog.result is not None:
            self.status.set("Настройки Google сохранены в data/google_gui_settings.txt")

    def _show_report_success(self, result: dict[str, Any]) -> None:
        link = result.get("webViewLink") or ""
        name = result.get("name") or "Отчёт"

        dialog = tk.Toplevel(self)
        dialog.title("Отчёт в Google Sheets")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=16)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Таблица создана", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        ttk.Label(body, text=f"Имя: {name}").pack(anchor="w", pady=(8, 4))
        ttk.Label(body, text="Ссылка:").pack(anchor="w")

        link_var = tk.StringVar(value=link)
        entry = ttk.Entry(body, textvariable=link_var, width=72)
        entry.pack(fill=tk.X, pady=4)
        entry.selection_range(0, tk.END)

        buttons = ttk.Frame(body)
        buttons.pack(fill=tk.X, pady=(12, 0))

        def open_link() -> None:
            if link:
                webbrowser.open(link)

        def copy_link() -> None:
            if not link:
                return
            self.clipboard_clear()
            self.clipboard_append(link)
            self.status.set("Ссылка скопирована в буфер обмена")

        ttk.Button(buttons, text="Открыть", command=open_link).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Копировать ссылку", command=copy_link).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(buttons, text="Закрыть", command=dialog.destroy).pack(side=tk.RIGHT)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_visibility()
        dialog.focus_set()

    def _export_tree_report(
        self,
        title: str,
        headers: tuple[str, ...],
        tree: ttk.Treeview,
    ) -> None:
        rows = self._tree_rows(tree)
        if not rows:
            messagebox.showinfo("Выгрузка", "Таблица пуста — нечего выгружать.", parent=self)
            return

        def action() -> None:
            self.status.set(f"Выгружаю «{title}» в Google Sheets…")
            self.update_idletasks()
            result = export_visible_table(title, headers, rows)
            self.status.set(f"Отчёт создан: {result.get('name')} ({result.get('rows')} строк)")
            self._show_report_success(result)

        self._handle(action)

    # ------------------------------- clients --------------------------------

    def _make_clients_tab(self) -> ttk.Frame:
        tab = ttk.Frame(self.notebook, padding=8)
        search_bar = ttk.Frame(tab)
        search_bar.pack(fill=tk.X, pady=(0, 6))
        self.client_search = tk.StringVar()
        ttk.Entry(search_bar, textvariable=self.client_search, width=40).pack(side=tk.LEFT)
        ttk.Button(search_bar, text="Поиск", command=self.search_clients).pack(side=tk.LEFT, padx=4)
        ttk.Button(search_bar, text="Сбросить", command=self.load_clients).pack(side=tk.LEFT)

        self._toolbar(
            tab,
            [
                ("Обновить", self.load_clients),
                ("Добавить", self.add_client),
                ("Изменить", self.edit_client),
                ("Архивировать", self.archive_client),
                ("Удалить", self.delete_client),
                ("Выгрузить отчёт", self.export_clients_report),
            ],
        )
        cols = ("id", "name", "phone", "email", "company", "status")
        self.clients_tree = self._tree(
            tab,
            cols,
            {
                "id": "ID",
                "name": "Имя",
                "phone": "Телефон",
                "email": "Email",
                "company": "Компания",
                "status": "Статус",
            },
            {"id": 50, "name": 180, "phone": 120, "email": 180, "company": 160, "status": 90},
        )
        return tab

    def load_clients(self) -> None:
        def action() -> None:
            items = self.api.get("/clients")
            self._fill(
                self.clients_tree,
                [
                    (
                        c["id"],
                        c.get("name") or "",
                        c.get("phone") or "",
                        c.get("email") or "",
                        c.get("company") or "",
                        c.get("status") or "",
                    )
                    for c in items
                ],
            )
            self.status.set(f"Клиенты: {len(items)}")

        self._handle(action)

    def search_clients(self) -> None:
        query = self.client_search.get().strip()
        if not query:
            self.load_clients()
            return

        def action() -> None:
            items = self.api.get("/clients/search", q=query)
            self._fill(
                self.clients_tree,
                [
                    (
                        c["id"],
                        c.get("name") or "",
                        c.get("phone") or "",
                        c.get("email") or "",
                        c.get("company") or "",
                        c.get("status") or "",
                    )
                    for c in items
                ],
            )
            self.status.set(f"Поиск клиентов «{query}»: {len(items)}")

        self._handle(action)

    def add_client(self) -> None:
        dialog = FormDialog(
            self,
            "Новый клиент",
            [
                ("name", "Имя *", "", "entry"),
                ("phone", "Телефон", "", "entry"),
                ("email", "Email", "", "entry"),
                ("company", "Компания", "", "entry"),
                ("notes", "Заметки", "", "text"),
                ("status", "Статус", "active", "combo:" + ",".join(CLIENT_STATUSES)),
            ],
        )
        self.wait_window(dialog)
        if not dialog.result or not dialog.result.get("name"):
            return

        def action() -> None:
            self.api.post("/clients", json=dialog.result)
            self.load_clients()

        self._handle(action)

    def edit_client(self) -> None:
        client_id = self._selected_id(self.clients_tree)
        if client_id is None:
            messagebox.showinfo("Клиенты", "Выберите клиента в таблице.")
            return

        def load_and_edit() -> None:
            client = self.api.get(f"/clients/{client_id}")
            dialog = FormDialog(
                self,
                f"Клиент #{client_id}",
                [
                    ("name", "Имя *", client.get("name"), "entry"),
                    ("phone", "Телефон", client.get("phone") or "", "entry"),
                    ("email", "Email", client.get("email") or "", "entry"),
                    ("company", "Компания", client.get("company") or "", "entry"),
                    ("notes", "Заметки", client.get("notes") or "", "text"),
                    (
                        "status",
                        "Статус",
                        client.get("status") or "active",
                        "combo:" + ",".join(CLIENT_STATUSES),
                    ),
                ],
            )
            self.wait_window(dialog)
            if not dialog.result or not dialog.result.get("name"):
                return
            self.api.patch(f"/clients/{client_id}", json=dialog.result)
            self.load_clients()

        self._handle(load_and_edit)

    def archive_client(self) -> None:
        client_id = self._selected_id(self.clients_tree)
        if client_id is None:
            messagebox.showinfo("Клиенты", "Выберите клиента в таблице.")
            return
        if not messagebox.askyesno("Архив", f"Архивировать клиента #{client_id}?"):
            return
        self._handle(lambda: (self.api.post(f"/clients/{client_id}/archive"), self.load_clients()))

    def delete_client(self) -> None:
        client_id = self._selected_id(self.clients_tree)
        if client_id is None:
            messagebox.showinfo("Клиенты", "Выберите клиента в таблице.")
            return
        if not messagebox.askyesno("Удаление", f"Удалить клиента #{client_id} безвозвратно?"):
            return
        self._handle(lambda: (self.api.delete(f"/clients/{client_id}"), self.load_clients()))

    def export_clients_report(self) -> None:
        self._export_tree_report("CRM Отчёт — Клиенты", self._client_headers, self.clients_tree)

    # -------------------------------- deals ---------------------------------

    def _make_deals_tab(self) -> ttk.Frame:
        tab = ttk.Frame(self.notebook, padding=8)
        search_bar = ttk.Frame(tab)
        search_bar.pack(fill=tk.X, pady=(0, 6))
        self.deal_search = tk.StringVar()
        ttk.Entry(search_bar, textvariable=self.deal_search, width=40).pack(side=tk.LEFT)
        ttk.Button(search_bar, text="Поиск", command=self.search_deals).pack(side=tk.LEFT, padx=4)
        ttk.Button(search_bar, text="Сбросить", command=self.load_deals).pack(side=tk.LEFT)

        self._toolbar(
            tab,
            [
                ("Обновить", self.load_deals),
                ("Добавить", self.add_deal),
                ("Изменить", self.edit_deal),
                ("Привязать клиента", self.attach_client_to_deal),
                ("Удалить", self.delete_deal),
                ("Выгрузить отчёт", self.export_deals_report),
            ],
        )
        cols = ("id", "title", "client_id", "amount", "currency", "status")
        self.deals_tree = self._tree(
            tab,
            cols,
            {
                "id": "ID",
                "title": "Название",
                "client_id": "Клиент ID",
                "amount": "Сумма",
                "currency": "Валюта",
                "status": "Статус",
            },
            {"id": 50, "title": 240, "client_id": 90, "amount": 100, "currency": 80, "status": 110},
        )
        return tab

    def load_deals(self) -> None:
        def action() -> None:
            items = self.api.get("/deals")
            self._fill(
                self.deals_tree,
                [
                    (
                        d["id"],
                        d.get("title") or "",
                        d.get("client_id") if d.get("client_id") is not None else "",
                        d.get("amount") if d.get("amount") is not None else "",
                        d.get("currency") or "",
                        d.get("status") or "",
                    )
                    for d in items
                ],
            )
            self.status.set(f"Сделки: {len(items)}")

        self._handle(action)

    def search_deals(self) -> None:
        query = self.deal_search.get().strip()
        if not query:
            self.load_deals()
            return

        def action() -> None:
            items = self.api.get("/deals/search", q=query)
            self._fill(
                self.deals_tree,
                [
                    (
                        d["id"],
                        d.get("title") or "",
                        d.get("client_id") if d.get("client_id") is not None else "",
                        d.get("amount") if d.get("amount") is not None else "",
                        d.get("currency") or "",
                        d.get("status") or "",
                    )
                    for d in items
                ],
            )
            self.status.set(f"Поиск сделок «{query}»: {len(items)}")

        self._handle(action)

    def add_deal(self) -> None:
        dialog = FormDialog(
            self,
            "Новая сделка",
            [
                ("title", "Название *", "", "entry"),
                ("client_id", "Клиент ID (опционально)", "", "entry"),
                ("amount", "Сумма", "0", "entry"),
                ("currency", "Валюта", "RUB", "entry"),
                ("status", "Статус", "new", "combo:" + ",".join(DEAL_STATUSES)),
                ("description", "Описание", "", "text"),
            ],
        )
        self.wait_window(dialog)
        if not dialog.result or not dialog.result.get("title"):
            return
        payload = dialog.result
        client_raw = payload.get("client_id", "").strip()
        payload["client_id"] = int(client_raw) if client_raw else None
        try:
            payload["amount"] = float(payload.get("amount") or 0)
        except ValueError:
            messagebox.showerror("Сделки", "Сумма должна быть числом.")
            return

        def action() -> None:
            self.api.post("/deals", json=payload)
            self.load_deals()

        self._handle(action)

    def edit_deal(self) -> None:
        deal_id = self._selected_id(self.deals_tree)
        if deal_id is None:
            messagebox.showinfo("Сделки", "Выберите сделку в таблице.")
            return

        def load_and_edit() -> None:
            deal = self.api.get(f"/deals/{deal_id}")
            dialog = FormDialog(
                self,
                f"Сделка #{deal_id}",
                [
                    ("title", "Название *", deal.get("title"), "entry"),
                    (
                        "client_id",
                        "Клиент ID",
                        "" if deal.get("client_id") is None else str(deal.get("client_id")),
                        "entry",
                    ),
                    ("amount", "Сумма", deal.get("amount") or 0, "entry"),
                    ("currency", "Валюта", deal.get("currency") or "RUB", "entry"),
                    (
                        "status",
                        "Статус",
                        deal.get("status") or "new",
                        "combo:" + ",".join(DEAL_STATUSES),
                    ),
                    ("description", "Описание", deal.get("description") or "", "text"),
                ],
            )
            self.wait_window(dialog)
            if not dialog.result or not dialog.result.get("title"):
                return
            payload = dialog.result
            client_raw = payload.get("client_id", "").strip()
            if client_raw:
                payload["client_id"] = int(client_raw)
            else:
                payload.pop("client_id", None)
                payload["detach_client"] = True
            payload["amount"] = float(payload.get("amount") or 0)
            self.api.patch(f"/deals/{deal_id}", json=payload)
            self.load_deals()

        self._handle(load_and_edit)

    def attach_client_to_deal(self) -> None:
        deal_id = self._selected_id(self.deals_tree)
        if deal_id is None:
            messagebox.showinfo("Сделки", "Выберите сделку в таблице.")
            return
        value = simpledialog.askstring(
            "Привязка клиента",
            "ID клиента (пусто = отвязать):",
            parent=self,
        )
        if value is None:
            return
        client_id = int(value) if value.strip() else None

        def action() -> None:
            self.api.post(f"/deals/{deal_id}/attach-client", client_id=client_id)
            self.load_deals()

        self._handle(action)

    def delete_deal(self) -> None:
        deal_id = self._selected_id(self.deals_tree)
        if deal_id is None:
            messagebox.showinfo("Сделки", "Выберите сделку в таблице.")
            return
        if not messagebox.askyesno("Удаление", f"Удалить сделку #{deal_id}?"):
            return
        self._handle(lambda: (self.api.delete(f"/deals/{deal_id}"), self.load_deals()))

    def export_deals_report(self) -> None:
        self._export_tree_report("CRM Отчёт — Сделки", self._deal_headers, self.deals_tree)

    # -------------------------------- tasks ---------------------------------

    def _make_tasks_tab(self) -> ttk.Frame:
        tab = ttk.Frame(self.notebook, padding=8)
        self._toolbar(
            tab,
            [
                ("Обновить", self.load_tasks),
                ("Добавить", self.add_task),
                ("Изменить", self.edit_task),
                ("Выполнено / не выполнено", self.toggle_task_done),
                ("Удалить", self.delete_task),
                ("Выгрузить отчёт", self.export_tasks_report),
            ],
        )
        cols = ("id", "title", "due_at", "is_done", "client_id", "deal_id")
        self.tasks_tree = self._tree(
            tab,
            cols,
            {
                "id": "ID",
                "title": "Задача",
                "due_at": "Срок",
                "is_done": "Готово",
                "client_id": "Клиент",
                "deal_id": "Сделка",
            },
            {"id": 50, "title": 280, "due_at": 140, "is_done": 80, "client_id": 80, "deal_id": 80},
        )
        return tab

    def load_tasks(self) -> None:
        def action() -> None:
            items = self.api.get("/tasks")
            self._fill(
                self.tasks_tree,
                [
                    (
                        t["id"],
                        t.get("title") or "",
                        t.get("due_at") or "",
                        "да" if t.get("is_done") else "нет",
                        t.get("client_id") if t.get("client_id") is not None else "",
                        t.get("deal_id") if t.get("deal_id") is not None else "",
                    )
                    for t in items
                ],
            )
            self.status.set(f"Задачи: {len(items)}")

        self._handle(action)

    def add_task(self) -> None:
        dialog = FormDialog(
            self,
            "Новая задача",
            [
                ("title", "Название *", "", "entry"),
                ("description", "Описание", "", "text"),
                ("due_at", "Срок (ISO/текст)", "", "entry"),
                ("client_id", "Клиент ID", "", "entry"),
                ("deal_id", "Сделка ID", "", "entry"),
                ("is_done", "Выполнено", False, "check"),
            ],
        )
        self.wait_window(dialog)
        if not dialog.result or not dialog.result.get("title"):
            return
        payload = dialog.result
        for key in ("client_id", "deal_id"):
            raw = str(payload.get(key, "")).strip()
            payload[key] = int(raw) if raw else None

        def action() -> None:
            self.api.post("/tasks", json=payload)
            self.load_tasks()

        self._handle(action)

    def edit_task(self) -> None:
        task_id = self._selected_id(self.tasks_tree)
        if task_id is None:
            messagebox.showinfo("Задачи", "Выберите задачу в таблице.")
            return

        def load_and_edit() -> None:
            task = self.api.get(f"/tasks/{task_id}")
            dialog = FormDialog(
                self,
                f"Задача #{task_id}",
                [
                    ("title", "Название *", task.get("title"), "entry"),
                    ("description", "Описание", task.get("description") or "", "text"),
                    ("due_at", "Срок", task.get("due_at") or "", "entry"),
                    (
                        "client_id",
                        "Клиент ID",
                        "" if task.get("client_id") is None else str(task.get("client_id")),
                        "entry",
                    ),
                    (
                        "deal_id",
                        "Сделка ID",
                        "" if task.get("deal_id") is None else str(task.get("deal_id")),
                        "entry",
                    ),
                    ("is_done", "Выполнено", bool(task.get("is_done")), "check"),
                ],
            )
            self.wait_window(dialog)
            if not dialog.result or not dialog.result.get("title"):
                return
            payload = dialog.result
            client_raw = str(payload.get("client_id", "")).strip()
            deal_raw = str(payload.get("deal_id", "")).strip()
            if client_raw:
                payload["client_id"] = int(client_raw)
            else:
                payload.pop("client_id", None)
                payload["detach_client"] = True
            if deal_raw:
                payload["deal_id"] = int(deal_raw)
            else:
                payload.pop("deal_id", None)
                payload["detach_deal"] = True
            self.api.patch(f"/tasks/{task_id}", json=payload)
            self.load_tasks()

        self._handle(load_and_edit)

    def toggle_task_done(self) -> None:
        task_id = self._selected_id(self.tasks_tree)
        if task_id is None:
            messagebox.showinfo("Задачи", "Выберите задачу в таблице.")
            return

        def action() -> None:
            task = self.api.get(f"/tasks/{task_id}")
            self.api.post(f"/tasks/{task_id}/done", json={"is_done": not bool(task.get("is_done"))})
            self.load_tasks()

        self._handle(action)

    def delete_task(self) -> None:
        task_id = self._selected_id(self.tasks_tree)
        if task_id is None:
            messagebox.showinfo("Задачи", "Выберите задачу в таблице.")
            return
        if not messagebox.askyesno("Удаление", f"Удалить задачу #{task_id}?"):
            return
        self._handle(lambda: (self.api.delete(f"/tasks/{task_id}"), self.load_tasks()))

    def export_tasks_report(self) -> None:
        self._export_tree_report("CRM Отчёт — Задачи", self._task_headers, self.tasks_tree)

    def refresh_all(self) -> None:
        self.load_clients()
        self.load_deals()
        self.load_tasks()


def main() -> None:
    app = CrmApp()
    app.mainloop()


if __name__ == "__main__":
    main()
