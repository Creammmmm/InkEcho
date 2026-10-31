"""Synthetic cleanup-failure checks; not a desktop delivery test."""

import asyncio

import pytest

from inkecho.platform import ibus, ibus_owned


@pytest.mark.parametrize("module", [ibus, ibus_owned])
@pytest.mark.parametrize("cancelled", [True, False])
def test_connect_preserves_stop_and_never_hides_cleanup_failure(module, cancelled):
    class BrokenCapability:
        def __init__(self, _root):
            self.calls = 0

        def close(self):
            self.calls += 1
            raise OSError("private path")

    class FailingClient:
        def __init__(self, cap):
            self.cap = cap

        async def begin(self):
            if cancelled:
                raise asyncio.CancelledError
            raise module.CandidateError("unavailable")

    async def run():
        bridge = module.IBusBridge(
            runtime_dir="/synthetic",
            capability_factory=BrokenCapability,
            client_factory=FailingClient,
        )
        error = asyncio.CancelledError if cancelled else module.IBusBridgeError
        with pytest.raises(error) as caught:
            await bridge.connect()
        if not cancelled:
            assert caught.value.code == "cleanup_failed"
            assert "private path" not in str(caught.value)
        assert bridge.preflight_cleanup_failed
        assert bridge._client is None

    asyncio.run(run())


@pytest.mark.parametrize("module", [ibus, ibus_owned])
@pytest.mark.parametrize("cancelled", [True, False])
def test_real_client_begin_cleanup_failure_is_not_lost(module, cancelled):
    class BrokenCapability:
        def close(self):
            raise OSError("private path")

    class Bus:
        async def connect(self):
            if cancelled:
                raise asyncio.CancelledError
            raise RuntimeError("connect failure")

        def disconnect(self):
            pass

    async def run():
        client = module.Client(BrokenCapability(), bus_factory=Bus)
        error = asyncio.CancelledError if cancelled else module.CandidateError
        with pytest.raises(error) as caught:
            await client.begin()
        if not cancelled:
            assert caught.value.code == "cleanup_failed"
        assert client.cleanup_failed
        assert client._bus is None

    asyncio.run(run())


def test_owned_auto_does_not_fallback_after_real_bridge_cleanup_failure():
    import time

    from test_output_router import Keyboard

    from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
    from inkecho.platform.output_router import OutputRouterError

    class BrokenCapability:
        def __init__(self, _root):
            pass

        def close(self):
            raise OSError("private path")

    class FailingClient:
        def __init__(self, _cap, **_kwargs):
            pass

        async def begin(self, **_kwargs):
            raise ibus_owned.CandidateError("unavailable")

    async def run():
        keyboard = Keyboard()
        reports = []

        async def state():
            return "enabled"

        async def detector():
            return None

        async def probe():
            return ("ibus", ":1.23")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state,
            system_detector=detector,
            owned_probe=probe,
            owned_factory=lambda: ibus_owned.IBusBridge(
                runtime_dir="/synthetic",
                capability_factory=BrokenCapability,
                client_factory=FailingClient,
            ),
        )
        router.set_diagnostic_handler(reports.append)
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="ibus_cleanup_failed"):
            async with router.output_session():
                await router.insert("甲", lambda: True, deadline=time.monotonic() + 2)
        assert keyboard.connects == keyboard.authorizations == 0
        assert keyboard.sent == []
        assert reports == ["input_cleanup_failed"]

    asyncio.run(run())


@pytest.mark.parametrize("module", [ibus, ibus_owned])
@pytest.mark.parametrize("failure", ["unknown_identity", "unlink", "fd_close"])
def test_real_capability_creation_failure_never_allows_unsafe_fallback(
    module, failure, tmp_path, monkeypatch
):
    import os
    import stat

    from inkecho.platform import ibus_lifecycle

    tmp_path.chmod(0o700)
    real_fstat = os.fstat
    real_unlink = os.unlink
    real_close = os.close
    closed = []

    def fstat(fd):
        info = real_fstat(fd)
        if failure == "unknown_identity" and stat.S_ISREG(info.st_mode):
            raise OSError("sensitive error")
        return info

    def unlink(path, **kwargs):
        if failure == "unlink" and str(path).startswith("cap-"):
            raise OSError("sensitive error")
        return real_unlink(path, **kwargs)

    def close(fd):
        info = real_fstat(fd)
        result = real_close(fd)
        closed.append(fd)
        if failure == "fd_close" and stat.S_ISREG(info.st_mode):
            raise OSError("sensitive error")
        return result

    def fail_fsync(_fd):
        raise OSError("sensitive error")

    async def run():
        bridge = module.IBusBridge(runtime_dir=tmp_path)
        with pytest.raises(module.IBusBridgeError, match="^cleanup_failed$"):
            await bridge.connect()
        assert bridge.preflight_cleanup_failed
        assert bridge._client is None

    with monkeypatch.context() as patch:
        patch.setattr(ibus_lifecycle.os, "fstat", fstat)
        patch.setattr(ibus_lifecycle.os, "unlink", unlink)
        patch.setattr(ibus_lifecycle.os, "close", close)
        if failure != "unknown_identity":
            patch.setattr(ibus_lifecycle.os, "fsync", fail_fsync)
        asyncio.run(run())
    assert len(closed) >= 2
    leftovers = list(tmp_path.iterdir())
    assert len(leftovers) == (0 if failure == "fd_close" else 1)
    for path in leftovers:
        path.unlink()


