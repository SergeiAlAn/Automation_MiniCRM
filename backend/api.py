"""
FastAPI-бэкенд мини-CRM.

Запуск из корня проекта:
    uvicorn backend.api:app --reload
Документация:
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .crm import CRM
from .models import CLIENT_STATUSES, DEAL_STATUSES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "crm.db"
crm = CRM(db_path=DB_PATH)

app = FastAPI(
    title="Mini CRM API",
    description="MVP CRM: клиенты, сделки, задачи (SQLite + FastAPI)",
    version="0.1.0",
)


# ----------------------------- Pydantic schemas -----------------------------


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    notes: str | None = None
    status: str = "active"


class ClientUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    notes: str | None = None
    status: str | None = None


class DealCreate(BaseModel):
    title: str = Field(..., min_length=1)
    client_id: int | None = None
    amount: float = 0.0
    currency: str = "RUB"
    status: str = "new"
    description: str | None = None


class DealUpdate(BaseModel):
    title: str | None = None
    client_id: int | None = None
    amount: float | None = None
    currency: str | None = None
    status: str | None = None
    description: str | None = None
    # явно отвязать клиента: {"detach_client": true}
    detach_client: bool = False


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    due_at: str | None = None
    is_done: bool = False
    client_id: int | None = None
    deal_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: str | None = None
    is_done: bool | None = None
    client_id: int | None = None
    deal_id: int | None = None
    detach_client: bool = False
    detach_deal: bool = False


class TaskDoneBody(BaseModel):
    is_done: bool = True


def _ok(data: Any) -> Any:
    return data


def _require(entity: dict[str, Any] | None, name: str = "Объект") -> dict[str, Any]:
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{name} не найден")
    return entity


# ---------------------------------- meta ------------------------------------


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "Mini CRM API",
        "docs": "/docs",
        "client_statuses": list(CLIENT_STATUSES),
        "deal_statuses": list(DEAL_STATUSES),
    }


# --------------------------------- clients ----------------------------------


@app.post("/clients", status_code=201)
def create_client(body: ClientCreate) -> dict[str, Any]:
    try:
        return _ok(crm.create_client(**body.model_dump()))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/clients")
def list_clients(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    return crm.list_clients(status=status, limit=limit, offset=offset)


@app.get("/clients/search")
def search_clients(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return crm.search_clients(q, limit=limit)


@app.get("/clients/{client_id}")
def get_client(client_id: int) -> dict[str, Any]:
    return _require(crm.get_client(client_id), "Клиент")


@app.patch("/clients/{client_id}")
def update_client(client_id: int, body: ClientUpdate) -> dict[str, Any]:
    if crm.get_client(client_id) is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    try:
        return _require(
            crm.update_client(client_id, **body.model_dump(exclude_unset=True)),
            "Клиент",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/clients/{client_id}/archive")
def archive_client(client_id: int) -> dict[str, Any]:
    if crm.get_client(client_id) is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return _require(crm.archive_client(client_id), "Клиент")


@app.delete("/clients/{client_id}")
def delete_client(client_id: int) -> dict[str, str]:
    if not crm.delete_client(client_id):
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return {"status": "deleted"}


# ---------------------------------- deals -----------------------------------


@app.post("/deals", status_code=201)
def create_deal(body: DealCreate) -> dict[str, Any]:
    try:
        return _ok(crm.create_deal(**body.model_dump()))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/deals")
def list_deals(
    status: str | None = Query(default=None),
    client_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    return crm.list_deals(status=status, client_id=client_id, limit=limit, offset=offset)


@app.get("/deals/search")
def search_deals(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return crm.search_deals(q, limit=limit)


@app.get("/deals/{deal_id}")
def get_deal(deal_id: int) -> dict[str, Any]:
    return _require(crm.get_deal(deal_id), "Сделка")


@app.patch("/deals/{deal_id}")
def update_deal(deal_id: int, body: DealUpdate) -> dict[str, Any]:
    if crm.get_deal(deal_id) is None:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    payload = body.model_dump(exclude_unset=True)
    detach = payload.pop("detach_client", False)
    if detach:
        payload["client_id"] = None
    try:
        return _require(crm.update_deal(deal_id, **payload), "Сделка")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/deals/{deal_id}/attach-client")
def attach_client(deal_id: int, client_id: int | None = Query(default=None)) -> dict[str, Any]:
    if crm.get_deal(deal_id) is None:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    try:
        return _require(crm.attach_client_to_deal(deal_id, client_id), "Сделка")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/deals/{deal_id}")
def delete_deal(deal_id: int) -> dict[str, str]:
    if not crm.delete_deal(deal_id):
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    return {"status": "deleted"}


# ---------------------------------- tasks -----------------------------------


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate) -> dict[str, Any]:
    try:
        return _ok(crm.create_task(**body.model_dump()))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/tasks")
def list_tasks(
    is_done: bool | None = Query(default=None),
    client_id: int | None = Query(default=None),
    deal_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    return crm.list_tasks(
        is_done=is_done,
        client_id=client_id,
        deal_id=deal_id,
        limit=limit,
        offset=offset,
    )


@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> dict[str, Any]:
    return _require(crm.get_task(task_id), "Задача")


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate) -> dict[str, Any]:
    if crm.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    payload = body.model_dump(exclude_unset=True)
    if payload.pop("detach_client", False):
        payload["client_id"] = None
    if payload.pop("detach_deal", False):
        payload["deal_id"] = None
    try:
        return _require(crm.update_task(task_id, **payload), "Задача")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/tasks/{task_id}/done")
def mark_task_done(task_id: int, body: TaskDoneBody | None = None) -> dict[str, Any]:
    if crm.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    is_done = True if body is None else body.is_done
    return _require(crm.set_task_done(task_id, is_done=is_done), "Задача")


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int) -> dict[str, str]:
    if not crm.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"status": "deleted"}
