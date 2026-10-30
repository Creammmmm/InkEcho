import asyncio
import json
import time
import types

from dbus_next import MessageType

from inkecho.platform.ibus_owned import INTERFACE, CandidateError, Client


def xml(begin="ssut", commit="ust", duplicate=False, legacy=False):
    def method(n, i, o):
        return (
            '<method name="'
            + n
            + '">'
            + "".join('<arg direction="in" type="' + x + '"/>' for x in i)
            + "".join('<arg direction="out" type="' + x + '"/>' for x in o)
            + "</method>"
        )

    s = (
        method(
            "BeginBatch" if legacy else "BeginBounded", "ssu" if legacy else begin, "b"
        )
        + method(
            "CommitBatch" if legacy else "CommitBounded",
            "us" if legacy else commit,
            "s",
        )
        + method("Cancel", "", "b")
    )
    if duplicate:
        s += method("CommitBounded", "ust", "s")
    return '<node><interface name="' + INTERFACE + '">' + s + "</interface></node>"


class Cap:
    name = "cap-" + "a" * 32
    token = "b" * 64

    def close(self):
        self.closed = True


class Bus:
    def __init__(self, schema):
        self.schema = schema
        self.calls = []
        self.mode = None
        self.disconnected = False

    async def connect(self):
        return self

    def disconnect(self):
        self.disconnected = True

    async def call(self, m):
        self.calls.append((m.member, m.signature, m.body))
        member = m.member
        if member == "GetNameOwner":
            sender = "org.freedesktop.DBus"
            signature = "s"
            body = [":1.23"]
        elif member == "Introspect":
            sender = ":1.23"
            signature = "s"
            body = [self.schema]
        elif member in {"BeginBounded", "Cancel"}:
            sender = ":1.23"
            signature = "b"
            body = [True]
        elif member == "CommitBounded":
            if self.mode == "timeout":
                raise TimeoutError()
            if self.mode == "cancel":
                await self.client.cancel()
            sender = ":1.23"
            signature = "s"
            body = ["attempted"]
        else:
            raise AssertionError(member)
        if self.mode == "foreign-sender" and member == "Introspect":
            sender = ":foreign"
        return types.SimpleNamespace(
            message_type=MessageType.METHOD_RETURN,
            sender=sender,
            signature=signature,
            body=body,
        )


async def client(schema=None):
    b = Bus(schema or xml())
    c = Client(
        Cap(),
        bus_factory=lambda b=b: b,
        owner_verifier=lambda owner: async_true(),
        expected_owner=":1.23",
    )
    b.client = c
    await c.begin()
    return c, b


async def async_true():
    return True


