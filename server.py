import socket
from _thread import *
import sys
import time
from settings import *
import threading
import logging
import json
import copy
from server_core.protocol import read_pos, make_pos
from server_core.broadcaster import broadcast_state
from server_core.session import Session
from server_core.rounds import manage_round

# Server logger: by default we silence server-side logs. The client may enable
# or display logs as needed. To enable server logging for debugging set a
# handler/level externally or modify this module.
logger = logging.getLogger('dhaagudu.server')
logger.addHandler(logging.NullHandler())

# If started with --auto-ip, bind to all interfaces and let the responder
# advertise the detected local IP instead of requiring settings.py to contain
# a specific address.
try:
    if '--auto-ip' in sys.argv:
        try:
            server = ''
        except Exception:
            pass
except Exception:
    pass

# Allow overriding port and number of players via command-line arguments
try:
    for i, a in enumerate(sys.argv):
        if a == '--port' and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
            except Exception:
                pass
        if a == '--num-players' and i + 1 < len(sys.argv):
            try:
                NUM_PLAYERS = int(sys.argv[i + 1])
            except Exception:
                pass
        if a == '--host-name' and i + 1 < len(sys.argv):
            try:
                HOST_NAME = sys.argv[i + 1]
            except Exception:
                HOST_NAME = None
except Exception:
    pass

# default host name if not provided
try:
    HOST_NAME
except NameError:
    import socket as _socket
    try:
        HOST_NAME = _socket.gethostname()
    except Exception:
        HOST_NAME = 'Host'
# Allow overriding port and number of players via command-line arguments
try:
    for i, a in enumerate(sys.argv):
        if a == '--port' and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
            except Exception:
                pass
        if a == '--num-players' and i + 1 < len(sys.argv):
            try:
                NUM_PLAYERS = int(sys.argv[i + 1])
            except Exception:
                pass
except Exception:
    pass


def _get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't have to be reachable; used to pick a suitable outbound iface
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        try:
            s.close()
        except Exception:
            pass
    return ip


def _start_discovery_responder():
    """Start a background UDP listener that replies to discovery broadcasts.
    Responds with: DISCOVER_RESPONSE::<ip>::<port>
    """
    def _responder():
        try:
            dsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            dsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                dsock.bind(('', DISCOVERY_PORT))
            except Exception:
                try:
                    dsock.bind((server, DISCOVERY_PORT))
                except Exception:
                    return
            host_ip = server if server and server not in ('0.0.0.0', '') else _get_local_ip()
            while True:
                try:
                    data, addr = dsock.recvfrom(1024)
                    if not data:
                        continue
                    try:
                        if data.strip() == b'DISCOVER_REQUEST':
                            # include host name in discovery response so clients can show it
                            resp = f"DISCOVER_RESPONSE::{host_ip}::{port}::{HOST_NAME}".encode('utf-8')
                            dsock.sendto(resp, addr)
                    except Exception:
                        continue
                except Exception:
                    # continue on intermittent errors
                    continue
        except Exception:
            pass

    t = threading.Thread(target=_responder, daemon=True)
    t.start()


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.bind((server, port))
except socket.error as e:
    logger.error(str(e))

# Start discovery responder so clients can find this server via UDP broadcasts
try:
    _start_discovery_responder()
except Exception:
    pass


# Listen for the configured number of players
s.listen(NUM_PLAYERS)
logger.info(f"Waiting for connections (expecting {NUM_PLAYERS})... Server Started")

# Server round state is now encapsulated in a Session object.

# default pos now represented as a dict (JSON-friendly)
# Default position template for an empty slot. 'occupied' marks whether a
# client has actually claimed this player index. Initially False so clients
# can render empty slots (or nothing) until a real player joins.
default_pos = {
    'x': 1272,
    'y': 2018,
    'state': 'down',
    'frame': 0,
    'equip': 'None',
    'equip_frame': 0,
    'name': '',
    'occupied': False,
}
# create a list of default positions sized to NUM_PLAYERS. Each entry will be
# replaced by the player's latest reported state (and marked occupied) when
# data is received from a connected client.
pos = [copy.deepcopy(default_pos) for _ in range(NUM_PLAYERS)]
# track frozen state server-side (False == not frozen)
frozen = [False for _ in range(NUM_PLAYERS)]

# Initialize session wrapper around authoritative state
session = Session(num_players=NUM_PLAYERS, pos=pos, frozen=frozen)

