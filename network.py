import socket
from settings import *
import time

DISCOVER_MSG = b"DISCOVER_REQUEST"
DISCOVER_RESP_PREFIX = b"DISCOVER_RESPONSE::"

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


def discover_servers(timeout=2.0):
    """Broadcast a UDP discovery request on the LAN and collect responses.
    Returns a list of dicts: [{'ip': ip, 'port': port}, ...]
    """
    results = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)
        # send to broadcast address
        try:
            sock.sendto(DISCOVER_MSG, ('<broadcast>', DISCOVERY_PORT))
        except Exception:
            # some platforms prefer using empty string for broadcast
            try:
                sock.sendto(DISCOVER_MSG, ('255.255.255.255', DISCOVERY_PORT))
            except Exception:
                pass

        end = time.time() + timeout
        seen = set()
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(1024)
                if data.startswith(DISCOVER_RESP_PREFIX):
                    try:
                        payload = data[len(DISCOVER_RESP_PREFIX):].decode('utf-8')
                        parts = payload.split('::')
                        ip = parts[0]
                        pport = int(parts[1]) if len(parts) > 1 else port
                        key = (ip, pport)
                        if key not in seen:
                            seen.add(key)
                            results.append({'ip': ip, 'port': pport, 'addr': addr})
                    except Exception:
                        # ignore malformed responses
                        pass
            except socket.timeout:
                # loop until full timeout
                continue
            except Exception:
                break
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return results