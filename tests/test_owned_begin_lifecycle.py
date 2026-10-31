import asyncio
import time
from types import SimpleNamespace

from dbus_next import MessageType

from inkecho.platform.ibus_owned import CandidateError, Client


class Cap:
    name = "cap"
    token = "token"

    def close(self):
        pass


class Bus:
    async def connect(self):
        pass

    def add_message_handler(self, _):
        pass

    def disconnect(self):
        pass


class C(Client):
    def __init__(self):
        super().__init__(Cap(), bus_factory=Bus, owner_verifier=self.verify)
        self.enter = asyncio.Event()
        self.release = asyncio.Event()
        self.methods = []
        self.remote = False

    async def verify(self, _):
        return True

    async def _call(self, m, _):
        if m.member == "AddMatch":
            return SimpleNamespace(message_type=MessageType.METHOD_RETURN)
        if m.member == "GetNameOwner":
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN, body=[":1.2"]
            )
        raise AssertionError(m.member)

    async def _negotiate_batch(self):
        return 2

    async def _request(self, method, *args):
        self.methods.append(method)
        if method.startswith("Begin"):
            await self.release.wait()
            self.remote = True
            return SimpleNamespace(
                signature="b", message_type=MessageType.METHOD_RETURN, body=[True]
            )
        was = self.remote
        self.remote = False
        return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[was])


def test_cancel_while_begin_inflight_is_compensated():
    async def main():
        c = C()
        task = asyncio.create_task(c.begin(deadline=time.monotonic() + 10))
        await asyncio.sleep(0.01)
        await c.cancel()
        c.release.set()
        try:
            await task
            raise AssertionError("begin accepted")
        except CandidateError as e:
            assert e.code == "cancelled"
        assert not c.remote and c.methods == ["BeginLongBounded", "Cancel", "Cancel"]
        c = C()
        task = asyncio.create_task(c.begin(deadline=time.monotonic() + 10))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
            raise AssertionError("task accepted")
        except asyncio.CancelledError:
            pass
        assert c.cleanup_failed

    asyncio.run(main())


def test_invalid_begin_replies_leave_cleanup_unknown():
    async def main():
        replies = [
            SimpleNamespace(
                signature="s", message_type=MessageType.METHOD_RETURN, body=["yes"]
            ),
            SimpleNamespace(signature="b", message_type=MessageType.ERROR, body=[True]),
            SimpleNamespace(
                signature="b", message_type=MessageType.METHOD_RETURN, body=[1]
            ),
        ]
        for reply in replies:
            c = C()

            async def request(method, *args, result=reply):
                return result

            c._request = request
            try:
                await c.begin(deadline=time.monotonic() + 10)
                raise AssertionError("malformed reply accepted")
            except CandidateError:
                pass
            assert c.cleanup_failed

    asyncio.run(main())
