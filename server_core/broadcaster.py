from __future__ import annotations

import json
from typing import List
from .payloads import build_broadcast_payload


def broadcast_state(connections, pos, role, round_start_ms, winner_index):
    """Broadcast authoritative state to all connections (JSON)."""
    try:
        payload = build_broadcast_payload(pos, role, round_start_ms, winner_index)
        bstr = json.dumps(payload)
    except Exception:
        bstr = ''
    if not bstr:
        return
    try:
        for c in connections:
            try:
                c.send(bstr.encode('utf-8'))
            except Exception:
                pass
    except Exception:
        pass
