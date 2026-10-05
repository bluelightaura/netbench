"""Стенд — сменный источник железок, а не containerlab.

Виртуальный стенд поднимается сам и живёт один прогон; настоящие железки уже
стоят, и к ним просто подключаются. Набор тестов об этом не знает: он получает
узлы с адресами и умениями, а откуда они взялись — дело слоя 1.

    BENCH=virtual-l3  pytest        поднятый containerlab
    BENCH=real.local  pytest        настоящие железки
"""
from __future__ import annotations

import contextlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from lab import clab

try:
    import yaml
except ImportError:                                  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent
BENCH = os.environ.get("BENCH", "virtual-l3")
USER = os.environ.get("BENCH_USER", "netops")


@dataclass
class Node:
    name: str
    address: str
    profile: str = ""
    port: int = 22
    user: str = ""
    can: set[str] = field(default_factory=set)
    # Что набирать на этой железке. Тест просит понятие, профиль даёт команду.
    commands: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)

    def cmd(self, what: str, **kw) -> str:
        """Команда по смыслу: cmd("version"), cmd("interface", iface="eth1").

        Нет такой команды в профиле — тест пропускается, а не падает: значит
        эта железка такого понятия не знает, и это не дефект.
        """
        template = self.commands.get(what)
        if not template:
            pytest.skip(f"профиль «{self.profile}» не знает команды «{what}»")
        return template.format(**{**self.vars, **kw})

    @property
    def password(self) -> str:
        """Пароль только из окружения: ни в описании стенда, ни в репозитории."""
        per_host = os.environ.get(f"BENCH_PASSWORD_{self.name.upper()}")
        return per_host or os.environ.get("BENCH_PASSWORD", "netops")


