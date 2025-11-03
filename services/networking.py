from __future__ import annotations

from typing import Optional

from core.contracts import INetworkClient
from network import Network as _LegacyNetwork


class TcpNetworkClient(INetworkClient):
    """Adapter that wraps the existing Network class to satisfy INetworkClient."""

    def __init__(self, host: str, port: int) -> None:
        self._impl = _LegacyNetwork(host, port)

    def get_initial(self) -> Optional[str]:
        try:
            return self._impl.getPos()
        except Exception:
            return None

    def send(self, data: str, wait_for_reply: bool = False) -> Optional[str]:
        try:
            return self._impl.send(data, wait_for_reply=wait_for_reply)
        except Exception:
            return None

    def get_latest(self) -> Optional[str]:
        try:
            return self._impl.get_latest()
        except Exception:
            return None

    def close(self) -> None:
        try:
            self._impl.close()
        except Exception:
            pass
