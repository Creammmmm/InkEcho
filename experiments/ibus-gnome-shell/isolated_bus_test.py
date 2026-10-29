import asyncio
import os

from client import INTERFACE, PATH, CandidateError, Capability, Client
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus


async def trusted_for_private_test(_owner):
    return True  # Only this fake private-bus service; no Shell identity claim.


async def run():
    cap = Capability(os.environ["XDG_RUNTIME_DIR"])
    client = Client(cap, owner_verifier=trusted_for_private_test)
    await client.begin()
    other = await MessageBus().connect()
    reply = await other.call(
        Message(
            destination=client._owner,
            path=PATH,
            interface=INTERFACE,
            member="Commit",
            signature="sus",
            body=[cap.token, 0, "甲"],
        )
    )
    assert reply.message_type == MessageType.METHOD_RETURN and reply.body == [
        "rejected"
    ]
    other.disconnect()
    assert await client.insert("甲乙", lambda: True) == 2
    await client.cancel()
    try:
        await client.insert("丙", lambda: True)
        raise AssertionError("cancelled client sent")
    except CandidateError as error:
        assert error.code == "not_ready"
    await client.close()
    assert not cap.path.exists()
    print("private D-Bus protocol checks passed")


asyncio.run(run())
