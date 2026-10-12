"""Exercise the real desktop notification service without creating Qt windows."""

import asyncio
import json

from inkecho.ui.notifications import DesktopNotifications


async def main():
    notices = DesktopNotifications(lambda *_: None)
    try:
        recording = await notices.show(
            "InkEcho 修复验证：录音状态与结束 / 取消按钮测试，不会实际录音。",
            recording=True,
            task_id="notification-probe",
        )
        first = notices.identifier
        await asyncio.sleep(0.2)
        finished = await notices.show("InkEcho 系统通知验证完成；未创建应用窗口。")
        print(
            json.dumps(
                {
                    "recording_accepted": recording,
                    "completion_accepted": finished,
                    "notification_replaced": bool(
                        first and first == notices.identifier
                    ),
                    "application_windows_created": 0,
                    "physical_notification_action_tested": False,
                }
            ),
            flush=True,
        )
        if not recording or not finished:
            raise SystemExit(1)
    finally:
        await notices.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
