from settings import *
import pygame
from os.path import join


class Player(pygame.sprite.Sprite):
    def __init__(self, pos, groups, collision_sprites):
        super().__init__(groups)
        
        # Load image and set rect
        self.image = pygame.image.load(join("images", "player", "down", "0.png")).convert_alpha()
        self.rect = self.image.get_rect(center=pos)  # ✅ use get_rect (not get_frect for compatibility)
        
        # Create hitbox (smaller for better collision feel)
        self.hitbox = self.rect.inflate(-60, -60)

        # Movement setup
        self.direction = pygame.math.Vector2()
        self.speed = 500
        self.collision_sprites = collision_sprites

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

    def update(self, dt):
        """Update player movement"""
        self.input()
        self.move(dt)