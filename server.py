import socket
from _thread import *
import sys
from settings import *


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.bind((server, port))
except socket.error as e:
    print(str(e))

def read_pos(data):
    data = data.split(",")
    return int(data[0]), int(data[1])

def make_pos(tup):
    # print("Tup=", tup)
    return str(tup[0]) + "," + str(tup[1])

s.listen(2)
print("Waiting for a connection, Server Started")

pos = [(0, 0), (100, 100)]

def threaded_client(conn, player):
    conn.send(str.encode(make_pos(pos[player])))
    reply = "" 
    while True:
        try:
            data = read_pos(conn.recv(2048).decode("utf-8"))
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
                print("Sending: ", reply)

            conn.send(str.encode(make_pos(reply)))
        except:
            break

    print("Lost connection")
    conn.close()

currentPlayer = 0
while True:
    conn, addr = s.accept()
    print("Connected to: " + addr[0] + ":" + str(addr[1]))
    start_new_thread(threaded_client, (conn, currentPlayer))
    currentPlayer += 1