async def main(tmp_path):
    n = 0
    for schema in [
        xml(legacy=True),
        xml(begin="ssud"),
        xml(commit="usts"),
        xml(duplicate=True),
        "<node/>",
    ]:
        b = Bus(schema)
        c = Client(
            Cap(), bus_factory=lambda b=b: b, owner_verifier=lambda owner: async_true()
        )
        try:
            await c.begin()
        except CandidateError as e:
            assert e.code == (
                "upgrade_required" if schema == xml(legacy=True) else "unavailable"
            )
        else:
            raise AssertionError("unsafe protocol accepted")
        assert b.disconnected and not any(
            x[0] in {"Commit", "CommitBatch", "CommitBounded", "BeginBounded"}
            for x in b.calls
        )
        n += 1
    c, b = await client()
    beg = next(x for x in b.calls if x[0] == "BeginBounded")
    assert beg[1] == "ssut" and beg[2][2] == 1 and type(beg[2][3]) is int
    n += 1
    deadline = time.monotonic() + 3
    assert await c.insert("A", lambda: True, deadline=deadline) == 1
    assert await c.insert("B", lambda: True, deadline=deadline + 1) == 1
    commits = [x for x in b.calls if x[0] == "CommitBounded"]
    assert all(x[1] == "ust" for x in commits) and commits[0][2][2] == commits[1][2][
        2
    ] <= int(deadline * 1e6)
    n += 1
    await c.close()
    c, b = await client()
    try:
        await c.insert("A", lambda: False, deadline=time.monotonic() + 1)
    except CandidateError as e:
        assert e.code == "cancelled"
    else:
        raise AssertionError()
    assert not any(x[0] == "CommitBounded" for x in b.calls)
    n += 1
    await c.close()
    c, b = await client()
    b.mode = "timeout"
    try:
        await c.insert("AB", lambda: True, deadline=time.monotonic() + 1)
    except CandidateError as e:
        assert e.code == "delivery_unknown"
    else:
        raise AssertionError()
    assert sum(x[0] == "CommitBounded" for x in b.calls) == 1
    try:
        await c.insert("A", lambda: True)
    except CandidateError as e:
        assert e.code == "not_ready"
    else:
        raise AssertionError("replayed")
    n += 1
    await c.close()
    c, b = await client()
    b.mode = "cancel"
    try:
        await c.insert("AB", lambda: True, deadline=time.monotonic() + 1)
    except CandidateError as e:
        assert e.code == "cancelled"
    else:
        raise AssertionError()
    assert sum(x[0] == "CommitBounded" for x in b.calls) == 1
    n += 1
    await c.close()
    for schema in [
        xml(commit="ust").replace(
            "</interface>",
            (
                '<method name="BeginBounded">'
                '<arg type="s" direction="in"/></method></interface>'
            ),
        ),
        xml(legacy=True).replace(
            "</interface>",
            (
                '<method name="CommitBounded">'
                '<arg type="u" direction="in"/></method></interface>'
            ),
        ),
    ]:
        b = Bus(schema)
        cap = Cap()
        c = Client(
            cap, bus_factory=lambda b=b: b, owner_verifier=lambda owner: async_true()
        )
        try:
            await c.begin()
        except CandidateError as error:
            assert error.code == "unavailable"
        else:
            raise AssertionError()
        assert (
            b.disconnected
            and cap.closed
            and not any(x[0] == "CommitBounded" for x in b.calls)
        )
        n += 1
    b = Bus(xml())
    b.mode = "foreign-sender"
    cap = Cap()
    c = Client(
        cap, bus_factory=lambda b=b: b, owner_verifier=lambda owner: async_true()
    )
    try:
        await c.begin()
    except CandidateError as error:
        assert error.code == "unavailable"
    else:
        raise AssertionError()
    assert b.disconnected and cap.closed
    n += 1
    b = Bus(xml())
    cap = Cap()
    c = Client(
        cap,
        bus_factory=lambda b=b: b,
        owner_verifier=lambda owner: async_true(),
        expected_owner=":wrong",
    )
    try:
        await c.begin()
    except CandidateError as error:
        assert error.code == "untrusted_owner"
    else:
        raise AssertionError()
    assert (
        b.disconnected
        and cap.closed
        and not any(x[0] == "BeginBounded" for x in b.calls)
    )
    n += 1

    from inkecho.logging import CODES, DiagnosticLog
    from inkecho.platform.ibus import IBusBridgeError
    from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter

    assert "ibus_upgrade_required" in CODES
    log = DiagnosticLog(tmp_path)
    log.record("error", "ibus_upgrade_required")
    assert "ibus_upgrade_required" in log.recent()
    log.handler.close()
    n += 1
    assert (
        DefaultAutoOutputRouter._owned_failure_code(IBusBridgeError("upgrade_required"))
        == "ibus_upgrade_required"
    )
    n += 1
    from inkecho.app import KEYBOARD_LABELS

    assert (
        "旧协议" in KEYBOARD_LABELS["ibus_upgrade_required"]
        and "重新登录" in KEYBOARD_LABELS["ibus_upgrade_required"]
    )
    n += 1
    from inkecho.platform.ibus_owned import IBusBridge

    class UpgradeClient:
        async def begin(self):
            raise CandidateError("upgrade_required")

    cap = Cap()
    bridge = IBusBridge(
        runtime_dir="/unused",
        capability_factory=lambda _: cap,
        client_factory=lambda _: UpgradeClient(),
    )
    try:
        await bridge.connect()
    except IBusBridgeError as error:
        assert error.code == "upgrade_required"
    else:
        raise AssertionError("upgrade diagnostic lost")
    assert cap.closed
    n += 1
    print(
        json.dumps(
            {
                "passed": n,
                "scope": (
                    "Actual production client, fake authenticated transport; "
                    "not real IPC or a target receipt"
                ),
            }
        )
    )


def test_bounded_client_protocol_and_task_boundaries(tmp_path):
    asyncio.run(main(tmp_path))
