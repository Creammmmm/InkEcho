from dataclasses import replace

import pytest

from inkecho.platform.framework_detection import Evidence, choose


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


def test_live_detector_requires_matching_real_owner(monkeypatch):
    import asyncio

    from inkecho.platform import framework_detection as module

    class Bus:
        async def connect(self):
            return self

        def disconnect(self):
            pass

    async def command(*arguments):
        if arguments[0].endswith("systemctl"):
            return "XMODIFIERS=@im=ibus\nQT_IM_MODULE=ibus\n"
        return "[('xkb', 'us')]\n"

    async def identity(_bus, name, **_kwargs):
        return ("ibus", ":1.12") if name == "org.freedesktop.IBus" else None

    monkeypatch.setattr(module, "_command", command)
    monkeypatch.setattr(module, "MessageBus", Bus)
    monkeypatch.setattr(module, "owner_identity", identity)
    assert asyncio.run(module.collect_system_framework()) == ("ibus", ":1.12")

    async def changed_identity(_bus, name, **_kwargs):
        return ("fcitx", ":1.55")

    monkeypatch.setattr(module, "owner_identity", changed_identity)
    assert asyncio.run(module.collect_system_framework()) is None


def test_live_detector_rejects_invalid_or_unavailable_sources(monkeypatch):
    import asyncio

    from inkecho.platform import framework_detection as module

    async def command(*arguments):
        if arguments[0].endswith("systemctl"):
            return "XMODIFIERS=@im=ibus\nQT_IM_MODULE=ibus\n"
        return "[(garbage)]"

    monkeypatch.setattr(module, "_command", command)
    assert asyncio.run(module.collect_system_framework()) is None


def test_fcitx_can_be_selected_with_valid_empty_gnome_sources(monkeypatch):
    import asyncio

    from inkecho.platform import framework_detection as module

    class Bus:
        async def connect(self):
            return self

        def disconnect(self):
            pass

    async def command(*arguments):
        if arguments[0].endswith("systemctl"):
            return "XMODIFIERS=@im=fcitx\nGTK_IM_MODULE=fcitx\nQT_IM_MODULE=fcitx\n"
        return "@a(ss) []\n"

    async def identity(_bus, name, **_kwargs):
        return ("fcitx", ":1.55")

    monkeypatch.setattr(module, "_command", command)
    monkeypatch.setattr(module, "MessageBus", Bus)
    monkeypatch.setattr(module, "owner_identity", identity)
    assert asyncio.run(module.collect_system_framework()) == ("fcitx", ":1.55")


def test_automatic_detector_only_enables_fcitx_hypothesis(monkeypatch):
    import asyncio
    import threading

    from inkecho.platform import framework_detection as module
    from inkecho.platform.fcitx5_install import FcitxInstaller

    async def ibus():
        return ("ibus", ":1.7")

    async def fcitx():
        return ("fcitx", ":1.8")

    monkeypatch.setattr(module, "collect_system_framework", ibus)
    assert asyncio.run(module.detect_system_framework()) is None
    monkeypatch.setattr(module, "collect_system_framework", fcitx)
    monkeypatch.setattr(FcitxInstaller, "auto_version", lambda self: None)
    assert asyncio.run(module.detect_system_framework()) is None
    main_thread = threading.get_ident()
    worker_threads = []

    def available(_self):
        worker_threads.append(threading.get_ident())
        return "5.1.19"

    async def live_version(owner, version):
        return owner == ":1.8" and version == "5.1.19"

    monkeypatch.setattr(module, "_live_fcitx_version_matches", live_version)
    monkeypatch.setattr(FcitxInstaller, "auto_version", available)
    assert asyncio.run(module.detect_system_framework()) == ("fcitx", ":1.8")
    assert worker_threads and worker_threads[0] != main_thread


@pytest.mark.parametrize(
    "sender,signature,body,owner,expected",
    [
        (":1.8", "s", ["5.1.19"], ("fcitx", ":1.8"), True),
        (":1.9", "s", ["5.1.19"], ("fcitx", ":1.8"), False),
        (":1.8", "s", ["5.1.7"], ("fcitx", ":1.8"), False),
        (":1.8", "s", ["5.1.19"], ("fcitx", ":1.9"), False),
        (":1.8", "", [], ("fcitx", ":1.8"), False),
    ],
)
def test_runtime_version_requires_pinned_sender_and_unchanged_owner(
    monkeypatch, sender, signature, body, owner, expected
):
    import asyncio
    from types import SimpleNamespace

    from dbus_next import MessageType

    from inkecho.platform import framework_detection as module

    class Bus:
        async def connect(self):
            return self

        async def call(self, message):
            assert message.destination == ":1.8"
            if message.member == "GetAddonsV2":
                return SimpleNamespace(
                    message_type=MessageType.METHOD_RETURN,
                    sender=":1.8",
                    signature="a(sssibbbasas)",
                    body=[[["inkecho", "InkEcho", "", 3, False, True, False, [], []]]],
                )
            assert message.member == "RuntimeVersion"
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN,
                sender=sender,
                signature=signature,
                body=body,
            )

        def disconnect(self):
            pass

    async def identity(*_args, **_kwargs):
        return owner

    monkeypatch.setattr(module, "MessageBus", Bus)
    monkeypatch.setattr(module, "owner_identity", identity)
    assert asyncio.run(module._live_fcitx_version_matches(":1.8", "5.1.19")) is expected


