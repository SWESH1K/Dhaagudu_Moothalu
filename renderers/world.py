from __future__ import annotations

import pygame


class WorldRenderer:
    """Renders world layers and entities using the camera/offset logic in AllSprites.

    Supports simple camera shake. Zoom is left as a future extension since AllSprites
    draws directly to the display surface (would require an off-screen buffer).
    """

    def __init__(self, game):
        self.g = game
        self._shake_until = 0
        self._shake_strength = (0, 0)

    def set_shake(self, dx: int, dy: int, duration_ms: int):
        now = pygame.time.get_ticks()
        self._shake_until = now + max(0, int(duration_ms))
        self._shake_strength = (int(dx), int(dy))

    def _current_shake(self):
        now = pygame.time.get_ticks()
        if now >= self._shake_until:
            return (0, 0)
        # simple alternating shake pattern
        phase = ((self._shake_until - now) // 50) % 2
        sx = self._shake_strength[0] if phase == 0 else -self._shake_strength[0]
        sy = self._shake_strength[1] if phase == 0 else -self._shake_strength[1]
        return (sx, sy)

    def draw(self):
        # AllSprites handles offset/camera internally based on target position
        base_target = self.g.player.rect.center
        sx, sy = self._current_shake()
        target = (base_target[0] + sx, base_target[1] + sy)
        self.g.all_sprites.draw(target)
