"""Описания стендов, топологий и профилей сходятся друг с другом.

Расхождение здесь не падает на этапе чтения - оно падает на стенде, через
полчаса после `make up`, и выглядит как «тесты пропущены, непонятно почему».
"""
from __future__ import annotations

import yaml


def _read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _benches(root):
    return sorted((root / "lab" / "benches").glob("*.yml"))


def _profiles(root):
    return sorted((root / "lab" / "profiles").glob("*.yml"))


def test_benches_exist(root):
    assert _benches(root), "нет ни одного описания стенда в lab/benches"


def test_every_bench_declares_its_kind(root):
    for path in _benches(root):
        spec = _read(path)
        assert spec.get("kind") in {"virtual", "real"}, f"{path.name}: kind не virtual и не real"


def test_virtual_bench_points_at_an_existing_topology(root):
    for path in _benches(root):
        spec = _read(path)
        if spec.get("kind") != "virtual":
            continue
        topology = root / "lab" / "topologies" / f"{spec['topology']}.clab.yml"
        assert topology.exists(), f"{path.name}: нет топологии {topology.name}"


def test_real_bench_nodes_name_a_profile(root):
    for path in _benches(root):
        spec = _read(path)
        if spec.get("kind") != "real":
            continue
        for name, row in (spec.get("nodes") or {}).items():
            profile = (row or {}).get("profile", "")
            assert (root / "lab" / "profiles" / f"{profile}.yml").exists(), \
                f"{path.name}: узел {name} ссылается на профиль «{profile}», которого нет"


def test_every_topology_node_names_a_profile_that_exists(root):
    for path in sorted((root / "lab" / "topologies").glob("*.clab.yml")):
        nodes = _read(path).get("topology", {}).get("nodes") or {}
        assert nodes, f"{path.name}: в топологии нет узлов"
        for name, node in nodes.items():
            profile = ((node or {}).get("labels") or {}).get("profile", "")
            assert profile, f"{path.name}: узел {name} без метки profile"
            assert (root / "lab" / "profiles" / f"{profile}.yml").exists(), \
                f"{path.name}: узел {name} ссылается на профиль «{profile}», которого нет"


def test_every_topology_binds_an_existing_config(root):
    for path in sorted((root / "lab" / "topologies").glob("*.clab.yml")):
        for name, node in (_read(path).get("topology", {}).get("nodes") or {}).items():
            for bind in (node or {}).get("binds") or []:
                source = bind.split(":")[0]
                assert (path.parent / source).resolve().exists(), \
                    f"{path.name}: узел {name} монтирует {source}, которого нет"


def test_profiles_declare_capabilities_and_commands(root):
    for path in _profiles(root):
        spec = _read(path)
        assert spec.get("capabilities"), f"{path.name}: профиль без capabilities"
        assert spec.get("commands"), f"{path.name}: профиль без commands"


def test_profile_commands_are_formattable(root):
    """Шаблон команды должен собираться из того, что профиль сам же и даёт.

    Иначе `cmd("interface")` падает KeyError уже на живой железке.
    """
    for path in _profiles(root):
        spec = _read(path)
        known = {k: v for k, v in spec.items() if k not in {"commands", "capabilities", "name"}}
        for what, template in (spec.get("commands") or {}).items():
            import string
            fields = {f for _, f, _, _ in string.Formatter().parse(template) if f}
            missing = fields - set(known)
            # Поля, которые тест передаёт сам (iface, vlan), заполняются вызовом.
            assert missing <= {"iface", "vlan", "neighbor", "peer"}, \
                f"{path.name}: команда «{what}» требует {missing}, профиль их не даёт"


def test_profile_that_claims_config_describes_how_to_enter_and_leave_it(root):
    """Умение «config» без описанных команд — обещание, которое не выполнить."""
    for path in _profiles(root):
        spec = _read(path)
        if "config" not in (spec.get("capabilities") or []):
            continue
        for key in ("config_enter", "config_exit", "config_cmd"):
            assert spec.get(key), f"{path.name}: объявлен config, но нет ключа {key}"


def test_leaving_config_mode_is_not_the_same_as_saving(root):
    """Выход и сохранение — разные действия.

    Совпали — почти наверняка одно из них описано неверно: так уже было, когда
    выходом значился commit, который сохраняет, но из режима не выводит, и
    следующая же команда получала «Unknown command».
    """
    for path in _profiles(root):
        spec = _read(path)
        exit_cmd, save_cmd = spec.get("config_exit"), spec.get("save_cmd")
        if exit_cmd and save_cmd:
            assert exit_cmd != save_cmd, \
                f"{path.name}: config_exit и save_cmd — одна и та же команда «{exit_cmd}»"