def threaded_client(conn, player, session: Session):
    # send initial positions plus this client's index, role and round start:
    # first connected (player 0) is the seeker, all others are hidders
    role = 'seeker' if player == 0 else 'hidder'
    # send initial state as JSON so clients can parse safely
    try:
        initial_payload = {
            'positions': session.pos,
            'player_index': player,
            'role': role,
            'round_start': session.round_start_ms,
            'winner': session.winner_index
        }
        conn.send(json.dumps(initial_payload).encode('utf-8'))
    except Exception:
        try:
            # fallback to older CSV-style reply for compatibility
            all_positions = "|".join([make_pos((p['x'], p['y'], p['state'], p['frame'], p['equip'], p['equip_frame'], p.get('name',''))) for p in session.pos])
            initial = all_positions + "::" + str(player) + "::" + role + "::" + str(session.round_start_ms) + "::" + (str(session.winner_index) if session.winner_index is not None else 'None')
            conn.send(str.encode(initial))
        except Exception:
            pass
    reply = "" 
    while True:
        try:
            raw = conn.recv(2048).decode("utf-8")
            # try to parse JSON update from client; fall back to CSV parser
            data = None
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and 'x' in parsed:
                    # expected JSON update
                    # coerce types
                    try:
                        parsed['x'] = int(parsed.get('x', 0))
                    except Exception:
                        parsed['x'] = 0
                    try:
                        parsed['y'] = int(parsed.get('y', 0))
                    except Exception:
                        parsed['y'] = 0
                    try:
                        parsed['frame'] = int(parsed.get('frame', 0))
                    except Exception:
                        parsed['frame'] = 0
                    parsed['equip'] = parsed.get('equip', 'None')
                    parsed['equip_frame'] = int(parsed.get('equip_frame', 0)) if parsed.get('equip_frame') is not None else 0
                    parsed['name'] = str(parsed.get('name', '') or '')
                    data = parsed
            except Exception:
                data = None

            if data is None:
                # fallback to CSV-style message
                data = read_pos(raw)

            # store incoming data and mark this slot occupied
            try:
                # ensure we preserve keys and set occupied flag
                if isinstance(data, dict):
                    data['occupied'] = True
                    session.pos[player] = data
                else:
                    # fallback for older CSV-style payloads: convert to dict
                    p = data
                    new = {'x': p.get('x', 0) if isinstance(p, dict) else p[0],
                           'y': p.get('y', 0) if isinstance(p, dict) else p[1],
                           'state': p.get('state', 'down') if isinstance(p, dict) else (p[2] if len(p) > 2 else 'down'),
                           'frame': int(p.get('frame', 0)) if isinstance(p, dict) else (int(p[3]) if len(p) > 3 else 0),
                           'equip': p.get('equip', 'None') if isinstance(p, dict) else (p[4] if len(p) > 4 else 'None'),
                           'equip_frame': int(p.get('equip_frame', 0)) if isinstance(p, dict) else (int(p[5]) if len(p) > 5 else 0),
                           'name': p.get('name','') if isinstance(p, dict) else (p[6] if len(p) > 6 else ''),
                           'occupied': True}
                    session.pos[player] = new
            except Exception:
                session.pos[player] = data
            logger.debug("data=%s", data)
            # If sender included a targeted CAUGHT event (format 'CAUGHT:<idx>')
            # and the sender is allowed to catch (we treat player 0 as seeker),
            # apply the caught state server-side so broadcasts are authoritative.
            try:
                equip_id = data.get('equip') if isinstance(data, dict) else None
            except Exception:
                equip_id = None
            try:
                if isinstance(equip_id, str) and equip_id.startswith('CAUGHT:'):
                    # parse target index
                    try:
                        target_idx = int(equip_id.split(':', 1)[1])
                    except Exception:
                        target_idx = None
                    # only process valid targets
                    if target_idx is not None and 0 <= target_idx < NUM_PLAYERS:
                        # Only accept CAUGHT from seeker role to avoid cheating
                        # role variable is computed earlier for this connection
                        if role == 'seeker' and not session.frozen[target_idx]:
                            session.frozen[target_idx] = True
                            logger.info("Player %s frozen by seeker %s", target_idx, player)
                            # mark the target's pos equip field to CAUGHT:<target_idx> so clients will see who was caught
                            try:
                                # pos entries are dicts
                                session.pos[target_idx]['equip'] = f'CAUGHT:{target_idx}'
                            except Exception:
                                try:
                                    # fallback for older tuple entries
                                    p = session.pos[target_idx]
                                    session.pos[target_idx] = {'x': p[0], 'y': p[1], 'state': p[2], 'frame': p[3], 'equip': f'CAUGHT:{target_idx}', 'equip_frame': p[5], 'name': p[6] if len(p) >=7 else ''}
                                except Exception:
                                    pass
                            # compute winner: if all non-seeker players frozen, record seeker as winner
                            try:
                                non_seekers = [i for i in range(session.num_players) if i != 0]
                                if all(session.frozen[i] for i in non_seekers):
                                    session.winner_index = 0
                            except Exception:
                                pass
            except Exception:
                pass
 
            if not data:
                logger.info("Disconnected")
                break
            else:
                # build the authoritative positions payload for all clients (JSON)
                logger.debug("Broadcasting JSON state")
                try:
                    broadcast_state(session.connections, session.pos, role, session.round_start_ms, session.winner_index)
                except Exception:
                    # fallback: send to this connection only
                    try:
                        payload = {
                            'positions': session.pos,
                            'role': role,
                            'round_start': session.round_start_ms,
                            'winner': session.winner_index
                        }
                        conn.send(json.dumps(payload).encode('utf-8'))
                    except Exception:
                        pass
        except:
            break

    logger.info("Lost connection")
    conn.close()


def _round_manager_adapter():
    # Delegate to extracted round manager with our session object
    try:
        manage_round(session, logger)
        # broadcast final state so clients update promptly
        try:
            broadcast_state(session.connections, session.pos, None, session.round_start_ms, session.winner_index)
        except Exception:
            pass
    except Exception:
        logger.exception('Round manager failed')

currentPlayer = 0
while True:
    conn, addr = s.accept()
    logger.info("Connected to: %s:%s", addr[0], addr[1])
    # keep a global list of connections to support broadcasting
    try:
        session.connections.append(conn)
    except Exception:
        session.connections = [conn]
    # If we've now reached the configured number of players, start the round.
    # Note: currentPlayer is 0-based; when it equals NUM_PLAYERS - 1 the most
    # recent connection filled the expected slots.
    if currentPlayer == (NUM_PLAYERS - 1):
        start_ms = int(time.time() * 1000) + 30000
        session.reset_for_new_round(start_ms)
        # start the round manager thread that will enforce per-hidder timers
        try:
            t = threading.Thread(target=_round_manager_adapter, daemon=True)
            t.start()
        except Exception:
            pass
    logger.info(f"All {NUM_PLAYERS} players connected — starting round at {session.round_start_ms}")

    start_new_thread(threaded_client, (conn, currentPlayer, session))
    currentPlayer += 1