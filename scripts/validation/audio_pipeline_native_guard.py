"""Test-only native receiver guard for the generic full audio Session probe.

No browser or desktop operation starts on import. The separate owner creates
and focuses its native fixture and publishes the existing native_guard schema.
Only press permission is added at Guardian's remote seam; mapper, timings,
acknowledgement, final-ASR barrier and cleanup remain production code.
"""

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import sys
import time
from pathlib import Path


def _origins(root):
    result = {}
    for name, module in sys.modules.items():
        if name == "inkecho" or name.startswith("inkecho."):
            file = getattr(module, "__file__", None)
            if file:
                path = Path(file).resolve()
                if not path.is_relative_to(root):
                    raise RuntimeError("unexpected_native_product_origin")
                result[name] = {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
    return result


def _save_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2)


async def _keymap_metadata(observer):
    state, data = await observer.snapshot(refresh=True)
    return {
        "map_sha256": hashlib.sha256(data).hexdigest(),
        **{key: state[key] for key in ("group", "depressed", "latched", "locked")},
    }


class NativePipelineGuard:
    """Configure the actual factory's worker seam, retaining the owned handles."""

    def __init__(self, product_root, helper_root, guard_path, guard_owner, work_root):
        self.root = Path(product_root).resolve(strict=True)
        self.helper_root = Path(helper_root).resolve(strict=True)
        self.guard_path = Path(guard_path).resolve(strict=True)
        self.guard_owner = int(guard_owner)
        self.work_root = Path(work_root)
        self.work_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.count_path = self.work_root / "native-counts.json"
        self.workers = []
        self.observer = None
        self.before = None
        self.ack_count = 0
        self.first_sent_at = None

    def configure(self, inputs):
        from inkecho.platform.keyboard import KeyboardError

        if not hasattr(inputs, "native") or not hasattr(inputs, "x11"):
            raise RuntimeError("actual_native_hybrid_factory_required")

        async def spawn(*_unused, **options):
            if self.workers:
                raise KeyboardError("session_closed")
            origins = self.work_root / "native-worker-origins.json"
            command = [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "--worker",
                "--product-root",
                str(self.root),
                "--helper-root",
                str(self.helper_root),
                "--guard-path",
                str(self.guard_path),
                "--guard-owner",
                str(self.guard_owner),
                "--sender-owner",
                str(os.getpid()),
                "--counts",
                str(self.count_path),
                "--origins",
                str(origins),
            ]
            process = await asyncio.create_subprocess_exec(*command, **options)
            self.workers.append((process, command))
            return process

        inputs.native._spawn = spawn
        request = inputs.native._request

        async def observed_request(operation, **fields):
            result = await request(operation, **fields)
            if operation == "key":
                self.ack_count += 1
                if self.first_sent_at is None:
                    self.first_sent_at = result.get("sent_at")
            return result

        inputs.native._request = observed_request

    def refuse_x11_presses(self, inputs):
        from inkecho.platform.keyboard import KeyboardError

        original = inputs.x11._send

        def guarded(window, code, pressed):
            if pressed:
                raise KeyboardError("input_cancelled")
            return original(window, code, pressed)

        inputs.x11._send = guarded

    async def before_capture(self):
        from inkecho.platform.wayland_worker import MutterSession

        self.observer = MutterSession()
        await self.observer.connect()
        await self.observer.authorize()
        self.before = await _keymap_metadata(self.observer)

    def counts(self):
        if not self.count_path.exists():
            return {"press_success": 0, "release_success": 0, "guard_rejections": 0}
        return json.loads(self.count_path.read_text())

    async def after_close(self):
        """Call after Session.close, so production cleanup finishes first."""
        report = {"before_keymap": self.before, "ack_count": self.ack_count}
        try:
            for process, command in self.workers:
                owner = {"pid": process.pid, "argv": command, "forced_signals": []}
                report.setdefault("workers", []).append(owner)
                try:
                    code = await asyncio.wait_for(asyncio.shield(process.wait()), 5)
                except TimeoutError:
                    owner.update(
                        original_wait_completed=False,
                        still_running=process.returncode is None,
                    )
                    raise
                owner.update(natural_exit_code=code, original_wait_completed=True)
            report["counts"] = self.counts()
            if self.observer is not None:
                report["after_keymap"] = await _keymap_metadata(self.observer)
                report["native_mapping_restored"] = (
                    self.before is not None and report["after_keymap"] == self.before
                )
        finally:
            if self.observer is not None:
                await self.observer.close()
            report["sender_origins"] = _origins(self.root)
            _save_new(self.work_root / "native-cleanup.json", report)
        return report


async def _worker(args):
    root = args.product_root.resolve(strict=True)
    helpers = args.helper_root.resolve(strict=True)
    sys.path.insert(0, str(root))
    sys.path.insert(1, str(helpers))
    os.environ["PYTHONPATH"] = str(root) + os.pathsep + str(helpers)
    browser_module = importlib.import_module("natural_owned_browser")
    guard_module = importlib.import_module("native_guard")
    for module in (browser_module, guard_module):
        if not Path(module.__file__).resolve().is_relative_to(helpers):
            raise RuntimeError("unexpected_native_guard_helper_origin")
    if browser_module.parent_pid(os.getpid()) != args.sender_owner:
        raise RuntimeError("native_guard_sender_changed")
    # Import the real Guardian before recording its provenance.
    importlib.import_module("inkecho.platform.wayland_worker")
    report = {
        "guard_owner": args.guard_owner,
        "sender_owner": args.sender_owner,
        "worker_pid": os.getpid(),
        "started_at": time.monotonic(),
        "origins_before": _origins(root),
        "helper_origins": {
            module.__name__: {
                "path": str(Path(module.__file__).resolve()),
                "sha256": hashlib.sha256(
                    Path(module.__file__).read_bytes()
                ).hexdigest(),
            }
            for module in (browser_module, guard_module)
        },
    }
    try:
        await guard_module.worker(args.guard_path, args.counts, args.guard_owner)
    finally:
        report["origins_after"] = _origins(root)
        report["finished_at"] = time.monotonic()
        _save_new(args.origins, report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--helper-root", type=Path, required=True)
    parser.add_argument("--guard-path", type=Path, required=True)
    parser.add_argument("--guard-owner", type=int, required=True)
    parser.add_argument("--sender-owner", type=int, required=True)
    parser.add_argument("--counts", type=Path, required=True)
    parser.add_argument("--origins", type=Path, required=True)
    asyncio.run(_worker(parser.parse_args()))