def test_owned_auto_real_capability_creation_cleanup_failure_stops_fallback(
    tmp_path, monkeypatch
):
    import os
    import time

    from test_output_router import Keyboard

    from inkecho.platform import ibus_lifecycle
    from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
    from inkecho.platform.output_router import OutputRouterError

    tmp_path.chmod(0o700)
    original_unlink = os.unlink

    def fail_unlink(path, **kwargs):
        if str(path).startswith("cap-"):
            raise OSError("sensitive error")
        return original_unlink(path, **kwargs)

    def fail_fsync(_fd):
        raise OSError("sensitive error")

    async def run():
        keyboard, reports = Keyboard(), []

        async def state():
            return "enabled"

        async def detector():
            return None

        async def probe():
            return ("ibus", ":1.23")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state,
            system_detector=detector,
            owned_probe=probe,
            owned_factory=lambda: ibus_owned.IBusBridge(runtime_dir=tmp_path),
        )
        router.set_diagnostic_handler(reports.append)
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="^ibus_cleanup_failed$"):
            async with router.output_session():
                await router.insert("甲", lambda: True, deadline=time.monotonic() + 2)
        assert not keyboard.sent and keyboard.connects == keyboard.authorizations == 0
        assert reports == ["input_cleanup_failed"]

    with monkeypatch.context() as patch:
        patch.setattr(ibus_lifecycle.os, "unlink", fail_unlink)
        patch.setattr(ibus_lifecycle.os, "fsync", fail_fsync)
        asyncio.run(run())
    for path in tmp_path.iterdir():
        path.unlink()


@pytest.mark.parametrize("module", [ibus, ibus_owned])
def test_real_capability_cancel_with_unlink_failure_preserves_cancellation(
    module, tmp_path, monkeypatch
):
    import os

    from inkecho.platform import ibus_lifecycle

    tmp_path.chmod(0o700)
    real_unlink = os.unlink

    def cancel_fsync(_fd):
        raise asyncio.CancelledError

    def fail_unlink(path, **kwargs):
        if str(path).startswith("cap-"):
            raise OSError("sensitive error")
        return real_unlink(path, **kwargs)

    async def run():
        bridge = module.IBusBridge(runtime_dir=tmp_path)
        with pytest.raises(asyncio.CancelledError):
            await bridge.connect()
        assert bridge.preflight_cleanup_failed
        assert bridge._client is None

    with monkeypatch.context() as patch:
        patch.setattr(ibus_lifecycle.os, "fsync", cancel_fsync)
        patch.setattr(ibus_lifecycle.os, "unlink", fail_unlink)
        asyncio.run(run())
    for path in tmp_path.iterdir():
        path.unlink()


@pytest.mark.parametrize(
    "case", ["consumed", "removed", "renamed", "hardlink", "foreign_used", "unknown"]
)
def test_capability_close_distinguishes_server_consumption_from_unknown_state(
    case, tmp_path, monkeypatch
):
    import os

    from inkecho.platform import ibus_lifecycle

    tmp_path.chmod(0o700)
    cap = ibus_lifecycle.Capability(tmp_path)
    used = tmp_path / ("used-" + cap.name)
    moved = tmp_path / "moved-away"
    if case == "consumed":
        cap.path.rename(used)
    elif case == "removed":
        cap.path.unlink()
    elif case == "renamed":
        cap.path.rename(moved)
    elif case == "hardlink":
        os.link(cap.path, moved)
    elif case == "foreign_used":
        used.write_text("unrelated")

    original_fstat = os.fstat

    def fstat(fd):
        if case == "unknown" and fd == cap._fd:
            raise OSError("sensitive error")
        return original_fstat(fd)

    with monkeypatch.context() as patch:
        patch.setattr(ibus_lifecycle.os, "fstat", fstat)
        if case in {"consumed", "removed"}:
            cap.close()
        else:
            with pytest.raises(
                ibus_lifecycle.LifecycleCleanupError, match="cleanup_failed"
            ):
                cap.close()
    assert cap.token == "" and cap._fd is None
    if case in {"renamed", "hardlink"}:
        assert moved.exists()
        moved.unlink()
    if case == "foreign_used":
        assert used.read_text() == "unrelated"
        used.unlink()
    assert list(tmp_path.iterdir()) == []
