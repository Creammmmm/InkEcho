"""Actual shipped provider widget with private config and fixed in-memory models."""

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from artifact_scope import audit_package, selected_artifact
from native_guard import save


async def exercise(page, store):
    from inkecho.realtime import PROTOCOL

    await page.discover()

    def choices():
        return {page.model.itemText(i) for i in range(page.model.count())}

    http = choices() == {"qwen3-asr-flash"}
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    live = choices() == {"qwen3-asr-flash-realtime"}
    page.protocol.setCurrentIndex(page.protocol.findData("http"))
    returned = choices() == {"qwen3-asr-flash"}
    page.model.setCurrentText("qwen3-asr-flash-realtime")
    page.protocol.setCurrentIndex(page.protocol.findData(PROTOCOL))
    await page.save()
    provider = store.load_provider(page.identifier)
    saved = (
        provider.model == "qwen3-asr-flash-realtime"
        and provider.parameters.get("asr_protocol") == PROTOCOL
    )
    page.load()
    return {
        "http_only_compatible_asr_models": http,
        "realtime_refiltered_without_rediscovery": live,
        "http_refiltered_without_rediscovery": returned,
        "private_config_saved_and_reloaded": saved
        and page.protocol.currentData() == PROTOCOL,
        "warning_does_not_claim_os_unsupported": "系统不支持"
        not in page.model_hint.text(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in [
        "artifact",
        "package-root",
        "frozen-source-root",
        "output",
        "work-root",
    ]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--run-ui", action="store_true")
    parser.add_argument(
        "--expected-platform", choices=["wayland", "xcb"], required=True
    )
    args = parser.parse_args()
    if not args.run_ui or args.output.exists() or args.work_root.exists():
        raise SystemExit(2) from None
    selected = selected_artifact(args.artifact, args.expected_sha)
    audit = audit_package(
        args.package_root, args.frozen_source_root, args.expected_version
    )
    from PySide6.QtWidgets import QApplication

    from inkecho.config import ConfigStore
    from inkecho.runtime import ManagedQtEventLoop
    from inkecho.ui.providers import ProviderPage

    args.work_root.mkdir(mode=0o700)
    store = ConfigStore(args.work_root / "config")
    store.initialize()
    counters = {"in_memory_model_lists": 0, "real_key_reads": 0}

    class Client:
        async def models(self, _provider, _key):
            counters["in_memory_model_lists"] += 1
            return [
                "qwen3-asr-flash",
                "qwen3-asr-flash-realtime",
                "qwen-plus",
                "qwen3-tts-flash",
            ]

    async def fake_key(_reference):
        return "fixed-local-widget-test-only"

    async def forbidden_save(*_args):
        raise ValueError("unexpected_credential_write")

    session = SimpleNamespace(
        store=store,
        key=fake_key,
        save_key=forbidden_save,
        provider_client=lambda _role: Client(),
    )
    app = QApplication([])
    if app.platformName() != args.expected_platform:
        raise SystemExit(2)
    app.setQuitOnLastWindowClosed(False)
    page = ProviderPage(session, "transcription")
    page.resize(1000, 900)
    page.show()
    report = {
        "passed": False,
        "artifact": selected,
        "runtime": audit,
        "evidence_kind": "actual_widget_fixed_model_list_not_cloud_capability",
        "cloud_requests": 0,
        "microphone": False,
        "keyring_access": False,
    }
    try:
        with ManagedQtEventLoop(app) as loop:
            asyncio.set_event_loop(loop)
            checks = loop.run_until_complete(exercise(page, store))
            app.processEvents()
            report.update(
                checks=checks,
                counters=counters,
                qt_platform=app.platformName(),
                widget_visible=page.isVisible(),
            )
            page.grab().save(str(args.work_root / "protocol-page.png"))
            report["passed"] = (
                all(checks.values()) and counters["in_memory_model_lists"] == 1
            )
            page.close()
    except Exception:
        report["failure_code"] = "ui_protocol_acceptance_failed"
    finally:
        page.close()
        save(args.output, report)
        print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "code": "acceptance_preflight_failed"}))
        raise SystemExit(2) from None
