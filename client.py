import pygame
from network import Network
from settings import *
from player import Player

pygame.init()


class Game:
    def __init__(self):
        pygame.init()
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Dhaagudu Moothalu")
        self.clock = pygame.time.Clock()
        # self.network = Network(server, port)
        self.running = True

        # Sprite Groups
        self.all_sprites = pygame.sprite.Group()

        # Player
        self.player = Player((100, 100), self.all_sprites)

    def run(self):
        while self.running:

            dt = self.clock.tick(FPS) / 1000  # Delta time in seconds.

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            # update
            self.all_sprites.update(dt)

            # draw
            self.display_surface.fill((30, 30, 30))
            self.all_sprites.draw(self.display_surface)
            pygame.display.update()
            self.clock.tick(FPS)

        pygame.quit()



if __name__ == "__main__":
    game = Game()
    game.run()