import pygame
from network import Network
from settings import *
from player import Player
from sprites import *
from pytmx.util_pygame import load_pygame
from os.path import join
from groups import AllSprites


class Game:
    def __init__(self):
        pygame.init()
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Dhaagudu Moothalu")
        self.clock = pygame.time.Clock()
        self.network = Network(server, port)
        self.running = True
        self.start_pos = self.read_pos(self.network.getPos())


        # Sprite Groups
        self.all_sprites = AllSprites()
        self.collision_sprites = pygame.sprite.Group()

        self.player = Player(self.start_pos, self.all_sprites, self.collision_sprites)
        # player2 is the remote player — don't let it read local keyboard input
        self.player2 = Player((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False)

        self.setup()

    def read_pos(self, pos):
        x, y = map(int, pos.split(","))
        return (x, y)
    
    def make_pos(self, tup):
        return str(tup[0]) + "," + str(tup[1])

    def setup(self):
        map = load_pygame(join("data", "maps", "world.tmx"))

        # Ground
        for x, y, image in map.get_layer_by_name("Ground").tiles():
            Sprite((x * SPRITE_SIZE, y * SPRITE_SIZE),
                            image,
                            self.all_sprites)

        # Trees
        for obj in map.get_layer_by_name("Objects"):
            CollisionSprite((obj.x, obj.y),
                            obj.image,
                            (self.all_sprites, self.collision_sprites))
            
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

    def run(self):
        while self.running:

            dt = self.clock.tick(FPS) / 1000  # Delta time in seconds.

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            # Send the player's hitbox center so server and other clients use the
            # same coordinate anchor (center) — previously rect.x/rect.y were
            # top-left which caused inconsistent interpretation on the remote
            # side and made positions appear out of sync.
            px, py = int(self.player.hitbox.centerx), int(self.player.hitbox.centery)
            player2_pos = self.read_pos(self.network.send(self.make_pos((px, py))))
            # update remote player's position via its hitbox so collisions/display stay consistent
            try:
                self.player2.hitbox.center = player2_pos
                self.player2.rect.center = self.player2.hitbox.center
            except Exception:
                # fall back to rect assignment if hitbox isn't available for some reason
                self.player2.rect.x = player2_pos[0]
                self.player2.rect.y = player2_pos[1]

            # update
            self.all_sprites.update(dt)

            # draw (render the world once, centered on the local player)
            self.display_surface.fill((30, 30, 30))
            self.all_sprites.draw(self.player.rect.center)
            pygame.display.update()
            self.clock.tick(FPS)

        pygame.quit()



if __name__ == "__main__":
    game = Game()
    game.run()