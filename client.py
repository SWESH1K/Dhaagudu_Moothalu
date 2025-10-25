import pygame
from network import Network
from settings import *

pygame.init()

# Create a window
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Dhaagudu Moothalu")

class Player:
    def __init__(self, x, y, width, height, color):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)

    def move(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.x -= 5
        if keys[pygame.K_RIGHT]:
            self.x += 5
        if keys[pygame.K_UP]:
            self.y -= 5
        if keys[pygame.K_DOWN]:
            self.y += 5

        self.update()

    def update(self):
        self.rect.topleft = (self.x, self.y)


def redraw_window(screen, player=None, player2=None):

    # Fill the screen with a color
    screen.fill((255, 255, 255))

    # Draw the player
    if player:
        player.draw(screen)

    if player2:
        player2.draw(screen)

    # Update the display
    pygame.display.update()

def read_pos(data):
    data = data.split(",")
    return int(data[0]), int(data[1])

def make_pos(tup):
    return str(tup[0]) + "," + str(tup[1])

def main():
    # Settings
    FPS = 60

    # Main loop
    net = Network(server, port)
    print(net.getPos())
    startPos = read_pos(net.getPos())
    print("StartPos=", startPos)

    player = Player(startPos[0], startPos[1], 50, 50, (0, 128, 255))
    player2 = Player(0, 0, 50, 50, (255, 0, 0))
    clock = pygame.time.Clock()

    running = True
    while running:
        clock.tick(FPS)

        player2_pos = read_pos(net.send(make_pos((player.x, player.y))))
        player2.x = player2_pos[0]
        player2.y = player2_pos[1]
        player2.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        player.move()
        redraw_window(screen, player, player2)

    pygame.quit()

if __name__ == "__main__":
    main()