import pygame
import sys
import time
import math
import json
from settings import *
from player import Player
from sprites import *
from pytmx.util_pygame import load_pygame
import os
from util.resource_path import resource_path, ResourceLocator
import sys as _sys_for_server
from core.contracts import INetworkClient
from services.networking import TcpNetworkClient
from services.audio import PygameAudioService
from services.timer import RoundTimer
from renderers.hud import HUDRenderer
from renderers.world import WorldRenderer
from net.sync import parse_initial, parse_tick, build_outgoing_strings
from core.contracts import GameState
from controllers.input import InputHandler

# When the frozen executable is invoked with --run-server, run the bundled server
# code in this process. This allows the client to spawn a server subprocess that
# uses the same bundled exe (works for PyInstaller one-file builds).
if '--run-server' in _sys_for_server.argv:
    try:
        import server  # server.py runs its server loop on import
    except Exception as _e:
        print('Failed to start embedded server:', _e)
    _sys_for_server.exit(0)
from groups import AllSprites
import subprocess
import os
import sys
import socket


class Game:
    def __init__(self):
        pygame.init()
        # initialize audio mixer (best-effort)
        try:
            pygame.mixer.init()
        except Exception:
            pass
        # Font for HUD
        try:
            pygame.font.init()
        except Exception:
            pass
        # Font for HUD (retro monospace)
        try:
            self.font = pygame.font.SysFont('couriernew', 18)
            self.large_font = pygame.font.SysFont('couriernew', 36)
        except Exception:
            self.font = pygame.font.SysFont(None, 20)
            self.large_font = pygame.font.SysFont(None, 36)
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        # try to set the window icon from images/logos/logo_500x500.png
        try:
            icon_path = resource_path(os.path.join("images", "logos", "logo_500x500.png"))
            try:
                icon_surf = pygame.image.load(icon_path).convert_alpha()
                pygame.display.set_icon(icon_surf)
            except Exception:
                # fallback: try loading without convert_alpha
                try:
                    icon_surf = pygame.image.load(icon_path)
                    pygame.display.set_icon(icon_surf)
                except Exception:
                    pass
        except Exception:
            pass
        pygame.display.set_caption("Dhaagudu Moothalu")
        self.clock = pygame.time.Clock()
        # Services (DIP)
        self.resource_locator = ResourceLocator()
        self.audio = PygameAudioService()
        self.timer = RoundTimer()
        self.network = TcpNetworkClient(server, port)
        self.running = True
        # The server now sends all players' positions and metadata.
        # Parse the initial response using the sync helper.
        initial_resp = self.network.get_initial()
        positions_list, my_index, role, round_start, winner = parse_initial(initial_resp)
        # Initialize shared game state model with our player index
        idx = my_index if my_index is not None else 0
        self.state = GameState(my_index=idx)
        # Keep legacy attribute for backward-compat, but prefer self.state.my_index
        self.my_index = idx

        # If server didn't send positions list, fall back to previous read_pos behavior
        if positions_list:
            # determine this client's start_pos using state.my_index
            sidx = self.state.my_index if getattr(self, 'state', None) else 0
            try:
                sp = positions_list[sidx]
                self.start_pos = (sp[0], sp[1])
            except Exception:
                # fallback to a sensible default if parsing failed
                self.start_pos = (500, 300)
            self.role = role
            # Initialize timer from server-provided round_start (epoch ms)
            try:
                self.timer.set_round_base(int(round_start) if round_start is not None else None)
            except Exception:
                self.timer.set_round_base(None)
            # If server declared a winner, apply it immediately
            try:
                if winner is not None:
                    # winner is an index (int)
                    try:
                        widx = int(winner)
                        # if winner is this client or someone else, set game_over and show text
                        self.game_over = True
                        self.game_over_start = pygame.time.get_ticks()
                        if widx == self.state.my_index:
                            self.winner_text = "You win!"
                        else:
                            # Distinguish seeker vs hidder wins
                            if widx == 0:
                                self.winner_text = "Seeker wins!"
                            else:
                                self.winner_text = "Hidder wins!"
                        # stop the round timer at this moment
                        try:
                            self.timer.stop()
                        except Exception:
                            pass
                        # mirror into state
                        try:
                            self.state.game_over = True
                            self.state.winner_text = self.winner_text
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            # fallback to old single-position reply format
            try:
                sp = self.read_pos(initial_resp)
                self.start_pos = (sp[0], sp[1])
                try:
                    self.role = sp[6]
                except Exception:
                    self.role = None
                try:
                    if sp[7] is not None:
                        try:
                            _rs_tmp = int(sp[7])
                            self.server_round_base = _rs_tmp if _rs_tmp > 0 else None
                        except Exception:
                            self.server_round_base = None
                    else:
                        self.server_round_base = None
                except Exception:
                    self.server_round_base = None
            except Exception:
                # ultimate fallback
                self.start_pos = (500, 300)
                self.role = None
                self.timer.set_round_base(None)

        # server-provided round start (epoch ms). If missing, keep as None so we can show waiting state
        try:
            if sp[7] is not None:
                try:
                    _rs_tmp = int(sp[7])
                    self.timer.set_round_base(_rs_tmp if _rs_tmp > 0 else None)
                except Exception:
                    self.timer.set_round_base(None)
            else:
                self.timer.set_round_base(None)
        except Exception:
            self.timer.set_round_base(None)


        # Sprite Groups
        self.all_sprites = AllSprites()
        self.collision_sprites = pygame.sprite.Group()

        # Create local Player and remote Player instances for every other participant.
        is_local_seeker = (self.role == 'seeker')
        try:
            from player import Seeker, Hidder
            self.player = (Seeker if is_local_seeker else Hidder)(self.start_pos, self.all_sprites, self.collision_sprites, controlled=True, name=None)
        except Exception:
            # fallback to base Player
            from player import Player as _BasePlayer
            self.player = _BasePlayer(self.start_pos, self.all_sprites, self.collision_sprites, controlled=True, isSeeker=is_local_seeker)

    # Build remote players mapping: index -> Player instance
        self.remote_map = {}
        try:
            # If we parsed positions_list above and my_index exists, create remotes
            if positions_list:
                        sidx = self.state.my_index if getattr(self, 'state', None) else None
                        for idx, p in enumerate(positions_list):
                            if sidx is not None and idx == sidx:
                                continue
                            # support optional 'occupied' flag appended as last element
                            try:
                                occupied = p[7] if len(p) >= 8 else True
                            except Exception:
                                occupied = True
                            if not occupied:
                                # slot unoccupied; don't create a remote player yet
                                continue
                            px, py = p[0], p[1]
                            is_seeker = (idx == 0)
                            # pass name if available to Player constructor or set after
                            try:
                                pname = p[6] if len(p) >= 7 else None
                            except Exception:
                                pname = None
                            try:
                                from player import Seeker, Hidder
                                remote = (Seeker if is_seeker else Hidder)((px, py), self.all_sprites, self.collision_sprites, controlled=False, name=pname)
                            except Exception:
                                remote = Player((px, py), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=is_seeker)
                            try:
                                if pname:
                                    remote.name = pname
                            except Exception:
                                pass
                            self.remote_map[idx] = remote
            else:
                # Fallback: create a single remote player at an offset for older server behavior
                try:
                    from player import Seeker, Hidder
                    remote = (Hidder if is_local_seeker else Seeker)((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, name=None)
                except Exception:
                    remote = Player((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=(not is_local_seeker))
                sidx = self.state.my_index if getattr(self, 'state', None) else None
                self.remote_map[1 if sidx in (0, None) else 0] = remote
        except Exception:
            # best-effort fallback
            try:
                try:
                    from player import Seeker, Hidder
                    remote = (Hidder if is_local_seeker else Seeker)((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, name=None)
                except Exception:
                    remote = Player((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=(not is_local_seeker))
                self.remote_map[1] = remote
            except Exception:
                pass

        self.setup()
        # HUD renderer
        self.hud = HUDRenderer(self)
        # Input handler
        self.input = InputHandler(self)
        # World renderer
        self.world = WorldRenderer(self)
        # Game over / caught state
        self.game_over = False
        self.game_over_start = None
        self.winner_text = ""
        # Round timer handled by service; initially configured above
        # Audio: background ambience
        # remember last second when we played the whistle so we only play once per interval
        self._last_whistle_second = None
        # debug: last whistle proximity info (volume 0.0-1.0, pan -1..1, timestamp ms)
        self._last_whistle_volume = None
        self._last_whistle_pan = 0.0
        self._last_whistle_time = 0
        # background ambience: looped beach sound
        try:
            self.audio.play_bg_loop(os.path.join("sounds", "beach_background.mp3"), volume=0.4)
        except Exception:
            pass

    def read_pos(self, pos):
        parts = pos.split(",")
        x = int(parts[0])
        y = int(parts[1])
        if len(parts) >= 4:
            state = parts[2]
            try:
                frame = int(parts[3])
            except Exception:
                frame = 0
        else:
            state = 'down'
            frame = 0

        # optional equip id (string)
        if len(parts) >= 5:
            equip_id = parts[4]
        else:
            equip_id = 'None'

        # optional equip_frame (int)
        if len(parts) >= 6:
            try:
                equip_frame = int(parts[5])
            except Exception:
                equip_frame = 0
        else:
            equip_frame = 0

        # optional role (string) appended by server on initial connect: 'seeker' or 'hidder'
        if len(parts) >= 7:
            role = parts[6]
        else:
            role = None

        # optional round_start (epoch ms) appended by server: used to sync timers
        if len(parts) >= 8:
            try:
                round_start = int(parts[7])
            except Exception:
                round_start = None
        else:
            round_start = None

        return (x, y, state, frame, equip_id, equip_frame, role, round_start)
    
    def make_pos(self, tup):
        # join any number of elements into comma-separated string
        return ",".join(map(str, tup))

    def setup(self):
        map = load_pygame(resource_path(os.path.join("data", "maps", "world.tmx")))

        # Ground
        for x, y, image in map.get_layer_by_name("Ground").tiles():
            Sprite((x * SPRITE_SIZE, y * SPRITE_SIZE),
                            image,
                            self.all_sprites)

        # Trees / objects: mark these as interactive so player can pick them up
        # Keep a map of objects by id so we can reference them when syncing equips
        self.object_map = {}
        for obj in map.get_layer_by_name("Objects"):
            obj_sprite = CollisionSprite((obj.x, obj.y),
                                        obj.image,
                                        (self.all_sprites, self.collision_sprites))
            # mark as interactive (e.g., pickup-able)
            obj_sprite.interactive = True
            # create an id for this object based on its map coordinates
            obj_id = f"{int(obj.x)}_{int(obj.y)}"
            obj_sprite.obj_id = obj_id
            self.object_map[obj_id] = obj_sprite
            
        # Collision Tiles
        for obj in map.get_layer_by_name("Collisions"):
            CollisionSprite((obj.x, obj.y),
                            pygame.Surface((obj.width, obj.height)),
                            self.collision_sprites)
            
        # Entities
        # for obj in map.get_layer_by_name("Entities"):
        #     if obj.name == "Player":
                # self.player = Player((obj.x, obj.y),
                #                      self.all_sprites,
                #                      self.collision_sprites)
                # self.player = Player((500, 300),
                #                      self.all_sprites,
                #                      self.collision_sprites)
                
                # # self.other_player_pos = self.get_pos(self.network.send(self.make_pos((obj.x, obj.y))))
                # self.other_player_pos = self.network.send(self.make_pos((obj.x, obj.y)))
                # print("Other player pos:", self.other_player_pos)
                # # self.player2 = Player((self.other_player_pos.x + 100, self.other_player_pos.y),
                # #                      self.all_sprites,
                # #                      self.collision_sprites)
    # Audio helpers now delegated to AudioService (kept for compatibility)
    def _play_whistle_at(self, source_pos):
        try:
            listener = (int(self.player.hitbox.centerx), int(self.player.hitbox.centery))
            self.audio.play_whistle_at(listener, (int(source_pos[0]), int(source_pos[1])), 2000.0, WINDOW_WIDTH)
            # store debug info for HUD
            try:
                dx = int(source_pos[0]) - listener[0]
                import math as _m
                dist = _m.hypot(dx, int(source_pos[1]) - listener[1])
                vol = max(0.0, 1.0 - (dist / 2000.0))
                pan_range = max(WINDOW_WIDTH / 2.0, 200.0)
                pan_norm = max(-1.0, min(1.0, -dx / pan_range))
                self._last_whistle_volume = vol
                self._last_whistle_pan = pan_norm
                self._last_whistle_time = pygame.time.get_ticks()
            except Exception:
                pass
        except Exception:
            pass

    def _play_whistle_normal(self):
        try:
            self.audio.play_whistle_normal()
            # debug info
            try:
                self._last_whistle_volume = 1.0
                self._last_whistle_pan = 0.0
                self._last_whistle_time = pygame.time.get_ticks()
            except Exception:
                pass
        except Exception:
            pass

    

    def run(self):
        while self.running:

            dt = self.clock.tick(FPS) / 1000  # Delta time in seconds.

            for event in pygame.event.get():
                self.input.handle_event(event)

            # Send the player's hitbox center + animation state/frame so the
            # remote client can show correct animation. We'll send a 4-part
            # payload: x,y,state,frame
            px, py = int(self.player.hitbox.centerx), int(self.player.hitbox.centery)
            # build outgoing state and send (JSON preferred, CSV fallback)
            try:
                safe_name = (getattr(self.player, 'name', '') or '')
            except Exception:
                safe_name = ''
            j, csv = build_outgoing_strings(self.player, safe_name, self.state)
            try:
                if j:
                    self.network.send(j, wait_for_reply=False)
                else:
                    self.network.send(csv, wait_for_reply=False)
            except Exception:
                pass
            # poll for any incoming server broadcast (non-blocking)
            try:
                resp = self.network.get_latest()
            except Exception:
                resp = None
            # Clear one-shot state flags after sending
            try:
                self.state.whistle_emit = False
                self.state.caught_target = None
            except Exception:
                pass
            if resp:
                positions_list, round_start, winner = parse_tick(resp)
                # Quick pass: if any remote hidder emitted a WHISTLE, ensure
                # seeker clients play positional audio immediately. This
                # guards against cases where the main per-entry loop may not
                # trigger playback in time.
                try:
                    if getattr(self.player, 'isSeeker', False):
                        for idx, p in enumerate(positions_list):
                            try:
                                # p may be a tuple (legacy CSV) or dict (JSON)
                                equip = p[4] if not isinstance(p, dict) else p.get('equip')
                            except Exception:
                                equip = None
                            try:
                                if equip == 'WHISTLE' and idx != self.state.my_index:
                                    # extract coordinates robustly
                                    sx = p[0] if not isinstance(p, dict) else p.get('x')
                                    sy = p[1] if not isinstance(p, dict) else p.get('y')
                                    try:
                                        self._play_whistle_at((sx, sy))
                                    except Exception:
                                        pass
                                    break
                            except Exception:
                                pass
                        
                except Exception:
                    pass
                # update server-provided round start if a valid epoch ms is provided
                try:
                    rs = None
                    try:
                        rs_candidate = int(round_start)
                        if rs_candidate > 0:
                            rs = rs_candidate
                    except Exception:
                        rs = None
                    if rs is not None:
                        self.timer.set_round_base(rs)
                except Exception:
                    pass

                # if server declared a winner, handle it (authoritative)
                try:
                    if winner is not None:
                        try:
                            widx = int(winner)
                            if not self.game_over:
                                self.game_over = True
                                self.game_over_start = pygame.time.get_ticks()
                                if widx == self.state.my_index:
                                    self.winner_text = "You win!"
                                else:
                                    # Distinguish seeker vs hidder wins
                                    if widx == 0:
                                        self.winner_text = "Seeker wins!"
                                    else:
                                        self.winner_text = "Hidder wins!"
                                try:
                                    self.timer.stop()
                                except Exception:
                                    pass
                                # mirror into state
                                try:
                                    self.state.game_over = True
                                    self.state.winner_text = self.winner_text
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

                    # Apply updates for every player entry we received
                try:
                    # keep track of frozen hidders for win-condition
                    frozen_count = 0
                    total_hidders = max(0, NUM_PLAYERS - 1)
                    for idx, p in enumerate(positions_list):
                        # robustly extract fields and optional occupied flag
                        try:
                            if len(p) >= 8:
                                x, y, state, frame, equip_id, equip_frame, pname, occupied = p
                            elif len(p) == 7:
                                x, y, state, frame, equip_id, equip_frame, pname = p
                                occupied = True
                            elif len(p) == 6:
                                x, y, state, frame, equip_id, equip_frame = p
                                pname = None
                                occupied = True
                            else:
                                continue
                        except Exception:
                            continue

                        # If this entry is the local player, skip applying remote updates
                        if idx == self.state.my_index:
                            continue

                        # If slot is not occupied, remove any existing remote player
                        if not occupied:
                            try:
                                if hasattr(self, 'remote_map') and idx in self.remote_map:
                                    try:
                                        self.remote_map[idx].kill()
                                    except Exception:
                                        pass
                                    try:
                                        del self.remote_map[idx]
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            # nothing else to do for this slot
                            continue

                        # Ensure a remote player exists for occupied slots
                        if not hasattr(self, 'remote_map'):
                            self.remote_map = {}
                        if idx not in self.remote_map:
                            try:
                                is_seeker = (idx == 0)
                                try:
                                    from player import Seeker, Hidder
                                    remote = (Seeker if is_seeker else Hidder)((x, y), self.all_sprites, self.collision_sprites, controlled=False, name=pname)
                                except Exception:
                                    remote = Player((x, y), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=is_seeker)
                                if pname:
                                    remote.name = pname
                                self.remote_map[idx] = remote
                            except Exception:
                                pass

                        # Update remote player state
                        if hasattr(self, 'remote_map') and idx in self.remote_map:
                            rp = self.remote_map[idx]
                            try:
                                rp.set_remote_state((x, y), state, frame, equip_frame)
                                # update remote player's name if provided
                                try:
                                    if pname:
                                        rp.name = pname
                                except Exception:
                                    pass
                            except Exception:
                                try:
                                    rp.rect.center = (x, y)
                                except Exception:
                                    pass
                        # Handle special equip events embedded per-player
                        try:
                            if isinstance(equip_id, str) and equip_id.startswith('CAUGHT:'):
                                # format CAUGHT:<target_index>
                                try:
                                    target_idx = int(equip_id.split(':', 1)[1])
                                except Exception:
                                    target_idx = None
                                if target_idx is not None:
                                    # if target is local player, freeze ourselves
                                    if target_idx == self.state.my_index:
                                        if not getattr(self.player, 'isSeeker', False):
                                            try:
                                                self.player.freeze()
                                            except Exception:
                                                self.player._frozen = True
                                                self.player.can_move = False
                                                try:
                                                    self.player.unequip()
                                                except Exception:
                                                    pass
                                    else:
                                        # freeze the targeted remote player
                                        if hasattr(self, 'remote_map') and target_idx in self.remote_map:
                                            try:
                                                self.remote_map[target_idx].freeze()
                                            except Exception:
                                                try:
                                                    self.remote_map[target_idx]._frozen = True
                                                    self.remote_map[target_idx].can_move = False
                                                    try:
                                                        self.remote_map[target_idx].unequip()
                                                    except Exception:
                                                        pass
                                                except Exception:
                                                    pass
                            elif equip_id == 'WHISTLE':
                                # someone emitted a whistle; if local is seeker, play positional
                                try:
                                    if getattr(self.player, 'isSeeker', False):
                                        self._play_whistle_at((x, y))
                                    else:
                                        self._play_whistle_normal()
                                except Exception:
                                    pass
                            else:
                                # apply equip/unequip for remote players if appropriate
                                if hasattr(self, 'remote_map') and idx in self.remote_map:
                                    rp = self.remote_map[idx]
                                    if not getattr(rp, 'isSeeker', False):
                                        if equip_id != 'None' and equip_id in self.object_map:
                                            obj_sprite = self.object_map[equip_id]
                                            rp.equip(obj_sprite.image)
                                            rp._equipped_id = equip_id
                                        else:
                                            rp.unequip()
                                            if hasattr(rp, '_equipped_id'):
                                                del rp._equipped_id
                        except Exception:
                            pass

                    # After processing all entries, if this client is a seeker check win
                    try:
                        if getattr(self.player, 'isSeeker', False):
                            frozen_known = 0
                            for idx, rp in (getattr(self, 'remote_map', {})).items():
                                if not getattr(rp, 'isSeeker', False) and getattr(rp, '_frozen', False):
                                    frozen_known += 1
                            # include local hidders if any (unlikely when seeker)
                            if frozen_known >= total_hidders:
                                if not self.game_over:
                                    self.game_over = True
                                    self.game_over_start = pygame.time.get_ticks()
                                    self.winner_text = "Seeker wins!"
                                    self.round_stopped = True
                                    self.round_stop_ms = int(time.time() * 1000)
                                    # mirror into state
                                    try:
                                        self.state.game_over = True
                                        self.state.winner_text = self.winner_text
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                except Exception:
                    pass

            # update round timer and movement permission (use epoch ms from server)
            now_ms = int(time.time() * 1000)
            timer_seconds = None
            try:
                timer_seconds = self.timer.elapsed_seconds(now_ms)
            except Exception:
                timer_seconds = None
            # ensure player can_move only when not a seeker OR when timer > 0
            try:
                if getattr(self.player, 'isSeeker', False):
                    # seeker cannot move until the round has a start time and timer > 0
                    self.player.can_move = (timer_seconds is not None and timer_seconds > 0)
                else:
                    self.player.can_move = True
            except Exception:
                pass

            # Play whistle for hidders every 25 seconds while the timer is positive.
            # Broadcast a WHISTLE event (sent via the regular payload) so other clients
            # can play the whistle with positional audio. Also play locally.
            try:
                if (not getattr(self.player, 'isSeeker', False)) and timer_seconds is not None and timer_seconds > 0:
                    ts_sec = int(timer_seconds)
                    if ts_sec % 25 == 0 and ts_sec != self._last_whistle_second:
                        # mark for network broadcast (next outgoing payload will carry WHISTLE)
                        # Use game state transient flag so the outgoing builder includes WHISTLE.
                        try:
                            self.state.whistle_emit = True
                        except Exception:
                            pass
                        # keep legacy player flag for backward compatibility (some older code paths)
                        try:
                            self.player._whistle_emit = True
                        except Exception:
                            pass
                        # play locally: hidder should hear a normal (non-positional) whistle
                        try:
                            self._play_whistle_normal()
                        except Exception:
                            pass
                        self._last_whistle_second = ts_sec
                    # If we're at a non-multiple second, we don't change _last_whistle_second
            except Exception:
                pass

            # update
            self.all_sprites.update(dt)

            # draw (render the world once, centered on the local player)
            self.display_surface.fill((30, 30, 30))
            self.world.draw()
            # Names above players
            self.hud.draw_names()
            # Role, hints, and caught counter
            self.hud.draw_role_and_hint()
            # Timer panel and controls helper
            self.hud.draw_timer_and_controls(timer_seconds)
            # Right-side players tab
            self.hud.draw_players_tab()
            # Overlays (frozen/game over)
            self.hud.draw_overlays()
            # Auto-exit to menu after showing game over for 10 seconds
            try:
                if self.game_over and self.game_over_start and pygame.time.get_ticks() - self.game_over_start >= 10000:
                    self.running = False
            except Exception:
                pass
            pygame.display.update()
            self.clock.tick(FPS)

        # Close network socket (best-effort) so server isn't left with a stale connection
        try:
            if hasattr(self, 'network') and getattr(self.network, 'client', None):
                try:
                    self.network.client.close()
                except Exception:
                    pass
        except Exception:
            pass
        # Return to caller (likely the menu) instead of quitting the whole process
        return



if __name__ == "__main__":
    # Show menu first; when Play is chosen create a Game and run it. After the
    # Game.run() returns we return to the menu. Quit exits the loop and the app.
    from menu import Menu, SettingsMenu
    import importlib
    import settings as settings_mod

    menu = Menu()
    # track server subprocess started by this client (if any) so we can terminate it
    host_proc = None
    while True:
        choice = menu.run()
        if choice == 'play':
            # Prompt for player name first (Play -> Name -> Host/Join)
            def _prompt_name(menu):
                disp = menu.display_surface
                clock = menu.clock
                font = menu.font
                title_font = menu.title_font
                text = ''
                prompt_rect = pygame.Rect(220, WINDOW_HEIGHT//2 - 20, WINDOW_WIDTH - 440, 40)
                while True:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            return None
                        if event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_RETURN:
                                return text.strip() if text.strip() else None
                            if event.key == pygame.K_ESCAPE:
                                return None
                            if event.key == pygame.K_BACKSPACE:
                                text = text[:-1]
                            else:
                                ch = event.unicode
                                if ch:
                                    text += ch
                    try:
                        if getattr(menu, 'bg_surface', None):
                            disp.blit(menu.bg_surface, (0,0))
                        else:
                            disp.fill((20,20,30))
                    except Exception:
                        disp.fill((20,20,30))
                    title = title_font.render('Enter your name', True, (240,240,240))
                    disp.blit(title, (WINDOW_WIDTH//2 - title.get_width()//2, 120))
                    pygame.draw.rect(disp, (30,30,40), prompt_rect)
                    pygame.draw.rect(disp, (120,120,120), prompt_rect, 2)
                    txt_s = font.render(text, True, (240,240,240))
                    disp.blit(txt_s, (prompt_rect.x + 8, prompt_rect.y + 6))
                    hint = font.render('Type your name and press Enter. Esc to cancel.', True, (200,200,200))
                    disp.blit(hint, (WINDOW_WIDTH//2 - hint.get_width()//2, WINDOW_HEIGHT - 80))
                    pygame.display.update()
                    clock.tick(30)

            player_name = _prompt_name(menu)
            if not player_name:
                continue

            # Offer Host / Join selection before starting a game
            def _pick_host_or_join(menu):
                disp = menu.display_surface
                clock = menu.clock
                font = menu.font
                w, h = 320, 64
                host_rect = pygame.Rect((WINDOW_WIDTH - w)//2, (WINDOW_HEIGHT//2) - h - 12, w, h)
                join_rect = pygame.Rect((WINDOW_WIDTH - w)//2, (WINDOW_HEIGHT//2) + 12, w, h)
                back_rect = menu.quit_rect
                while True:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            return 'back'
                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            mx, my = pygame.mouse.get_pos()
                            if host_rect.collidepoint(mx, my):
                                return 'host'
                            if join_rect.collidepoint(mx, my):
                                return 'join'
                            if back_rect.collidepoint(mx, my):
                                return 'back'
                        if event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                return 'back'
                            if event.key == pygame.K_h:
                                return 'host'
                            if event.key == pygame.K_j:
                                return 'join'

                    # draw
                    try:
                        if getattr(menu, 'bg_surface', None):
                            disp.blit(menu.bg_surface, (0,0))
                        else:
                            disp.fill((20,20,30))
                    except Exception:
                        disp.fill((20,20,30))

                    title = menu.title_font.render('Play', True, (240,240,240))
                    disp.blit(title, (WINDOW_WIDTH//2 - title.get_width()//2, 80))

                    # buttons
                    mx, my = pygame.mouse.get_pos()
                    pygame.draw.rect(disp, (80,140,80) if host_rect.collidepoint(mx,my) else (60,120,60), host_rect, border_radius=8)
                    pygame.draw.rect(disp, (80,140,80) if join_rect.collidepoint(mx,my) else (60,120,60), join_rect, border_radius=8)
                    host_s = font.render('Host', True, (255,255,255))
                    join_s = font.render('Join', True, (255,255,255))
                    disp.blit(host_s, host_s.get_rect(center=host_rect.center))
                    disp.blit(join_s, join_s.get_rect(center=join_rect.center))

                    hint = font.render('H = Host, J = Join, Esc = Back', True, (200,200,200))
                    disp.blit(hint, (WINDOW_WIDTH//2 - hint.get_width()//2, WINDOW_HEIGHT - 80))

                    pygame.display.update()
                    clock.tick(30)

            pick = _pick_host_or_join(menu)
            if pick == 'back':
                continue

            # reload settings module so changes saved from menu are applied
            try:
                importlib.reload(settings_mod)
                for name in dir(settings_mod):
                    # update uppercase constants and common names
                    if name.isupper() or name in ('server', 'port'):
                        try:
                            globals()[name] = getattr(settings_mod, name)
                        except Exception:
                            pass
            except Exception:
                pass

            if pick == 'host':
                # Prompt for host configuration: port, number of players, player name
                def _host_config_prompt(menu, initial_name=None):
                    """Simplified, compact host configuration modal.
                    Fields: Hosting name (text), Port (digits), Players (click +/-)
                    Only responds to click events for +/- to avoid sensitivity.
                    """
                    disp = menu.display_surface
                    clock = menu.clock
                    font = menu.font

                    # defaults
                    try:
                        import settings as _smod
                        default_port = getattr(_smod, 'port', 5555)
                        default_players = getattr(_smod, 'NUM_PLAYERS', 2)
                    except Exception:
                        default_port = 5555
                        default_players = 2

                    name_str = (initial_name or 'Player')[:20]
                    port_str = str(default_port)
                    players_val = int(default_players)
                    active = None
                    error_msg = ''

                    panel_w = 360
                    panel_h = 200
                    panel_rect = pygame.Rect((WINDOW_WIDTH - panel_w)//2, (WINDOW_HEIGHT - panel_h)//2, panel_w, panel_h)

                    # rows
                    pad = 16
                    row_h = 36
                    name_rect = pygame.Rect(panel_rect.x + pad, panel_rect.y + 28, panel_w - pad*2, row_h)
                    port_rect = pygame.Rect(panel_rect.x + pad, name_rect.bottom + 8, 120, row_h)
                    players_rect = pygame.Rect(port_rect.right + 12, name_rect.bottom + 8, 60, row_h)

                    minus_rect = pygame.Rect(players_rect.right + 6, players_rect.y, 32, row_h)
                    plus_rect = pygame.Rect(minus_rect.right + 8, minus_rect.y, 32, row_h)

                    start_rect = pygame.Rect(panel_rect.centerx - 80, panel_rect.bottom - 44, 82, 32)
                    cancel_rect = pygame.Rect(panel_rect.centerx + 8, panel_rect.bottom - 44, 87, 32)

                    while True:
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                return None
                            if event.type == pygame.KEYDOWN:
                                if event.key == pygame.K_ESCAPE:
                                    return None
                                if active == 'name':
                                    if event.key == pygame.K_BACKSPACE:
                                        name_str = name_str[:-1]
                                    else:
                                        ch = event.unicode
                                        if ch and len(name_str) < 20:
                                            name_str += ch
                                elif active == 'port':
                                    if event.key == pygame.K_BACKSPACE:
                                        port_str = port_str[:-1]
                                    else:
                                        ch = event.unicode
                                        if ch and ch.isdigit() and len(port_str) < 5:
                                            port_str += ch
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                mx, my = pygame.mouse.get_pos()
                                if name_rect.collidepoint(mx, my):
                                    active = 'name'
                                elif port_rect.collidepoint(mx, my):
                                    active = 'port'
                                elif minus_rect.collidepoint(mx, my):
                                    players_val = max(2, players_val - 1)
                                elif plus_rect.collidepoint(mx, my):
                                    players_val = min(16, players_val + 1)
                                elif start_rect.collidepoint(mx, my):
                                    # validate
                                    try:
                                        port_val = int(port_str)
                                    except Exception:
                                        error_msg = 'Port must be a number'
                                        continue
                                    # check port availability
                                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    try:
                                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                                        s.bind(('', port_val))
                                    except Exception:
                                        error_msg = f'Port {port_val} is not available'
                                        try:
                                            s.close()
                                        except Exception:
                                            pass
                                        continue
                                    finally:
                                        try:
                                            s.close()
                                        except Exception:
                                            pass
                                    if players_val < 2:
                                        error_msg = 'Players must be >= 2'
                                        continue
                                    return (port_val, players_val, name_str.strip())
                                elif cancel_rect.collidepoint(mx, my):
                                    return None

                        # draw
                        try:
                            if getattr(menu, 'bg_surface', None):
                                disp.blit(menu.bg_surface, (0,0))
                            else:
                                disp.fill((18,18,28))
                        except Exception:
                            disp.fill((18,18,28))

                        pygame.draw.rect(disp, (30,30,36), panel_rect, border_radius=8)

                        # title
                        title_s = font.render('Host', True, (240,240,240))
                        disp.blit(title_s, (panel_rect.x + 12, panel_rect.y-3))

                        # name field
                        pygame.draw.rect(disp, (22,22,26), name_rect)
                        pygame.draw.rect(disp, (200,200,200) if active=='name' else (80,80,90), name_rect, 2)
                        ns = font.render(name_str or 'Player name', True, (230,230,230))
                        disp.blit(ns, (name_rect.x + 8, name_rect.y + 6))

                        # port
                        pygame.draw.rect(disp, (22,22,26), port_rect)
                        pygame.draw.rect(disp, (200,200,200) if active=='port' else (80,80,90), port_rect, 2)
                        ps = font.render(port_str, True, (230,230,230))
                        disp.blit(ps, (port_rect.x + 8, port_rect.y + 6))

                        # players +/-
                        pygame.draw.rect(disp, (22,22,26), players_rect)
                        pygame.draw.rect(disp, (80,80,90), players_rect, 2)
                        pv = font.render(str(players_val), True, (230,230,230))
                        disp.blit(pv, (players_rect.x + 10, players_rect.y + 6))

                        pygame.draw.rect(disp, (80,80,80), minus_rect)
                        pygame.draw.rect(disp, (80,80,80), plus_rect)
                        disp.blit(font.render('-', True, (255,255,255)), (minus_rect.x + 8, minus_rect.y + 6))
                        disp.blit(font.render('+', True, (255,255,255)), (plus_rect.x + 6, plus_rect.y + 6))

                        # buttons
                        mx, my = pygame.mouse.get_pos()
                        pygame.draw.rect(disp, (60,140,60) if start_rect.collidepoint((mx,my)) else (50,120,50), start_rect, border_radius=6)
                        pygame.draw.rect(disp, (140,60,60) if cancel_rect.collidepoint((mx,my)) else (120,50,50), cancel_rect, border_radius=6)
                        disp.blit(font.render('Start', True, (255,255,255)), (start_rect.x + 3, start_rect.y + 6))
                        disp.blit(font.render('Cancel', True, (255,255,255)), (cancel_rect.x + 3, cancel_rect.y + 6))

                        if error_msg:
                            em = font.render(error_msg, True, (220,100,100))
                            disp.blit(em, (panel_rect.centerx - em.get_width()//2, panel_rect.bottom - 76))

                        pygame.display.update()
                        clock.tick(30)

                cfg = _host_config_prompt(menu, initial_name=player_name)
                if not cfg:
                    continue
                chosen_port, chosen_players, chosen_name = cfg

                # start server in background and connect to localhost using chosen port/players
                try:
                    cwd = os.path.dirname(__file__)
                    # Use same Python executable to avoid PATH issues. If running as a
                    # bundled exe (PyInstaller onefile), spawn the same exe with a
                    # special flag so it starts the embedded server code.
                    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
                        host_cmd = [sys.executable, '--run-server', '--auto-ip', '--port', str(chosen_port), '--num-players', str(chosen_players)]
                    else:
                        host_cmd = [sys.executable, os.path.join(cwd, 'server.py'), '--auto-ip', '--port', str(chosen_port), '--num-players', str(chosen_players)]
                    # On Windows, suppress creating a new console window for the child process
                    try:
                        if os.name == 'nt':
                            CREATE_NO_WINDOW = 0x08000000
                            host_proc = subprocess.Popen(host_cmd, cwd=cwd, creationflags=CREATE_NO_WINDOW)
                        else:
                            host_proc = subprocess.Popen(host_cmd, cwd=cwd)
                    except TypeError:
                        # fallback if creationflags unsupported for some reason
                        host_proc = subprocess.Popen(host_cmd, cwd=cwd)
                    # give server a moment to bind sockets
                    time.sleep(0.5)
                    try:
                        import settings as _smod
                        _smod.server = '127.0.0.1'
                        _smod.port = chosen_port
                        _smod.NUM_PLAYERS = chosen_players
                        globals()['server'] = '127.0.0.1'
                        globals()['port'] = chosen_port
                        globals()['NUM_PLAYERS'] = chosen_players
                        # store player name for use after Game constructed
                        globals()['PLAYER_NAME'] = chosen_name
                    except Exception:
                        globals()['server'] = '127.0.0.1'
                        globals()['port'] = chosen_port
                        globals()['NUM_PLAYERS'] = chosen_players
                        globals()['PLAYER_NAME'] = chosen_name
                except Exception as e:
                    print('Failed to start server:', e)

            elif pick == 'join':
                # Show a simple server browser using LAN discovery with click-to-join
                chosen_ip = None
                try:
                    import network as netmod
                except Exception:
                    netmod = None

                def _prompt_ip(menu):
                    disp = menu.display_surface
                    clock = menu.clock
                    font = menu.font
                    text = ''
                    prompt_rect = pygame.Rect(220, WINDOW_HEIGHT//2 - 20, WINDOW_WIDTH - 440, 40)
                    while True:
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                return None
                            if event.type == pygame.KEYDOWN:
                                if event.key == pygame.K_RETURN:
                                    return text.strip()
                                elif event.key == pygame.K_BACKSPACE:
                                    text = text[:-1]
                                elif event.key == pygame.K_ESCAPE:
                                    return None
                                else:
                                    ch = event.unicode
                                    if ch:
                                        text += ch
                        try:
                            if getattr(menu, 'bg_surface', None):
                                disp.blit(menu.bg_surface, (0,0))
                            else:
                                disp.fill((20,20,30))
                        except Exception:
                            disp.fill((20,20,30))
                        title = menu.title_font.render('Join - Enter IP', True, (240,240,240))
                        disp.blit(title, (WINDOW_WIDTH//2 - title.get_width()//2, 120))
                        pygame.draw.rect(disp, (30,30,40), prompt_rect)
                        pygame.draw.rect(disp, (120,120,120), prompt_rect, 2)
                        txt_s = font.render(text, True, (240,240,240))
                        disp.blit(txt_s, (prompt_rect.x + 8, prompt_rect.y + 6))
                        hint = font.render('Type server IP and press Enter. Esc to cancel.', True, (200,200,200))
                        disp.blit(hint, (WINDOW_WIDTH//2 - hint.get_width()//2, WINDOW_HEIGHT - 80))
                        pygame.display.update()
                        clock.tick(30)

                def _select_server(menu):
                    disp = menu.display_surface
                    clock = menu.clock
                    font = menu.font

                    # UI rects
                    back_rect = menu.quit_rect
                    refresh_rect = pygame.Rect(WINDOW_WIDTH - 180, 24, 160, 36)
                    manual_rect = pygame.Rect(WINDOW_WIDTH - 360, 24, 160, 36)

                    results = []
                    selected = None

                    def _refresh():
                        nonlocal results
                        results = []
                        if netmod:
                            try:
                                results = netmod.discover_servers(timeout=1.5)
                            except Exception:
                                results = []

                    _refresh()

                    while True:
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                return None
                            if event.type == pygame.KEYDOWN:
                                if event.key == pygame.K_ESCAPE:
                                    return None
                                if event.key == pygame.K_r:
                                    _refresh()
                                if event.key == pygame.K_m:
                                    ip = _prompt_ip(menu)
                                    return ip
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                mx, my = pygame.mouse.get_pos()
                                if back_rect.collidepoint(mx, my):
                                    return None
                                if refresh_rect.collidepoint(mx, my):
                                    _refresh()
                                if manual_rect.collidepoint(mx, my):
                                    ip = _prompt_ip(menu)
                                    return ip
                                # check clicks on server list
                                y_start = 120
                                item_h = 48
                                for idx, r in enumerate(results):
                                    item_rect = pygame.Rect(120, y_start + idx * (item_h + 8), WINDOW_WIDTH - 240, item_h)
                                    if item_rect.collidepoint(mx, my):
                                        # join this server (return full record)
                                        return r

                        # draw
                        try:
                            if getattr(menu, 'bg_surface', None):
                                disp.blit(menu.bg_surface, (0,0))
                            else:
                                disp.fill((20,20,30))
                        except Exception:
                            disp.fill((20,20,30))

                        title = menu.title_font.render('Join - Available Servers', True, (240,240,240))
                        disp.blit(title, (WINDOW_WIDTH//2 - title.get_width()//2, 40))

                        # action buttons
                        pygame.draw.rect(disp, (60,120,60), refresh_rect, border_radius=6)
                        pygame.draw.rect(disp, (60,120,60), manual_rect, border_radius=6)
                        rtxt = font.render('Refresh (R)', True, (255,255,255))
                        mtxt = font.render('Manual IP (M)', True, (255,255,255))
                        disp.blit(rtxt, (refresh_rect.x + 10, refresh_rect.y + 6))
                        disp.blit(mtxt, (manual_rect.x + 8, manual_rect.y + 6))

                        hint = font.render('Click a server to join, M = manual IP, R = refresh, Esc = Back', True, (200,200,200))
                        disp.blit(hint, (WINDOW_WIDTH//2 - hint.get_width()//2, WINDOW_HEIGHT - 80))

                        # list results
                        y = 120
                        if not results:
                            no_s = font.render('No servers discovered on LAN', True, (220,220,220))
                            disp.blit(no_s, (WINDOW_WIDTH//2 - no_s.get_width()//2, y))
                        else:
                            item_h = 48
                            mx, my = pygame.mouse.get_pos()
                            for idx, r in enumerate(results):
                                item_rect = pygame.Rect(120, y + idx * (item_h + 8), WINDOW_WIDTH - 240, item_h)
                                hover = item_rect.collidepoint(mx, my)
                                pygame.draw.rect(disp, (100,180,100) if hover else (60,120,60), item_rect, border_radius=6)
                                host_name = r.get('name') or f"{r.get('ip')}"
                                title = f"{host_name}'s Server"
                                subtitle = f"{r.get('ip')}:{r.get('port')}"
                                t = font.render(title, True, (255,255,255))
                                st = font.render(subtitle, True, (200,200,200))
                                disp.blit(t, (item_rect.x + 12, item_rect.y + 6))
                                disp.blit(st, (item_rect.x + 12, item_rect.y + 6 + t.get_height()))

                        pygame.display.update()
                        clock.tick(30)

                # Run server selector
                sel = _select_server(menu)

                if sel:
                    # sel is a dict with ip/port/name
                    chosen_ip = sel.get('ip')
                    chosen_port = sel.get('port')

                # apply chosen server IP/port if available
                if chosen_ip:
                    try:
                        import settings as _smod
                        _smod.server = chosen_ip
                        _smod.port = chosen_port
                        globals()['server'] = chosen_ip
                        globals()['port'] = chosen_port
                    except Exception:
                        globals()['server'] = chosen_ip
                        globals()['port'] = chosen_port

            # start the game (client) after host/join selection
            game = Game()
            # apply chosen player name from the name prompt (or fallback to global)
            try:
                try:
                    game.player.name = player_name
                except Exception:
                    if 'PLAYER_NAME' in globals():
                        try:
                            game.player.name = globals().get('PLAYER_NAME')
                        except Exception:
                            pass
            except Exception:
                pass
            game.run()

            # If we started a local server when hosting, terminate it so a fresh
            # server can be launched for the next game. Use terminate() first
            # and escalate to kill if it doesn't exit within a short timeout.
            if host_proc is not None:
                try:
                    if host_proc.poll() is None:
                        try:
                            host_proc.terminate()
                        except Exception:
                            pass
                        # wait a short moment for graceful exit
                        try:
                            host_proc.wait(timeout=1.0)
                        except Exception:
                            try:
                                host_proc.kill()
                            except Exception:
                                pass
                except Exception:
                    pass
                finally:
                    host_proc = None
        elif choice == 'settings':
            # open settings editor. It will save to settings.py and reload the module.
            sm = SettingsMenu(menu.display_surface, menu.clock, menu.font, menu.title_font)
            res = sm.run()
            if res == 'saved':
                try:
                    importlib.reload(settings_mod)
                    for name in dir(settings_mod):
                        if name.isupper() or name in ('server', 'port'):
                            globals()[name] = getattr(settings_mod, name)
                except Exception:
                    pass
        else:
            break
    # cleanup and exit
    pygame.quit()
    sys.exit()