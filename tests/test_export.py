"""Выгрузка стенда в формате инструмента.

Смысл выгрузки в том, что адреса живут в одном месте. Поэтому проверяется не
«не упало», а что в выдаче ровно то, что инструмент ожидает прочитать.
"""
from __future__ import annotations

import json

import pytest
import yaml

NODES = [
    {"name": "sw1", "address": "sw1.example.net", "profile": "l3-switch", "port": 22},
    {"name": "sw2", "address": "sw2.example.net", "profile": "l3-switch", "port": 22},
    {"name": "cpe1", "address": "cpe1.example.net", "profile": "cpe-generic", "port": 2022},
]


def _sections(text: str) -> dict[str, list[str]]:
    r"""Разобрать inventory.conf на секции.

    Делить просто по «[» нельзя: приглашение в профиле — регулярное выражение
    и само содержит скобки (\S+[#>]). Заголовок — это строка целиком.
    """
    out: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("[") and line.rstrip().endswith("]"):
            current = line.strip()[1:-1]
            out[current] = []
        elif current and line.strip():
            out[current].append(line)
    return out


def test_clirunner_groups_nodes_by_profile(export):
    sections = _sections(export.as_clirunner(NODES))
    assert {"defaults", "l3-switch", "cpe-generic"} <= set(sections), \
        "секции по классам железок не разделены"
    # Коммутатор не должен получить настройки CPE: узлы стоят в своей секции.
    switch = "\n".join(sections["l3-switch"])
    assert "sw1" in switch and "sw2" in switch
    assert "cpe1" not in switch
    assert "sw1" not in "\n".join(sections["cpe-generic"])


def test_clirunner_does_not_merge_profile_keys_into_defaults(export):
    """Ключи разных профилей, слитые в [defaults], означали бы чужие настройки."""
    sections = _sections(export.as_clirunner(NODES))
    defaults = "\n".join(sections["defaults"])
    for key in ("prompt", "config_enter", "config_exit", "save_cmd"):
        assert key not in defaults, f"ключ {key} утёк в [defaults]"


def test_clirunner_carries_profile_keys(export, root):
    """Ключи различий берутся из профиля, а не пишутся руками."""
    profile = yaml.safe_load((root / "lab" / "profiles" / "l3-switch.yml").read_text("utf-8"))
    out = export.as_clirunner(NODES)
    for key in ("prompt", "config_enter", "config_exit", "save_cmd"):
        if profile.get(key):
            assert f"{key} = {profile[key]}" in out, f"в выгрузке нет ключа {key} из профиля"


def test_clirunner_keeps_the_port(export):
    assert "port=2022" in export.as_clirunner(NODES)


def test_traphy_export_is_valid_json_with_hosts(export):
    rows = json.loads(export.as_traphy(NODES))
    assert [r["name"] for r in rows] == ["sw1", "sw2", "cpe1"]
    assert [r["host"] for r in rows] == [n["address"] for n in NODES]
    assert all(r["use_ssh"] for r in rows)


def test_cliradar_export_names_the_password_variable_and_holds_no_secret(export):
    """Пароль не должен попадать в файл - только имя переменной окружения."""
    cfg = yaml.safe_load(export.as_cliradar(NODES))
    device = cfg["device"]
    assert device["password_env"] == "BENCH_PASSWORD"
    assert "password" not in device, "в выгрузке CLIRadar оказался сам пароль"
    assert device["host"] == "sw1.example.net"


def test_cliradar_export_refuses_an_empty_bench(export):
    with pytest.raises(IndexError):
        export.as_cliradar([])


def test_real_bench_is_read_without_containerlab(export, root, monkeypatch):
    """Настоящий стенд описан файлом: поднимать нечего, containerlab не нужен."""
    monkeypatch.setattr(export, "BENCH", "real.example")
    rows = export.nodes()
    assert {r["name"] for r in rows} == {"cpe1", "cpe2", "sw1"}
    assert all(r.get("address") for r in rows)