def test_owner_identity_rejects_forged_daemon_reply():
    import asyncio
    from types import SimpleNamespace

    from dbus_next import MessageType

    from inkecho.platform.framework_detection import owner_identity

    class SpoofBus:
        async def call(self, _message):
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN, body=[":1.42"], sender=":1.99"
            )

    assert asyncio.run(owner_identity(SpoofBus(), "org.fcitx.Fcitx5")) is None


@pytest.mark.parametrize(
    "state",
    [
        "enabled",
        "disabled",
        "missing",
        "duplicate",
        "bad_type",
        "wrong_sender",
        "wrong_signature",
        "error",
    ],
)
def test_live_fcitx_addon_requires_unique_enabled_verified_reply(monkeypatch, state):
    import asyncio
    from types import SimpleNamespace

    from dbus_next import MessageType

    from inkecho.platform import framework_detection as module

    row = ["inkecho", "InkEcho", "", 3, False, state != "disabled", False, [], []]
    if state == "bad_type":
        row[5] = 1
    rows = [] if state == "missing" else [row, row] if state == "duplicate" else [row]
    calls = []

    class Bus:
        async def connect(self):
            return self

        async def call(self, message):
            calls.append(message.member)
            if message.member == "GetAddonsV2":
                if state == "error":
                    raise RuntimeError("unavailable")
                return SimpleNamespace(
                    message_type=MessageType.METHOD_RETURN,
                    sender=":1.99" if state == "wrong_sender" else ":1.8",
                    signature="bad" if state == "wrong_signature" else "a(sssibbbasas)",
                    body=[rows],
                )
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN,
                sender=":1.8",
                signature="s",
                body=["5.1.19"],
            )

        def disconnect(self):
            pass

    async def identity(*args, **kwargs):
        return ("fcitx", ":1.8")

    monkeypatch.setattr(module, "MessageBus", Bus)
    monkeypatch.setattr(module, "owner_identity", identity)
    assert asyncio.run(module._live_fcitx_version_matches(":1.8", "5.1.19")) is (
        state == "enabled"
    )
    assert calls == (
        ["GetAddonsV2", "RuntimeVersion"] if state == "enabled" else ["GetAddonsV2"]
    )


@pytest.mark.parametrize(
    "desktop, session, xmodifiers, gtk, qt, expected",
    [
        ("XFCE", "x11", "@im=fcitx", "fcitx", "fcitx", ("fcitx", ":1.55")),
        ("ubuntu:GNOME", "x11", "@im=fcitx", "fcitx", "fcitx", None),
        ("XFCE", "wayland", "@im=fcitx", "fcitx", "fcitx", None),
        ("", "x11", "@im=fcitx", "fcitx", "fcitx", None),
        ("XFCE", "x11", "@im=ibus", "ibus", "ibus", None),
        ("XFCE", "x11", "@im=fcitx", "simple", "fcitx", None),
        ("XFCE", "x11", "@im=fcitx", "", "", None),
    ],
)
def test_xfce_xorg_fcitx_does_not_require_gnome_schema(
    monkeypatch, desktop, session, xmodifiers, gtk, qt, expected
):
    import asyncio

    from inkecho.platform import framework_detection as module

    class Bus:
        async def connect(self):
            return self

        def disconnect(self):
            pass

    async def command(*arguments):
        if arguments[0].endswith("systemctl"):
            return (
                f"XDG_CURRENT_DESKTOP={desktop}\nXDG_SESSION_TYPE={session}\n"
                f"XMODIFIERS={xmodifiers}\nGTK_IM_MODULE={gtk}\nQT_IM_MODULE={qt}\n"
            )
        if arguments[1] == "list-schemas":
            return "org.example.other\n"
        raise ValueError("gsettings schema unavailable")

    async def identity(_bus, name, **_kwargs):
        return ("fcitx", ":1.55") if name == "org.fcitx.Fcitx5" else None

    monkeypatch.setattr(module, "_command", command)
    monkeypatch.setattr(module, "MessageBus", Bus)
    monkeypatch.setattr(module, "owner_identity", identity)
    assert asyncio.run(module.collect_system_framework()) == expected


@pytest.mark.parametrize("failure", [TimeoutError(), OSError(), ValueError()])
def test_xfce_xorg_never_assumes_missing_schema_when_inventory_fails(
    monkeypatch, failure
):
    import asyncio

    from inkecho.platform import framework_detection as module

    async def command(*arguments):
        if arguments[0].endswith("systemctl"):
            return (
                "XDG_CURRENT_DESKTOP=XFCE\nXDG_SESSION_TYPE=x11\n"
                "XMODIFIERS=@im=fcitx\nGTK_IM_MODULE=fcitx\n"
            )
        raise failure

    monkeypatch.setattr(module, "_command", command)
    assert asyncio.run(module.collect_system_framework()) is None


def test_xfce_xorg_does_not_hide_broken_installed_schema(monkeypatch):
    import asyncio

    from inkecho.platform import framework_detection as module

    async def command(*arguments):
        if arguments[0].endswith("systemctl"):
            return (
                "XDG_CURRENT_DESKTOP=XFCE\nXDG_SESSION_TYPE=x11\n"
                "XMODIFIERS=@im=fcitx\nGTK_IM_MODULE=fcitx\n"
            )
        if arguments[1] == "list-schemas":
            return "org.gnome.desktop.input-sources\n"
        raise ValueError("unreadable installed schema")

    monkeypatch.setattr(module, "_command", command)
    assert asyncio.run(module.collect_system_framework()) is None
