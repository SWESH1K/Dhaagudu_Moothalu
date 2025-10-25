import pygame
import sys
from settings import WINDOW_WIDTH, WINDOW_HEIGHT, SPRITE_SIZE
from pytmx.util_pygame import load_pygame
from os.path import join
import pygame as _pygame
import re
import shutil
import importlib
import os
import settings as settings_mod


class Menu:
    def __init__(self):
        # initialize pygame display/font if not already
        try:
            pygame.init()
        except Exception:
            pass
        try:
            pygame.font.init()
        except Exception:
            pass

        self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Dhaagudu Moothalu - Menu")
        try:
            self.title_font = pygame.font.SysFont('couriernew', 64)
            self.font = pygame.font.SysFont('couriernew', 24)
        except Exception:
            self.title_font = pygame.font.SysFont(None, 64)
            self.font = pygame.font.SysFont(None, 24)

        self.clock = pygame.time.Clock()

        # prepare blurred map background
        try:
            self._prepare_background()
        except Exception:
            self.bg_surface = None

        # pre-render an attractive, bold title surface (outline + shadow)
        try:
            self.title_surf = self._create_title_surface("Dhaagudu Moothalu")
            # scale the title surface to be 50% of window width while preserving aspect
            try:
                target_w = int(WINDOW_WIDTH * 0.5)
                tw = self.title_surf.get_width()
                th = self.title_surf.get_height()
                if tw > 0 and tw != target_w:
                    scale_factor = target_w / float(tw)
                    new_h = max(1, int(th * scale_factor))
                    self.title_surf = pygame.transform.smoothscale(self.title_surf, (target_w, new_h))
            except Exception:
                pass
            self.title_rect = self.title_surf.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//4))
        except Exception:
            self.title_surf = None
            self.title_rect = None

        # button geometry
        self.button_w = 240
        self.button_h = 64
        self.play_rect = pygame.Rect((WINDOW_WIDTH - self.button_w)//2,
                                     (WINDOW_HEIGHT//2) - self.button_h//2 - 40,
                                     self.button_w, self.button_h)
        self.settings_rect = pygame.Rect((WINDOW_WIDTH - self.button_w)//2,
                                          (WINDOW_HEIGHT//2) - self.button_h//2 + 40,
                                          self.button_w, self.button_h)
        self.quit_rect = pygame.Rect((WINDOW_WIDTH - self.button_w)//2,
                                     (WINDOW_HEIGHT//2) - self.button_h//2 + 120,
                                     self.button_w, self.button_h)

    def _draw_button(self, rect, text, hover=False):
        color = (100, 200, 100) if hover else (80, 160, 80)
        pygame.draw.rect(self.display_surface, color, rect, border_radius=8)
        txt = self.font.render(text, True, (255, 255, 255))
        tr = txt.get_rect(center=rect.center)
        self.display_surface.blit(txt, tr)

    def _create_title_surface(self, text: str):
        # Create a blocky, pixel-art title reminiscent of a voxel/block game style.
        # We render the text at a small resolution, then draw each 'on' pixel as
        # a filled block on a larger surface to achieve a chunky, Minecraft-like look
        # without copying any trademarked artwork.
        #
        # Steps:
        # 1. Render text to a small temporary surface using a monospace font.
        # 2. For each pixel that is non-transparent, draw a block (rect) on the
        #    final surface scaled by `scale`.
        # 3. Draw an outline by expanding the blocks and a drop shadow.

        # small render size and scale factor
        # choose a slightly larger scale for a bolder block look
        scale = 5
        small_font_size = max(18, int(self.title_font.get_linesize() * 0.45))
        try:
            small_font = pygame.font.SysFont('couriernew', small_font_size)
        except Exception:
            small_font = pygame.font.SysFont(None, small_font_size)

        small = small_font.render(text, True, (255, 255, 255))
        sw, sh = small.get_size()
        pad_blocks = 2

        tw = (sw + pad_blocks*2) * scale
        th = (sh + pad_blocks*2) * scale
        surf = pygame.Surface((tw, th), pygame.SRCALPHA)

        # draw drop shadow blocks (offset by a few pixels)
        shadow_color = (10, 10, 10, 200)
        shadow_offset = (int(scale*0.5), int(scale*0.5))

        # read small surface pixels
        small_locked = small.copy().convert_alpha()
        for y in range(sh):
            for x in range(sw):
                col = small_locked.get_at((x, y))
                if col.a > 16:
                    # draw shadow block
                    rx = (x + pad_blocks) * scale + shadow_offset[0]
                    ry = (y + pad_blocks) * scale + shadow_offset[1]
                    pygame.draw.rect(surf, shadow_color, (rx, ry, scale, scale))

        # outline color (dark)
        outline_color = (8, 8, 8)
        # main block color: pure white (user requested)
        main_block_color = (255, 255, 255)

        # draw main blocks with outline per-block to get chunky look
        # enlarge main blocks slightly and make outline a bit larger so there
        # are no inner gaps (removes inner squares)
        for y in range(sh):
            for x in range(sw):
                col = small_locked.get_at((x, y))
                if col.a > 16:
                    rx = (x + pad_blocks) * scale
                    ry = (y + pad_blocks) * scale
                    # outline by drawing a larger dark rect behind
                    pygame.draw.rect(surf, outline_color, (rx-2, ry-2, scale+4, scale+4))
                    # draw main white block slightly bigger to avoid gaps
                    pygame.draw.rect(surf, main_block_color, (rx-1, ry-1, scale+2, scale+2))

        return surf

    def _prepare_background(self):
        # Load tiled map and render a window-sized view centered on the map,
        # then create a blurred version by downscaling and upscaling.
        try:
            tmx = load_pygame(join('data', 'maps', 'world.tmx'))
        except Exception:
            self.bg_surface = None
            return

        map_w = tmx.width * SPRITE_SIZE
        map_h = tmx.height * SPRITE_SIZE

        # Render map into a window-sized surface centered on map center
        surf = _pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT)).convert_alpha()
        surf.fill((0, 0, 0, 0))

        # center of map in pixels
        center_x = map_w // 2
        center_y = map_h // 2
        offset_x = -(center_x - (WINDOW_WIDTH // 2))
        offset_y = -(center_y - (WINDOW_HEIGHT // 2))

        # draw ground layer if present
        try:
            layer = tmx.get_layer_by_name('Ground')
            for x, y, image in layer.tiles():
                if image:
                    px = x * SPRITE_SIZE + offset_x
                    py = y * SPRITE_SIZE + offset_y
                    surf.blit(image, (px, py))
        except Exception:
            pass

        # draw objects layer (non-ground)
        try:
            layer = tmx.get_layer_by_name('Objects')
            for obj in layer:
                if getattr(obj, 'image', None):
                    px = int(obj.x) + offset_x
                    py = int(obj.y) + offset_y
                    surf.blit(obj.image, (px, py))
        except Exception:
            pass

        # create blurred version: downscale then upscale
        try:
            scale = 6  # larger = stronger blur
            small = _pygame.transform.smoothscale(surf, (max(1, WINDOW_WIDTH//scale), max(1, WINDOW_HEIGHT//scale)))
            blur = _pygame.transform.smoothscale(small, (WINDOW_WIDTH, WINDOW_HEIGHT))
            # darken a bit for menu readability
            dark = _pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), _pygame.SRCALPHA)
            dark.fill((10, 10, 20, 120))
            blur.blit(dark, (0, 0))
            self.bg_surface = blur
        except Exception:
            self.bg_surface = surf

    def run(self):
        # returns 'play' or 'quit'
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        return 'play'
                    elif event.key == pygame.K_ESCAPE:
                        return 'quit'
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    if self.play_rect.collidepoint(mx, my):
                        return 'play'
                    if self.settings_rect.collidepoint(mx, my):
                        return 'settings'
                    if self.quit_rect.collidepoint(mx, my):
                        return 'quit'

            # draw blurred map background if available
            if getattr(self, 'bg_surface', None):
                try:
                    self.display_surface.blit(self.bg_surface, (0, 0))
                except Exception:
                    self.display_surface.fill((20, 20, 30))
            else:
                self.display_surface.fill((20, 20, 30))

            # Title
            # Title (use pre-rendered attractive surface if available)
            if getattr(self, 'title_surf', None):
                try:
                    self.display_surface.blit(self.title_surf, self.title_rect)
                except Exception:
                    pass
            else:
                title_surf = self.title_font.render("Dhaagudu Moothalu", True, (240, 240, 240))
                title_rect = title_surf.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//4))
                self.display_surface.blit(title_surf, title_rect)

            # Buttons
            mx, my = pygame.mouse.get_pos()
            play_hover = self.play_rect.collidepoint(mx, my)
            settings_hover = self.settings_rect.collidepoint(mx, my)
            quit_hover = self.quit_rect.collidepoint(mx, my)
            self._draw_button(self.play_rect, "Play", hover=play_hover)
            self._draw_button(self.settings_rect, "Settings", hover=settings_hover)
            self._draw_button(self.quit_rect, "Quit", hover=quit_hover)

            # hint
            hint = self.font.render("Press Enter / Click Play to join a game", True, (200, 200, 200))
            hint_rect = hint.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 60))
            self.display_surface.blit(hint, hint_rect)

            pygame.display.update()
            self.clock.tick(30)

        return 'quit'


class SettingsMenu:
    """A simple settings editor that edits top-level constants in settings.py.
    It supports basic string/int editing and writes back to the file.
    """
    def __init__(self, display_surface, clock, font, title_font):
        self.display_surface = display_surface
        self.clock = clock
        self.font = font
        self.title_font = title_font
        # load current settings from module
        self._load_current()
        # prepare rects
        self.field_rects = []
        self.field_values = []
        self.field_keys = []
        self.active = 0
        # Define which settings we allow to be edited and their display order
        self.keys = [
            'server',
            'port',
            'WINDOW_WIDTH',
            'WINDOW_HEIGHT',
            'FPS',
            'SPRITE_SIZE',
            'NUM_PLAYERS'
        ]
        # initial field values as strings
        for k in self.keys:
            v = getattr(settings_mod, k, None)
            self.field_keys.append(k)
            self.field_values.append('' if v is None else str(v))

        # UI buttons
        w = 140
        h = 44
        center_x = WINDOW_WIDTH // 2
        self.save_rect = pygame.Rect(center_x - w - 12, WINDOW_HEIGHT - 80, w, h)
        self.cancel_rect = pygame.Rect(center_x + 12, WINDOW_HEIGHT - 80, w, h)

    def _load_current(self):
        try:
            importlib.reload(settings_mod)
        except Exception:
            pass

    def _draw_field(self, idx, key, value, y, active=False):
        key_surf = self.font.render(f"{key}:", True, (220, 220, 220))
        self.display_surface.blit(key_surf, (120, y))
        rect = pygame.Rect(350, y - 6, 520, 28)
        pygame.draw.rect(self.display_surface, (30, 30, 40), rect)
        pygame.draw.rect(self.display_surface, (120, 120, 120) if active else (70, 70, 70), rect, 2)
        val_surf = self.font.render(value, True, (240, 240, 240))
        self.display_surface.blit(val_surf, (rect.x + 6, rect.y + 4))
        return rect

    def _write_settings_file(self, values_map):
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.py')
        backup_path = settings_path + '.bak'
        try:
            shutil.copyfile(settings_path, backup_path)
        except Exception:
            pass

        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = f.read()
        except Exception as e:
            print('Failed to read settings.py:', e)
            return False

        for k, v in values_map.items():
            # produce Python literal for value
            try:
                # Try to keep ints as ints, others as repr'ed strings
                if v.isdigit():
                    lit = v
                else:
                    # allow negative integers and simple numeric forms
                    try:
                        _ = int(v)
                        lit = v
                    except Exception:
                        lit = repr(v)
            except Exception:
                lit = repr(v)

            pattern = r'^' + re.escape(k) + r"\s*=.*$"
            repl = f"{k} = {lit}"
            new_data, count = re.subn(pattern, repl, data, flags=re.MULTILINE)
            if count == 0:
                # If key not found, append at end
                new_data = new_data + "\n" + repl + "\n"
            data = new_data

        try:
            with open(settings_path, 'w', encoding='utf-8') as f:
                f.write(data)
        except Exception as e:
            print('Failed to write settings.py:', e)
            try:
                # attempt to restore backup
                if os.path.exists(backup_path):
                    shutil.copyfile(backup_path, settings_path)
            except Exception:
                pass
            return False

        return True

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        self.active = (self.active + 1) % len(self.field_values)
                    elif event.key == pygame.K_UP:
                        self.active = (self.active - 1) % len(self.field_values)
                    elif event.key == pygame.K_DOWN:
                        self.active = (self.active + 1) % len(self.field_values)
                    elif event.key == pygame.K_RETURN:
                        # noop here
                        pass
                    elif event.key == pygame.K_BACKSPACE:
                        s = self.field_values[self.active]
                        self.field_values[self.active] = s[:-1]
                    else:
                        # add the unicode char
                        ch = event.unicode
                        if ch:
                            self.field_values[self.active] += ch
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    # update active based on click
                    # compute field rect positions
                    y = 120
                    for idx in range(len(self.field_values)):
                        rect = pygame.Rect(350, y - 6, 520, 28)
                        if rect.collidepoint(mx, my):
                            self.active = idx
                            break
                        y += 44
                    if self.save_rect.collidepoint(mx, my):
                        # build map and write
                        m = {k: v for k, v in zip(self.field_keys, self.field_values)}
                        ok = self._write_settings_file(m)
                        if ok:
                            # reload module so external code can pick up when requested
                            try:
                                importlib.reload(settings_mod)
                            except Exception:
                                pass
                            return 'saved'
                        else:
                            return 'error'
                    if self.cancel_rect.collidepoint(mx, my):
                        return 'cancel'

            self.display_surface.fill((18, 18, 28))
            title = self.title_font.render('Settings', True, (240, 240, 240))
            self.display_surface.blit(title, (WINDOW_WIDTH//2 - title.get_width()//2, 40))

            # draw fields
            y = 120
            self.field_rects = []
            for idx, (k, v) in enumerate(zip(self.field_keys, self.field_values)):
                active = (idx == self.active)
                rect = self._draw_field(idx, k, v, y, active=active)
                self.field_rects.append(rect)
                y += 44

            # draw save/cancel
            pygame.draw.rect(self.display_surface, (60, 140, 60), self.save_rect, border_radius=6)
            pygame.draw.rect(self.display_surface, (140, 60, 60), self.cancel_rect, border_radius=6)
            save_s = self.font.render('Save', True, (255, 255, 255))
            cancel_s = self.font.render('Cancel', True, (255, 255, 255))
            self.display_surface.blit(save_s, (self.save_rect.x + 36, self.save_rect.y + 10))
            self.display_surface.blit(cancel_s, (self.cancel_rect.x + 30, self.cancel_rect.y + 10))

            pygame.display.update()
            self.clock.tick(30)

        return 'cancel'


if __name__ == '__main__':
    m = Menu()
    result = m.run()
    if result == 'quit':
        pygame.quit()
        sys.exit()
