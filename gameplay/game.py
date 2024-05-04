from .clock import Clock
from gameplay.office import Office
from gameplay.systems import Cameras
from gameplay.power import PowerManager
from gameplay.buttons import *
from gameplay import Bonnie, Chica, Lefty, Knight
from data.game.constants import *
import json
from data.saves.save import SaveManager
import random


def create_phone_calls(path: str):
    phone_calls = []
    for i in range(10):
        try:
            phone_calls.append(pygame.mixer.Sound(path + str(i + 1) + '.mp3'))
        except FileNotFoundError:
            phone_calls.append(None)
    return phone_calls


def create_mute_call() -> pygame.Surface:
    font = pygame.font.Font('resources/fonts/five-nights-at-freddys.ttf', 50)
    surface = pygame.Surface((200, 50))
    base = pygame.rect.Rect(0, 0, 200, 50)
    text = font.render('Mute Call', True, 'white')
    text_rect = text.get_rect()
    text_rect.center = (100, 30)
    pygame.draw.rect(surface, 'white', base, 5, 5)
    base_rect = pygame.Surface((200, 50))
    pygame.draw.rect(base_rect, (200, 200, 200), pygame.Rect(0, 0, 200, 50), border_radius=5)
    base_rect.set_alpha(200)
    surface.blit(base_rect, (0, 0))
    surface.blit(text, text_rect)
    return surface


def init_flick(image: pygame.surface.Surface):
    screen = pygame.display.get_surface()
    camera_flick = Flick(image,
                         (int(screen.get_width() * 4 / 11), screen.get_height() - 25),
                         pygame.event.Event(CAMERA_FLIPPED_UP),
                         pygame.event.Event(CAMERA_FLIPPED_DOWN),
                         draw_type='midbottom',
                         scale=screen.get_width() / (screen.get_width() * 1.4))
    return camera_flick


