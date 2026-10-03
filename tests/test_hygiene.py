"""Что не должно уехать в публичный репозиторий.

Правило простое: описание настоящего стенда - это адреса и логины живой сети,
и ему здесь не место. Проверять это глазами перед каждым пушем бесполезно,
поэтому проверяет тест.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# Диапазоны, выделенные под документацию (RFC 5737), плюс служебные адреса.
# Всё остальное в репозитории считается адресом живой сети.
ALLOWED = re.compile(
    r"^(?:192\.0\.2\.\d{1,3}|198\.51\.100\.\d{1,3}|203\.0\.113\.\d{1,3}"
    r"|0\.0\.0\.0|127\.0\.0\.1|255(?:\.\d{1,3}){3})$"
)

SKIP_DIRS = {".git", ".venv", "allure-results", "allure-report", "__pycache__",
             ".pytest_cache", ".ruff_cache", "assets"}
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".md", ".ini", ".cfg", ".conf", ".toml",
                 ".tf", ".tftpl", ".sh", ".txt", ""}


def _files(root: Path):
    """Файлы, которые уедут в репозиторий.

    Спрашивается git, а не файловая система: рядом с исходниками лежит то, что
    оставляют инструменты - containerlab пишет свой каталог прогона с адресами
    контейнеров и сгенерированными паролями. Он закрыт .gitignore, никуда не
    уедет, и ругаться на него незачем.
    """
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, text=True, check=False,
    )
    if listed.returncode == 0:
        names = [n for n in listed.stdout.split("\0") if n]
    else:                                            # не репозиторий - обойти руками
        names = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
        names = [n for n in names if not any(part in SKIP_DIRS or part.startswith("clab-")
                                             or part.endswith(".egg-info")
                                             for part in Path(n).parts)]
    for name in names:
        path = root / name
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def test_no_addresses_outside_the_documentation_ranges(root):
    """Адрес живой сети в репозитории - утечка, а не опечатка."""
    found: list[str] = []
    for path in _files(root):
        for number, line in enumerate(path.read_text("utf-8", "replace").splitlines(), 1):
            for match in IP.findall(line):
                if not ALLOWED.match(match):
                    found.append(f"{path.relative_to(root)}:{number}: {match}")
    assert not found, "адреса вне диапазонов для документации:\n" + "\n".join(found)


def test_bench_descriptors_carry_no_addresses_at_all(root):
    """Образец настоящего стенда описывается именами, а не адресами.

    В своём `*.local.yml` можно писать что угодно - он закрыт .gitignore.
    """
    found = []
    for path in sorted((root / "lab" / "benches").glob("*.yml")):
        for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if IP.search(line):
                found.append(f"{path.name}:{number}: {line.strip()}")
    assert not found, "в описании стенда оказались адреса:\n" + "\n".join(found)


def test_no_real_bench_descriptor_is_committed(root):
    leaked = sorted(p.name for p in (root / "lab" / "benches").glob("*.local.yml"))
    assert not leaked, f"описание настоящего стенда лежит в репозитории: {leaked}"


def test_no_password_is_written_anywhere(root):
    """Пароли берутся из окружения. Строка с паролем в файле - ошибка."""
    suspicious = re.compile(r"^\s*(?:password|passwd|secret)\s*[:=]\s*(?!$)(?!\$)(?!\{)", re.I)
    found = []
    for path in _files(root):
        if path.name.startswith("test_"):
            continue
        for number, line in enumerate(path.read_text("utf-8", "replace").splitlines(), 1):
            if suspicious.match(line) and "_env" not in line:
                found.append(f"{path.relative_to(root)}:{number}: {line.strip()}")
    assert not found, "похоже на записанный пароль:\n" + "\n".join(found)
