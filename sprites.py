from settings import *
import pygame

class Sprite(pygame.sprite.Sprite):
    def __init__(self, pos, surface, groups):
        super().__init__(groups)
        self.image =surface
        self.rect = self.image.get_rect(topleft=pos)
        self.ground = True

class CollisionSprite(pygame.sprite.Sprite):
    def __init__(self, pos, surface, groups):
        super().__init__(groups)
        self.image = surface
        # use get_rect; set topleft so positions coming from Tiled (obj.x,obj.y)
        # align correctly. Also mark these sprites as non-ground objects by
        # default; specific interactive objects can be flagged after creation.
        self.rect = self.image.get_rect(topleft=pos)
        self.ground = False
        # whether this sprite is an interactive object (e.g., a pickup)
        self.interactive = False