"""Research verdict only; no registration, no text dispatch or fallback."""
def verdict(panel, target, current):
    if not panel.get('live') or not target or not target.get('focused'):
        return 'unknown'
    if not target.get('editable') or not target.get('text_interface'):
        return 'unsupported'
    cursor = panel.get('cursor')
    if (panel.get('pid') != target.get('pid') or not panel.get('path')
            or panel['path'] != current or not cursor
            or cursor.get('epoch') != panel.get('epoch')
            or cursor.get('at', 0) < panel.get('focusAt', 0)):
        return 'unknown'
    if panel.get('preedit') is not False:
        return 'busy_or_unknown'
    if cursor.get('kind') != 'set-cursor-location-relative' or panel.get('scale') != 1:
        return 'unknown_coordinate_space'
    area, caret = target.get('window'), cursor.get('raw')
    if not area or not caret or len(area) != 4 or len(caret) != 4:
        return 'unknown'
    x,y,w,h=area;cx,cy,cw,ch=caret
    if min(w,h,ch) <= 0 or not (x-2 <= cx <= x+w+2 and y-2 <= cy <= y+h+2):
        return 'geometry_mismatch'
    return 'candidate_only'
