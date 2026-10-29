from dataclasses import replace

import pytest
from evidence import Evidence, choose


@pytest.fixture
def ibus():
    return Evidence("@im=ibus", "", "ibus", False, True, False, True, True)


def test_coherent_session_signals_allow_candidate(ibus):
    assert choose(ibus) == "ibus"
    fcitx = Evidence("@im=fcitx", "fcitx", "fcitx", True, True, True, True, True)
    assert choose(fcitx) == "fcitx"  # GNOME's background IBus can coexist.


@pytest.mark.parametrize(
    "change",
    [
        {"xmodifiers": None},
        {"qt": None},
        {"gtk": "simple"},
        {"qt": "fcitx"},
        {"ibus_owner": False},
        {"ibus_owner": None},
        {"ibus_bridge": False},
        {"ibus_bridge": None},
        {"source_configuration_readable": False},
    ],
)
def test_missing_conflicting_or_unverified_evidence_falls_back(ibus, change):
    assert choose(replace(ibus, **change)) is None


def test_fcitx_bridge_absence_is_not_inferred_from_ibus_presence():
    assert (
        choose(Evidence("@im=fcitx", "fcitx", "", True, True, False, True, True))
        is None
    )
