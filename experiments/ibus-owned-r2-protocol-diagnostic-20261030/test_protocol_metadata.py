from protocol_metadata import metadata


def test_text_never_returned():
    for text in ['secret', 'hello\\nworld', '\\"private\\"', '\\\\private']:
        row = metadata('[123.4] zwp_text_input_v3#12.commit_string("' + text + '")')
        assert row and row['event'] == 'commit_string'
        assert set(row) <= {'at', 'protocol_at', 'direction', 'interface', 'object', 'event', 'length'}
        assert 'secret' not in repr(row) and 'private' not in repr(row)


def test_surrounding_keys_and_other_messages_dropped():
    for line in ['[1] -> zwp_text_input_v3@3.set_surrounding_text("secret", 6, 6)', '[1] wl_keyboard@3.key(1,2,3,4)', '[1] wl_registry#2.global(1,"secret",3)', 'ERROR secret']:
        assert metadata(line) is None
    assert metadata('[1] zwp_text_input_v3@3.commit_string("' + 's' * 65536 + '")') is None


def test_order_and_numeric_protocol_metadata():
    assert metadata('[1] -> zwp_text_input_v3@4.enable()')['direction'] == 'request'
    assert metadata('[2] zwp_text_input_v3#4.done(13)')['serial'] == 13
    assert metadata('[3] zwp_text_input_v3#4.commit_string("\\n第")')['length'] == 2
    assert metadata('[4] -> zwp_text_input_v3#4.set_cursor_rectangle(1,2,3,4)')['event'] == 'set_cursor_rectangle'


def test_report_payload_redacted_and_malformed_header_ignored():
    from protocol_metadata import redact_report
    row = redact_report({'sample': 'secret', 'first_dom': {'a': 'secret', 'events': [{'data': 'secret', 'type': 'beforeinput'}]}})
    assert 'secret' not in repr(row) and row['sample_length'] == 6
    assert metadata('[1.2.3] zwp_text_input_v3#4.done(1)')['serial'] == 1
    assert metadata('[123.4] {Default Queue} -> zwp_text_input_v3#4.enable()')['direction'] == 'request'


def test_multiline_string_emits_length_only():
    from protocol_metadata import TraceDecoder
    d = TraceDecoder()
    assert d.feed('[1] {Default Queue} zwp_text_input_v3#4.commit_string("\n') is None
    row = d.feed('第")\n')
    assert row['length'] == 2 and '第' not in repr(row)
