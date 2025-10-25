from settings import *
import pygame
from os.path import join
from os import walk


class Player(pygame.sprite.Sprite):
    def __init__(self, pos, groups, collision_sprites, controlled=True):
        super().__init__(groups)
        self.load_images()
        
        # Load image and set rect
        self.state, self.frame_index = 'down', 0
        self.image = pygame.image.load(join("images", "player", "down", "0.png")).convert_alpha()
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

    def load_images(self):
        self.frames = {
            'up': [],
            'down': [],
            'left': [],
            'right': []
        }
        for state in self.frames.keys():
            for folder_path, subfolder, filenames in walk(join("images", "player", state)):
                if filenames:
                    for filename in sorted(filenames, key=lambda x: int(x.split('.')[0])):
                            full_path = join(folder_path, filename)
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

        self.image = self.frames[self.state][int(self.frame_index) % len(self.frames[self.state])]

        

    def update(self, dt):
        """Update player movement"""
        # Only process input/movement/animation for the locally controlled player.
        if self.controlled:
            self.input()
            self.move(dt)
            self.animate(dt)
        else:
            # For remote players we expect position to be set from network.
            # Ensure rect stays in sync with hitbox if network updates the hitbox.
            try:
                self.rect.center = self.hitbox.center
            except Exception:
                # Fall back to rect center if hitbox not set
                pass