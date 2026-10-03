"""Конфигурация применяется и откатывается — общее для всех железок.

Помечено changes_config: на виртуальном стенде идёт всегда, на настоящей
железке — только с --apply. За живой конфигурацией стоит чей-то сервис.
"""
import allure
import pytest

pytestmark = [pytest.mark.lab, pytest.mark.needs("config"),
              pytest.mark.changes_config,
              pytest.mark.regress]


@allure.feature("Конфигурация")
@allure.title("Правка применяется и снимается")
def test_change_applies_and_rolls_back(bench, one, session, cmd):
    name = one()
    conn = session(name)
    iface = bench[name].vars.get("interface", "eth1")
    with allure.step("ставлю описание на интерфейс"):
        conn.configure([f"interface {iface}", "description bench-check"])
    assert "bench-check" in conn.send_command(cmd(name, "running_config"))
    with allure.step("снимаю описание обратно"):
        conn.configure([f"interface {iface}", "no description"])
    assert "bench-check" not in conn.send_command(cmd(name, "running_config"))
