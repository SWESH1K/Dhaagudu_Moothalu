from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional, Tuple, Sequence, Dict, Any


@dataclass(frozen=True)
class GameConfig:
    window_width: int
    window_height: int
    fps: int
    sprite_size: int
    num_players: int


@dataclass
class PlayerSnapshot:
    x: int
    y: int
    state: str
    frame: int
    equip: str = "None"
    equip_frame: int = 0
    name: Optional[str] = None
    occupied: bool = True


@dataclass
class GameState:
    """Mutable game state shared across systems.

    - my_index: the local player's index assigned by server
    - game_over: whether the round has ended
    - winner_text: UI-friendly winner message
    - whistle_emit: transient flag to emit a whistle in next outgoing payload
    - caught_target: transient target index for a CAUGHT event in next payload
    """
    my_index: int = 0
    game_over: bool = False
    winner_text: str = ""
    whistle_emit: bool = False
    caught_target: Optional[int] = None


class INetworkClient(Protocol):
    """Abstraction for client networking to support DIP and testing."""

    def get_initial(self) -> Optional[str]:
        ...

    def send(self, data: str, wait_for_reply: bool = False) -> Optional[str]:
        ...

    def get_latest(self) -> Optional[str]:
        ...

    def close(self) -> None:
        ...


class IAudioService(Protocol):
    def play_bg_loop(self, path: str, volume: float = 0.4) -> None:
        ...

    def play_whistle_normal(self) -> None:
        ...

    def play_whistle_at(self, listener_xy: Tuple[int, int], source_xy: Tuple[int, int], max_hear_dist: float,
                         window_width: int) -> None:
        ...


class ITimerService(Protocol):
    """Provides round-timer logic and read-only view for UI.

    round_base: optional epoch ms when round began (hide phase start).
    """

    def set_round_base(self, epoch_ms: Optional[int]) -> None:
        ...

    def stop(self) -> None:
        ...

    def elapsed_seconds(self, now_epoch_ms: int) -> Optional[float]:
        ...


class IResourceLocator(Protocol):
    def path(self, relative: str) -> str:
        ...


class IHUDRenderer(Protocol):
    def draw_controls(self) -> None:
        ...

    def draw_players_tab(self) -> None:
        ...
