"""
Модели таблиц мини-CRM для SQLite.

Типы SQLite:
  INTEGER — целые числа, булевы флаги (0/1), внешние ключи
  REAL    — суммы сделок
  TEXT    — строки, статусы, даты в ISO-8601
"""

from __future__ import annotations

from typing import Final

# --- Статусы (соглашения приложения) ---

CLIENT_STATUSES: Final = ("active", "archived")
DEAL_STATUSES: Final = ("new", "in_progress", "won", "lost", "cancelled")

# --- SQL DDL ---

CREATE_CLIENTS: Final = """
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT,
    email       TEXT,
    company     TEXT,
    notes       TEXT,
    status      TEXT    NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'archived')),
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""

CREATE_DEALS: Final = """
CREATE TABLE IF NOT EXISTS deals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    client_id   INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    amount      REAL    NOT NULL DEFAULT 0,
    currency    TEXT    NOT NULL DEFAULT 'RUB',
    status      TEXT    NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new', 'in_progress', 'won', 'lost', 'cancelled')),
    description TEXT,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""

CREATE_TASKS: Final = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    due_at      TEXT,
    is_done     INTEGER NOT NULL DEFAULT 0
                        CHECK (is_done IN (0, 1)),
    client_id   INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    deal_id     INTEGER REFERENCES deals(id) ON DELETE SET NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""

CREATE_INDEXES: Final = (
    "CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);",
    "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);",
    "CREATE INDEX IF NOT EXISTS idx_deals_client ON deals(client_id);",
    "CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_deal ON tasks(deal_id);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(is_done);",
)

ALL_CREATE_STATEMENTS: Final = (
    CREATE_CLIENTS,
    CREATE_DEALS,
    CREATE_TASKS,
    *CREATE_INDEXES,
)
