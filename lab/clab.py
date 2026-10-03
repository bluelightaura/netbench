"""Разбор вывода containerlab. Одно место на весь проект.

Формат `inspect --format json` менялся: раньше контейнеры лежали списком или под
ключом `containers`, с версии 0.68 они сгруппированы по имени стенда. Набор
должен понимать все три вида — иначе обновление containerlab на раннере молча
превращает прогон в пропуски: стенд поднят, узлы работают, а разбор возвращает
пустоту, и тесты пропускаются с «стенд не поднят». Зелёный прогон из одних
пропусков — худший вид красного, потому что он выглядит как успех.

Имя узла берётся сопоставлением с тем, что объявлено в топологии, а не
отрезанием всего до последнего дефиса: узел вполне может называться `cpe-1`.
"""
from __future__ import annotations

from typing import Any


def containers(data: Any) -> list[dict]:
    """Контейнеры из вывода inspect, в каком бы виде он ни пришёл."""
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("containers"), list):
        return [row for row in data["containers"] if isinstance(row, dict)]
    found: list[dict] = []
    for value in data.values():                 # 0.68+: ключ — имя стенда
        if isinstance(value, list):
            found.extend(row for row in value if isinstance(row, dict))
    return found


def node_name(row: dict, declared: list[str]) -> str:
    """Короткое имя узла по тому, что объявлено в топологии.

    containerlab зовёт контейнер `clab-<стенд>-<узел>`. Сопоставляем с
    объявленными именами, начиная с самых длинных: иначе `leaf1` подойдёт
    раньше, чем `leaf10`.
    """
    full = str(row.get("name") or row.get("label") or "")
    if not full:
        return ""
    for name in sorted(declared, key=len, reverse=True):
        if full == name or full.endswith(f"-{name}"):
            return name
    return ""


def address(row: dict) -> str:
    """Адрес узла без длины префикса."""
    value = row.get("ipv4_address") or row.get("ipv4-address") or ""
    return str(value).split("/")[0]


def nodes(data: Any, declared: list[str]) -> dict[str, str]:
    """Имя узла -> адрес. Узлы без имени или без адреса не берутся."""
    found: dict[str, str] = {}
    for row in containers(data):
        name = node_name(row, declared)
        addr = address(row)
        if name and addr:
            found[name] = addr
    return found
