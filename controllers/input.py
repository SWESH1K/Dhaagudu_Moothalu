from __future__ import annotations

import json
import pygame


class InputHandler:
    """Centralizes input handling and related immediate actions.

    Delegates to the Game instance for state and helper methods when needed.
    """

    def __init__(self, game):
        self.g = game

    def handle_event(self, event):
        g = self.g
        if event.type == pygame.QUIT:
            g.running = False
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_x:
            # Interact / catch / equip logic
            if g.game_over:
                return
            if getattr(g.player, '_frozen', False):
                return

            if getattr(g.player, 'isSeeker', False):
                self._seeker_try_catch()
            # Hidders: transform/equip or unequip
            obj = g.player.get_object_in_front(g.collision_sprites)
            if obj:
                try:
                    g.player.equip(obj.image)
                    if hasattr(obj, 'obj_id'):
                        g.player._equipped_id = obj.obj_id
                except Exception:
                    pass
            else:
                g.player.unequip()
                if hasattr(g.player, '_equipped_id'):
                    del g.player._equipped_id

        elif event.key == pygame.K_y:
            # Manual whistle for hidders
            if g.game_over or getattr(g.player, '_frozen', False):
                return
            if getattr(g.player, 'isSeeker', False):
                return
            # mark transient whistle on game state
            try:
                g.state.whistle_emit = True
            except Exception:
                pass
            try:
                g._play_whistle_normal()
            except Exception:
                pass
            # send immediate broadcast using unified builder
            try:
                from net.sync import build_outgoing_strings
                safe_name = (getattr(g.player, 'name', '') or '')
                j, csv = build_outgoing_strings(g.player, safe_name, g.state)
                try:
                    if j:
                        g.network.send(j, wait_for_reply=False)
                    else:
                        g.network.send(csv, wait_for_reply=False)
                except Exception:
                    pass
                # clear one-shot whistle flag after immediate send
                try:
                    g.state.whistle_emit = False
                except Exception:
                    pass
            except Exception:
                pass

    # internals
    def _seeker_try_catch(self):
        g = self.g
        # small probe rect in front of seeker
        probe_w, probe_h = 24, 24
        if g.player.state == 'up':
            probe = pygame.Rect(g.player.hitbox.centerx - probe_w//2, g.player.hitbox.top - 16 - probe_h, probe_w, probe_h)
        elif g.player.state == 'down':
            probe = pygame.Rect(g.player.hitbox.centerx - probe_w//2, g.player.hitbox.bottom + 16, probe_w, probe_h)
        elif g.player.state == 'left':
            probe = pygame.Rect(g.player.hitbox.left - 16 - probe_w, g.player.hitbox.centery - probe_h//2, probe_w, probe_h)
        else:  # right
            probe = pygame.Rect(g.player.hitbox.right + 16, g.player.hitbox.centery - probe_h//2, probe_w, probe_h)

        try:
            target_idx = None
            for idx, rp in getattr(g, 'remote_map', {}).items():
                try:
                    other_hitbox = rp.hitbox
                except Exception:
                    other_hitbox = rp.rect
                if probe.colliderect(other_hitbox):
                    target_idx = idx
                    try:
                        rp.freeze()
                    except Exception:
                        try:
                            rp._frozen = True
                            rp.can_move = False
                            rp.unequip()
                        except Exception:
                            pass
                    break
            if target_idx is not None:
                try:
                    rp_local = g.remote_map.get(target_idx)
                    if rp_local is not None:
                        try:
                            rp_local.freeze()
                        except Exception:
                            try:
                                rp_local._frozen = True
                                rp_local.can_move = False
                                rp_local.unequip()
                            except Exception:
                                pass
                    # mark transient caught target in game state
                    g.state.caught_target = int(target_idx)
                except Exception:
                    pass

                # Send immediate CAUGHT event
                try:
                    from net.sync import build_outgoing_strings
                    safe_name = (getattr(g.player, 'name', '') or '')
                    j, csv = build_outgoing_strings(g.player, safe_name, g.state)
                    try:
                        if j:
                            g.network.send(j, wait_for_reply=False)
                        else:
                            g.network.send(csv, wait_for_reply=False)
                    except Exception:
                        pass
                    # clear one-shot caught flag after immediate send
                    g.state.caught_target = None
                except Exception:
                    pass
        except Exception:
            pass
