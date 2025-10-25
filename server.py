import socket
from _thread import *
import sys
import time
from settings import *


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.bind((server, port))
except socket.error as e:
    print(str(e))

def read_pos(data):
    parts = data.split(",")
    x = int(parts[0])
    y = int(parts[1])
    if len(parts) >= 4:
        state = parts[2]
        try:
            frame = int(parts[3])
        except Exception:
            frame = 0
    else:
        state = 'down'
        frame = 0
    # optional equip id
    if len(parts) >= 5:
        equip_id = parts[4]
    else:
        equip_id = 'None'

    # optional equip_frame
    if len(parts) >= 6:
        try:
            equip_frame = int(parts[5])
        except Exception:
            equip_frame = 0
    else:
        equip_frame = 0

    return (x, y, state, frame, equip_id, equip_frame)

def make_pos(tup):
    # join any tuple elements into comma-separated string
    return ",".join(map(str, tup))

# Listen for the configured number of players
s.listen(NUM_PLAYERS)
print(f"Waiting for connections (expecting {NUM_PLAYERS})... Server Started")

# Server round start timestamp (epoch ms). Start at now - 30s so clients see -00:30 initially.
ROUND_START_MS = None

# authoritative winner index when round ends (None when ongoing)
WINNER_INDEX = None

default_pos = (1272, 2018, 'down', 0, 'None', 0)
# create a list of default positions sized to NUM_PLAYERS. Each entry will be
# replaced by the player's latest reported state when data is received.
pos = [default_pos for _ in range(NUM_PLAYERS)]
# track frozen state server-side (False == not frozen)
frozen = [False for _ in range(NUM_PLAYERS)]

def threaded_client(conn, player):
    global WINNER_INDEX
    # send initial positions plus this client's index, role and round start:
    # first connected (player 0) is the seeker, all others are hidders
    role = 'seeker' if player == 0 else 'hidder'
    # send all players' positions joined by '|' so clients can render all players
    all_positions = "|".join([make_pos(p) for p in pos])
    # include the receiver's player index so the client knows which entry is theirs
    initial = all_positions + "::" + str(player) + "::" + role + "::" + str(ROUND_START_MS) + "::" + (str(WINNER_INDEX) if WINNER_INDEX is not None else 'None')
    conn.send(str.encode(initial))
    reply = "" 
    while True:
        try:
            raw = conn.recv(2048).decode("utf-8")
            data = read_pos(raw)
            pos[player] = data
            print("data=", data)
            # If sender included a targeted CAUGHT event (format 'CAUGHT:<idx>')
            # and the sender is allowed to catch (we treat player 0 as seeker),
            # apply the caught state server-side so broadcasts are authoritative.
            try:
                equip_id = data[4]
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
                        if role == 'seeker' and not frozen[target_idx]:
                            frozen[target_idx] = True
                            print(f"Player {target_idx} frozen by seeker {player}")
                            # mark the target's pos equip field to CAUGHT:<target_idx> so clients will see who was caught
                            try:
                                tx, ty, tstate, tframe, _, teframe = pos[target_idx]
                                pos[target_idx] = (tx, ty, tstate, tframe, f'CAUGHT:{target_idx}', teframe)
                            except Exception:
                                try:
                                    px, py, st, fr, eid, ef = pos[target_idx]
                                    pos[target_idx] = (px, py, st, fr, f'CAUGHT:{target_idx}', ef)
                                except Exception:
                                    pass
                            # compute winner: if all non-seeker players frozen, record seeker as winner
                            try:
                                non_seekers = [i for i in range(NUM_PLAYERS) if i != 0]
                                if all(frozen[i] for i in non_seekers):
                                    WINNER_INDEX = 0
                            except Exception:
                                pass
            except Exception:
                pass
 
            if not data:
                print("Disconnected")
                break
            else:
                # build the authoritative positions payload for all clients
                all_positions = "|".join([make_pos(p) for p in pos])
                reply = all_positions

                print("Received: ", data)
                # prepare reply augmented with role, round start and winner so clients stay in sync
                send_payload = reply + "::" + role + "::" + str(ROUND_START_MS) + "::" + (str(WINNER_INDEX) if WINNER_INDEX is not None else 'None')
                print("Broadcasting: ", send_payload)

                # Broadcast authoritative state to all connected clients so events
                # like CAUGHT propagate immediately (helps multi-player consistency).
                try:
                    for c in connections:
                        try:
                            c.send(str.encode(send_payload))
                        except Exception:
                            # ignore individual send failures; connection removal handled elsewhere
                            pass
                except Exception:
                    # fallback: send to this connection only
                    try:
                        conn.send(str.encode(send_payload))
                    except Exception:
                        pass
        except:
            break

    print("Lost connection")
    conn.close()

currentPlayer = 0
while True:
    conn, addr = s.accept()
    print("Connected to: " + addr[0] + ":" + str(addr[1]))
    # keep a global list of connections to support broadcasting
    try:
        connections.append(conn)
    except NameError:
        connections = [conn]
    # If we've now reached the configured number of players, start the round.
    # Note: currentPlayer is 0-based; when it equals NUM_PLAYERS - 1 the most
    # recent connection filled the expected slots.
    if currentPlayer == (NUM_PLAYERS - 1):
        ROUND_START_MS = int(time.time() * 1000) + 30000
        print(f"All {NUM_PLAYERS} players connected — starting round at", ROUND_START_MS)

    start_new_thread(threaded_client, (conn, currentPlayer))
    currentPlayer += 1