def _load(path: Path) -> dict:
    """Прочитать описание. Нет файла или нет PyYAML - пустой словарь.

    Без skip внутри: хуки pytest вызываются вне теста, и skip оттуда роняет
    прогон с INTERNALERROR вместо внятного сообщения.
    """
    if yaml is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _yaml(path: Path) -> dict:
    """То же, но внутри теста: нечего читать - тест пропускается."""
    if yaml is None:
        pytest.skip("нужен PyYAML: pip install -e '.[test]'")
    if not path.exists():
        pytest.skip(f"нет файла {path.relative_to(ROOT)}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _caps(name: str) -> set[str]:
    """Умения профиля. Вне теста, поэтому через загрузчик без skip."""
    if not name:
        return set()
    return set(_load(ROOT / "lab" / "profiles" / f"{name}.yml").get("capabilities") or [])


def _benches() -> list[str]:
    """Имена стендов, которые можно назвать в --bench."""
    folder = ROOT / "lab" / "benches"
    return sorted(p.name[: -len(".yml")] for p in folder.glob("*.yml")) if folder.exists() else []


def _profile(name: str) -> dict:
    if not name:
        return {}
    return _yaml(ROOT / "lab" / "profiles" / f"{name}.yml")


def _virtual(spec: dict) -> dict[str, Node]:
    """Узлы живого containerlab: адреса раздаёт он, зашивать их нельзя."""
    topology = ROOT / "lab" / "topologies" / f"{spec['topology']}.clab.yml"
    declared = {
        name: ((node or {}).get("labels") or {}).get("profile", "")
        for name, node in (_yaml(topology).get("topology", {}).get("nodes") or {}).items()
    }
    try:
        out = subprocess.run(
            ["containerlab", "inspect", "-t", str(topology), "--format", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"стенд не поднят: {exc}")
    found = clab.nodes(json.loads(out), list(declared))
    if not found:
        pytest.skip(f"containerlab не вернул ни одного узла стенда «{BENCH}»")
    return {name: Node(name, address, declared.get(name, ""))
            for name, address in found.items()}


def _real(spec: dict) -> dict[str, Node]:
    """Железки, которые уже стоят: адреса из описания стенда."""
    nodes = {}
    for name, row in (spec.get("nodes") or {}).items():
        nodes[name] = Node(
            name=name,
            address=str(row.get("address", "")),
            profile=str(row.get("profile", "")),
            port=int(row.get("port", 22)),
            user=str(row.get("user", "")),
        )
    return nodes


@pytest.fixture(scope="session")
def bench_spec() -> dict:
    return _yaml(ROOT / "lab" / "benches" / f"{BENCH}.yml")


@pytest.fixture(scope="session")
def bench(bench_spec) -> dict[str, Node]:
    kind = bench_spec.get("kind", "virtual")
    nodes = _virtual(bench_spec) if kind == "virtual" else _real(bench_spec)
    if not nodes:
        pytest.skip(f"в стенде «{BENCH}» нет узлов")
    for node in nodes.values():
        spec = _profile(node.profile)
        node.can = set(spec.get("capabilities") or [])
        node.commands = dict(spec.get("commands") or {})
        node.vars = {k: v for k, v in spec.items()
                     if k not in {"commands", "capabilities", "name"}}
    return nodes


@pytest.fixture(scope="session")
def is_real(bench_spec) -> bool:
    return bench_spec.get("kind", "virtual") == "real"


@pytest.fixture
def cmd(bench):
    """Ярлык: cmd("r1", "version") — команда для этой железки.

    Ни одной вендорской строки в тестах; всё, что набирается, лежит в профиле.
    """
    def pick(node: str, what: str, **kw) -> str:
        return bench[node].cmd(what, **kw)
    return pick


@pytest.fixture
def one(bench):
    """Один узел стенда: `one()` — любой, `one("leaf")` — с таким началом имени.

    Нет подходящего узла — тест пропускается с объяснением, а не падает
    непрозрачным IndexError. Это тот же принцип, что у умений: стенд не про
    эту железку — не повод для красного.
    """
    def pick(prefix: str = "") -> str:
        for name in sorted(bench):
            if name.startswith(prefix):
                return name
        pytest.skip(f"в стенде «{BENCH}» нет узла с именем на «{prefix}»")
    return pick


@pytest.fixture
def every(bench):
    """Все узлы с таким началом имени, по порядку."""
    def pick(prefix: str = "") -> list[str]:
        return [name for name in sorted(bench) if name.startswith(prefix)]
    return pick


@pytest.fixture(scope="session")
def can(bench) -> set[str]:
    """Что умеет стенд целиком — объединение умений его узлов."""
    out: set[str] = set()
    for node in bench.values():
        out |= node.can
    return out


class Recorded:
    """Сессия, которая помнит разговор.

    Нужна не для отладки, а для отчёта: «прошло» без транскрипта ничем не
    отличается от «никто не смотрел». Каждая команда и каждый ответ ложатся в
    запись, которая потом уезжает вложением в Allure.
    """

    def __init__(self, conn, name: str, node: Node | None = None):
        self._conn = conn
        self._node = node
        self.name = name
        self.lines: list[str] = []

    def __getattr__(self, item):                     # всё прочее — как у netmiko
        return getattr(self._conn, item)

    def send_command(self, command: str, **kw) -> str:
        out = self._conn.send_command(command, **kw)
        self.lines.append(f"$ {command}\n{out}")
        return out

    def configure(self, commands) -> str:
        """Правка конфигурации командами из профиля, а не догадками библиотеки.

        send_config_set у netmiko решает за нас, как войти в режим настройки, и
        для device_type=linux это sudo. На железке, где вход сразу в CLI вроде
        vtysh, такой разговор не складывается: ждут приглашение оболочки,
        которого не будет. Что набирать, знает профиль — ровно как и везде
        здесь.

        Ответ читается по времени, а не по ожидаемому приглашению: в режиме
        настройки оно другое, и угадывать его значило бы снова зашить знание о
        конкретной платформе в набор.
        """
        keys = (self._node.vars if self._node else {})
        enter, leave = keys.get("config_enter"), keys.get("config_exit")
        if not enter or not leave:
            profile = self._node.profile if self._node else "?"
            pytest.skip(f"профиль «{profile}» не описывает вход в конфигурацию")
        answers = []
        for command in [enter, *commands, leave]:
            out = self._conn.send_command_timing(
                command, strip_prompt=False, strip_command=False)
            answers.append(f"$ {command}\n{out}")
        self.lines.extend(answers)
        return "\n".join(answers)

    @property
    def transcript(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def session(bench, request):
    """Сессия до узла. Закрывается всегда, транскрипт уходит в отчёт."""
    from netmiko import ConnectHandler

    opened: list[Recorded] = []

    def connect(name: str) -> Recorded:
        node = bench[name]
        import allure

        with allure.step(f"подключаюсь к {name} ({node.address}:{node.port})"):
            conn = ConnectHandler(
                device_type="linux", host=node.address, port=node.port,
                username=node.user or USER, password=node.password, fast_cli=False,
            )
        rec = Recorded(conn, name, node)
        opened.append(rec)
        return rec

    yield connect

    mode = request.config.getoption("--evidence")
    failed = getattr(request.node, "bench_failed", False)
    if mode == "always" or (mode == "auto" and failed):
        _attach(opened)
    for rec in opened:
        # Разорвать соединение можно и не суметь — узел уже мог уйти. На
        # результат теста это не влияет, а прогон ронять не должно.
        with contextlib.suppress(Exception):
            rec.disconnect()


def _attach(sessions: list[Recorded]) -> None:
    """Транскрипт каждой сессии — вложением к шагу отчёта."""
    try:
        import allure
    except ImportError:
        return
    for rec in sessions:
        if rec.lines:
            allure.attach(rec.transcript, name=f"транскрипт {rec.name}",
                          attachment_type=allure.attachment_type.TEXT)


def pytest_sessionfinish(session, exitstatus):
    """Слой 4: доложить отчёту, против чего гоняли, и не выдать пропуски за успех.

    Без этого Allure показывает результаты без контекста, и через неделю по
    отчёту уже не сказать, какой это был стенд и какая топология. Пишется
    здесь, а не в пайплайне, чтобы контекст был одинаковый во всех трёх CI
    и при запуске руками.
    """
    # Прогон, где все проверки на стенде пропущены, зелёный — и это худший
    # вид красного: выглядит как успех. Так уже было, когда containerlab сменил
    # формат вывода: стенд поднимался, узлы работали, разбор возвращал пустоту.
    if session.config.getoption("--require-bench") and not getattr(session, "bench_ran", False):
        session.exitstatus = 1
        print(f"\nстенд «{BENCH}»: ни одна проверка на стенде не выполнилась — "
              f"все пропущены. Прогон засчитан провальным (--require-bench).")

    results = Path(session.config.getoption("--alluredir") or "allure-results")
    if not results.exists():
        return
    spec = _load(ROOT / "lab" / "benches" / f"{BENCH}.yml")
    kind = spec.get("kind", "virtual")
    rows = {
        "Стенд": BENCH,
        "Тип": "настоящие железки" if kind == "real" else "виртуальный (containerlab)",
        "Топология": spec.get("topology", "-"),
        "Узлов в описании": len(spec.get("nodes") or {}) or "-",
        "Правка конфигурации разрешена": "да" if session.config.getoption("--apply") else "нет",
        "Доказательства": session.config.getoption("--evidence"),
        "Python": platform.python_version(),
        "pytest": pytest.__version__,
    }
    # XML, а не .properties: тот формат читается как ISO-8859-1 и разделяет
    # ключ и значение по первому пробелу. Русские названия превращались в
    # кракозябры, а «Узлов в описании» резалось на ключ «Узлов» и значение
    # «в описании». XML — UTF-8, и пробел в названии для него просто пробел.
    rendered = "".join(
        f"  <parameter>\n    <key>{escape(str(k))}</key>\n"
        f"    <value>{escape(str(v))}</value>\n  </parameter>\n"
        for k, v in rows.items())
    (results / "environment.xml").write_text(
        f"<environment>\n{rendered}</environment>\n", encoding="utf-8")

    categories = ROOT / "lab" / "allure" / "categories.json"
    if categories.exists():
        shutil.copyfile(categories, results / "categories.json")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Пометить тест стендом, на котором он шёл.

    Без этого отчёт из трёх стендов показывает один: Allure считает тест тем
    же самым, когда совпадают имя и параметры, а имя стенда в них не входило.
    Три прогона складывались в повторы одного, и «47 проверок на фабрике ЦОД»
    в отчёте было не найти.

    Хуком, а не фикстурой, и строго первым: до теста, пропущенного ещё при
    сборе, фикстура не доходит - а пропуск на одном стенде и пропуск на другом
    это тоже два разных факта.
    """
    try:
        import allure
    except ImportError:                              # pragma: no cover
        return
    allure.dynamic.parameter("стенд", BENCH)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Отметить падение, чтобы фикстура знала, прикладывать ли доказательства."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        item.bench_failed = True
    if report.when == "call" and item.get_closest_marker("lab") and not report.skipped:
        item.session.bench_ran = True


def pytest_addoption(parser):
    group = parser.getgroup("стенд")
    group.addoption(
        "--bench", action="store", default=None, metavar="ИМЯ",
        help="какой стенд брать: lab/benches/<ИМЯ>.yml (или переменная BENCH)",
    )
    group.addoption(
        "--apply", action="store_true", default=False,
        help="разрешить проверки, меняющие конфигурацию, на настоящих железках",
    )
    group.addoption(
        "--require-bench", action="store_true", default=False,
        help="считать прогон провальным, если ни одна проверка на стенде не выполнилась",
    )
    group.addoption(
        "--evidence", action="store", default="auto",
        choices=["auto", "always", "never"],
        help="прикладывать транскрипт сессии к отчёту: при падении, всегда, никогда",
    )


def pytest_configure(config):
    """Флаг главнее переменной окружения, переменная - умолчания.

    Здесь же проверяется, что такой стенд вообще есть: опечатка в имени
    должна читаться как опечатка, а не как внутренняя ошибка pytest.
    """
    global BENCH
    if config.getoption("--bench"):
        BENCH = config.getoption("--bench")
    if yaml is not None and not (ROOT / "lab" / "benches" / f"{BENCH}.yml").exists():
        known = ", ".join(_benches()) or "ни одного"
        raise pytest.UsageError(
            f"нет стенда «{BENCH}»: файла lab/benches/{BENCH}.yml не существует.\n"
            f"Есть: {known}"
        )


def pytest_collection_modifyitems(config, items):
    """Два фильтра: умения стенда и защита настоящего железа.

    Умение, которого стенд не объявил, — не повод для красного: набор просто
    не про эту железку. А вот правка конфигурации на живой железке без явного
    разрешения не должна случаться вовсе: там за ней стоит чей-то сервис.
    """
    spec = _load(ROOT / "lab" / "benches" / f"{BENCH}.yml")
    real = spec.get("kind", "virtual") == "real"
    have: set[str] = set()
    if real:
        for row in (spec.get("nodes") or {}).values():
            have |= _caps(str(row.get("profile", "")))
    else:
        topology = ROOT / "lab" / "topologies" / f"{spec.get('topology')}.clab.yml"
        for node in (_load(topology).get("topology", {}).get("nodes") or {}).values():
            have |= _caps(((node or {}).get("labels") or {}).get("profile", ""))

    for item in items:
        for mark in item.iter_markers(name="needs"):
            for want in mark.args:
                if want not in have:
                    item.add_marker(pytest.mark.skip(
                        reason=f"стенд «{BENCH}» не объявляет умение «{want}»"))
        if real and item.get_closest_marker("changes_config") and not config.getoption("--apply"):
            item.add_marker(pytest.mark.skip(
                reason="правка конфигурации на настоящей железке: добавь --apply"))
