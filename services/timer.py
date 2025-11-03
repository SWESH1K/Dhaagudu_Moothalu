from __future__ import annotations

from typing import Optional

from core.contracts import ITimerService


class RoundTimer(ITimerService):
    """Round timer that tracks a server-provided epoch ms base and optional stop time."""

    def __init__(self) -> None:
        self._round_base: Optional[int] = None
        self._stopped: bool = False
        self._stop_ms: Optional[int] = None

    def set_round_base(self, epoch_ms: Optional[int]) -> None:
        self._round_base = epoch_ms if (isinstance(epoch_ms, (int, float)) and int(epoch_ms) > 0) else None
        self._stopped = False
        self._stop_ms = None

    def stop(self) -> None:
        import time
        self._stopped = True
        self._stop_ms = int(time.time() * 1000)

    def elapsed_seconds(self, now_epoch_ms: int) -> Optional[float]:
        if self._round_base is None or not isinstance(now_epoch_ms, (int, float)):
            return None
        base = float(self._round_base)
        if self._stopped and self._stop_ms is not None:
            return (float(self._stop_ms) - base) / 1000.0
        return (float(now_epoch_ms) - base) / 1000.0

    # helpers to expose state if needed
    @property
    def is_running(self) -> bool:
        return self._round_base is not None and not self._stopped
