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
        # Font for HUD
        try:
            pygame.font.init()
        except Exception:
            pass
        self.font = pygame.font.SysFont('arial', 20)
        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Dhaagudu Moothalu")
        self.clock = pygame.time.Clock()
        self.network = Network(server, port)
        self.running = True
        # read_pos now returns (x, y, state, frame). For initial spawn we only
        # need the x,y center coordinates for Player creation.
        sp = self.read_pos(self.network.getPos())
        self.start_pos = (sp[0], sp[1])
        # optional role returned by server: 'seeker' or 'hidder'
        try:
            self.role = sp[6]
        except Exception:
            self.role = None


        # Sprite Groups
        self.all_sprites = AllSprites()
        self.collision_sprites = pygame.sprite.Group()

        # pass isSeeker to Player so each client knows their role and which skin to use
        is_local_seeker = (self.role == 'seeker')
        self.player = Player(self.start_pos, self.all_sprites, self.collision_sprites, controlled=True, isSeeker=is_local_seeker)
        # player2 is the remote player — don't let it read local keyboard input
        # remote player's role is the opposite of local player's role
        self.player2 = Player((self.start_pos[0] + 100, self.start_pos[1]), self.all_sprites, self.collision_sprites, controlled=False, isSeeker=(not is_local_seeker))

        self.setup()

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

        return (x, y, state, frame, equip_id, equip_frame, role)
    
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

    def run(self):
        while self.running:

            dt = self.clock.tick(FPS) / 1000  # Delta time in seconds.

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_x:
                        # interact: equip object in front or unequip
                        # Seekers are not allowed to transform/equip objects
                        if getattr(self.player, 'isSeeker', False):
                            # ignore equip/unequip attempts for seekers
                            continue

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
            if getattr(self.player, '_equipped', False) and hasattr(self.player, '_equipped_id'):
                equip_id = str(self.player._equipped_id)
                equip_frame = int(self.player.frame_index)
            else:
                equip_id = 'None'
                equip_frame = 0

            payload = (px, py, self.player.state, int(self.player.frame_index), equip_id, equip_frame)
            resp = self.network.send(self.make_pos(payload))
            if resp:
                x, y, state, frame, equip_id, equip_frame, _role = self.read_pos(resp)
                # apply remote state (position + animation)
                try:
                    self.player2.set_remote_state((x, y), state, frame, equip_frame)
                except Exception:
                    # fallback: set rect directly
                    self.player2.rect.center = (x, y)

                # apply equip/unequip on remote player based on equip_id
                try:
                    # Only apply equip on remote if that remote is allowed to equip
                    if not getattr(self.player2, 'isSeeker', False):
                        if equip_id != 'None' and equip_id in self.object_map:
                            obj_sprite = self.object_map[equip_id]
                            self.player2.equip(obj_sprite.image)
                            self.player2._equipped_id = equip_id
                        else:
                            # remote unequip
                            self.player2.unequip()
                            if hasattr(self.player2, '_equipped_id'):
                                del self.player2._equipped_id
                except Exception:
                    pass

            # update
            self.all_sprites.update(dt)

            # draw (render the world once, centered on the local player)
            self.display_surface.fill((30, 30, 30))
            self.all_sprites.draw(self.player.rect.center)
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
                if not getattr(self.player, 'isSeeker', False):
                    hint_surf = self.font.render("Press X to transform", True, (200, 200, 0))
                    self.display_surface.blit(hint_surf, (12, 12 + role_surf.get_height() + 6))
            except Exception:
                pass
            pygame.display.update()
            self.clock.tick(FPS)

        pygame.quit()



if __name__ == "__main__":
    game = Game()
    game.run()