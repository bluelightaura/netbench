"""Офлайн-проверки каркаса: без containerlab, без SSH, без железок.

Слой 2 проверяет железки, а эти тесты проверяют сам слой 2: что описания
читаются, профили сходятся с топологиями, выгрузка даёт то, что инструмент
ожидает увидеть. Они гоняются всегда, в том числе в CI без стенда, — иначе
зелёный прогон из одних пропусков ничего не доказывает.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def export():
    """lab/export.py как модуль: он скрипт, а не пакет."""
    spec = importlib.util.spec_from_file_location("bench_export", ROOT / "lab" / "export.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_export"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def harness():
    """Корневой conftest как обычный модуль: в нём живёт разбор стенда.

    Грузится по пути, а не по имени: модулей с именем conftest в прогоне два,
    и какой из них достанется по импорту - вопрос везения.
    """
    spec = importlib.util.spec_from_file_location("bench_harness", ROOT / "conftest.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_harness"] = module
    spec.loader.exec_module(module)
    return module
