"""Что отчёт обязан рассказать про прогон - и в каком виде.

Обе проверки здесь стоят за найденным в опубликованном отчёте. Блок
«окружение» показывал кракозябры вместо русских названий и резал «Узлов в
описании» пополам. А три прогона по трём стендам складывались в один: 53
теста в отчёте вместо 138, потому что стенд не входил в личность теста.
"""
from __future__ import annotations

import json
import sys
import types
from xml.etree import ElementTree


class FakeConfig:
    def __init__(self, alluredir):
        self.values = {"--alluredir": str(alluredir), "--require-bench": False,
                       "--apply": False, "--evidence": "auto"}

    def getoption(self, name):
        return self.values[name]


class FakeSession:
    def __init__(self, alluredir):
        self.config = FakeConfig(alluredir)
        self.exitstatus = 0
        self.bench_ran = True


def _finish(harness, tmp_path):
    results = tmp_path / "allure-results"
    results.mkdir()
    harness.pytest_sessionfinish(FakeSession(results), 0)
    return results


def test_environment_is_written_as_xml(harness, tmp_path):
    """.properties читается как ISO-8859-1 - русские названия там не живут."""
    results = _finish(harness, tmp_path)
    assert (results / "environment.xml").exists()
    assert not (results / "environment.properties").exists(), \
        "старый формат остался рядом - Allure покажет кракозябры"


def test_environment_is_valid_xml(harness, tmp_path):
    results = _finish(harness, tmp_path)
    root = ElementTree.fromstring((results / "environment.xml").read_text("utf-8"))
    assert root.tag == "environment"
    assert root.findall("parameter"), "в окружении ни одного параметра"


def test_cyrillic_survives(harness, tmp_path):
    results = _finish(harness, tmp_path)
    root = ElementTree.fromstring((results / "environment.xml").read_text("utf-8"))
    keys = [p.find("key").text for p in root.findall("parameter")]
    assert "Стенд" in keys and "Топология" in keys


def test_a_key_with_spaces_stays_whole(harness, tmp_path):
    """В .properties пробел разделяет ключ и значение, и ключ резало пополам."""
    results = _finish(harness, tmp_path)
    root = ElementTree.fromstring((results / "environment.xml").read_text("utf-8"))
    pairs = {p.find("key").text: p.find("value").text for p in root.findall("parameter")}
    assert "Правка конфигурации разрешена" in pairs
    assert pairs["Правка конфигурации разрешена"] == "нет"


def test_categories_travel_with_the_results(harness, tmp_path):
    results = _finish(harness, tmp_path)
    categories = json.loads((results / "categories.json").read_text("utf-8"))
    assert any("стенд" in c.get("name", "").lower() for c in categories)


def test_every_test_is_marked_with_its_bench(harness, monkeypatch):
    """Иначе три стенда в отчёте складываются в один прогон с повторами."""
    recorded = []
    fake = types.ModuleType("allure")
    fake.dynamic = types.SimpleNamespace(
        parameter=lambda name, value: recorded.append((name, value)))
    monkeypatch.setitem(sys.modules, "allure", fake)

    harness.pytest_runtest_setup(object())
    assert recorded == [("стенд", harness.BENCH)]


def test_marking_survives_a_bench_without_allure(harness, monkeypatch):
    """Набор зависит от allure не больше, чем от любого другого инструмента."""
    monkeypatch.setitem(sys.modules, "allure", None)
    harness.pytest_runtest_setup(object())      # не должно падать
