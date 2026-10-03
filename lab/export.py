#!/usr/bin/env python3
"""Отдать стенд инструментам в их родном виде.

Стенд знает про себя всё: адреса, порты, профили. Инструменты знают свой формат
инвентаря. Сводить это руками — значит однажды развести. Поэтому стенд
выгружает себя сам:

    python lab/export.py clirunner > inventory.conf
    python lab/export.py traphy
    python lab/export.py cliradar

Зависимости ни на один инструмент здесь нет: это просто текст в их формате.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BENCH = os.environ.get("BENCH", "virtual-l3")


def nodes() -> list[dict]:
    spec = yaml.safe_load((ROOT / "lab" / "benches" / f"{BENCH}.yml").read_text(encoding="utf-8"))
    if spec.get("kind") == "real":
        return [{"name": n, **(row or {})} for n, row in (spec.get("nodes") or {}).items()]

    topology = ROOT / "lab" / "topologies" / f"{spec['topology']}.clab.yml"
    declared = yaml.safe_load(topology.read_text(encoding="utf-8"))
    profiles = {n: ((v or {}).get("labels") or {}).get("profile", "")
                for n, v in (declared.get("topology", {}).get("nodes") or {}).items()}
    out = subprocess.run(
        ["containerlab", "inspect", "-t", str(topology), "--format", "json"],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    rows = data.get("containers", data if isinstance(data, list) else [])
    found = []
    for row in rows:
        name = (row.get("label") or row.get("name") or "").split("-")[-1]
        address = (row.get("ipv4_address") or "").split("/")[0]
        if name and address:
            found.append({"name": name, "address": address,
                          "profile": profiles.get(name, ""), "port": 22})
    return found


def profile(name: str) -> dict:
    path = ROOT / "lab" / "profiles" / f"{name}.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def as_clirunner(ns: list[dict]) -> str:
    """inventory.conf: секция на класс железки, ключи различий из профиля.

    Группировать обязательно: ключи разных профилей, слитые в [defaults],
    означали бы, что коммутатор получил настройки CPE.
    """
    user = os.environ.get("BENCH_USER", "netops")
    lines = ["[defaults]", f"user   = {user}", "port   = 22", ""]
    by_profile: dict[str, list[dict]] = {}
    for n in ns:
        by_profile.setdefault(n.get("profile") or "bench", []).append(n)

    for name, rows in sorted(by_profile.items()):
        lines.append(f"[{name}]")
        p = profile(name)
        for key in ("prompt", "config_enter", "config_exit", "config_cmd", "save_cmd"):
            if p.get(key):
                lines.append(f"{key} = {p[key]}")
        for n in rows:
            lines.append(f"{n['name']}  {n['address']}  port={n.get('port', 22)}")
        lines.append("")
    return "\n".join(lines)


def as_traphy(ns: list[dict]) -> str:
    """Цели traphy: имя, хост, движок."""
    return json.dumps(
        [{"name": n["name"], "host": n["address"], "engine": "scapy",
          "use_ssh": True} for n in ns],
        indent=2, ensure_ascii=False) + "\n"


def as_cliradar(ns: list[dict]) -> str:
    """config.yml CLIRadar: одна цель за раз — берём первую."""
    first = ns[0]
    p = profile(first.get("profile", ""))
    return yaml.safe_dump({
        "device": {
            "host": first["address"],
            "port": first.get("port", 22),
            "username": os.environ.get("BENCH_USER", "netops"),
            "password_env": "BENCH_PASSWORD",
            "transport": "ssh",
            "prompt": p.get("prompt", ""),
        }
    }, allow_unicode=True, sort_keys=False)


FORMATS = {"clirunner": as_clirunner, "traphy": as_traphy, "cliradar": as_cliradar}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in FORMATS:
        print(f"как: {Path(__file__).name} [{' | '.join(FORMATS)}]", file=sys.stderr)
        return 2
    ns = nodes()
    if not ns:
        print("стенд пуст или не поднят", file=sys.stderr)
        return 1
    sys.stdout.write(FORMATS[sys.argv[1]](ns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
