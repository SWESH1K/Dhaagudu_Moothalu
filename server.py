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

s.listen(2)
print("Waiting for a connection, Server Started")

# Server round start timestamp (epoch ms). Start at now - 30s so clients see -00:30 initially.
ROUND_START_MS = None

pos = [(1272, 2018, 'down', 0, 'None', 0), (1272, 2018, 'down', 0, 'None', 0)]

def threaded_client(conn, player):
    # send initial position plus role and round start: first connected (player 0) is seeker
    role = 'seeker' if player == 0 else 'hidder'
    initial = make_pos(pos[player]) + "," + role + "," + str(ROUND_START_MS)
    conn.send(str.encode(initial))
    reply = "" 
    while True:
        try:
            raw = conn.recv(2048).decode("utf-8")
            data = read_pos(raw)
            pos[player] = data
            print("data=", data)
 
            if not data:
                print("Disconnected")
                break
            else:
                if player == 1:
                    reply = pos[0]
                else:
                    reply = pos[1]

                print("Received: ", data)
                # prepare reply augmented with role and round start so clients stay in sync
                send_payload = make_pos(reply) + "," + role + "," + str(ROUND_START_MS)
                print("Sending: ", send_payload)

            conn.send(str.encode(send_payload))
        except:
            break

    print("Lost connection")
    conn.close()

currentPlayer = 0
while True:
    conn, addr = s.accept()
    print("Connected to: " + addr[0] + ":" + str(addr[1]))
    # If this is the second player connecting (currentPlayer == 1 before increment),
    # start the round now and set the ROUND_START_MS so clients see -30s initially.
    if currentPlayer == 1:
        ROUND_START_MS = int(time.time() * 1000) + 30000
        print("Both players connected — starting round at", ROUND_START_MS)

    start_new_thread(threaded_client, (conn, currentPlayer))
    currentPlayer += 1