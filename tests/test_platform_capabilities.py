from inkecho.platform.capabilities import detect_desktop


def test_non_gnome_wayland_does_not_offer_native_injection(tmp_path):
    release = tmp_path / "os-release"
    release.write_text('PRETTY_NAME="Ubuntu 26.04 LTS"\n')
    result = detect_desktop(
        {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE"}, release
    )
    assert result.distribution == "Ubuntu 26.04 LTS"
    assert not result.injection_ready
    assert "compatible XWayland apps" in result.reason
    assert "Native delivery on this desktop has not been validated" in result.reason
    assert "experimental current-cursor keyboard route" not in result.reason


def test_gnome_wayland_reports_experimental_scope_without_claiming_readiness(tmp_path):
    result = detect_desktop(
        {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"},
        tmp_path / "missing",
    )
    assert not result.injection_ready
    assert (
        "GNOME Wayland has an experimental current-cursor keyboard route"
        in result.reason
    )
    assert "native and XWayland clients" in result.reason
    assert "BMP text and runtime checks required" in result.reason
    assert "has not been validated" not in result.reason


def test_missing_session_is_explicit(tmp_path):
    result = detect_desktop({}, tmp_path / "missing")
    assert result.session == "unknown"
    assert not result.injection_ready
    assert "could not be verified" in result.reason
