"""Ownership of asynchronous page actions when a UI closes immediately."""

import asyncio
import inspect
from types import SimpleNamespace

import pytest

from inkecho.ui.widgets import Page


def test_immediate_cancel_closes_unstarted_operation(qt_app):
    async def scenario():
        page = Page("title", "subtitle")

        async def operation():
            raise AssertionError("The cancelled operation must not run")

        inner = operation()
        task = page.run(inner)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)  # allow the task's cleanup callback to execute
        assert inspect.getcoroutinestate(inner) == inspect.CORO_CLOSED
        page.close()

    asyncio.run(scenario())


def test_started_operation_is_cancelled_and_can_clean_up(qt_app):
    async def scenario():
        page = Page("title", "subtitle")
        entered, cleaned = asyncio.Event(), asyncio.Event()

        async def operation():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        task = page.run(operation())
        await entered.wait()
        task.cancel()
        await task
        assert cleaned.is_set()
        assert page.message.text() == "操作已取消。"
        page.close()

    asyncio.run(scenario())


def test_spawn_failure_closes_both_coroutines(qt_app):
    page = Page("title", "subtitle")

    def fail_spawn(wrapper):
        raise RuntimeError("spawn failed")

    page.session = SimpleNamespace(spawn_ui=fail_spawn)

    async def operation():
        pass

    inner = operation()
    with pytest.raises(RuntimeError, match="spawn failed"):
        page.run(inner)
    assert inspect.getcoroutinestate(inner) == inspect.CORO_CLOSED
    page.close()


def test_immediate_cancel_cancels_unstarted_future(qt_app):
    async def scenario():
        page = Page("title", "subtitle")
        future = asyncio.get_running_loop().create_future()
        task = page.run(future)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        assert future.cancelled()
        page.close()

    asyncio.run(scenario())


def test_started_failure_is_sanitized_and_not_reported_as_cancellation(qt_app):
    async def scenario():
        page = Page("title", "subtitle")

        async def operation():
            raise RuntimeError("sensitive detail")

        await page.run(operation())
        assert page.message.text() == "操作未完成，请检查设置与系统服务。"
        assert "sensitive detail" not in page.message.text()
        page.close()

    asyncio.run(scenario())


def test_stale_cancel_does_not_replace_newer_status(qt_app):
    async def scenario():
        page = Page("title", "subtitle")
        page.revision = 1
        started = asyncio.Event()

        async def operation():
            started.set()
            await asyncio.Event().wait()

        task = page.run(operation())
        await started.wait()
        page.revision = 2
        page.message.setText("较新的状态")
        task.cancel()
        await task
        assert page.message.text() == "较新的状态"
        page.close()

    asyncio.run(scenario())


def test_unstarted_completed_future_error_is_retrieved(qt_app):
    async def scenario():
        page = Page("title", "subtitle")
        future = asyncio.get_running_loop().create_future()
        failure = RuntimeError("completed before wrapper starts")
        future.set_exception(failure)
        task = page.run(future)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        # The done callback consumed the failure; destroying this future will
        # not produce an unhandled-future diagnostic.
        assert not future._log_traceback
        assert future.exception() is failure
        page.close()

    asyncio.run(scenario())


def test_session_spawn_immediate_cancel_closes_inner_coroutine(qt_app):
    async def scenario():
        page = Page("title", "subtitle")
        spawned = []

        def spawn(wrapper):
            task = asyncio.create_task(wrapper)
            spawned.append(task)
            return task

        page.session = SimpleNamespace(spawn_ui=spawn)

        async def operation():
            raise AssertionError("cancelled before dispatch")

        inner = operation()
        task = page.run(inner)
        assert spawned == [task]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)
        assert inspect.getcoroutinestate(inner) == inspect.CORO_CLOSED
        page.close()

    asyncio.run(scenario())


def test_no_event_loop_closes_unstarted_operation(qt_app):
    page = Page("title", "subtitle")

    async def operation():
        pass

    inner = operation()
    with pytest.raises(RuntimeError, match="no running event loop"):
        page.run(inner)
    assert inspect.getcoroutinestate(inner) == inspect.CORO_CLOSED
    page.close()
