// Isolated prototype. A same-UID process is not a security boundary.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export function consumeCapability(name, token) {
    if (!/^cap-[0-9a-f]{32}$/.test(name) || !/^[0-9a-f]{64}$/.test(token)) return false;
    const runtime = GLib.getenv('XDG_RUNTIME_DIR');
    if (!runtime) return false;
    let dirfd = -1, fd = -1, stream = null;
    try {
        // Linux O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC, anchored via procfs to fd.
        dirfd = GLib.open(runtime, 0x10000 | 0x20000 | 0x80000, 0);
        if (dirfd < 0) return false;
        const base = `/proc/self/fd/${dirfd}`;
        const uid = new Gio.Credentials().get_unix_user();
        const dirInfo = Gio.File.new_for_path(base).query_info(
            'standard::type,unix::uid,unix::mode', Gio.FileQueryInfoFlags.NONE, null);
        if (dirInfo.get_file_type() !== Gio.FileType.DIRECTORY ||
            dirInfo.get_attribute_uint32('unix::uid') !== uid ||
            (dirInfo.get_attribute_uint32('unix::mode') & 0o077) !== 0) return false;
        const source = Gio.File.new_for_path(`${base}/${name}`);
        const dest = Gio.File.new_for_path(`${base}/used-${name}`);
        fd = GLib.open(`${base}/${name}`, 0x20000 | 0x80000 | 0x800, 0);
        if (fd < 0) return false;
        stream = new Gio.UnixInputStream({fd, close_fd: true});
        const info = Gio.File.new_for_path(`/proc/self/fd/${fd}`).query_info(
            'standard::type,standard::size,unix::uid,unix::mode,unix::device,unix::inode,unix::nlink',
            Gio.FileQueryInfoFlags.NONE, null);
        if (info.get_file_type() !== Gio.FileType.REGULAR ||
            info.get_attribute_uint32('unix::uid') !== uid ||
            (info.get_attribute_uint32('unix::mode') & 0o777) !== 0o600 ||
            info.get_attribute_uint32('unix::nlink') !== 1 || info.get_size() !== 64 ||
            new TextDecoder().decode(stream.read_bytes(65, null).get_data()) !== token) return false;
        // GIO native move must not overwrite or silently fall back to copying.
        source.move(dest, Gio.FileCopyFlags.NOFOLLOW_SYMLINKS |
            Gio.FileCopyFlags.NO_FALLBACK_FOR_MOVE, null, null);
        const moved = dest.query_info('standard::type,unix::device,unix::inode',
            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, null);
        return moved.get_file_type() === Gio.FileType.REGULAR &&
            moved.get_attribute_uint32('unix::device') === info.get_attribute_uint32('unix::device') &&
            moved.get_attribute_uint64('unix::inode') === info.get_attribute_uint64('unix::inode');
    } catch (_) { return false; }
    finally {
        if (stream) stream.close(null);
        else if (fd >= 0) GLib.close(fd);
        if (dirfd >= 0) GLib.close(dirfd);
    }
}
