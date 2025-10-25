import socket
from settings import *

class Network:
    def __init__(self, server_ip, server_port):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = server_ip
        self.port = server_port
        self.addr = (self.server, self.port)
        self.pos = self.connect()

    def getPos(self):
        return self.pos

    def connect(self):
        try:
            self.client.connect(self.addr)
            return self.client.recv(2048).decode("utf-8")
        except socket.error as e:
            print(str(e))

    def send(self, data):
        try:
            self.client.sendall(str.encode(data))
            reply = self.client.recv(2048).decode("utf-8")
            return reply
        except socket.error as e:
            print(str(e))
            return None
        
if __name__ == "__main__":
    n = Network(server, port)
    print(n.send("Hello, Server!"))