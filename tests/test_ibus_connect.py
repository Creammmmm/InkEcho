import asyncio

import pytest
from dbus_next.aio import MessageBus

from inkecho.platform.ibus import Capability, Client


@pytest.mark.parametrize("mode", ["timeout", "cancel"])
def test_incomplete_authentication_closes_connection(tmp_path, mode):
    async def run():
        tmp_path.chmod(0o700)
        accepted = asyncio.Event()
        disconnected = asyncio.Event()

        async def hang_auth(reader, writer):
            accepted.set()
            try:
                while await reader.read(1024):
                    pass
            finally:
                disconnected.set()
                writer.close()
                await writer.wait_closed()

        sock = str(tmp_path / "bus")
        server = await asyncio.start_unix_server(hang_auth, sock)
        buses = []

        def factory():
            bus = MessageBus(bus_address="unix:path=" + sock)
            buses.append(bus)
            return bus

        cap = Capability(tmp_path)
        client = Client(
            cap, bus_factory=factory, timeout=0.1 if mode == "timeout" else 3
        )
        try:
            task = asyncio.create_task(client.begin())
            await accepted.wait()
            if mode == "cancel":
                task.cancel()
            with pytest.raises(
                TimeoutError if mode == "timeout" else asyncio.CancelledError
            ):
                await task
            assert accepted.is_set()
            assert not cap.path.exists()
            await asyncio.wait_for(disconnected.wait(), 0.2)
        finally:
            for bus in buses:
                bus.disconnect()
            server.close()
            await server.wait_closed()

    asyncio.run(run())