class Game:
    def __init__(self):
        # Loading Resources
        self.phone_calls = create_phone_calls('resources/sounds/night_')
        self.flick_up_image = pygame.image.load('resources/ui/buttons/flick_up.png').convert_alpha()
        self.flick_down_image = pygame.image.load('resources/ui/buttons/flick_down.png').convert_alpha()
        self.victory_sound = pygame.mixer.Sound('resources/sounds/five-nights-at-freddys-6-am.mp3')
        self.jump_scare_sound = pygame.mixer.Sound('resources/sounds/jump_scare.mp3')
        self.GLOBAL_FONT = pygame.font.Font('resources/fonts/five-nights-at-freddys.ttf', 55)
        self.BIGGER_GLOBAL_FONT = pygame.font.Font('resources/fonts/five-nights-at-freddys.ttf', 65)

        # Initialize Managers and Systems
        self.save_manager = SaveManager()
        self.night = self.save_manager.load_data()['night']
        with open('data/game/nights.json', 'r') as f:
            self.night_dict = json.loads(f.read())
            self.night_data = self.night_dict[str(self.night)]
        self.power_manager = PowerManager(self.night_data['power_time'])
        self.clock = Clock(self.night)

        self.systems = {"Cameras": Cameras()}
        self.office = Office(self)

        # Initialize Animatronics
        self.animatronics = []
        animatronic_key = {"Bonnie": Bonnie, "Chica": Chica, "Lefty": Lefty, "Knight": Knight}
        for animatronic, data in self.night_data['animatronics'].items():
            self.animatronics.append(animatronic_key[animatronic](self))

        # Define Variables
        self.status = None
        self.debugger = None
        self.active = None
        self._win = None
        self._killed = None
        self.end_function = None
        self.kill_anim = None
        self.phone_call = None
        self.mute_button = None
        self.blacked_out = None
        self.reset_counter = None
        self.reset_time = None

        self.jump_scare_sound.set_volume(0.3)
        self.flick = init_flick(self.flick_up_image)

    def start(self):
        # Setup Variables
        self.status = 'playing'
        self.debugger = False
        self.active = False
        self._win = False
        self._killed = False
        self.end_function = 'next'
        self.kill_anim = None
        self.phone_call = None
        self.active = True
        self.blacked_out = False
        self.reset_counter = 0
        self.reset_time = 0

        self.save_manager.load_data()
        self.night = self.save_manager.data['night']

        # Start Systems
        self.flick.start()
        self.office.start()
        self.clock.start(self.night)
        for system in self.systems.values():
            system.start()
        self.power_manager.start()

        # Start Animatronics
        self.night_data = self.night_dict[str(self.night)]
        for i, animatronic in enumerate(self.animatronics):
            animatronic.set_difficulty(self.night_data['animatronics'][animatronic.name]['difficulty'])
        for animatronic in self.animatronics:
            animatronic.start()

        # Start Phone
        pygame.time.set_timer(MUTE_TIME, 2500)
        if self.phone_calls[self.night - 1] is not None:
            self.phone_call = self.phone_calls[self.night - 1]
            pygame.mixer.find_channel(True).play(self.phone_call)
            self.mute_button = 'start'

    def stop(self):
        pygame.time.set_timer(MUTE_TIME, 0)
        pygame.time.set_timer(GAME_TIMER, 0)
        pygame.time.set_timer(POWER_RESET, 0)

        pygame.mixer.stop()
        self.office.stop()
        self.save_manager.save_game()
        self.power_manager.stop()
        self.clock.stop()
        for system in self.systems.values():
            system.stop()

        for animatronic in self.animatronics:
            animatronic.stop()

        if self.night == 7:
            self.save_manager.data["night"] = 6
        self.save_manager.save_game()

    def global_tick(self, event: pygame.event.Event):
        if event.type == pygame.WINDOWRESIZED:
            for system in self.systems.values():
                system.resize()
            self.power_manager.resize()
        if event.type == POWER_OUT:
            self.power_out()
        if event.type == WIN:
            self.win()
        for animatronic in self.animatronics:
            animatronic.tick(event)
        for system in self.systems.values():
            system.tick(event)
        if not self.blacked_out:
            self.flick.tick(event)
        self.office.tick(event)
        self.tick(event)
        self.clock.tick(event)
        self.power_manager.tick(event)
        if event.type == CLOCK:
            for animatronic in self.animatronics:
                change_list = self.night_data['animatronics'][animatronic.name]['change']
                for change in change_list:
                    if change[0] == self.clock.hour:
                        animatronic.update_aggression(change[1])
                        break

    def global_draw(self):
        screen = pygame.display.get_surface()
        self.office.draw()
        for system in self.systems.values():
            system.draw()
        if not self.blacked_out:
            self.flick.draw(screen)
        if self.status == 'win':
            screen.fill('black')
            text = pygame.transform.scale_by(self.BIGGER_GLOBAL_FONT.render("6:00 AM", True, "white"), 3)
            rect = text.get_rect()
            rect.center = (screen.get_width() / 2, screen.get_height() / 2)
            screen.blit(text, rect)
        else:
            self.clock.draw(screen)
        if self.mute_button is not None and self.mute_button != 'start':
            self.mute_button.draw(screen)
        if not self.blacked_out:
            self.power_manager.draw(screen)
        else:
            self.power_manager.draw_reset(screen, self.reset_counter, self.reset_time)

        if self.kill_anim is not None:
            self.kill_anim.draw(screen)

    def tick(self, event: pygame.event.Event):
        if event.type == MUTE_TIME:
            if self.mute_button == 'start':
                self.mute_button = Button(create_mute_call(), (20, 20),
                                          activate=self.mute_call)
                pygame.time.set_timer(MUTE_TIME, 10000)
            else:
                self.mute_button = None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.stop()
                self.active = False
                pygame.event.post(pygame.event.Event(MENU_CHANGE, {'func': 'menu'}))
        if event.type == GAME_TIMER:
            if self.status == 'killed':
                pygame.event.post(pygame.event.Event(MENU_CHANGE, {'func': 'menu'}))
            else:
                self.victory_sound.fadeout(1000)
                self.active = False
                self.stop()
                pygame.event.post(pygame.event.Event(MENU_CHANGE, {'func': 'next'}))
        if event.type == UPDATE_POWER:
            self.power_manager.update_power(self.get_power_usage())
        if event.type == KILL and self.status == 'playing':
            self.kill(event.animation)
        if event.type == WIN and self.status == 'playing':
            self.win()
        if self.mute_button is not None and self.mute_button != 'start':
            self.mute_button.tick(event)
        if event.type == POWER_RESET:
            if self.blacked_out:
                if self.reset_counter >= self.reset_time:
                    self.un_black_out()
                else:
                    self.reset_counter += 1
            else:
                self.reset_power()
        if event.type == CAMERA_FLIPPED_UP:
            self.flick.change_surface(self.flick_down_image)
        if event.type == CAMERA_FLIPPED_DOWN:
            self.flick.change_surface(self.flick_up_image)

    def mute_call(self):
        self.phone_call.stop()
        self.mute_button = None

    def next_night(self):
        self.save_manager.save_game()

    def get_power_usage(self) -> int:
        if not self.blacked_out:
            power_usage = 1
        else:
            power_usage = 0
        power_usage += self.office.get_power_usage()
        for system in self.systems.values():
            if system.active:
                power_usage += 1
        return min(power_usage, 5)

    def kill(self, animation):
        self.kill_anim = animation
        self.kill_anim.play_forward()
        pygame.mixer.stop()
        self.stop()
        self.status = 'killed'
        self.jump_scare_sound.play(maxtime=1000)
        pygame.time.set_timer(KILL, 0)
        pygame.time.set_timer(GAME_TIMER, 1000)

    def win(self):
        pygame.mixer.stop()
        self.save_manager.data["night"] = self.night + 1
        self.stop()
        self.status = 'win'
        self.victory_sound.play(fade_ms=1000)
        pygame.time.set_timer(GAME_TIMER, int(self.victory_sound.get_length() * 1000) - 1000)

    def update_animatronics(self):
        for animatronic in self.animatronics:
            animatronic.update_images()

    def stop_timer(self):
        pass

    def reset_power(self):
        # Ok Charlie... Ideally we don't have any system have a variable called "Blacked out". Only the ones
        # like the office, doors, and power need the function, and then we use the Game class to eliminate
        # the possibility of even activating any of the other systems like removing the flick button.
        self.black_out()
        self.reset_time = 150
        pygame.time.set_timer(POWER_RESET, 100, self.reset_time + 1)
        # wait 10 - 30 seconds
        # bright office

    def un_black_out(self):
        self.reset_counter = 0
        self.reset_time = 0
        self.power_manager.reset_count = 0
        self.office.reset()
        self.blacked_out = False
        self.update_animatronics()

    def black_out(self):
        pygame.mixer.Sound('resources/sounds/power_off.mp3').play()
        self.blacked_out = True
        self.office.blackout()
        self.systems["Cameras"].blackout()

    def power_out(self):
        self.black_out()
        pygame.time.set_timer(pygame.event.Event(KILL, {'animation': self.animatronics[3].jumpscare}),
                              random.randint(5000, 40000))
        self.animatronics = []
        self.office.doors = []
