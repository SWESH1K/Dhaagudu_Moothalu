from __future__ import annotations

import time
from typing import Optional


def manage_round(session, logger=None):
    """Background manager that enforces the hide/seek timing rules.

    Behavior:
    - Wait until session.round_start_ms (initial 30s hide phase already encoded)
    - For each hidder (players 1..N-1) give the seeker 45 seconds to catch that hidder.
      If not caught within 45s, that hidder becomes the winner and the round ends.
    - If the seeker catches all hidders within their allotted windows, the seeker wins.
    """
    try:
        if session.round_start_ms is None:
            return
        wait_ms = session.round_start_ms - int(time.time() * 1000)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)

        # now the hide phase has ended; enforce 45s per hidder
        hidders = [i for i in range(session.num_players) if i != 0]
        for hid in hidders:
            if session.winner_index is not None:
                break
            if session.frozen[hid]:
                if logger:
                    logger.info("Hidder %s already frozen at start of their window, skipping", hid)
                continue

            if logger:
                logger.info("Starting 45s catch window for hidder %s", hid)
            start = time.time()
            timed_out = True
            while time.time() - start < 45:
                if session.frozen[hid]:
                    timed_out = False
                    if logger:
                        logger.info("Hidder %s was caught within 45s", hid)
                    break
                if session.winner_index is not None:
                    timed_out = False
                    break
                time.sleep(0.25)

            if timed_out:
                session.winner_index = hid
                if logger:
                    logger.info("Hidder %s wins: not caught within 45s", hid)
                break

        if session.winner_index is None:
            session.winner_index = 0
            if logger:
                logger.info("Seeker wins: all hidders caught within allotted time")
    except Exception:
        if logger:
            logger.exception('Round manager failed')
