import pygame
import sys
import time
import math
import json
from network import Network
from settings import *
from player import Player
from sprites import *
from pytmx.util_pygame import load_pygame
from os.path import join
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
        pygame.display.set_caption("Dhaagudu Moothalu")
        self.clock = pygame.time.Clock()
        self.network = Network(server, port)
        self.running = True
        # The server now sends all players' positions joined by '|' and appends
        # metadata separated by '::'. The initial reply also includes this
        # client's player index so we can map which entry is local.
        initial_resp = self.network.getPos()
        # parse initial response into positions list and metadata
        def _parse_server_resp(resp):
            # returns (positions_list, player_index_or_None, role_or_None, round_start_or_None, winner_index_or_None)
            if resp is None:
                return ([], None, None, None, None)
            # if server sent JSON, parse it directly
            try:
                j = json.loads(resp)
                if isinstance(j, dict) and 'positions' in j:
                    positions = []
                    for p in j.get('positions', []):
                        try:
                            x = int(p.get('x', 0))
                        except Exception:
                            x = 0
                        try:
                            y = int(p.get('y', 0))
                        except Exception:
                            y = 0
                        state = p.get('state', 'down')
                        try:
                            frame = int(p.get('frame', 0))
                        except Exception:
                            frame = 0
                        equip = p.get('equip', 'None')
                        try:
                            equip_frame = int(p.get('equip_frame', 0))
                        except Exception:
                            equip_frame = 0
                        name = p.get('name')
                        positions.append((x, y, state, frame, equip, equip_frame, name))
                    player_index = j.get('player_index')
                    role = j.get('role')
                    round_start = j.get('round_start')
                    winner = j.get('winner')
                    return (positions, player_index, role, round_start, winner)
            except Exception:
                pass
            # Server appends trailing metadata separated by '::'. Use rsplit to
            # safely extract trailing fields and avoid accidental inclusion in names.
            try:
                parts = resp.rsplit('::', 4)
            except Exception:
                parts = [resp]

            player_index = None
            role = None
            round_start = None
            winner = None

            if len(parts) == 5:
                all_positions_str, player_idx_s, role_s, round_s, winner_s = parts
                try:
                    player_index = int(player_idx_s)
                except Exception:
                    player_index = None
                role = role_s if role_s != 'None' else None
                try:
                    round_start = int(round_s)
                except Exception:
                    round_start = None
                winner = winner_s if winner_s != 'None' else None
            elif len(parts) == 4:
                # Non-initial reply: no player index
                all_positions_str, role_s, round_s, winner_s = parts
                role = role_s if role_s != 'None' else None
                try:
                    round_start = int(round_s)
                except Exception:
                    round_start = None
                winner = winner_s if winner_s != 'None' else None
            else:
                all_positions_str = parts[0]

            positions = []
            try:
                if all_positions_str:
                    # each position encoded as comma-separated fields; multiple entries separated by '|'
                    entries = all_positions_str.split('|')
                    for e in entries:
                        if not e:
                            continue
                        parts_c = e.split(',')
                        try:
                            x = int(parts_c[0]); y = int(parts_c[1])
                        except Exception:
                            continue
                        state = parts_c[2] if len(parts_c) >= 3 else 'down'
                        try:
                            frame = int(parts_c[3]) if len(parts_c) >= 4 else 0
                        except Exception:
                            frame = 0
                        equip_id = parts_c[4] if len(parts_c) >= 5 else 'None'
                        try:
                            equip_frame = int(parts_c[5]) if len(parts_c) >= 6 else 0
                        except Exception:
                            equip_frame = 0
                        # optional name field
                        name = parts_c[6] if len(parts_c) >= 7 else None
                        # strip any stray metadata markers from name
                        if isinstance(name, str):
                            try:
                                name = name.split('::')[0].strip()
                            except Exception:
                                name = name.strip()
                        positions.append((x, y, state, frame, equip_id, equip_frame, name))
            except Exception:
                positions = []

            return (positions, player_index, role, round_start, winner)

        positions_list, my_index, role, round_start, winner = _parse_server_resp(initial_resp)
        # store our player index for later incoming updates
        self.my_index = my_index if my_index is not None else 0

        # If server didn't send positions list, fall back to previous read_pos behavior
        if positions_list:
            # determine this client's start_pos using self.my_index if provided
            if self.my_index is None:
                self.my_index = 0
            try:
                sp = positions_list[self.my_index]
                self.start_pos = (sp[0], sp[1])
            except Exception:
                # fallback to a sensible default if parsing failed
                self.start_pos = (500, 300)
            self.role = role
            self.server_round_base = round_start
            # If server declared a winner, apply it immediately
            try:
                if winner is not None:
                    # winner is an index (int)
                    try:
                        widx = int(winner)
                        # if winner is this client or someone else, set game_over and show text
                        self.game_over = True
                        self.game_over_start = pygame.time.get_ticks()
                        if widx == self.my_index:
                            self.winner_text = "You win!"
                        else:
                            # If winner is seeker (0) we show Seeker wins
                            self.winner_text = "Seeker wins!"
                        # stop the round timer at this moment
                        self.round_stopped = True
                        self.round_stop_ms = int(time.time() * 1000)
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
                            self.server_round_base = int(sp[7])
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
                self.server_round_base = None

        # server-provided round start (epoch ms). If missing, keep as None so we can show waiting state
        try:
            if sp[7] is not None:
                try:
                    self.server_round_base = int(sp[7])
                except Exception:
                    self.server_round_base = None
            else:
                self.server_round_base = None
        except Exception:
            self.server_round_base = None


        # Sprite Groups
        self.all_sprites = AllSprites()
        self.collision_sprites = pygame.sprite.Group()

        # Create local Player and remote Player instances for every other participant.
        is_local_seeker = (self.role == 'seeker')
        self.player = Player(self.start_pos, self.all_sprites, self.collision_sprites, controlled=True, isSeeker=is_local_seeker)

        # Build remote players mapping: index -> Player instance
        self.remote_map = {}
        try:
            # If we parsed positions_list above and my_index exists, create remotes
            if positions_list and my_index is not None:
                        for idx, p in enumerate(positions_list):
                            if idx == my_index:
                                continue
                            px, py = p[0], p[1]
                            is_seeker = (idx == 0)
                            # pass name if available to Player constructor or set after
                            try:
                                pname = p[6] if len(p) >= 7 else None
                            except Exception:
                                pname = None
                            remote = Player((px, py), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=is_seeker)
                            try:
                                if pname:
                                    remote.name = pname
                            except Exception:
                                pass
                            self.remote_map[idx] = remote
            else:
                # Fallback: create a single remote player at an offset for older server behavior
                remote = Player((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=(not is_local_seeker))
                self.remote_map[1 if my_index in (0, None) else 0] = remote
        except Exception:
            # best-effort fallback
            try:
                remote = Player((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=(not is_local_seeker))
                self.remote_map[1] = remote
            except Exception:
                pass

        self.setup()
        # Game over / caught state
        self.game_over = False
        self.game_over_start = None
        self.winner_text = ""
        # Round timer base (server-provided epoch ms)
        self.round_base = self.server_round_base
        # round stopped flag and stop timestamp (epoch ms)
        self.round_stopped = False
        self.round_stop_ms = None
        # load whistle sound for hidders (best-effort)
        try:
            self.whistle_sound = pygame.mixer.Sound(join("sounds", "whistle.wav"))
        except Exception:
            self.whistle_sound = None
        # remember last second when we played the whistle so we only play once per interval
        self._last_whistle_second = None
        # debug: last whistle proximity info (volume 0.0-1.0, pan -1..1, timestamp ms)
        self._last_whistle_volume = None
        self._last_whistle_pan = 0.0
        self._last_whistle_time = 0
        # background ambience: looped beach sound
        try:
            bg_path = join("sounds", "beach_background.mp3")
            # use music module for long, looped background audio
            try:
                pygame.mixer.music.load(bg_path)
                pygame.mixer.music.set_volume(0.4)
                pygame.mixer.music.play(-1)  # loop indefinitely
            except Exception:
                # fall back to a Sound object if music fails
                try:
                    self._bg_sound = pygame.mixer.Sound(bg_path)
                    ch = pygame.mixer.find_channel()
                    if ch:
                        ch.play(self._bg_sound, loops=-1)
                        ch.set_volume(0.4)
                    else:
                        self._bg_sound.play(loops=-1)
                except Exception:
                    pass
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
        map = load_pygame(join("data", "maps", "world.tmx"))

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
    def _play_whistle_at(self, source_pos):
        """Play the loaded whistle sound as if originating from source_pos (x,y).
        Volume and stereo panning are computed based on listener (local player) position.
        """
        if not getattr(self, 'whistle_sound', None):
            return
        try:
            listener_x = int(self.player.hitbox.centerx)
            listener_y = int(self.player.hitbox.centery)
            sx, sy = int(source_pos[0]), int(source_pos[1])
            dx = sx - listener_x
            dy = sy - listener_y
            dist = math.hypot(dx, dy)

            # tuning constants
            MAX_HEAR_DIST = 2000.0  # increase audible radius so seeker hears distant whistles
            if dist > MAX_HEAR_DIST:
                # still store debug info with zero volume
                try:
                    self._last_whistle_volume = 0.0
                    self._last_whistle_pan = 0.0
                    self._last_whistle_time = pygame.time.get_ticks()
                except Exception:
                    pass
                return
            # linear distance attenuation (1.0..0.0) with gentle falloff
            vol = max(0.0, 1.0 - (dist / MAX_HEAR_DIST))

            # stereo panning based on horizontal offset; pan_norm in [-1..1]
            pan_range = max(WINDOW_WIDTH / 2.0, 200.0)
            # invert horizontal offset when computing pan so game X -> audio L/R match
            # (previously used dx/pan_range which produced inverted left/right on some setups)
            pan_norm = max(-1.0, min(1.0, -dx / pan_range))
            # store debug info for HUD (after pan_norm computed)
            try:
                self._last_whistle_volume = vol
                self._last_whistle_pan = pan_norm
                self._last_whistle_time = pygame.time.get_ticks()
            except Exception:
                pass
            left = vol * (1.0 - pan_norm) / 2.0
            right = vol * (1.0 + pan_norm) / 2.0

            # attempt to grab a free channel so we can set per-channel stereo volumes
            ch = None
            try:
                ch = pygame.mixer.find_channel()
            except Exception:
                ch = None

            if ch:
                try:
                    ch.set_volume(left, right)
                    ch.play(self.whistle_sound)
                except Exception:
                    # fallback
                    try:
                        self.whistle_sound.set_volume(vol)
                        self.whistle_sound.play()
                    except Exception:
                        pass
            else:
                try:
                    self.whistle_sound.set_volume(vol)
                    self.whistle_sound.play()
                except Exception:
                    try:
                        self.whistle_sound.play()
                    except Exception:
                        pass
        except Exception:
            # defensive: don't break the game loop on audio failures
            pass

    def _play_whistle_normal(self):
        """Play the whistle at full volume (no positional attenuation).
        Also update debug HUD fields.
        """
        if not getattr(self, 'whistle_sound', None):
            return
        try:
            ch = None
            try:
                ch = pygame.mixer.find_channel()
            except Exception:
                ch = None
            if ch:
                try:
                    ch.set_volume(1.0, 1.0)
                    ch.play(self.whistle_sound)
                except Exception:
                    try:
                        self.whistle_sound.set_volume(1.0)
                        self.whistle_sound.play()
                    except Exception:
                        pass
            else:
                try:
                    self.whistle_sound.set_volume(1.0)
                    self.whistle_sound.play()
                except Exception:
                    try:
                        self.whistle_sound.play()
                    except Exception:
                        pass
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
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_x:
                        # interact: equip object in front or unequip
                        # If game already over, ignore
                        if self.game_over:
                            continue
                        # If local player is frozen, they cannot interact
                        if getattr(self.player, '_frozen', False):
                            continue

                        # If player is seeker, attempt to catch the other player
                        if getattr(self.player, 'isSeeker', False):
                            # build a small probe rect in front of seeker (similar to get_object_in_front)
                            probe_w, probe_h = 24, 24
                            if self.player.state == 'up':
                                probe = pygame.Rect(self.player.hitbox.centerx - probe_w//2,
                                                    self.player.hitbox.top - 16 - probe_h,
                                                    probe_w, probe_h)
                            elif self.player.state == 'down':
                                probe = pygame.Rect(self.player.hitbox.centerx - probe_w//2,
                                                    self.player.hitbox.bottom + 16,
                                                    probe_w, probe_h)
                            elif self.player.state == 'left':
                                probe = pygame.Rect(self.player.hitbox.left - 16 - probe_w,
                                                    self.player.hitbox.centery - probe_h//2,
                                                    probe_w, probe_h)
                            else:  # right
                                probe = pygame.Rect(self.player.hitbox.right + 16,
                                                    self.player.hitbox.centery - probe_h//2,
                                                    probe_w, probe_h)

                            # check collisions against all remote players to find a hit target
                            try:
                                target_idx = None
                                for idx, rp in getattr(self, 'remote_map', {}).items():
                                    try:
                                        other_hitbox = rp.hitbox
                                    except Exception:
                                        other_hitbox = rp.rect
                                    if probe.colliderect(other_hitbox):
                                        target_idx = idx
                                        # mark remote frozen locally so seeker sees immediate effect
                                        try:
                                            rp._frozen = True
                                            rp.can_move = False
                                            try:
                                                rp.unequip()
                                            except Exception:
                                                pass
                                        except Exception:
                                            pass
                                        break
                                if target_idx is not None:
                                    # instruct server to broadcast the CAUGHT event targeted
                                    # at the given index by setting our outgoing equip marker
                                    try:
                                        # mark remote frozen locally so seeker sees immediate effect
                                        rp_local = self.remote_map.get(target_idx)
                                        if rp_local is not None:
                                            try:
                                                rp_local._frozen = True
                                                rp_local.can_move = False
                                                try:
                                                    rp_local.unequip()
                                                except Exception:
                                                    pass
                                            except Exception:
                                                pass

                                        self.player._caught = f"CAUGHT:{target_idx}"
                                    except Exception:
                                        pass

                                    # Send the CAUGHT event immediately so the server/state updates
                                    # and other clients learn about the freeze without waiting
                                    # for the next frame payload (helps with multi-hider scenarios).
                                    try:
                                        px, py = int(self.player.hitbox.centerx), int(self.player.hitbox.centery)
                                        payload = (px, py, self.player.state, int(self.player.frame_index), str(self.player._caught), 0)
                                        # send once immediately (non-blocking)
                                        try:
                                            self.network.send(self.make_pos(payload), wait_for_reply=False)
                                        except Exception:
                                            pass
                                        # clear transient _caught after sending
                                        try:
                                            if hasattr(self.player, '_caught'):
                                                del self.player._caught
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass

                                    # Do not declare win locally here — server will broadcast the winner
                            except Exception:
                                pass

                        # Not a seeker or didn't catch: proceed with transform/unequip for hidders
                        obj = self.player.get_object_in_front(self.collision_sprites)
                        if obj:
                            try:
                                self.player.equip(obj.image)
                                # record equipped object id to sync over network
                                if hasattr(obj, 'obj_id'):
                                    self.player._equipped_id = obj.obj_id
                            except Exception:
                                pass
                        else:
                            self.player.unequip()
                            if hasattr(self.player, '_equipped_id'):
                                del self.player._equipped_id

            # Send the player's hitbox center + animation state/frame so the
            # remote client can show correct animation. We'll send a 4-part
            # payload: x,y,state,frame
            px, py = int(self.player.hitbox.centerx), int(self.player.hitbox.centery)
            # include equipped object id if any so remote clients can show the same
            # priority: CAUGHT -> WHISTLE event -> equipped object -> None
            if hasattr(self.player, '_caught') and self.player._caught:
                # _caught may be a string like 'CAUGHT:<target_idx>' when targeting a specific player
                try:
                    equip_id = str(self.player._caught)
                except Exception:
                    equip_id = 'CAUGHT'
                equip_frame = 0
            elif getattr(self.player, '_whistle_emit', False):
                equip_id = 'WHISTLE'
                equip_frame = 0
            elif getattr(self.player, '_equipped', False) and hasattr(self.player, '_equipped_id'):
                equip_id = str(self.player._equipped_id)
                equip_frame = int(self.player.frame_index)
            else:
                equip_id = 'None'
                equip_frame = 0

            # include player name and send as JSON
            try:
                safe_name = (getattr(self.player, 'name', '') or '')
            except Exception:
                safe_name = ''
            payload_obj = {
                'x': px,
                'y': py,
                'state': self.player.state,
                'frame': int(self.player.frame_index),
                'equip': equip_id,
                'equip_frame': equip_frame,
                'name': safe_name
            }
            try:
                # non-blocking send: server broadcasts will be received by background thread
                self.network.send(json.dumps(payload_obj), wait_for_reply=False)
            except Exception:
                # fallback to old CSV if needed
                payload = (px, py, self.player.state, int(self.player.frame_index), equip_id, equip_frame, safe_name.replace(',', ''))
                try:
                    self.network.send(self.make_pos(payload), wait_for_reply=False)
                except Exception:
                    pass
            # poll for any incoming server broadcast (non-blocking)
            try:
                resp = self.network.get_latest()
            except Exception:
                resp = None
            # clear transient whistle emit so it is only broadcast once
            try:
                if hasattr(self.player, '_whistle_emit'):
                    del self.player._whistle_emit
            except Exception:
                pass
            # clear transient CAUGHT marker so we don't repeatedly broadcast it
            try:
                if hasattr(self.player, '_caught'):
                    del self.player._caught
            except Exception:
                pass
            if resp:
                # Server now sends all players' positions joined by '|' and metadata separated by '::'.
                # Parse accordingly and update every remote player we know about.
                def _parse_resp(resp):
                    # returns (positions_list, round_start_or_None, winner_or_None)
                    if resp is None:
                        return ([], None, None)
                    # if server sent JSON, parse it directly
                    try:
                        j = json.loads(resp)
                        if isinstance(j, dict) and 'positions' in j:
                            positions = []
                            for p in j.get('positions', []):
                                try:
                                    x = int(p.get('x', 0))
                                except Exception:
                                    x = 0
                                try:
                                    y = int(p.get('y', 0))
                                except Exception:
                                    y = 0
                                state = p.get('state', 'down')
                                try:
                                    frame = int(p.get('frame', 0))
                                except Exception:
                                    frame = 0
                                equip = p.get('equip', 'None')
                                try:
                                    equip_frame = int(p.get('equip_frame', 0))
                                except Exception:
                                    equip_frame = 0
                                name = p.get('name')
                                # sanitize
                                if isinstance(name, str):
                                    try:
                                        name = name.split('::')[0].strip()
                                    except Exception:
                                        name = name.strip()
                                positions.append((x, y, state, frame, equip, equip_frame, name))
                            round_start = j.get('round_start')
                            winner = j.get('winner')
                            return (positions, round_start, winner)
                    except Exception:
                        pass
                    # split off trailing metadata safely using rsplit so names
                    # don't accidentally absorb the trailing '::role::round::winner'
                    try:
                        parts = resp.rsplit('::', 3)
                    except Exception:
                        parts = [resp]
                    round_start = None
                    winner = None
                    if len(parts) == 4:
                        all_positions_str, role_s, round_s, winner_s = parts
                        try:
                            round_start = int(round_s)
                        except Exception:
                            round_start = None
                        winner = winner_s if winner_s != 'None' else None
                    elif len(parts) == 3:
                        all_positions_str, round_s, winner_s = parts
                        try:
                            round_start = int(round_s)
                        except Exception:
                            round_start = None
                        winner = winner_s if winner_s != 'None' else None
                    else:
                        all_positions_str = parts[0]

                    positions = []
                    try:
                        if all_positions_str:
                            entries = all_positions_str.split('|')
                            for e in entries:
                                if not e:
                                    continue
                                parts_c = e.split(',')
                                try:
                                    x = int(parts_c[0]); y = int(parts_c[1])
                                except Exception:
                                    continue
                                state = parts_c[2] if len(parts_c) >= 3 else 'down'
                                try:
                                    frame = int(parts_c[3]) if len(parts_c) >= 4 else 0
                                except Exception:
                                    frame = 0
                                equip_id = parts_c[4] if len(parts_c) >= 5 else 'None'
                                try:
                                    equip_frame = int(parts_c[5]) if len(parts_c) >= 6 else 0
                                except Exception:
                                    equip_frame = 0
                                name = parts_c[6] if len(parts_c) >= 7 else None
                                # sanitize
                                if isinstance(name, str):
                                    try:
                                        name = name.split('::')[0].strip()
                                    except Exception:
                                        name = name.strip()
                                positions.append((x, y, state, frame, equip_id, equip_frame, name))
                    except Exception:
                        positions = []

                    return (positions, round_start, winner)

                positions_list, round_start, winner = _parse_resp(resp)
                # update server-provided round start if present so timers stay synced
                try:
                    if round_start is not None:
                        self.server_round_base = int(round_start)
                        self.round_base = self.server_round_base
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
                                if widx == self.my_index:
                                    self.winner_text = "You win!"
                                else:
                                    # assume seeker wins otherwise
                                    self.winner_text = "Seeker wins!"
                                self.round_stopped = True
                                self.round_stop_ms = int(time.time() * 1000)
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
                        # support both 6-field and 7-field tuples
                        try:
                            x, y, state, frame, equip_id, equip_frame, pname = p
                        except Exception:
                            try:
                                x, y, state, frame, equip_id, equip_frame = p
                                pname = None
                            except Exception:
                                continue
                        # If this entry is the local player, update nothing (local authoritative)
                        # else apply to corresponding remote player
                        if hasattr(self, 'server_round_base') and self.server_round_base is None:
                            pass
                        # Update remote players
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
                                    if target_idx == self.my_index:
                                        if not getattr(self.player, 'isSeeker', False):
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
                    except Exception:
                        pass
                except Exception:
                    pass

            # update round timer and movement permission (use epoch ms from server)
            now_ms = int(time.time() * 1000)
            if self.round_base is None:
                timer_seconds = None
            else:
                if getattr(self, 'round_stopped', False) and self.round_stop_ms is not None:
                    timer_seconds = (self.round_stop_ms - self.round_base) / 1000.0
                else:
                    timer_seconds = (now_ms - self.round_base) / 1000.0
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
                if (not getattr(self.player, 'isSeeker', False)) and timer_seconds is not None and timer_seconds > 0 and self.whistle_sound:
                    ts_sec = int(timer_seconds)
                    if ts_sec % 25 == 0 and ts_sec != self._last_whistle_second:
                        # mark for network broadcast (next outgoing payload will carry WHISTLE)
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
            self.all_sprites.draw(self.player.rect.center)
            # Draw player names above each character (remote and local)
            try:
                # remote players
                offset = getattr(self.all_sprites, 'offset', pygame.math.Vector2(0,0))
                for idx, rp in (getattr(self, 'remote_map', {})).items():
                    try:
                        name = getattr(rp, 'name', None)
                        if name:
                            nm_s = self.font.render(str(name), True, (255, 255, 255))
                            x = rp.rect.centerx + offset.x - nm_s.get_width()//2
                            y = rp.rect.top + offset.y - nm_s.get_height() - 6
                            # draw subtle shadow for readability
                            shadow = self.font.render(str(name), True, (0,0,0))
                            self.display_surface.blit(shadow, (x+1, y+1))
                            self.display_surface.blit(nm_s, (x, y))
                    except Exception:
                        pass
                # local player
                try:
                    lname = getattr(self.player, 'name', None)
                    if lname:
                        ln_s = self.font.render(str(lname), True, (200, 220, 255))
                        lx = self.player.rect.centerx + offset.x - ln_s.get_width()//2
                        ly = self.player.rect.top + offset.y - ln_s.get_height() - 6
                        shadow = self.font.render(str(lname), True, (0,0,0))
                        self.display_surface.blit(shadow, (lx+1, ly+1))
                        self.display_surface.blit(ln_s, (lx, ly))
                except Exception:
                    pass
            except Exception:
                pass
            # HUD: show role and hint for hidders
            try:
                role_text = "Role: Seeker" if getattr(self.player, 'isSeeker', False) else "Role: Hidder"
                role_surf = self.font.render(role_text, True, (255, 255, 255))
                # draw semi-opaque background for readability
                bg_rect = role_surf.get_rect(topleft=(8, 8)).inflate(8, 8)
                s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                s.fill((0, 0, 0, 120))
                self.display_surface.blit(s, bg_rect.topleft)
                self.display_surface.blit(role_surf, (12, 12))

                # hint for hidders
                hint_y = 12 + role_surf.get_height() + 6
                if not getattr(self.player, 'isSeeker', False):
                    hint_surf = self.font.render("Press X to transform", True, (200, 200, 0))
                    self.display_surface.blit(hint_surf, (12, hint_y))
                    hint_y += hint_surf.get_height() + 6

                # show seeker progress: number of hidders caught out of total
                try:
                    if getattr(self.player, 'isSeeker', False):
                        frozen_known = 0
                        total_hidders = max(0, NUM_PLAYERS - 1)
                        for idx, rp in (getattr(self, 'remote_map', {})).items():
                            if not getattr(rp, 'isSeeker', False) and getattr(rp, '_frozen', False):
                                frozen_known += 1
                        caught_text = f"Caught: {frozen_known}/{total_hidders}"
                        caught_surf = self.font.render(caught_text, True, (200, 200, 0))
                        self.display_surface.blit(caught_surf, (12, hint_y))
                        hint_y += caught_surf.get_height() + 6
                except Exception:
                    pass

                # (timer is rendered separately at the top-center)
            except Exception:
                pass

            # render round timer at top-center with 50% opaque black background and thick white text
            try:
                # If timer_seconds is None, the server hasn't started the round yet
                if timer_seconds is None:
                    text = "Waiting for player..."
                else:
                    ts = timer_seconds
                    sign = '-' if ts < 0 else ''
                    secs = int(abs(ts))
                    mins = secs // 60
                    secs_rem = secs % 60
                    timer_text = f"{sign}{mins:02d}:{secs_rem:02d}"
                    text = f"{timer_text}"

                # render large text surface
                txt_surf = self.large_font.render(text, True, (255, 255, 255))
                w, h = txt_surf.get_size()
                padding_x, padding_y = 16, 8

                panel_w = w + padding_x * 2
                panel_h = h + padding_y * 2
                panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
                # 50% opacity black background
                panel_surf.fill((0, 0, 0, 128))

                # make thick text by blitting the text multiple times with slight offsets
                text_surf = self.large_font.render(text, True, (255, 255, 255))
                w, h = text_surf.get_size()
                thick_surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
                offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]
                for ox, oy in offsets:
                    thick_surf.blit(self.large_font.render(text, True, (255, 255, 255)), (ox + 2, oy + 2))

                # center thick_surf inside panel
                panel_surf.blit(thick_surf, (padding_x - 2, padding_y - 2))

                # blit panel at top center
                x = (WINDOW_WIDTH - panel_w) // 2
                y = 8
                self.display_surface.blit(panel_surf, (x, y))

                # Debug: if a whistle was recently played, show proximity volume in bottom-left
                try:
                    now_ms = pygame.time.get_ticks()
                    if getattr(self, '_last_whistle_time', 0) and now_ms - self._last_whistle_time <= 3000 and self._last_whistle_volume is not None:
                        vol = max(0.0, min(1.0, float(self._last_whistle_volume)))
                        pan = getattr(self, '_last_whistle_pan', 0.0)
                        percent = int(vol * 100)
                        txt = f"Whistle vol: {percent}%"
                        txt_surf2 = self.font.render(txt, True, (255, 255, 255))
                        padding = 6
                        bg_rect = txt_surf2.get_rect(bottomleft=(12, WINDOW_HEIGHT - 12)).inflate(padding * 2, padding * 2)
                        s2 = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                        s2.fill((0, 0, 0, 160))
                        self.display_surface.blit(s2, bg_rect.topleft)
                        self.display_surface.blit(txt_surf2, (bg_rect.left + padding, bg_rect.top + padding))
                        # draw a small volume bar below the text
                        bar_w = 120
                        bar_h = 10
                        bar_x = bg_rect.left + padding
                        bar_y = bg_rect.top + padding + txt_surf2.get_height() + 6
                        # border
                        pygame.draw.rect(self.display_surface, (200, 200, 200), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2), 1)
                        fill_w = int(vol * bar_w)
                        pygame.draw.rect(self.display_surface, (100, 220, 100), (bar_x, bar_y, fill_w, bar_h))
                except Exception:
                    pass
            except Exception:
                pass

            # If local player is frozen (caught), render a freeze overlay
            if getattr(self.player, '_frozen', False) and not self.game_over:
                try:
                    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 120))
                    self.display_surface.blit(overlay, (0, 0))
                    # show a clearer caught message to the hidder
                    freeze_surf = self.large_font.render("You are caught", True, (255, 255, 255))
                    freeze_rect = freeze_surf.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2))
                    self.display_surface.blit(freeze_surf, freeze_rect)
                except Exception:
                    pass

            # If game over, render overlay and exit after 10 seconds
            if self.game_over:
                try:
                    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 160))
                    self.display_surface.blit(overlay, (0, 0))
                    win_surf = self.font.render(self.winner_text, True, (255, 255, 255))
                    win_rect = win_surf.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2))
                    self.display_surface.blit(win_surf, win_rect)
                    # after 10 seconds, return to menu
                    if self.game_over_start and pygame.time.get_ticks() - self.game_over_start >= 10000:
                        # End the current game and return to menu (caller will handle quitting)
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
                    # Use same Python executable to avoid PATH issues
                    host_proc = subprocess.Popen([sys.executable, os.path.join(cwd, 'server.py'), '--auto-ip', '--port', str(chosen_port), '--num-players', str(chosen_players)], cwd=cwd)
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