from __future__ import annotations

from typing import Dict, Any


def read_pos(data: str):
    """Backward-compatible CSV parser for older clients.
    Returns a dict with keys: x,y,state,frame,equip,equip_frame,name
    """
    try:
        parts = data.split(",")
        x = int(parts[0])
        y = int(parts[1])
    except Exception:
        return None
    if len(parts) >= 4:
        state = parts[2]
        try:
            frame = int(parts[3])
        except Exception:
            frame = 0
    else:
        state = 'down'
        frame = 0
    equip = parts[4] if len(parts) >= 5 else 'None'
    try:
        equip_frame = int(parts[5]) if len(parts) >= 6 else 0
    except Exception:
        equip_frame = 0
    name = parts[6] if len(parts) >= 7 else ''
    return {'x': x, 'y': y, 'state': state, 'frame': frame, 'equip': equip, 'equip_frame': equip_frame, 'name': name}


def make_pos(tup):
    """Simple CSV joiner used for backward-compatible fallback replies."""
    try:
        return ",".join(map(str, tup))
    except Exception:
        return ""
