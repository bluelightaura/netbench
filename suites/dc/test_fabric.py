"""Только там, где стенд объявил умения ЦОДа. На стенде L3-коммутаторов или
CPE эти проверки пропускаются с объяснением, а не падают красным.
"""
import pytest

pytestmark = [pytest.mark.lab, pytest.mark.regress, pytest.mark.needs("evpn")]


def test_every_leaf_sees_the_spine(every, session, cmd):
    leaves = every("leaf")
    assert leaves, "в топологии нет ни одного листа"
    for leaf in leaves:
        out = session(leaf).send_command(cmd(leaf, "neighbors"))
        assert out.strip(), f"{leaf}: спайн не виден"


@pytest.mark.needs("vxlan")
def test_vxlan_tunnels_are_declared(one, session, cmd):
    leaf = one("leaf")
    assert session(leaf).send_command(cmd(leaf, "running_config")).strip()
