from inkecho.platform.capabilities import detect_desktop


def test_wayland_never_promises_unsupported_injection(tmp_path):
    release = tmp_path / "os-release"
    release.write_text('PRETTY_NAME="Ubuntu 26.04 LTS"\n')
    result = detect_desktop({"XDG_SESSION_TYPE": "wayland"}, release)
    assert result.distribution == "Ubuntu 26.04 LTS"
    assert not result.injection_ready
    assert "compatible XWayland apps" in result.reason
    assert "Native Wayland applications are not supported" in result.reason


def test_missing_session_is_explicit(tmp_path):
    result = detect_desktop({}, tmp_path / "missing")
    assert result.session == "unknown"
    assert not result.injection_ready
    assert "could not be verified" in result.reason
