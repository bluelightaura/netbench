"""Инструменты против живого стенда — по описаниям, а не по коду.

Каждый инструмент описан файлом в lab/tools/*.yml: чем зовётся, в каком виде
ему отдать стенд, что проверить. Подключить свой — положить рядом такой же.

Стенд от инструментов не зависит: нет в системе — набор пропускается с
объяснением. Отсутствие не дефект.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import allure
import pytest
import yaml

pytestmark = [pytest.mark.lab, pytest.mark.regress, pytest.mark.needs("cli")]

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = sorted((ROOT / "lab" / "tools").glob("*.yml"))


def _cases():
    for path in TOOLS:
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for check in spec.get("checks") or []:
            yield pytest.param(spec, check,
                               id=f"{spec.get('name', path.stem)}-{check.get('title', '')[:30]}")


@pytest.mark.parametrize("spec,check", list(_cases()))
def test_tool_against_the_bench(spec, check, tmp_path):
    name = spec.get("name", "?")
    binary = shutil.which(spec.get("binary", name))
    if not binary:
        pytest.skip(f"инструмент «{name}» не установлен — это не дефект стенда")

    allure.dynamic.epic("Инструменты на стенде")
    allure.dynamic.feature(name)
    allure.dynamic.title(check.get("title", "проверка"))

    # Стенд выгружает себя в родном для инструмента виде: адреса не должны
    # жить в двух местах.
    with allure.step(f"выгружаю стенд как {spec.get('export')}"):
        dump = subprocess.run(
            [sys.executable, str(ROOT / "lab" / "export.py"), spec["export"]],
            capture_output=True, text=True)
        if dump.returncode != 0:
            pytest.skip(f"стенд не выгружается: {dump.stderr.strip()}")
        export = tmp_path / spec.get("export_as", "bench.txt")
        export.write_text(dump.stdout, encoding="utf-8")
        allure.attach(dump.stdout, f"стенд для {name}", allure.attachment_type.TEXT)

    extra = {}
    if check.get("needs_file"):
        f = tmp_path / check["needs_file"]["name"]
        f.write_text(check["needs_file"]["text"], encoding="utf-8")
        extra["file"] = str(f)

    args = [a.format(export=str(export), **extra) for a in check.get("run", [])]
    with allure.step(f"{name} {' '.join(args)}"):
        out = subprocess.run([binary, *args], capture_output=True, text=True, timeout=180)
        allure.attach(out.stdout + out.stderr, "вывод", allure.attachment_type.TEXT)

    want = check.get("expect", ".")
    assert re.search(want, out.stdout + out.stderr), \
        f"{name}: в выводе нет «{want}»\n{(out.stdout + out.stderr)[:400]}"
