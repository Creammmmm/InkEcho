"""Actual Qt loops own async generators and restore thread-local hooks."""

import asyncio
import sys
import threading

import pytest

from inkecho.runtime import ManagedQtEventLoop


async def start_generator(closed):
    async def values():
        try:
            yield 1
        finally:
            await asyncio.sleep(0.01)
            closed.append(True)

    generator = values()
    assert await anext(generator) == 1
    hooks = sys.get_asyncgen_hooks()
    assert hooks.firstiter.__self__ is asyncio.get_running_loop()
    return generator


def test_qt_loop_shutdown_finishes_async_generator_and_restores_hooks(qt_app):
    previous = sys.get_asyncgen_hooks()
    closed = []
    with ManagedQtEventLoop(qt_app) as loop:
        generator = loop.run_until_complete(start_generator(closed))
        assert sys.get_asyncgen_hooks() == previous
        assert not closed
    assert closed == [True] and generator.ag_frame is None
    assert sys.get_asyncgen_hooks() == previous and loop.is_closed()


def test_qt_loop_exception_path_still_restores_and_cleans(qt_app):
    previous = sys.get_asyncgen_hooks()
    closed = []
    with pytest.raises(RuntimeError, match="owned-test-error"):
        with ManagedQtEventLoop(qt_app) as loop:
            generator = loop.run_until_complete(start_generator(closed))
            raise RuntimeError("owned-test-error")
    assert closed == [True] and generator.ag_frame is None
    assert sys.get_asyncgen_hooks() == previous and loop.is_closed()


def test_nested_qt_contexts_restore_existing_custom_hooks(qt_app):
    previous = sys.get_asyncgen_hooks()

    def custom(_generator):
        pass

    sys.set_asyncgen_hooks(firstiter=custom, finalizer=custom)
    try:
        closed = []
        with ManagedQtEventLoop(qt_app) as outer:
            generator = outer.run_until_complete(start_generator(closed))
            assert sys.get_asyncgen_hooks().firstiter is custom
            with ManagedQtEventLoop(qt_app) as inner:
                second = inner.run_until_complete(start_generator(closed))
                assert sys.get_asyncgen_hooks().firstiter is custom
            assert second.ag_frame is None
            assert sys.get_asyncgen_hooks().firstiter is custom
        assert generator.ag_frame is None and closed == [True, True]
        assert sys.get_asyncgen_hooks().firstiter is custom
        assert sys.get_asyncgen_hooks().finalizer is custom
    finally:
        sys.set_asyncgen_hooks(*previous)


def test_hook_installation_does_not_change_other_threads(qt_app):
    ready, release = threading.Event(), threading.Event()
    seen = []

    def custom(_generator):
        pass

    def worker():
        previous = sys.get_asyncgen_hooks()
        try:
            sys.set_asyncgen_hooks(firstiter=custom, finalizer=custom)
            ready.set()
            assert release.wait(2)
            seen.append(sys.get_asyncgen_hooks())
        finally:
            sys.set_asyncgen_hooks(*previous)

    thread = threading.Thread(target=worker)
    thread.start()
    assert ready.wait(2)

    async def scenario():
        assert sys.get_asyncgen_hooks().firstiter.__self__ is loop
        release.set()
        await asyncio.to_thread(thread.join, 2)

    with ManagedQtEventLoop(qt_app) as loop:
        loop.run_until_complete(scenario())
    assert not thread.is_alive()
    assert (
        len(seen) == 1 and seen[0].firstiter is custom and seen[0].finalizer is custom
    )


def test_standard_asyncio_run_remains_unchanged():
    previous = sys.get_asyncgen_hooks()
    closed = []

    async def scenario():
        generator = await start_generator(closed)
        await generator.aclose()

    asyncio.run(scenario())
    assert closed == [True] and sys.get_asyncgen_hooks() == previous
