"""Measure two seconds of microphone input in RAM; never save audio."""

import argparse
import json
import sys

from PySide6.QtCore import QBuffer, QCoreApplication, QIODevice, QTimer
from PySide6.QtMultimedia import QAudioSource, QMediaDevices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    app = QCoreApplication(sys.argv)
    devices = QMediaDevices.audioInputs()
    print(json.dumps({"devices": [device.description() for device in devices]}))
    if not devices:
        return 1
    if not args.record:
        return 0

    device = QMediaDevices.defaultAudioInput()
    audio_format = device.preferredFormat()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    source = QAudioSource(device, audio_format)
    source.start(buffer)
    QTimer.singleShot(2000, app.quit)
    app.exec()
    error = source.error().name
    source.stop()
    byte_count = buffer.size()
    print(
        json.dumps(
            {
                "device": device.description(),
                "sample_rate": audio_format.sampleRate(),
                "channels": audio_format.channelCount(),
                "sample_format": audio_format.sampleFormat().name,
                "bytes": byte_count,
                "error": error,
                "audio_saved": False,
            }
        )
    )
    buffer.close()
    buffer.setData(b"")
    return 0 if byte_count > 0 and error == "NoError" else 1


if __name__ == "__main__":
    raise SystemExit(main())
