"""
CRUD-слой мини-CRM на SQLite3 (встроенный модуль sqlite3).

При инициализации создаёт таблицы из models.py, если их ещё нет.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ALL_CREATE_STATEMENTS, CLIENT_STATUSES, DEAL_STATUSES


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


class CRM:
    """CRUD-операции для клиентов, сделок и задач."""

    def __init__(self, db_path: str | Path = "crm.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # SQLite LOWER() не умеет кириллицу — регистрируем unicode-версию
        conn.create_function("ULOWER", 1, lambda value: value.lower() if value else "")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            for statement in ALL_CREATE_STATEMENTS:
                conn.execute(statement)
            conn.commit()

    # ------------------------------------------------------------------ clients

    def create_client(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        company: str | None = None,
        notes: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        if status not in CLIENT_STATUSES:
            raise ValueError(f"Недопустимый статус клиента: {status}")
        stamp = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO clients (name, phone, email, company, notes, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, phone, email, company, notes, status, stamp, stamp),
            )
            conn.commit()
            return self.get_client(cursor.lastrowid, conn=conn)  # type: ignore[arg-type]

    def get_client(
        self,
        client_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        owns = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM clients WHERE id = ?",
                (client_id,),
            ).fetchone()
            return _row_to_dict(row)
        finally:
            if owns:
                conn.close()

    def list_clients(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM clients"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_client(self, client_id: int, **fields: Any) -> dict[str, Any] | None:
        allowed = {"name", "phone", "email", "company", "notes", "status"}
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if "status" in updates and updates["status"] not in CLIENT_STATUSES:
            raise ValueError(f"Недопустимый статус клиента: {updates['status']}")
        if not updates:
            return self.get_client(client_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [client_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE clients SET {assignments} WHERE id = ?", values)
            conn.commit()
            return self.get_client(client_id, conn=conn)

    def archive_client(self, client_id: int) -> dict[str, Any] | None:
        return self.update_client(client_id, status="archived")

    def delete_client(self, client_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            conn.commit()
            return cursor.rowcount > 0

    def search_clients(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Поиск клиентов без учёта регистра (аналог ILIKE)."""
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM clients
                WHERE ULOWER(name) LIKE ULOWER(?)
                   OR ULOWER(IFNULL(phone, '')) LIKE ULOWER(?)
                   OR ULOWER(IFNULL(email, '')) LIKE ULOWER(?)
                   OR ULOWER(IFNULL(company, '')) LIKE ULOWER(?)
                   OR ULOWER(IFNULL(notes, '')) LIKE ULOWER(?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, pattern, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------- deals

    def create_deal(
        self,
        title: str,
        client_id: int | None = None,
        amount: float = 0.0,
        currency: str = "RUB",
        status: str = "new",
        description: str | None = None,
    ) -> dict[str, Any]:
        if status not in DEAL_STATUSES:
            raise ValueError(f"Недопустимый статус сделки: {status}")
        if client_id is not None and self.get_client(client_id) is None:
            raise ValueError(f"Клиент id={client_id} не найден")
        stamp = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO deals (title, client_id, amount, currency, status, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, client_id, amount, currency, status, description, stamp, stamp),
            )
            conn.commit()
            return self.get_deal(cursor.lastrowid, conn=conn)  # type: ignore[arg-type]

    def get_deal(
        self,
        deal_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        owns = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
            return _row_to_dict(row)
        finally:
            if owns:
                conn.close()

    def list_deals(
        self,
        status: str | None = None,
        client_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if client_id is not None:
            clauses.append("client_id = ?")
            params.append(client_id)
        query = "SELECT * FROM deals"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_deal(self, deal_id: int, **fields: Any) -> dict[str, Any] | None:
        allowed = {"title", "client_id", "amount", "currency", "status", "description"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        # None для client_id допустим (отвязать клиента); остальные None пропускаем
        updates = {
            key: value
            for key, value in updates.items()
            if key == "client_id" or value is not None
        }
        if "status" in updates and updates["status"] not in DEAL_STATUSES:
            raise ValueError(f"Недопустимый статус сделки: {updates['status']}")
        if "client_id" in updates and updates["client_id"] is not None:
            if self.get_client(updates["client_id"]) is None:
                raise ValueError(f"Клиент id={updates['client_id']} не найден")
        if not updates:
            return self.get_deal(deal_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [deal_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE deals SET {assignments} WHERE id = ?", values)
            conn.commit()
            return self.get_deal(deal_id, conn=conn)

    def attach_client_to_deal(self, deal_id: int, client_id: int | None) -> dict[str, Any] | None:
        return self.update_deal(deal_id, client_id=client_id)

    def delete_deal(self, deal_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
            conn.commit()
            return cursor.rowcount > 0

    def search_deals(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Поиск сделок без учёта регистра (аналог ILIKE)."""
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM deals
                WHERE ULOWER(title) LIKE ULOWER(?)
                   OR ULOWER(IFNULL(description, '')) LIKE ULOWER(?)
                   OR ULOWER(IFNULL(currency, '')) LIKE ULOWER(?)
                   OR ULOWER(status) LIKE ULOWER(?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------- tasks

    def create_task(
        self,
        title: str,
        description: str | None = None,
        due_at: str | None = None,
        is_done: bool = False,
        client_id: int | None = None,
        deal_id: int | None = None,
    ) -> dict[str, Any]:
        if client_id is not None and self.get_client(client_id) is None:
            raise ValueError(f"Клиент id={client_id} не найден")
        if deal_id is not None and self.get_deal(deal_id) is None:
            raise ValueError(f"Сделка id={deal_id} не найдена")
        stamp = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (title, description, due_at, is_done, client_id, deal_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, description, due_at, int(is_done), client_id, deal_id, stamp, stamp),
            )
            conn.commit()
            return self.get_task(cursor.lastrowid, conn=conn)  # type: ignore[arg-type]

    def get_task(
        self,
        task_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        owns = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            data = _row_to_dict(row)
            if data is not None:
                data["is_done"] = bool(data["is_done"])
            return data
        finally:
            if owns:
                conn.close()

    def list_tasks(
        self,
        is_done: bool | None = None,
        client_id: int | None = None,
        deal_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if is_done is not None:
            clauses.append("is_done = ?")
            params.append(int(is_done))
        if client_id is not None:
            clauses.append("client_id = ?")
            params.append(client_id)
        if deal_id is not None:
            clauses.append("deal_id = ?")
            params.append(deal_id)
        query = "SELECT * FROM tasks"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["is_done"] = bool(item["is_done"])
                result.append(item)
            return result

    def update_task(self, task_id: int, **fields: Any) -> dict[str, Any] | None:
        allowed = {"title", "description", "due_at", "is_done", "client_id", "deal_id"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        updates = {
            key: value
            for key, value in updates.items()
            if key in {"client_id", "deal_id", "due_at"} or value is not None
        }
        if "is_done" in updates:
            updates["is_done"] = int(bool(updates["is_done"]))
        if "client_id" in updates and updates["client_id"] is not None:
            if self.get_client(updates["client_id"]) is None:
                raise ValueError(f"Клиент id={updates['client_id']} не найден")
        if "deal_id" in updates and updates["deal_id"] is not None:
            if self.get_deal(updates["deal_id"]) is None:
                raise ValueError(f"Сделка id={updates['deal_id']} не найдена")
        if not updates:
            return self.get_task(task_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [task_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", values)
            conn.commit()
            return self.get_task(task_id, conn=conn)

    def set_task_done(self, task_id: int, is_done: bool = True) -> dict[str, Any] | None:
        return self.update_task(task_id, is_done=is_done)

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0
