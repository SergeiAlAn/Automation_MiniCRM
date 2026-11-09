"""
Тестовый сидер CRM: заполняет клиенты / сделки / задачи через HTTP API.

Запуск (бэкенд должен быть доступен, по умолчанию http://127.0.0.1:8000):
    python seed_crm_data.py

В каждую сущность пишется ~1000 реалистичных записей.
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

API_URL = os.getenv("CRM_API_URL", "http://127.0.0.1:8000").rstrip("/")
COUNT = 1000

FIRST_NAMES = [
    "Александр", "Анна", "Дмитрий", "Елена", "Иван", "Мария", "Сергей", "Ольга",
    "Андрей", "Наталья", "Алексей", "Екатерина", "Павел", "Татьяна", "Николай",
    "Юлия", "Максим", "Ирина", "Владимир", "Светлана", "Кирилл", "Дарья",
    "Роман", "Полина", "Артём", "Виктория", "Михаил", "Алина", "Егор", "Валерия",
]
LAST_NAMES = [
    "Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Васильев",
    "Новиков", "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов",
    "Егоров", "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев",
    "Макаров", "Никитин", "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев",
]
COMPANIES = [
    "ООО «СеверТорг»", "АО «Технолайн»", "ИП Ковалёв", "ООО «Городские системы»",
    "ООО «Альфа Логистика»", "АО «МеталлПром»", "ООО «ЦифраСофт»", "ООО «ЭкоДом»",
    "АО «Ривьера»", "ООО «Сфера»", "ИП Морозова", "ООО «Невский Партнёр»",
    "ООО «Байкал Сервис»", "АО «Орион»", "ООО «СтройМакс»", "ООО «ФинКонсалт»",
    "ООО «МедТех»", "АО «АгроПоле»", "ООО «КлиматПро»", "ООО «ДатаХаб»",
]
DEAL_TITLES = [
    "Поставка оборудования", "Годовой контракт поддержки", "Внедрение CRM",
    "Аудит инфраструктуры", "Лицензии ПО", "Маркетинговая кампания",
    "Аутсорс разработки", "Поставка комплектующих", "Сервисное обслуживание",
    "Обучение персонала", "Облачная подписка", "Ремонт и монтаж",
    "Пилотный проект", "Расширение SLA", "Интеграция API",
]
TASK_TITLES = [
    "Позвонить клиенту", "Подготовить КП", "Согласовать договор",
    "Напомнить об оплате", "Назначить встречу", "Собрать документы",
    "Проверить акт", "Отправить счёт", "Уточнить требования",
    "Передать в бухгалтерию", "Обновить статус сделки", "Запросить реквизиты",
]
NOTES = [
    "Постоянный клиент", "Пришёл с рекомендации", "Интересует отсрочка",
    "Нужен счёт до пятницы", "Корпоративный сегмент", "Малый бизнес",
    "Повторная продажа", "Холодный лид", "VIP", "Региональный партнёр",
]
CLIENT_STATUSES = ["active", "active", "active", "active", "archived"]
DEAL_STATUSES = ["new", "in_progress", "in_progress", "won", "won", "lost", "cancelled"]
CURRENCIES = ["RUB", "RUB", "RUB", "USD", "EUR"]


def _phone() -> str:
    return f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"


def _email(first: str, last: str, index: int) -> str:
    domains = ["mail.ru", "yandex.ru", "gmail.com", "company.ru", "biz.ru"]
    return f"{first.lower()}.{last.lower()}{index % 97}@{random.choice(domains)}"


def _due_at() -> str | None:
    if random.random() < 0.15:
        return None
    day = date.today() + timedelta(days=random.randint(-20, 60))
    return day.isoformat()


def _log(message: str) -> None:
    print(message, flush=True)


def create_clients(session: requests.Session) -> list[int]:
    ids: list[int] = []
    _log(f"Создаю {COUNT} клиентов…")
    for i in range(1, COUNT + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        # согласование фамилии для женских имён — упрощённо
        if first[-1] in "аяь" and not last.endswith("а") and last.endswith(("ов", "ев", "ин")):
            last = last + "а"
        payload = {
            "name": f"{last} {first}",
            "phone": _phone(),
            "email": _email(first, last, i),
            "company": random.choice(COMPANIES),
            "notes": random.choice(NOTES),
            "status": random.choice(CLIENT_STATUSES),
        }
        response = session.post(f"{API_URL}/clients", json=payload, timeout=30)
        response.raise_for_status()
        ids.append(response.json()["id"])
        if i % 100 == 0 or i == COUNT:
            _log(f"  клиенты: {i}/{COUNT}")
    return ids


def create_deals(session: requests.Session, client_ids: list[int]) -> list[int]:
    ids: list[int] = []
    _log(f"Создаю {COUNT} сделок…")
    for i in range(1, COUNT + 1):
        attach_client = random.random() > 0.12
        payload = {
            "title": f"{random.choice(DEAL_TITLES)} #{i}",
            "client_id": random.choice(client_ids) if attach_client else None,
            "amount": round(random.uniform(5_000, 2_500_000), 2),
            "currency": random.choice(CURRENCIES),
            "status": random.choice(DEAL_STATUSES),
            "description": random.choice(
                [
                    "Счёт выставлен",
                    "Ждём согласование юристов",
                    "Клиент запросил скидку 5%",
                    "Поставка в два этапа",
                    "Нужна предоплата 30%",
                    "Контракт на 12 месяцев",
                ]
            ),
        }
        response = session.post(f"{API_URL}/deals", json=payload, timeout=30)
        response.raise_for_status()
        ids.append(response.json()["id"])
        if i % 100 == 0 or i == COUNT:
            _log(f"  сделки: {i}/{COUNT}")
    return ids


def create_tasks(
    session: requests.Session,
    client_ids: list[int],
    deal_ids: list[int],
) -> None:
    _log(f"Создаю {COUNT} задач…")
    for i in range(1, COUNT + 1):
        link_client = random.random() > 0.25
        link_deal = random.random() > 0.35
        payload = {
            "title": f"{random.choice(TASK_TITLES)} #{i}",
            "description": random.choice(
                [
                    "Связаться до конца дня",
                    "Подготовить материалы к созвону",
                    "Проверить вложение в письме",
                    "Согласовать с руководителем",
                    "Зафиксировать результат в CRM",
                ]
            ),
            "due_at": _due_at(),
            "is_done": random.random() < 0.35,
            "client_id": random.choice(client_ids) if link_client else None,
            "deal_id": random.choice(deal_ids) if link_deal else None,
        }
        response = session.post(f"{API_URL}/tasks", json=payload, timeout=30)
        response.raise_for_status()
        if i % 100 == 0 or i == COUNT:
            _log(f"  задачи: {i}/{COUNT}")


def main() -> int:
    _log(f"API: {API_URL}")
    session = requests.Session()
    try:
        health = session.get(f"{API_URL}/", timeout=10)
        health.raise_for_status()
    except requests.RequestException as error:
        _log(f"API недоступен: {error}")
        _log("Запустите backend (docker compose up -d или uvicorn) и повторите.")
        return 1

    try:
        client_ids = create_clients(session)
        deal_ids = create_deals(session, client_ids)
        create_tasks(session, client_ids, deal_ids)
    except requests.HTTPError as error:
        _log(f"Ошибка HTTP: {error.response.status_code} {error.response.text[:500]}")
        return 1
    except requests.RequestException as error:
        _log(f"Ошибка запроса: {error}")
        return 1

    _log("Готово: по ~1000 клиентов, сделок и задач.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
