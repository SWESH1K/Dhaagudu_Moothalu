from __future__ import annotations

import json
from typing import List, Optional, Tuple
from core.contracts import GameState


def parse_initial(resp: Optional[str]):
    """Parse server's initial response.

    Returns: (positions_list, player_index, role, round_start, winner)
    positions_list entries are tuples: (x, y, state, frame, equip, equip_frame, name, occupied?)
    """
    if resp is None:
        return ([], None, None, None, None)
    # Try JSON first
    try:
        j = json.loads(resp)
        if isinstance(j, dict) and 'positions' in j:
            positions = []
            for p in j.get('positions', []):
                try:
                    x = int(p.get('x', 0))
                except Exception:
                    x = 0
                try:
                    y = int(p.get('y', 0))
                except Exception:
                    y = 0
                state = p.get('state', 'down')
                try:
                    frame = int(p.get('frame', 0))
                except Exception:
                    frame = 0
                equip = p.get('equip', 'None')
                try:
                    equip_frame = int(p.get('equip_frame', 0))
                except Exception:
                    equip_frame = 0
                name = p.get('name')
                occupied = p.get('occupied', True)
                positions.append((x, y, state, frame, equip, equip_frame, name, occupied))
            player_index = j.get('player_index')
            role = j.get('role')
            round_start = j.get('round_start')
            winner = j.get('winner')
            return (positions, player_index, role, round_start, winner)
    except Exception:
        pass

    # CSV with trailing metadata separated by '::'
    try:
        parts = resp.rsplit('::', 4)
    except Exception:
        parts = [resp]

    player_index = None
    role = None
    round_start = None
    winner = None

    if len(parts) == 5:
        all_positions_str, player_idx_s, role_s, round_s, winner_s = parts
        try:
            player_index = int(player_idx_s)
        except Exception:
            player_index = None
        role = role_s if role_s != 'None' else None
        try:
            round_start = int(round_s)
        except Exception:
            round_start = None
        winner = winner_s if winner_s != 'None' else None
    elif len(parts) == 4:
        all_positions_str, role_s, round_s, winner_s = parts
        role = role_s if role_s != 'None' else None
        try:
            round_start = int(round_s)
        except Exception:
            round_start = None
        winner = winner_s if winner_s != 'None' else None
    else:
        all_positions_str = parts[0]

    positions = []
    try:
        if all_positions_str:
            entries = all_positions_str.split('|')
            for e in entries:
                if not e:
                    continue
                parts_c = e.split(',')
                try:
                    x = int(parts_c[0]); y = int(parts_c[1])
                except Exception:
                    continue
                state = parts_c[2] if len(parts_c) >= 3 else 'down'
                try:
                    frame = int(parts_c[3]) if len(parts_c) >= 4 else 0
                except Exception:
                    frame = 0
                equip_id = parts_c[4] if len(parts_c) >= 5 else 'None'
                try:
                    equip_frame = int(parts_c[5]) if len(parts_c) >= 6 else 0
                except Exception:
                    equip_frame = 0
                name = parts_c[6] if len(parts_c) >= 7 else None
                if isinstance(name, str):
                    try:
                        name = name.split('::')[0].strip()
                    except Exception:
                        name = name.strip()
                positions.append((x, y, state, frame, equip_id, equip_frame, name))
    except Exception:
        positions = []
    return (positions, player_index, role, round_start, winner)


