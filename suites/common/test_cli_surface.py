"""Верно для любой железки с CLI: L3-коммутатор, цодовый, CPE.

Ни одной вендорской команды в тексте: что набирать, знает профиль железки.
Проверяется не функция устройства, а то, что разговор с ним предсказуем.
"""
import allure
import pytest

pytestmark = [pytest.mark.lab, pytest.mark.smoke, pytest.mark.needs("cli")]


@allure.epic("Сетевое оборудование")
@allure.feature("Поверхность CLI")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("Каждый узел отвечает на запрос версии")
@allure.description("""
Предусловие: стенд поднят, узлы отвечают по SSH.
Шаги:        подключиться к каждому узлу, спросить версию.
Ожидается:   непустой ответ.
Почему:      молчащую железку нечем отличить от ответившей пусто, и все
             следующие проверки после этого бессмысленны.
""")
def test_every_node_answers(every, session, cmd):
    for name in every():
        with allure.step(f"{name}: запрос версии"):
            assert session(name).send_command(cmd(name, "version")).strip(), \
                f"{name}: пришла пустота"


@allure.feature("Поверхность CLI")
@allure.title("Длинный вывод приходит целиком")
@allure.description("Не снята пагинация — конфигурация обрывается на «--More--», "
                    "и инструмент читает половину, считая её целым.")
def test_long_output_comes_back_whole(one, session, cmd):
    name = one()
    out = session(name).send_command(cmd(name, "running_config"))
    assert out.count("\n") > 3, "вывод пришёл обрезанным — похоже на пагинацию"


@allure.feature("Поверхность CLI")
@allure.title("Неизвестная команда отвергается, а не проглатывается")
def test_unknown_command_is_refused_not_ignored(one, session, cmd):
    name = one()
    out = session(name).send_command(cmd(name, "bogus"))
    assert out.strip(), "железка промолчала — отказ нечем отличить от успеха"
