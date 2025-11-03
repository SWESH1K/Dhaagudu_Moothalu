from __future__ import annotations

import os
import pygame
from typing import Optional, Tuple

from util.resource_path import resource_path
from core.contracts import IAudioService


class PygameAudioService(IAudioService):
    """Pygame-backed audio implementation.

    Encapsulates audio setup and common effects (bg music, whistle positional).
    """

    def __init__(self) -> None:
        # best-effort mixer init
        try:
            pygame.mixer.init()
        except Exception:
            pass

        self._whistle: Optional[pygame.mixer.Sound] = self._load_sound(os.path.join("sounds", "whistle.wav"))
        self._last_whistle_info: Tuple[float, float, int] | None = None

    def _load_sound(self, rel_path: str) -> Optional[pygame.mixer.Sound]:
        try:
            snd = pygame.mixer.Sound(resource_path(rel_path))
            return snd
        except Exception:
            return None

    def play_bg_loop(self, path: str, volume: float = 0.4) -> None:
        try:
            pygame.mixer.music.load(resource_path(path))
            pygame.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))
            pygame.mixer.music.play(-1)
        except Exception:
            # fallback: try as Sound
            try:
                snd = pygame.mixer.Sound(resource_path(path))
                ch = pygame.mixer.find_channel()
                if ch:
                    ch.play(snd, loops=-1)
                    ch.set_volume(volume)
                else:
                    snd.play(loops=-1)
            except Exception:
                pass

    def play_whistle_normal(self) -> None:
        if not self._whistle:
            return
        try:
            ch = pygame.mixer.find_channel()
        except Exception:
            ch = None
        try:
            if ch:
                ch.set_volume(1.0, 1.0)
                ch.play(self._whistle)
            else:
                self._whistle.set_volume(1.0)
                self._whistle.play()
        except Exception:
            try:
                self._whistle.play()
            except Exception:
                pass

    def play_whistle_at(self, listener_xy: Tuple[int, int], source_xy: Tuple[int, int], max_hear_dist: float,
                         window_width: int) -> None:
        if not self._whistle:
            return
        try:
            lx, ly = int(listener_xy[0]), int(listener_xy[1])
            sx, sy = int(source_xy[0]), int(source_xy[1])
            dx, dy = sx - lx, sy - ly
            import math as _math
            dist = _math.hypot(dx, dy)
            if dist > max(1.0, float(max_hear_dist)):
                # too far; no sound
                return
            vol = max(0.0, 1.0 - (dist / float(max_hear_dist)))
            pan_range = max(float(window_width) / 2.0, 200.0)
            pan = max(-1.0, min(1.0, -dx / pan_range))
            left = vol * (1.0 - pan) / 2.0
            right = vol * (1.0 + pan) / 2.0
            ch = None
            try:
                ch = pygame.mixer.find_channel()
            except Exception:
                ch = None
            if ch:
                try:
                    ch.set_volume(left, right)
                    ch.play(self._whistle)
                except Exception:
                    try:
                        self._whistle.set_volume(vol)
                        self._whistle.play()
                    except Exception:
                        pass
            else:
                try:
                    self._whistle.set_volume(vol)
                    self._whistle.play()
                except Exception:
                    pass
        except Exception:
            pass
