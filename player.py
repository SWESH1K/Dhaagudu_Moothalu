from settings import *
import pygame
import os
from os import walk
from util.resource_path import resource_path


class Player(pygame.sprite.Sprite):
    def __init__(self, pos, groups, collision_sprites, controlled=True, isSeeker=False, name=None):
        super().__init__(groups)
        # Role flag: seeker cannot transform into objects
        self.isSeeker = bool(isSeeker)

        # player display name (used to track players when joining/hosting)
        try:
            self.name = str(name) if name is not None else 'Player'
        except Exception:
            self.name = 'Player'

        # determine which skin folder to use. Default: seekers use 'player2',
        # hiders use 'player' unless explicitly overridden via isSeeker
        self.skin_folder = 'player2' if self.isSeeker else 'player'

        self.load_images()

        # Load image and set rect
        self.state, self.frame_index = 'down', 0
        # initial image uses chosen skin folder
        self.image = pygame.image.load(resource_path(os.path.join("images", self.skin_folder, "down", "0.png"))).convert_alpha()
        self.rect = self.image.get_rect(center=pos)  # ✅ use get_rect (not get_frect for compatibility)
        
        # Create hitbox (smaller for better collision feel)
        self.hitbox = self.rect.inflate(-60, -60)

        # Movement setup
        self.direction = pygame.math.Vector2()
        self.speed = 500
        self.collision_sprites = collision_sprites
        # Whether this player is controlled locally (reads keyboard). Remote players
        # should be created with controlled=False so they don't respond to local input.
        self.controlled = controlled
        # Whether this player is allowed to move (can be controlled externally by Game)
        self.can_move = True
        # Whether this player is frozen (caught by seeker). Frozen players cannot move
        # or transform and should display a freeze message on their client.
        self._frozen = False
        # walking sound (loop while moving) - best-effort load
        try:
            self._walk_sound = pygame.mixer.Sound(resource_path(os.path.join("sounds", "walking_sound.mp3")))
        except Exception:
            self._walk_sound = None
        # channel used to play walking sound (if any)
        self._walk_channel = None
        # shape shift sound (play once on equip/unequip)
        try:
            self._shape_shift_sound = pygame.mixer.Sound(resource_path(os.path.join("sounds", "shape_shift.mp3")))
        except Exception:
            self._shape_shift_sound = None

    def load_images(self):
        self.frames = {
            'up': [],
            'down': [],
            'left': [],
            'right': []
        }
        for state in self.frames.keys():
            # walk through the chosen skin folder for this player
            for folder_path, subfolder, filenames in walk(resource_path(os.path.join("images", self.skin_folder, state))):
                if filenames:
                    for filename in sorted(filenames, key=lambda x: int(x.split('.')[0])):
                        full_path = os.path.join(folder_path, filename)
                        surf = pygame.image.load(full_path).convert_alpha()
                        self.frames[state].append(surf)

    def input(self):
        """Handle player input"""
        keys = pygame.key.get_pressed()

        # Movement vector (1 for pressed, 0 for not pressed)
        self.direction.x = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        self.direction.y = keys[pygame.K_DOWN] - keys[pygame.K_UP]

        # Normalize vector only if moving
        if self.direction.magnitude() > 0:
            self.direction = self.direction.normalize()

    def get_object_in_front(self, collision_sprites, distance=16):
        """Return the first interactive sprite in front of the player within distance.

        Uses the player's current facing (`self.state`) to test a small rect in
        front of the hitbox.
        """
        # Build a small probe rect in front of the player based on facing
        probe_w, probe_h = 16, 16
        if self.state == 'up':
            probe = pygame.Rect(self.hitbox.centerx - probe_w//2,
                                self.hitbox.top - distance - probe_h,
                                probe_w, probe_h)
        elif self.state == 'down':
            probe = pygame.Rect(self.hitbox.centerx - probe_w//2,
                                self.hitbox.bottom + distance,
                                probe_w, probe_h)
        elif self.state == 'left':
            probe = pygame.Rect(self.hitbox.left - distance - probe_w,
                                self.hitbox.centery - probe_h//2,
                                probe_w, probe_h)
        else:  # right
            probe = pygame.Rect(self.hitbox.right + distance,
                                self.hitbox.centery - probe_h//2,
                                probe_w, probe_h)

        for sprite in collision_sprites:
            # only consider sprites explicitly marked interactive
            if getattr(sprite, 'interactive', False):
                if probe.colliderect(sprite.rect):
                    return sprite
        return None

    def move(self, dt):
        """Move player using delta time"""
        # Horizontal movement
        self.hitbox.x += self.direction.x * self.speed * dt
        self.collision("horizontal")

        # Vertical movement
        self.hitbox.y += self.direction.y * self.speed * dt
        self.collision("vertical")

        # Sync main rect with hitbox
        self.rect.center = self.hitbox.center

    def collision(self, direction):
        """Handle collision with environment"""
        for sprite in self.collision_sprites:
            if self.hitbox.colliderect(sprite.rect):  # ✅ missing collision check!
                if direction == "horizontal":
                    if self.direction.x > 0:  # moving right
                        self.hitbox.right = sprite.rect.left
                    elif self.direction.x < 0:  # moving left
                        self.hitbox.left = sprite.rect.right
                elif direction == "vertical":
                    if self.direction.y > 0:  # moving down
                        self.hitbox.bottom = sprite.rect.top
                    elif self.direction.y < 0:  # moving up
                        self.hitbox.top = sprite.rect.bottom

    def animate(self, dt):
        if self.direction.x != 0:
            self.state = 'right' if self.direction.x > 0 else 'left'
        elif self.direction.y != 0:
            self.state = 'down' if self.direction.y > 0 else 'up'

        # Animate only when moving
        if self.direction.magnitude() > 0:
            self.frame_index += 5 * dt  # animation speed
            if self.frame_index >= len(self.frames[self.state]):
                self.frame_index = 0  # loop animation
        else:
            self.frame_index = 0  # freeze on first frame when idle

        # If equipped with an object, show that image instead of player's
        # Choose which image to display. If the player is equipped with an
        # object, use the object's surface at its native size and adjust rect
        # / hitbox when equipping (handled in equip()). Otherwise use the
        # animated player frame.
        base_frame = self.frames[self.state][int(self.frame_index) % len(self.frames[self.state])]
        if getattr(self, '_equipped', False) and getattr(self, 'equipped_surface', None):
            # equipped image is set during equip(); keep it and ensure center
            try:
                self.rect.center = self.hitbox.center
            except Exception:
                pass
        else:
            self.image = base_frame

        

    def update(self, dt):
        """Update player movement"""
        # Only process input/movement/animation for the locally controlled player.
        # If frozen, the player cannot move or change animation.
        if self.controlled and getattr(self, 'can_move', True) and not getattr(self, '_frozen', False):
            self.input()
            self.move(dt)
            self.animate(dt)
            # play/stop walking ambient when moving
            try:
                moving = self.direction.magnitude() > 0
                if getattr(self, '_walk_sound', None):
                    if moving:
                        # if already playing on a reserved channel, ensure it's busy
                        ch = getattr(self, '_walk_channel', None)
                        is_busy = False
                        try:
                            is_busy = bool(ch and ch.get_busy())
                        except Exception:
                            is_busy = False

                        if not is_busy:
                            # try to find a free channel and play looped
                            try:
                                newch = pygame.mixer.find_channel()
                            except Exception:
                                newch = None
                            try:
                                if newch:
                                    newch.play(self._walk_sound, loops=-1)
                                    try:
                                        newch.set_volume(0.6 * float(VOLUME))
                                    except Exception:
                                        newch.set_volume(0.6)
                                    self._walk_channel = newch
                                else:
                                    # fallback to Sound.play (may use shared channels)
                                    self._walk_sound.play(loops=-1)
                            except Exception:
                                pass
                    else:
                        # stop any walking playback when idle
                        try:
                            ch = getattr(self, '_walk_channel', None)
                            if ch:
                                ch.stop()
                                self._walk_channel = None
                            else:
                                # stop global sound if it was played that way
                                try:
                                    self._walk_sound.stop()
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
        else:
            # For remote players we expect position to be set from network.
            # Ensure rect stays in sync with hitbox if network updates the hitbox.
            try:
                self.rect.center = self.hitbox.center
            except Exception:
                # Fall back to rect center if hitbox not set
                pass

    def equip(self, surface):
        """Equip an object: change the player's visible skin and hitbox to the
        object's native size so the player appears the same size as the
        object.
        """
        # Seekers are not allowed to transform/equip objects
        if getattr(self, 'isSeeker', False):
            return
        # If already equipped, unequip first
        if getattr(self, '_equipped', False):
            self.unequip()

        # Save current rect/hitbox/image/speed to restore on unequip
        self._saved_rect = self.rect.copy()
        self._saved_hitbox = self.hitbox.copy()
        self._saved_image = self.image
        self._saved_speed = self.speed

        # Assign equipped surface and update rect/hitbox to object's size
        self.equipped_surface = surface
        self._equipped = True

        try:
            # Use object's native size; center it on the player's previous center
            self.image = self.equipped_surface
            self.rect = self.image.get_rect(center=self._saved_rect.center)
            # make hitbox a bit smaller than the visual rect
            pad_w = max(2, int(self.rect.width * 0.2))
            pad_h = max(2, int(self.rect.height * 0.2))
            self.hitbox = self.rect.inflate(-pad_w, -pad_h)
        except Exception:
            # fallback: don't change size if something goes wrong
            self.rect = self._saved_rect.copy()
            self.hitbox = self._saved_hitbox.copy()

        # play shape shift sound once for locally controlled players
        try:
            if getattr(self, 'controlled', False) and getattr(self, '_shape_shift_sound', None):
                # play once (no loops)
                try:
                    ch = pygame.mixer.find_channel()
                except Exception:
                    ch = None
                try:
                    if ch:
                        ch.play(self._shape_shift_sound)
                    else:
                        self._shape_shift_sound.play()
                except Exception:
                    pass
        except Exception:
            pass

        # Reduce player's movement speed to 75% of original while equipped
        try:
            self.speed = float(self._saved_speed) * 0.75
        except Exception:
            # if speed not numeric for some reason, keep it unchanged
            pass

    def unequip(self):
        """Remove equipped object and revert to normal player skin."""
        if getattr(self, '_equipped', False):
            # preserve current center so we don't teleport back to equip spot
            try:
                current_center = self.rect.center
            except Exception:
                current_center = None

            # restore saved visuals but keep current position
            try:
                self.rect = self._saved_rect.copy()
                if current_center:
                    self.rect.center = current_center

                self.hitbox = self._saved_hitbox.copy()
                if current_center:
                    self.hitbox.center = current_center

                self.image = self._saved_image
            except Exception:
                pass

            # clear equipped flags
            if hasattr(self, 'equipped_surface'):
                del self.equipped_surface
            if hasattr(self, '_saved_rect'):
                del self._saved_rect
            if hasattr(self, '_saved_hitbox'):
                del self._saved_hitbox

            # restore speed if we saved it
            try:
                if hasattr(self, '_saved_speed'):
                    self.speed = self._saved_speed
                    del self._saved_speed
            except Exception:
                pass

            if hasattr(self, '_saved_image'):
                del self._saved_image
            self._equipped = False

            # play shape shift sound once for locally controlled players
            try:
                if getattr(self, 'controlled', False) and getattr(self, '_shape_shift_sound', None):
                    try:
                        ch = pygame.mixer.find_channel()
                    except Exception:
                        ch = None
                    try:
                        if ch:
                            ch.play(self._shape_shift_sound)
                        else:
                            self._shape_shift_sound.play()
                    except Exception:
                        pass
            except Exception:
                pass

    def set_remote_state(self, pos, state, frame_index, equip_frame=0):
        """Apply remote player's position and animation state.

        pos: (x, y) tuple (center coordinates)
        state: animation state string ('up','down','left','right')
        frame_index: integer frame index (will be clamped)
        """
        # Update position (prefer hitbox if available)
        try:
            self.hitbox.center = (int(pos[0]), int(pos[1]))
            self.rect.center = self.hitbox.center
        except Exception:
            self.rect.center = (int(pos[0]), int(pos[1]))

        # Update animation state/frame
        if state in self.frames:
            self.state = state

        try:
            fi = int(frame_index)
        except Exception:
            fi = 0

        # If the remote player is equipped and an equip_frame was provided,
        # prefer that as the index for the equipped-asset animation.
        use_frame = fi
        try:
            ef = int(equip_frame)
            use_frame = ef if ef is not None else fi
        except Exception:
            pass

        # Clamp frame index and set image immediately so remote animation is visible
        frames_list = self.frames.get(self.state)
        if frames_list:
            self.frame_index = use_frame % len(frames_list)
            self.image = frames_list[int(self.frame_index) % len(frames_list)]