"""Только там, где стенд объявил умение «l2»."""
import pytest

pytestmark = [pytest.mark.lab, pytest.mark.regress, pytest.mark.needs("l2")]


def test_link_between_nodes_is_up(bench, one, session, cmd):
    name = one()
    iface = bench[name].vars.get("interface", "eth1")
    out = session(name).send_command(cmd(name, "interface", iface=iface))
    assert "up" in out.lower(), "линк между узлами не поднялся"
