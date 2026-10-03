"""Только там, где стенд объявил умения SD-WAN. На стенде коммутаторов
эти проверки не падают красным, а пропускаются с объяснением.
"""
import pytest

pytestmark = [pytest.mark.lab, pytest.mark.regress, pytest.mark.needs("sdwan")]


def test_cpe_sees_the_controller(one, session, cmd):
    cpe = one("cpe")
    out = session(cpe).send_command(cmd(cpe, "neighbors"))
    assert out.strip(), "CPE не отвечает на запрос о соседях"


@pytest.mark.needs("bfd")
def test_bfd_sessions_are_alive(one, session, cmd):
    cpe = one("cpe")
    assert session(cpe).send_command(cmd(cpe, "tunnels")).strip()
