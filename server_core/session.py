from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class Session:
    """Holds authoritative mutable state for a single round/session.

    This is a light wrapper around existing server globals to improve testability
    and enable cleaner dependency injection across helpers.
    """

    num_players: int
    pos: List[Any]
    frozen: List[bool]
    round_start_ms: Optional[int] = None
    winner_index: Optional[int] = None
    connections: List[Any] = field(default_factory=list)

    def reset_for_new_round(self, start_ms: int):
        self.round_start_ms = start_ms
        self.winner_index = None
        # reset frozen flags in-place
        for i in range(len(self.frozen)):
            self.frozen[i] = False
