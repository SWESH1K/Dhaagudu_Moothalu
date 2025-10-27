import socket
from settings import *
import time
import threading
import queue

DISCOVER_MSG = b"DISCOVER_REQUEST"
DISCOVER_RESP_PREFIX = b"DISCOVER_RESPONSE::"


class Network:
    """Simple TCP client with a background receiver thread.

    - connect() performs the initial blocking handshake and returns the server's
      initial reply.
    - After connecting, a background thread reads server broadcasts and
      buffers them into an internal queue. Call get_latest() to poll the
      most recent buffered message (non-blocking).
    - send(data, wait_for_reply=False) will by default just send data and
      return immediately. If wait_for_reply=True it will block and try to
      read a reply (keeps compatibility with legacy behavior).
    """
    def __init__(self, server_ip, server_port):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = server_ip
        self.port = server_port
        self.addr = (self.server, self.port)
        # perform initial connect+handshake (blocking)
        self.pos = self.connect()

        # inbox for incoming server messages (strings)
        self._inbox = queue.Queue()
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread_stop = threading.Event()
        self._recv_thread.start()

    def getPos(self):
        return self.pos

    def connect(self):
        try:
            self.client.connect(self.addr)
            # initial reply from server (blocking) — return to caller
            return self.client.recv(2048).decode("utf-8")
        except socket.error as e:
            print(str(e))

    def _recv_loop(self):
        # background receive loop that buffers incoming messages
        while not self._recv_thread_stop.is_set():
            try:
                data = self.client.recv(4096)
                if not data:
                    # remote closed
                    break
                try:
                    s = data.decode('utf-8')
                except Exception:
                    s = None
                if s is not None:
                    # push into inbox (non-blocking)
                    try:
                        self._inbox.put_nowait(s)
                    except Exception:
                        # if queue full or other error, drop this message
                        pass
            except Exception:
                # small sleep to avoid busy loop on persistent errors
                time.sleep(0.01)
        # ensure socket closed on exit
        try:
            self.client.close()
        except Exception:
            pass

    def send(self, data, wait_for_reply=False):
        try:
            self.client.sendall(str.encode(data))
            if wait_for_reply:
                try:
                    reply = self.client.recv(2048).decode("utf-8")
                    return reply
                except Exception:
                    return None
            return None
        except socket.error as e:
            print(str(e))
            return None

    def get_latest(self):
        """Return the most recent buffered message or None if none available."""
        last = None
        try:
            while True:
                last = self._inbox.get_nowait()
        except queue.Empty:
            return last

    def close(self):
        try:
            self._recv_thread_stop.set()
        except Exception:
            pass
        try:
            self.client.close()
        except Exception:
            pass


if __name__ == "__main__":
    n = Network(server, port)
    print(n.getPos())


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
                        name = parts[2] if len(parts) > 2 else None
                        key = (ip, pport)
                        if key not in seen:
                            seen.add(key)
                            results.append({'ip': ip, 'port': pport, 'name': name, 'addr': addr})
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