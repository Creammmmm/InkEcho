// SPDX-License-Identifier: MIT
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export function checkCapability(token) {
    if (typeof token !== 'string' || !/^[a-f0-9]{64}$/.test(token)) return false;
    const dir = GLib.getenv('XDG_RUNTIME_DIR');
    if (!dir) return false;
    const path = GLib.build_filenamev([dir, 'inkecho-ibus-candidate.cap']);
    // Linux O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK. Metadata and bytes are read
    // from the same held descriptor, not from a path after a separate check.
    let stream = null;
    let fd = -1;
    try {
        fd = GLib.open(path, 0x20000 | 0x80000 | 0x800, 0);
        if (fd < 0) return false;
        stream = new Gio.UnixInputStream({fd, close_fd: true});
        const info = Gio.File.new_for_path(`/proc/self/fd/${fd}`).query_info(
            'standard::type,standard::size,unix::uid,unix::mode',
            Gio.FileQueryInfoFlags.NONE, null);
        const uid = new Gio.Credentials().get_unix_user();
        if (info.get_file_type() !== Gio.FileType.REGULAR ||
            info.get_attribute_uint32('unix::uid') !== uid ||
            (info.get_attribute_uint32('unix::mode') & 0o077) !== 0 ||
            info.get_size() !== 64) return false;
        const bytes = stream.read_bytes(65, null).get_data();
        return new TextDecoder().decode(bytes) === token;
    } catch (_) { return false; }
    finally {
        if (stream) stream.close(null);
        else if (fd >= 0) GLib.close(fd);
    }
}
