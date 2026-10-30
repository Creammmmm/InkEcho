"""Drop all payload text; retain owned Wayland protocol scheduling metadata."""
import ast
import re
import time

_HEADER = re.compile(r'(zwp_text_input_v3|wl_keyboard)[@#](\d+)\.([a-z_]+)\((.*)\)\s*$', re.DOTALL)
_ALLOWED = {'enable', 'disable', 'commit', 'commit_string', 'done', 'enter', 'leave', 'set_cursor_rectangle', 'set_content_type'}
_TEXT = re.compile(r'"(?:[^"\\]|\\.)*"')


def metadata(line):
    """Return no raw line, strings, resource names, surrounding text or keycodes."""
    if len(line) > 65536:
        return None
    match = _HEADER.search(line.strip())
    if match is None:
        return None
    interface, object_id, event, args = match.groups()
    prefix = line[:match.start()].rstrip()
    outgoing = prefix.endswith('->')
    if event not in _ALLOWED:
        return None
    if interface == 'wl_keyboard' and event not in {'enter', 'leave'}:
        return None
    row = {'at': time.monotonic(), 'direction': 'request' if outgoing else 'event', 'interface': interface, 'object': int(object_id), 'event': event}
    if event == 'done' and args.isdecimal():
        row['serial'] = int(args)
    if event == 'commit_string':
        quoted = _TEXT.fullmatch(args)
        if quoted:
            try:
                value = ast.literal_eval(quoted.group().replace('\n', r'\n').replace('\r', r'\r'))
                if type(value) is str:
                    row['length'] = len(value)
            except (SyntaxError, ValueError, MemoryError):
                pass
    return row


def redact_report(value):
    if isinstance(value, list):
        return [redact_report(x) for x in value]
    if isinstance(value, dict):
        return {(k + '_length' if k in {'sample', 'data', 'text', 'a', 'b'} and isinstance(v, str) else k): (len(v) if k in {'sample', 'data', 'text', 'a', 'b'} and isinstance(v, str) else ('redacted' if k == 'message' else redact_report(v))) for k, v in value.items()}
    return value


class TraceDecoder:
    def __init__(self):
        self.pending = ''

    def feed(self, line):
        if self.pending:
            combined = self.pending + line
            self.pending = ''
            if len(combined) > 65536:
                return None
            row = metadata(combined)
            if row is not None:
                return row
            self.pending = combined
            return None
        row = metadata(line)
        if row is not None:
            return row
        if len(line) <= 65536 and re.search(r'zwp_text_input_v3[@#]\d+\.commit_string\("', line):
            self.pending = line
        return None
