from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_broadcast_payload(positions: List[Any], role: Optional[str], round_start_ms: Optional[int], winner_index: Optional[int]) -> Dict[str, Any]:
    """Construct the authoritative broadcast payload in a single place.

    Ensures consistent field names and value shapes for clients.
    """
    return {
        'positions': positions,
        'role': role,
        'round_start': round_start_ms,
        'winner': winner_index,
    }
