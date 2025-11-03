from __future__ import annotations

import pygame
from typing import Optional

from settings import WINDOW_WIDTH, WINDOW_HEIGHT, NUM_PLAYERS


class HUDRenderer:
    """Draws HUD elements, player names, controls hints, timer panel, and overlays.

    It reads needed state from the passed-in game instance to avoid tight coupling.
    """

    def __init__(self, game):
        self.g = game

    def draw_players_tab(self):
        g = self.g
        try:
            entries = []
            try:
                local_name = getattr(g.player, 'name', None) or 'You'
                local_role = 'Seeker' if getattr(g.player, 'isSeeker', False) else 'Hidder'
                entries.append((local_name, local_role, True))
            except Exception:
                pass
            try:
                for idx, rp in sorted((getattr(g, 'remote_map', {}) or {}).items()):
                    try:
                        pname = getattr(rp, 'name', None) or f'Player{idx}'
                        prot = 'Seeker' if getattr(rp, 'isSeeker', False) else 'Hidder'
                        entries.append((pname, prot, False))
                    except Exception:
                        pass
            except Exception:
                pass

            if not entries:
                return

            padding = 8
            icon_size = 22
            font = g.font if getattr(g, 'font', None) else pygame.font.SysFont(None, 18)
            row_h = max(icon_size, font.get_height()) + 8
            total_h = row_h * len(entries)

            panel_w = max(220, 8 + icon_size + 8 + 8 + max((font.size(f"[{r}] {n}")[0] for n, r, _ in entries)))
            panel_w = min(panel_w, WINDOW_WIDTH // 4)

            base_x = WINDOW_WIDTH - panel_w - 12
            base_y = (WINDOW_HEIGHT // 2) - (total_h // 2)

            for i, (name, role, is_local) in enumerate(entries):
                y = base_y + i * row_h
                panel_h = row_h
                panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
                panel_surf.fill((0, 0, 0, 140))

                icon_x = padding
                icon_y = (panel_h - icon_size) // 2
                if role.lower().startswith('seek'):
                    color = (60, 140, 200)
                else:
                    color = (220, 140, 40)
                try:
                    pygame.draw.rect(panel_surf, color, (icon_x, icon_y, icon_size, icon_size), border_radius=6)
                except TypeError:
                    pygame.draw.rect(panel_surf, color, (icon_x, icon_y, icon_size, icon_size))

                try:
                    letter = 'S' if role.lower().startswith('seek') else 'H'
                    letter_s = font.render(letter, True, (0, 0, 0))
                    lx = icon_x + (icon_size - letter_s.get_width()) // 2
                    ly = icon_y + (icon_size - letter_s.get_height()) // 2
                    panel_surf.blit(letter_s, (lx, ly))
                except Exception:
                    pass

                try:
                    tag_text = f"[{role.capitalize()}]"
                    tag_s = font.render(tag_text, True, (200, 200, 200))
                    name_s = font.render(name, True, (240, 220, 160))
                    text_x = icon_x + icon_size + 8
                    text_y = (panel_h - name_s.get_height()) // 2
                    panel_surf.blit(tag_s, (text_x, text_y))
                    panel_surf.blit(name_s, (text_x + tag_s.get_width() + 6, text_y))
                except Exception:
                    pass

                if is_local:
                    try:
                        highlight = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
                        highlight.fill((255, 255, 255, 16))
                        panel_surf.blit(highlight, (0, 0))
                    except Exception:
                        pass

                try:
                    g.display_surface.blit(panel_surf, (base_x, y))
                except Exception:
                    pass
        except Exception:
            pass

    def draw_names(self):
        g = self.g
        try:
            offset = getattr(g.all_sprites, 'offset', pygame.math.Vector2(0, 0))
            # remote players
            for idx, rp in (getattr(g, 'remote_map', {})).items():
                try:
                    if getattr(rp, '_equipped', False):
                        continue
                    name = getattr(rp, 'name', None)
                    if name:
                        nm_s = g.font.render(str(name), True, (255, 255, 255))
                        x = rp.rect.centerx + offset.x - nm_s.get_width() // 2
                        y = rp.rect.top + offset.y - nm_s.get_height() - 6
                        shadow = g.font.render(str(name), True, (0, 0, 0))
                        g.display_surface.blit(shadow, (x + 1, y + 1))
                        g.display_surface.blit(nm_s, (x, y))
                except Exception:
                    pass
            # local player
            try:
                if not getattr(g.player, '_equipped', False):
                    lname = getattr(g.player, 'name', None)
                    if lname:
                        ln_s = g.font.render(str(lname), True, (200, 220, 255))
                        lx = g.player.rect.centerx + offset.x - ln_s.get_width() // 2
                        ly = g.player.rect.top + offset.y - ln_s.get_height() - 6
                        shadow = g.font.render(str(lname), True, (0, 0, 0))
                        g.display_surface.blit(shadow, (lx + 1, ly + 1))
                        g.display_surface.blit(ln_s, (lx, ly))
            except Exception:
                pass
        except Exception:
            pass

    def draw_role_and_hint(self):
        g = self.g
        try:
            role_text = "Role: Seeker" if getattr(g.player, 'isSeeker', False) else "Role: Hidder"
            role_surf = g.font.render(role_text, True, (255, 255, 255))
            bg_rect = role_surf.get_rect(topleft=(8, 8)).inflate(8, 8)
            s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 120))
            g.display_surface.blit(s, bg_rect.topleft)
            g.display_surface.blit(role_surf, (12, 12))

            hint_y = 12 + role_surf.get_height() + 6
            if not getattr(g.player, 'isSeeker', False):
                hint_surf = g.font.render("Press X to transform", True, (200, 200, 0))
                g.display_surface.blit(hint_surf, (12, hint_y))
                hint_y += hint_surf.get_height() + 6

            try:
                if getattr(g.player, 'isSeeker', False):
                    frozen_known = 0
                    total_hidders = max(0, NUM_PLAYERS - 1)
                    for idx, rp in (getattr(g, 'remote_map', {})).items():
                        if not getattr(rp, 'isSeeker', False) and getattr(rp, '_frozen', False):
                            frozen_known += 1
                    caught_text = f"Caught: {frozen_known}/{total_hidders}"
                    caught_surf = g.font.render(caught_text, True, (200, 200, 0))
                    g.display_surface.blit(caught_surf, (12, hint_y))
            except Exception:
                pass
        except Exception:
            pass

    def draw_timer_and_controls(self, timer_seconds: Optional[float]):
        g = self.g
        try:
            if timer_seconds is None:
                try:
                    joined = 1 + len(getattr(g, 'remote_map', {}))
                except Exception:
                    joined = 1
                text = f"Waiting for other players — {joined}/{NUM_PLAYERS}"
            else:
                elapsed = float(timer_seconds)
                HIDE_SECONDS = 30
                PER_HIDDER_SECONDS = 45
                total_hidders = max(0, NUM_PLAYERS - 1)
                total_hunt_seconds = PER_HIDDER_SECONDS * total_hidders

                if elapsed < 0:
                    remaining = max(0.0, -elapsed)
                    phase_label = "Hidders hide"
                else:
                    hunt_elapsed = elapsed
                    remaining = max(0.0, total_hunt_seconds - hunt_elapsed)
                    phase_label = "Seeker hunting"

                try:
                    import math as _math
                    secs = int(_math.ceil(remaining))
                except Exception:
                    secs = int(max(0, remaining))
                mins = secs // 60
                secs_rem = secs % 60
                timer_text = f"{mins:02d}:{secs_rem:02d}"
                text = f"{phase_label} — {timer_text}"

            txt_surf = g.large_font.render(text, True, (255, 255, 255))
            w, h = txt_surf.get_size()
            padding_x, padding_y = 16, 8
            panel_w = w + padding_x * 2
            panel_h = h + padding_y * 2
            panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel_surf.fill((0, 0, 0, 128))

            text_surf = g.large_font.render(text, True, (255, 255, 255))
            w, h = text_surf.get_size()
            thick_surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]
            for ox, oy in offsets:
                thick_surf.blit(g.large_font.render(text, True, (255, 255, 255)), (ox + 2, oy + 2))
            panel_surf.blit(thick_surf, (padding_x - 2, padding_y - 2))
            x = (WINDOW_WIDTH - panel_w) // 2
            y = 8
            g.display_surface.blit(panel_surf, (x, y))

            # Controls helper in bottom-left
            try:
                x_label = 'Check' if getattr(g.player, 'isSeeker', False) else 'Transform'
                y_label = 'Inventory' if getattr(g.player, 'isSeeker', False) else 'Whistle'
                entries = [
                    ('Y', (220, 180, 40), y_label),
                    ('X', (60, 140, 220), x_label),
                ]
                padding = 8
                icon_size = 22
                font_h = g.font.get_height()
                row_h = max(icon_size, font_h) + 8
                total_h = row_h * len(entries)
                base_x = 12
                base_y = WINDOW_HEIGHT - 12 - total_h
                for i, (label_char, color, label_text) in enumerate(entries):
                    ry = base_y + i * row_h
                    txt_surf2 = g.font.render(label_text, True, (255, 255, 255))
                    panel_w2 = icon_size + 8 + txt_surf2.get_width() + padding * 2
                    panel_h2 = row_h
                    panel_surf2 = pygame.Surface((panel_w2, panel_h2), pygame.SRCALPHA)
                    panel_surf2.fill((0, 0, 0, 140))
                    g.display_surface.blit(panel_surf2, (base_x, ry))
                    icon_x = base_x + padding
                    icon_y = ry + (panel_h2 - icon_size) // 2
                    try:
                        pygame.draw.rect(g.display_surface, color, (icon_x, icon_y, icon_size, icon_size), border_radius=6)
                    except TypeError:
                        pygame.draw.rect(g.display_surface, color, (icon_x, icon_y, icon_size, icon_size))
                    letter_s = g.font.render(label_char, True, (0, 0, 0))
                    lx = icon_x + (icon_size - letter_s.get_width()) // 2
                    ly = icon_y + (icon_size - letter_s.get_height()) // 2
                    g.display_surface.blit(letter_s, (lx, ly))
                    text_x = icon_x + icon_size + 8
                    text_y = ry + (panel_h2 - txt_surf2.get_height()) // 2
                    g.display_surface.blit(txt_surf2, (text_x, text_y))
            except Exception:
                pass

            # Optional whistle debug meter
            try:
                now_ms = pygame.time.get_ticks()
                if getattr(g, '_last_whistle_time', 0) and now_ms - g._last_whistle_time <= 3000 and g._last_whistle_volume is not None:
                    vol = max(0.0, min(1.0, float(g._last_whistle_volume)))
                    txt = f"Whistle vol: {int(vol * 100)}%"
                    txt_surf3 = g.font.render(txt, True, (255, 255, 255))
                    padding3 = 6
                    bg_rect = txt_surf3.get_rect(bottomleft=(12, WINDOW_HEIGHT - 12)).inflate(padding3 * 2, padding3 * 2)
                    s3 = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                    s3.fill((0, 0, 0, 160))
                    g.display_surface.blit(s3, bg_rect.topleft)
                    g.display_surface.blit(txt_surf3, (bg_rect.left + padding3, bg_rect.top + padding3))
                    bar_w = 120
                    bar_h = 10
                    bar_x = bg_rect.left + padding3
                    bar_y = bg_rect.top + padding3 + txt_surf3.get_height() + 6
                    pygame.draw.rect(g.display_surface, (200, 200, 200), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2), 1)
                    fill_w = int(vol * bar_w)
                    pygame.draw.rect(g.display_surface, (100, 220, 100), (bar_x, bar_y, fill_w, bar_h))
            except Exception:
                pass
        except Exception:
            pass

    def draw_overlays(self):
        g = self.g
        # Frozen overlay
        if getattr(g.player, '_frozen', False) and not getattr(getattr(g, 'state', g), 'game_over', getattr(g, 'game_over', False)):
            try:
                overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 120))
                g.display_surface.blit(overlay, (0, 0))
                freeze_surf = g.large_font.render("You are caught", True, (255, 255, 255))
                freeze_rect = freeze_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
                g.display_surface.blit(freeze_surf, freeze_rect)
            except Exception:
                pass

        # Game over overlay
        if getattr(getattr(g, 'state', g), 'game_over', getattr(g, 'game_over', False)):
            try:
                overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                g.display_surface.blit(overlay, (0, 0))
                text = getattr(getattr(g, 'state', g), 'winner_text', getattr(g, 'winner_text', ''))
                win_surf = g.font.render(text, True, (255, 255, 255))
                win_rect = win_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
                g.display_surface.blit(win_surf, win_rect)
            except Exception:
                pass
