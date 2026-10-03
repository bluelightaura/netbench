#!/usr/bin/env python3
"""Динамический инвентарь Ansible из описания стенда.

Смысл — один источник правды. Тот же lab/benches/<имя>.yml, по которому
работает pytest, кормит и плейбуки: иначе адреса пришлось бы держать в двух
местах, и однажды они разойдутся.

    BENCH=real.local ansible-playbook -i lab/provision/inventory.py baseline.yml
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
BENCH = os.environ.get("BENCH", "real.local")


def main() -> int:
    spec_path = ROOT / "lab" / "benches" / f"{BENCH}.yml"
    if not spec_path.exists():
        print(json.dumps({"_meta": {"hostvars": {}}}))
        return 0
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}

    if spec.get("kind") != "real":
        # Виртуальный стенд разворачивает containerlab: конфигурации
        # монтируются при старте узла, плейбуку там делать нечего.
        print(json.dumps({"_meta": {"hostvars": {}}}))
        return 0

    hostvars, groups = {}, {}
    for name, row in (spec.get("nodes") or {}).items():
        profile = str(row.get("profile", ""))
        hostvars[name] = {
            "ansible_host": row.get("address"),
            "ansible_port": int(row.get("port", 22)),
            "ansible_user": row.get("user") or os.environ.get("BENCH_USER", "netops"),
            "bench_profile": profile,
        }
        # Группа на класс железки: плейбук применяет своё к своим.
        groups.setdefault(profile or "unprofiled", {"hosts": []})["hosts"].append(name)

    out = {"_meta": {"hostvars": hostvars},
           "bench": {"children": sorted(groups)},
           **groups}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
