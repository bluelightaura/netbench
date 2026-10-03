"""Образец теста. Не собирается pytest: имя файла не начинается с test_.

Скопировать в нужную папку под именем test_<о чём>.py и править.

Куда класть:
    suites/common/   верно для любой железки с CLI
    suites/l2/       коммутация: влан, транк, таблица MAC
    suites/dc/       ЦОД: evpn, vxlan, фабрика
    suites/sdwan/    SD-WAN: туннели, bfd, политика
    suites/<своё>/   новый класс — новая папка, ничего настраивать не надо

Папка — для людей, а что реально выполнится, решают метки needs().
"""
import allure
import pytest

# lab          — нужен поднятый стенд
# needs(...)   — умение из профиля железки; нет его — тест пропускается
#                с объяснением, а не падает красным
# smoke/regress/slow — уровень, выбирается через -m
pytestmark = [pytest.mark.lab, pytest.mark.regress, pytest.mark.needs("cli")]


# Тесткейс живёт здесь же, а не отдельным документом: иначе он разойдётся с
# кодом, и через месяц никто не будет знать, какая из двух версий правда.
# Allure собирает из этих аннотаций читаемую карточку в отчёте.
@allure.epic("Сетевое оборудование")
@allure.feature("Поверхность CLI")
@allure.story("Железка отвечает на запрос версии")
@allure.title("show version возвращает непустой ответ")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("""
Предусловие: стенд поднят, узел отвечает на SSH.
Шаги:        подключиться, выполнить show version.
Ожидается:   непустой ответ.
Почему:      если железка молчит, отличить «ответила пусто» от «не ответила»
             нечем, и все следующие проверки бессмысленны.
""")
# Ссылка на систему управления тестами, если она есть. Номер — единственное,
# что дублируется, и он не протухает.
# @allure.testcase("https://tms.example.com/case/123", "TMS-123")
def test_something(one, session, cmd):
    """Что именно проверяем и почему это важно."""
    name = one()
    conn = session(name)                 # сессия пишет транскрипт сама

    with allure.step("что делаем на этом шаге"):
        # Вендорских строк в тестах нет: просим понятие, команду даёт профиль.
        #   cmd(name, "version")            -> show version      (l3-switch)
        #   cmd(name, "interface", iface=…) -> show interface eth1
        out = conn.send_command(cmd(name, "version"))

    assert out.strip(), f"{name}: пришла пустота"


# Тест, который правит железку, помечается отдельно: на виртуальном стенде он
# идёт всегда, на настоящей — только с --apply.
@pytest.mark.changes_config
@pytest.mark.needs("config")
def test_something_that_changes_the_device(one, session):
    conn = session(one())
    conn.send_config_set(["interface eth1", "description проба"])
    assert "проба" in conn.send_command("show running-config")
    conn.send_config_set(["interface eth1", "no description"])


# Доступные фикстуры:
#   bench       узлы стенда: имя -> адрес, порт, профиль, умения
#   one         one() любой узел, one("cpe") первый с таким началом имени;
#               нет подходящего — тест пропускается, а не падает
#   every       every("leaf") все узлы с таким началом имени
#   session     вызов session("имя") даёт сессию до узла
#   cmd         cmd("узел", "понятие") -> команда именно этой железки
#   can         множество умений стенда целиком
#   is_real     настоящие железки или виртуальные
#   bench_spec  описание стенда как есть
