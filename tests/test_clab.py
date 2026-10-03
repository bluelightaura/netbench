"""Разбор вывода containerlab во всех формах, которые он принимал.

Этот разбор однажды тихо сломался: containerlab 0.68 стал группировать
контейнеры по имени стенда, набор ждал старую форму и получал пустоту. Стенд
поднимался, узлы работали, а все проверки на стенде пропускались — и прогон
был зелёный. Тесты ниже держат все три формы сразу.
"""
from __future__ import annotations

from lab import clab

DECLARED = ["sw1", "sw2"]

# Текущий формат: контейнеры сгруппированы по имени стенда (0.68 и новее).
BY_LAB = {
    "bench-l3": [
        {"lab_name": "bench-l3", "name": "clab-bench-l3-sw1", "state": "running",
         "ipv4_address": "192.0.2.2/24", "kind": "linux"},
        {"lab_name": "bench-l3", "name": "clab-bench-l3-sw2", "state": "running",
         "ipv4_address": "192.0.2.3/24", "kind": "linux"},
    ]
}

# Прежний формат: контейнеры под ключом containers.
WITH_KEY = {"containers": [
    {"name": "clab-bench-l3-sw1", "ipv4_address": "192.0.2.2/24"},
    {"name": "clab-bench-l3-sw2", "ipv4_address": "192.0.2.3/24"},
]}

# Совсем прежний: просто список.
PLAIN = [
    {"name": "clab-bench-l3-sw1", "ipv4_address": "192.0.2.2/24"},
    {"name": "clab-bench-l3-sw2", "ipv4_address": "192.0.2.3/24"},
]


def test_every_known_format_gives_the_same_nodes():
    want = {"sw1": "192.0.2.2", "sw2": "192.0.2.3"}
    for name, data in (("по стендам", BY_LAB), ("containers", WITH_KEY), ("списком", PLAIN)):
        assert clab.nodes(data, DECLARED) == want, f"форма «{name}» разобрана не так"


def test_address_loses_the_prefix_length():
    assert clab.address({"ipv4_address": "192.0.2.2/24"}) == "192.0.2.2"
    assert clab.address({}) == ""


def test_node_name_handles_a_dash_inside_the_name():
    """Узел может называться cpe-1: резать всё до последнего дефиса нельзя."""
    row = {"lab_name": "bench-cpe", "name": "clab-bench-cpe-cpe-1"}
    assert clab.node_name(row, ["cpe-1", "cpe-2", "ctrl"]) == "cpe-1"


def test_longer_name_wins_over_its_own_prefix():
    """leaf1 не должен подойти раньше, чем leaf10."""
    row = {"name": "clab-dc-leaf10"}
    assert clab.node_name(row, ["leaf1", "leaf10"]) == "leaf10"


def test_container_not_declared_in_the_topology_is_ignored():
    data = {"bench-l3": [{"name": "clab-bench-l3-stranger", "ipv4_address": "192.0.2.9/24"}]}
    assert clab.nodes(data, DECLARED) == {}


def test_node_without_an_address_is_not_taken():
    data = {"bench-l3": [{"name": "clab-bench-l3-sw1", "ipv4_address": ""}]}
    assert clab.nodes(data, DECLARED) == {}


def test_empty_and_broken_output_gives_nothing_instead_of_raising():
    for data in ({}, [], None, "", {"bench-l3": None}, {"bench-l3": "не список"}):
        assert clab.nodes(data, DECLARED) == {}