def parse_tick(resp: Optional[str]):
    """Parse per-tick server broadcast.

    Returns: (positions_list, round_start, winner)
    positions_list entries are tuples: (x, y, state, frame, equip, equip_frame, name, occupied?)
    """
    if resp is None:
        return ([], None, None)
    try:
        j = json.loads(resp)
        if isinstance(j, dict) and 'positions' in j:
            positions = []
            for p in j.get('positions', []):
                try:
                    x = int(p.get('x', 0))
                except Exception:
                    x = 0
                try:
                    y = int(p.get('y', 0))
                except Exception:
                    y = 0
                state = p.get('state', 'down')
                try:
                    frame = int(p.get('frame', 0))
                except Exception:
                    frame = 0
                equip = p.get('equip', 'None')
                try:
                    equip_frame = int(p.get('equip_frame', 0))
                except Exception:
                    equip_frame = 0
                name = p.get('name')
                if isinstance(name, str):
                    try:
                        name = name.split('::')[0].strip()
                    except Exception:
                        name = name.strip()
                occupied = p.get('occupied', True)
                positions.append((x, y, state, frame, equip, equip_frame, name, occupied))
            round_start = j.get('round_start')
            winner = j.get('winner')
            return (positions, round_start, winner)
    except Exception:
        pass

    # CSV with metadata using '::'
    try:
        parts = resp.rsplit('::', 3)
    except Exception:
        parts = [resp]
    round_start = None
    winner = None
    if len(parts) == 4:
        all_positions_str, role_s, round_s, winner_s = parts
        try:
            round_start = int(round_s)
        except Exception:
            round_start = None
        winner = winner_s if winner_s != 'None' else None
    elif len(parts) == 3:
        all_positions_str, round_s, winner_s = parts
        try:
            round_start = int(round_s)
        except Exception:
            round_start = None
        winner = winner_s if winner_s != 'None' else None
    else:
        all_positions_str = parts[0]

    positions = []
    try:
        if all_positions_str:
            entries = all_positions_str.split('|')
            for e in entries:
                if not e:
                    continue
                parts_c = e.split(',')
                try:
                    x = int(parts_c[0]); y = int(parts_c[1])
                except Exception:
                    continue
                state = parts_c[2] if len(parts_c) >= 3 else 'down'
                try:
                    frame = int(parts_c[3]) if len(parts_c) >= 4 else 0
                except Exception:
                    frame = 0
                equip_id = parts_c[4] if len(parts_c) >= 5 else 'None'
                try:
                    equip_frame = int(parts_c[5]) if len(parts_c) >= 6 else 0
                except Exception:
                    equip_frame = 0
                name = parts_c[6] if len(parts_c) >= 7 else None
                if isinstance(name, str):
                    try:
                        name = name.split('::')[0].strip()
                    except Exception:
                        name = name.strip()
                # assume occupied for legacy CSV responses
                positions.append((x, y, state, frame, equip_id, equip_frame, name, True))
    except Exception:
        positions = []
    return (positions, round_start, winner)


def build_outgoing_strings(player, safe_name: str, state: Optional[GameState] = None) -> Tuple[str, str]:
    """Build outgoing payload for a player's current state.

    Returns a tuple of (json_string, csv_fallback_string).
    """
    try:
        px, py = int(player.hitbox.centerx), int(player.hitbox.centery)
    except Exception:
        try:
            px, py = int(player.rect.centerx), int(player.rect.centery)
        except Exception:
            px, py = 0, 0

    equip_id = 'None'
    equip_frame = 0

    # Transient game-state driven events take priority
    try:
        if state is not None and state.caught_target is not None:
            try:
                equip_id = f"CAUGHT:{int(state.caught_target)}"
            except Exception:
                equip_id = 'CAUGHT'
        elif state is not None and getattr(state, 'whistle_emit', False):
            equip_id = 'WHISTLE'
        elif getattr(player, '_equipped', False) and hasattr(player, '_equipped_id'):
            equip_id = str(player._equipped_id)
            try:
                equip_frame = int(player.frame_index)
            except Exception:
                equip_frame = 0
    except Exception:
        pass

    try:
        frame = int(player.frame_index)
    except Exception:
        frame = 0

    payload_obj = {
        'x': px,
        'y': py,
        'state': getattr(player, 'state', 'down'),
        'frame': frame,
        'equip': equip_id,
        'equip_frame': equip_frame,
        'name': safe_name or ''
    }
    try:
        j = json.dumps(payload_obj)
    except Exception:
        j = ''
    # CSV fallback mirrors legacy format; strip commas from name
    csv_name = (safe_name or '').replace(',', '')
    csv = f"{px},{py},{payload_obj['state']},{frame},{equip_id},{equip_frame},{csv_name}"
    return j, csv
