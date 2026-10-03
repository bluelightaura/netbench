"""Поведение каркаса: что делает узел, когда его просят о несуществующем.

Главное свойство набора - отсутствие умения не превращается в красный тест.
Проверяется именно оно, потому что сломать его легко и незаметно.
"""
from __future__ import annotations

import pytest


def test_command_comes_from_the_profile(harness):
    node = harness.Node("sw1", "sw1.example.net", "l3-switch",
                        commands={"version": "show version"})
    assert node.cmd("version") == "show version"


def test_command_template_takes_arguments(harness):
    node = harness.Node("sw1", "sw1.example.net", "l3-switch",
                        commands={"interface": "show interface {iface}"})
    assert node.cmd("interface", iface="eth1") == "show interface eth1"


def test_command_template_takes_profile_variables(harness):
    """Переменная из профиля подставляется без участия теста."""
    node = harness.Node("sw1", "sw1.example.net", "l3-switch",
                        commands={"neighbors": "show {proto} neighbor"},
                        vars={"proto": "ip ospf"})
    assert node.cmd("neighbors") == "show ip ospf neighbor"


def test_unknown_command_skips_instead_of_failing(harness):
    """Железка не знает понятия - это не дефект, это другая железка."""
    node = harness.Node("sw1", "sw1.example.net", "l3-switch", commands={})
    with pytest.raises(BaseException) as caught:
        node.cmd("evpn")
    assert caught.typename == "Skipped", f"ожидался пропуск, получили {caught.typename}"


def test_password_comes_from_the_environment_not_the_descriptor(harness, monkeypatch):
    monkeypatch.setenv("BENCH_PASSWORD", "общий")
    node = harness.Node("sw1", "sw1.example.net", "l3-switch")
    assert node.password == "общий"


def test_per_node_password_wins_over_the_common_one(harness, monkeypatch):
    monkeypatch.setenv("BENCH_PASSWORD", "общий")
    monkeypatch.setenv("BENCH_PASSWORD_SW1", "отдельный")
    node = harness.Node("sw1", "sw1.example.net", "l3-switch")
    assert node.password == "отдельный"


def test_known_benches_are_listed_for_a_typo(harness):
    """Список стендов нужен сообщению об ошибке - он не должен быть пустым."""
    assert "virtual-l3" in harness._benches()


def test_capabilities_are_read_without_raising_on_a_missing_profile(harness):
    assert harness._caps("no-such-profile") == set()
    assert "cli" in harness._caps("l3-switch")
