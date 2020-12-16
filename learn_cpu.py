import time
import os
import sys
from numpy.lib.arraysetops import isin

import pygame
from pygame import mouse
from pygame.display import update
from pygame.locals import *
import numpy as np

from cpu_sim import BitDisplay, draw_circle

gate_update_chance = 0.5 # chance that a gate will update according to its input on each tick, use to simulate gate delay
update_to_1 = True # whether the gate_update_chance will be set to 1 after a certain amount of time

class BinaryGate:
    """ Abstract superclass for binary gate classes """
    def __init__(self, input1, input2, cpos = (0,0), size = 30,
                 font = None):
        self._input1 = input1
        self._input2 = input2
        self._size = size
        self._width = size*2
        self.cpos = cpos
        self.font = font
        self.text = None
        self.orig_text = None
        self._color = (200, 200, 200)
        self._in1_color = (150, 150, 150)
        self._in2_color = (150, 150, 150)
        self._value = False

    def set_input1(self, input1):
        self._input1 = input1

    def set_input2(self, input2):
        self._input2 = input2

    def set_inputs(self, input1, input2):
        self._input1 = input1
        self._input2 = input2

    def update(self):
        self._value = False

    def get_inputs(self):
        return self._input1, self._input2

    @property
    def input_loc1(self):
        return np.array(self._input_loc1)

    @property
    def input_loc2(self):
        return np.array(self._input_loc2)

    @property
    def output_loc(self):
        return np.array(self._output_loc)

    @property
    def cpos(self):
        return self._cpos

    @property
    def value(self):
        return self._value

    def disable_font(self):
        self.font = None
        self.text = None

    def enable_font(self, font):
        self.font = font
        self.text = self.font.render(self.orig_text, True, (0, 0, 0))

    @cpos.setter
    def cpos(self, cpos):
        self._cpos = cpos
        size = self._size
        width = self._width
        self._rect = pygame.Rect(cpos[0] - width//2, cpos[1] - size//2, width, size)

        self._input_loc2 = None
        if isinstance(self, SingleInputGate):
            self._input_loc1 = (cpos[0] - width//2, cpos[1])
        else:
            self._input_loc1 = (cpos[0] - width//2, cpos[1] - size//3)
            self._input_loc2 = (cpos[0] - width//2, cpos[1] + size//3)

        self._output_loc = (cpos[0] + width//2, cpos[1])

    def mouse_within(self, mouse_pos):
        try:
            x, y = self._input_loc1
            mouse_dist = (mouse_pos[0] - x)**2 + (mouse_pos[1] - y)**2
            if mouse_dist < (self._size//6)**2:
                return 1 # return 1 if the mouse is over the first input
        except TypeError:
            pass

        try:
            x, y = self._input_loc2
            mouse_dist = (mouse_pos[0] - x)**2 + (mouse_pos[1] - y)**2
            if mouse_dist < (self._size//6)**2:
                return 2 # return 2 if the mouse is over the second input
        except TypeError:
            pass

        try:
            x, y = self._output_loc
            mouse_dist = (mouse_pos[0] - x)**2 + (mouse_pos[1] - y)**2
            if mouse_dist < (self._size//6)**2:
                return 3 # return 3 if the mouse is over the output
        except TypeError:
            pass

        try:
            x, y = self._cpos
            mbx, mby = mouse_pos
            if (mbx > x - self._width//2 and mbx < x + self._width//2) and (mby > y - self._size//2 and mby < y + self._size//2):
                return 4 # return 3 if the mouse is over the gate
        except TypeError:
            pass

        return 0 # if neither, return 0

    def render(self, screen):
        if self._input1 is None:
            self._in1_color = (150, 150, 150)
        else:
            self._in1_color = (50, 50, 50)
        if self._input2 is None:
            self._in2_color = (150, 150, 150)
        else:
            self._in2_color = (50, 50, 50)
        pygame.draw.rect(screen, self._color, self._rect, border_radius = 7)
        draw_circle(screen, self._input_loc1[0], self._input_loc1[1], self._size//6, self._in1_color)
        if not self._input_loc2 is None:
            draw_circle(screen, self._input_loc2[0], self._input_loc2[1], self._size//6, self._in2_color)
        draw_circle(screen, self._output_loc[0], self._output_loc[1], self._size//6, (150, 150, 150))
        if not self.font is None:
            text_x = self.cpos[0] - self.text.get_width()//2
            text_y = self.cpos[1] - self.text.get_height()//2
            screen.blit(self.text, (text_x, text_y))

    def __call__(self):
        return self.value


class AndGate(BinaryGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        super().__init__(input1, input2, cpos, size, font)
        self._color = (100, 100, 255)
        self.orig_text = "AND"
        if not self.font is None:
            self.text = self.font.render("AND", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None and self._input2 is not None:
            if np.random.random() < gate_update_chance:
                self._value = (self._input1() and self._input2())


class OrGate(BinaryGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        super().__init__(input1, input2, cpos, size, font)
        self._color = (100, 255, 100)
        self.orig_text = "OR"
        if not self.font is None:
            self.text = self.font.render("OR", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None and self._input2 is not None:
            if np.random.random() < gate_update_chance:
                self._value = (self._input1() or self._input2())


class XOrGate(BinaryGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        super().__init__(input1, input2, cpos, size, font)
        self._color = (200, 255, 100)
        self.orig_text = "XOR"
        if not self.font is None:
            self.text = self.font.render("XOR", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None and self._input2 is not None:
            if np.random.random() < gate_update_chance:
                self._value = (self._input1() != self._input2())


class NAndGate(BinaryGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        super().__init__(input1, input2, cpos, size, font)
        self._color = (200, 100, 255)
        self.orig_text = "NAND"
        if not self.font is None:
            self.text = self.font.render("NAND", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None and self._input2 is not None:
            if np.random.random() < gate_update_chance:
                self._value = not (self._input1() and self._input2())


class NOrGate(BinaryGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        super().__init__(input1, input2, cpos, size, font)
        self._color = (100, 255, 200)
        self.orig_text = "NOR"
        if not self.font is None:
            self.text = self.font.render("NOR", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None and self._input2 is not None:
            if np.random.random() < gate_update_chance:
                self._value = not (self._input1() or self._input2())


class SingleInputGate(BinaryGate):
    """ Abstract superclass for gates with only a single input. """


class NotGate(SingleInputGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        if not input2 is None:
            raise ValueError("Not gate cannot have two inputs")

        super().__init__(input1, input2, cpos, size, font)
        self._color = (255, 100, 100)
        self.orig_text = "NOT"
        if not self.font is None:
            self.text = self.font.render("NOT", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None:
            if np.random.random() < gate_update_chance:
                self._value = not (self._input1())


class BufferGate(SingleInputGate):
    def __init__(self, input1 = None, input2 = None, cpos = (0,0), size = 30,
                 font = None):
        if not input2 is None:
            raise ValueError("Buffer gate cannot have two inputs")

        super().__init__(input1, input2, cpos, size, font)
        self._color = (255, 255, 180)
        self.orig_text = "BUF"
        if not self.font is None:
            self.text = self.font.render("BUF", True, (0, 0, 0))

    def update(self):
        if self._input1 is not None:
            if np.random.random() < gate_update_chance:
                self._value = (self._input1())


class CircleItem:
    """ Abstract superclass for small circular items """


class BitButton(CircleItem):
    def __init__(self, oncolor = (60, 255, 60), offcolor = (60, 60, 60),
                 cpos = (0,0), radius = 10, toggle = True):
        """ Uses the BitDisplay class to make a single-bit button which can be
        either on or off.
        
        Arguments:
        oncolor     -   color of an LED when on     (R,G,B)
        offcolor    -   color of an LED when off    (R,G,B)
        cpos        -   center position of display  (x,y)
        radius      -   radius of the LED's
        toggle      -   whether the button toggles or is on only while pressed
        """

        self.bit_display = BitDisplay(oncolor = oncolor, offcolor = offcolor,
                                      cpos = cpos, radius = radius, length = 1)

        self._toggle = toggle
        self._pressed_last = False
        self._value = 0
        self._create_time = time.time()

    @property
    def cpos(self):
        return self.bit_display.cpos

    @property
    def x(self):
        return self.bit_display.cpos[0]

    @property
    def y(self):
        return self.bit_display.cpos[1]

    @cpos.setter
    def cpos(self, value):
        self.bit_display.cpos = value

    @property
    def radius(self):
        return self.bit_display.radius

    @property
    def value(self):
        return self._value

    def __call__(self):
        return self.value

    def mouse_within(self, mouse_pos):
        pos = self.cpos
        x = pos[0]
        y = pos[1]
        mouse_dist = (mouse_pos[0] - x)**2 + (mouse_pos[1] - y)**2
        if mouse_dist < self.radius**2:
            return True

    def update(self, mouse_pos, mb1):
        """ Updates the state of the button depending on the state of the mouse
        
        Arguments:
        mouse_pos   -   tuple containing the (x,y)-position of the mouse pointer
        mb1         -   boolean, should be true if mouse button 1 is pressed,
                        false otherwise
        """
        if time.time() - self._create_time < 0.5:
            return 0
        if mb1:
            if self.mouse_within(mouse_pos):
                if not self._toggle:
                    self._value = 1
                elif not self._pressed_last:
                    if self._value == 0:
                        self._value = 1
                    else:
                        self._value = 0
                    self._pressed_last = True
            else:
                if not self._toggle:
                    self._value = 0
        else:
            if not self._toggle:
                self._value = 0
            self._pressed_last = False

        return self.value

    def render(self, screen):
        self.bit_display.draw_number(self.value, screen)


class Pulser(CircleItem):
    def __init__(self, oncolor = (60, 255, 60), offcolor = (60, 60, 60),
                 cpos = (0,0), radius = 10, interval = 3):
        """ Uses the BitDisplay class to make a single-bit pulser which can be
        either on or off.
        
        Arguments:
        oncolor     -   color of an LED when on     (R,G,B)
        offcolor    -   color of an LED when off    (R,G,B)
        cpos        -   center position of display  (x,y)
        radius      -   radius of the LED's
        interval    -   how long (seconds) the pulser stays in each state
        """

        self.bit_display = BitDisplay(oncolor = oncolor, offcolor = offcolor,
                                      cpos = cpos, radius = radius, length = 1)

        self._pressed_last = False
        self._value = 0
        self._create_time = time.time()
        self._last_switch_time = time.time()
        self._interval = interval
        self._interval_index = 0
        self._interval_list = [interval, 2, 1, 0.5, 0.2, 0.1, 0.05]

    @property
    def cpos(self):
        return self.bit_display.cpos

    @property
    def x(self):
        return self.bit_display.cpos[0]

    @property
    def y(self):
        return self.bit_display.cpos[1]

    @cpos.setter
    def cpos(self, value):
        self.bit_display.cpos = value

    @property
    def radius(self):
        return self.bit_display.radius

    @property
    def value(self):
        return self._value

    def __call__(self):
        return self.value

    def mouse_within(self, mouse_pos):
        pos = self.cpos
        x = pos[0]
        y = pos[1]
        mouse_dist = (mouse_pos[0] - x)**2 + (mouse_pos[1] - y)**2
        if mouse_dist < self.radius**2:
            return True

    def next_interval(self):
        self._interval_index += 1
        if self._interval_index == len(self._interval_list):
            self._interval_index = 0
        self._interval = self._interval_list[self._interval_index]

    def update(self):
        """ Updates the state of the pulser """
        if time.time() - self._last_switch_time > self._interval:
            if self.value:
                self._value = 0
            else:
                self._value = 1
            self._last_switch_time = time.time()

        return self.value

    def render(self, screen):
        self.bit_display.draw_number(self.value, screen)


class OneBitDisplay(CircleItem):
    def __init__(self, input1 = None, oncolor = (60, 255, 60), offcolor = (60, 60, 60),
                 cpos = (0,0), radius = 10):
        """ Uses the BitDisplay class to make a single-bit button which can be
        either on or off.
        
        Arguments:
        input1      -   The object which provides the input value
        oncolor     -   color of an LED when on     (R,G,B)
        offcolor    -   color of an LED when off    (R,G,B)
        cpos        -   center position of display  (x,y)
        radius      -   radius of the LED's
        """

        self.bit_display = BitDisplay(oncolor = oncolor, offcolor = offcolor,
                                      cpos = cpos, radius = radius, length = 1)

        self._input = input1
        self._pressed_last = False
        self.value = 0

    def set_input(self, input1):
        self._input = input1

    def get_input(self):
        return self._input

    @property
    def cpos(self):
        return self.bit_display.cpos

    @cpos.setter
    def cpos(self, cpos):
        self.bit_display.cpos = cpos

    @property
    def radius(self):
        return self.bit_display.radius

    def mouse_within(self, mouse_pos):
        pos = self.cpos
        x = pos[0]
        y = pos[1]
        mouse_dist = (mouse_pos[0] - x)**2 + (mouse_pos[1] - y)**2
        if mouse_dist < self.radius**2:
            return True

    def __call__(self):
        return self.update()

    def update(self):
        if self._input is not None:
            self.value = self._input()
            return self.value
        else:
            self.value = 0
            return 0

    def render(self, screen):
        self.bit_display.draw_number(self.value, screen)


class Wire:
    def __init__(self, positions, in_connection, oncolor = (60, 130, 60),
                 offcolor = (70, 70, 70)):
        self._positions = positions
        self._in_connection = in_connection
        self._oncolor = oncolor
        self._offcolor = offcolor
        self._value = 0

    def add_joint(self, point):
        self._positions.append(point)

    def get_input(self):
        return self._in_connection

    def render(self, screen, width = 3):
        value = self._value
        if value == 1:
            color = self._oncolor
        else:
            color = self._offcolor
        for i, pos in enumerate(self._positions[:-1]):
            pos1 = pos
            pos2 = self._positions[i + 1]
            pygame.draw.line(screen, color,
                             pos1, pos2,
                             width = width)

    @property
    def positions(self):
        return self._positions

    def update(self):
        self._value = self._in_connection()

    def __call__(self):
        return self._value


class Scene:
    def __init__(self, main_screen,
                 xoffset = 0, yoffset = 0):
        self.buttons = []
        self.wires = []
        self.gates = []
        self.displays = []
        self.texts = []
        self._main_screen = main_screen
        self._xoffset = xoffset
        self._yoffset = yoffset

        surface = pygame.Surface(main_screen.get_size(), pygame.SRCALPHA, 32)
        self._surface = surface.convert_alpha()
        self._surface.fill((0, 0, 0, 0))

    def add_button(self, button):
        if isinstance(button, BitButton):
            self.buttons.append(button)
        else:
            raise AttributeError("Button must be object of BitButton type.")

    def add_wire(self, wire):
        if isinstance(wire, Wire):
            self.wires.append(wire)
        else:
            raise AttributeError("Wire must be object of Wire type.")

    def add_gate(self, gate):
        if isinstance(gate, BinaryGate):
            self.gates.append(gate)
        else:
            raise AttributeError("Gate must be object of subclass of BinaryGate.")

    def add_display(self, display):
        if isinstance(display, OneBitDisplay):
            self.displays.append(display)
        else:
            raise AttributeError("Display must be object of OneBitDisplay type.")

    def add_text(self, text):
        if isinstance(text, PosText):
            self.texts.append(text)
        else:
            raise AttributeError("text must be object of PosText type.")

    def set_offsets(self, x, y):
        self._xoffset = x
        self._yoffset = y

    def get_offsets(self):
        return (self._xoffset, self._yoffset)

    def update(self, mouse_pos, mb1):
        mouse_pos = (mouse_pos[0] - self._xoffset, mouse_pos[1] - self._yoffset)
        for button in self.buttons:
            button.update(mouse_pos, mb1)

        for display in self.displays:
            display.update()

    def render(self, screen):
        self._surface.fill((0, 0, 0, 0))

        for wire in self.wires:
            wire.render(self._surface)
        
        for button in self.buttons:
            button.render(self._surface)

        for gate in self.gates:
            gate.render(self._surface)

        for display in self.displays:
            display.render(self._surface)

        for text in self.texts:
            text.render(self._surface)

        screen.blit(self._surface, (self._xoffset, self._yoffset))


class PosText:
    def __init__(self, text, font, pos = (0,0), color = (255,255,255)):
        """ Text object for use with Pygame which can contain the position of
        the text.
        """
        self._font = font
        self._pos = pos
        self._color = color
        self.text = text

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, pos):
        self._pos = pos

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._color = color
        self._rendered_text = self._font.render(self.text, True, self._color)

    @property
    def text(self):
        return self._text
    
    @text.setter
    def text(self, text):
        self._text = text
        self._rendered_text = self._font.render(text, True, self._color)

    def render(self, screen, x_offset = 0, y_offset = 0):
        pos = (x_offset + self.pos[0], y_offset + self.pos[1])
        screen.blit(self._rendered_text, pos)


class Button:
    def __init__(self, pos, func, width = 100, height = 30,
                 text = "", font = None,
                 color = (200, 200, 200),
                 color_hover = (180, 180, 180),
                 color_press = (100, 100, 100),
                 color_disabled = (50, 50, 50)):

        if callable(func):
            self._func = func
        else:
            raise AttributeError("Func must be callable.")

        self._width = width
        self._height = height
        self.pos = pos
        self._color = color
        self._color_hover = color_hover
        self._color_press = color_press
        self._color_disabled = color_disabled
        self._font = font
        self.text = text
        self._drawcolor = color

        self._pressed = False

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text, font = None):
        if font is not None:
            self._font = font
        self._text = text
        if self._font is not None:
            if np.average(self._color) > 130:
                textcolor = (0, 0, 0)
            else:
                textcolor = (255, 255, 255)
            self._text_rendered = self._font.render(text, True, textcolor)
        else:
            self._text_rendered = None

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, pos):
        self._pos = pos
        self._rect = pygame.Rect(pos[0], pos[1], self._width, self._height)

    def update(self, mouse_pos, mb1, *args):
        pos = self.pos
        x = pos[0]
        y = pos[1]
        mouse_x = mouse_pos[0]
        mouse_y = mouse_pos[1]

        self._drawcolor = self._color
        if (mouse_x > x and mouse_x < x + self._width) and (mouse_y > y and mouse_y < y + self._height):
            self._drawcolor = self._color_hover
            if mb1:
                self._drawcolor = self._color_press
                if not self._pressed:
                    self._pressed = True
                    return self._func(*args)
        else:
            if mb1:
                self._pressed = True

        if not mb1:
            self._pressed = False

    def render(self, screen):
        pygame.draw.rect(screen, self._drawcolor, self._rect, border_radius = 4)
        pos = self.pos
        x = pos[0]
        y = pos[1]
        text_x = x + self._width//2 - self._text_rendered.get_width()//2
        text_y = y + self._height//2 - self._text_rendered.get_height()//2
        screen.blit(self._text_rendered, (text_x, text_y))


class Game:
    """ Main control class. Handles rendering, timing control and user input. """
    def __init__(self):
        self._running = True
        self._screen = None
        self._width = 1600
        self._height = 900
        self._size = (self._width, self._height)
        self.fps = 0
        self.interactive = True

        self.WHITE = (255, 255, 255)
        self.TEXTGREY = (180, 180, 180)
        self.GREY = (115, 115, 115)
        self.DARKGREY = (20, 20, 20)
        self.BRIGHTRED = (255, 75, 75)
        self.RED = (255, 0, 0)
        self.DARKRED = (200, 0, 0)
        self.DARKERRED = (30, 0, 0)
        self.PURPLEISH = (150, 0, 255)
        self.DARKPURPLEISH = (50, 0, 150)
        self.DARKERPURPLEISH = (5, 0, 15)
        self.GREEN = (0, 255, 0)
        self.DARKGREEN = (0, 200, 0)
        self.DARKKGREEN = (0, 130, 0)
        self.DARKERGREEN = (0, 30, 0)
        self.BLUE = (0, 0, 255)
        self.DARKBLUE = (0, 0, 200)
        self.DARKERBLUE = (0, 0, 30)
        self.BLACK = (0, 0, 0)

    def setup_fonts(self):
        pygame.font.init()
        self._font_exobold = pygame.font.Font(os.path.join(os.getcwd(), "font", "ExoBold-qxl5.otf"), 19)
        self._font_exobold_small = pygame.font.Font(os.path.join(os.getcwd(), "font", "ExoBold-qxl5.otf"), 13)
        self._font_brush = pygame.font.Font(os.path.join(os.getcwd(), "font", "BrushSpidol.otf"), 25)
        self._font_segmentdisplay = pygame.font.Font(os.path.join(os.getcwd(), "font", "28segment.ttf"), 80)
        self._font_console_bold = pygame.font.SysFont("monospace", 17, bold = True)
        self._font_small_console = pygame.font.SysFont("monospace", 11)
        self._font_small_console_bold = pygame.font.SysFont("monospace", 11, bold = True, italic = True)
        self._font_verysmall_console = pygame.font.SysFont("monospace", 10)
        self._font_verysmall_console_bold = pygame.font.SysFont("monospace", 10, bold = True)
        self._font_veryverysmall_console = pygame.font.SysFont("monospace", 9)
        self._font_veryverysmall_console_bold = pygame.font.SysFont("monospace", 9, bold = True)
        self._font_small = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 11)
        self._font = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 16)
        self._font_large = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 25)
        self._font_larger = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 45)
        self._font_verylarge = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 64)

    def twobutton_gate(self, pos = (0,0), gatetype = AndGate):
        scene = Scene(self._screen)

        pos = np.array(pos)

        button1 = BitButton(cpos = pos)
        button2 = BitButton(cpos = pos + (0,40))
        gate1 = gatetype(None, None, cpos = pos + (70, 20),
                         font = self._font_console_bold)
        out_light = OneBitDisplay(None, cpos = pos + (140, 20))
        wire1 = Wire([button1.cpos, (button1.x, gate1.input_loc1[1]), gate1.input_loc1], button1)
        wire2 = Wire([button2.cpos, (button2.x, gate1.input_loc2[1]), gate1.input_loc2], button2)
        wire3 = Wire([gate1.output_loc, out_light.cpos], gate1)

        gate1.set_inputs(wire1, wire2)
        out_light.set_input(wire3)

        scene.add_button(button1)
        scene.add_button(button2)
        scene.add_gate(gate1)
        scene.add_display(out_light)
        scene.add_wire(wire1)
        scene.add_wire(wire2)
        scene.add_wire(wire3)

        return scene

    def onebutton_gate(self, pos = (0,0), gatetype = NotGate):
        scene = Scene(self._screen)

        pos = np.array(pos)

        button1 = BitButton(cpos = pos)
        gate1 = gatetype(None, None, cpos = pos + (70, 0),
                         font = self._font_console_bold)
        out_light = OneBitDisplay(None, cpos = pos + (140, 0))
        wire1 = Wire([button1.cpos, (button1.x, gate1.input_loc1[1]), gate1.input_loc1], button1)
        wire3 = Wire([gate1.output_loc, out_light.cpos], gate1)

        gate1.set_input1(wire1)
        out_light.set_input(wire3)

        scene.add_button(button1)
        scene.add_gate(gate1)
        scene.add_display(out_light)
        scene.add_wire(wire1)
        scene.add_wire(wire3)

        return scene

    def init_game(self):
        pygame.init()
        pygame.display.set_caption("Learn CPU")

        self._screen = pygame.display.set_mode(self._size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self._running = True
        self.mouse_pos = np.array(pygame.mouse.get_pos())
        self.start_time = time.time()
        
        self.setup_fonts()

        self._bg = pygame.Surface(self._size)
        self._bg.fill((20, 20, 20))
        self._clock = pygame.time.Clock()

        self.scenes = []
        self._clear_interactive()

        self.interactive_menu = []
        self.interactive_menu.append(Button((10, 10), self._place_AND, text = "AND",
                                     font = self._font_console_bold, width = 60))
        self.interactive_menu.append(Button((80, 10), self._place_OR, text = "OR",
                                     font = self._font_console_bold, width = 60))
        self.interactive_menu.append(Button((150, 10), self._place_XOR, text = "XOR",
                                     font = self._font_console_bold, width = 60))
        self.interactive_menu.append(Button((220, 10), self._place_NAND, text = "NAND",
                                     font = self._font_console_bold, width = 60))
        self.interactive_menu.append(Button((290, 10), self._place_NOR, text = "NOR",
                                     font = self._font_console_bold, width = 60))
        self.interactive_menu.append(Button((360, 10), self._place_NOT, text = "NOT",
                                     font = self._font_console_bold, width = 60))
        self.interactive_menu.append(Button((430, 10), self._place_BUF, text = "Buffer",
                                     font = self._font_console_bold, width = 80))
        self.interactive_menu.append(Button((520, 10), self._place_button, text = "Button",
                                     font = self._font_console_bold,
                                     color = (180, 255, 255),
                                     color_hover = (160, 240, 240),
                                     color_press = (100, 150, 150)))
        self.interactive_menu.append(Button((630, 10), self._place_display, text = "Output LED",
                                     font = self._font_console_bold,
                                     color = (180, 255, 255),
                                     color_hover = (160, 240, 240),
                                     color_press = (100, 150, 150), width = 110))
        self.interactive_menu.append(Button((750, 10), self._place_pulser, text = "Pulser",
                                     font = self._font_console_bold,
                                     color = (180, 255, 255),
                                     color_hover = (160, 240, 240),
                                     color_press = (100, 150, 150)))
        self.interactive_menu.append(Button((860, 10), self._save_interactive, text = "Save",
                                     font = self._font_console_bold,
                                     color = (180, 180, 255),
                                     color_hover = (160, 160, 240),
                                     color_press = (100, 100, 150)))
        self.interactive_menu.append(Button((970, 10), self._load_interactive, text = "Load",
                                     font = self._font_console_bold,
                                     color = (180, 180, 255),
                                     color_hover = (160, 160, 240),
                                     color_press = (100, 100, 150)))
        self.interactive_menu.append(Button((1080, 10), self._copy_load, text = "Copy load",
                                     font = self._font_console_bold,
                                     color = (180, 180, 255),
                                     color_hover = (160, 160, 240),
                                     color_press = (100, 100, 150)))
        self.interactive_menu.append(Button((1490, 10), self._clear_interactive, text = "Clear",
                                     font = self._font_console_bold,
                                     color = (255, 180, 180),
                                     color_hover = (240, 160, 160),
                                     color_press = (150, 100, 100)))

        self._grid_snap = False
        self.reset_placing()

    def reset_placing(self):
        self.placing = None
        self.placing_button = False
        self.placing_display = False
        self.placing_wire = None
        self.placing_pulser = False
        self.placing_copy = False
        self.placing_copy_rect = None
        self.copy_size = (0, 0)
        self.copy_origin = (0, 0)
        self._top_is_gate = False
        self.add_interactive_wires = []
        self.add_interactive_buttons = []
        self.add_interactive_gates = []
        self.add_interactive_displays = []
        self.add_interactive_pulsers = []

    def _place_AND(self):
        self.reset_placing()
        self.placing = AndGate

    def _place_OR(self):
        self.reset_placing()
        self.placing = OrGate

    def _place_XOR(self):
        self.reset_placing()
        self.placing = XOrGate

    def _place_NAND(self):
        self.reset_placing()
        self.placing = NAndGate

    def _place_NOR(self):
        self.reset_placing()
        self.placing = NOrGate

    def _place_NOT(self):
        self.reset_placing()
        self.placing = NotGate

    def _place_BUF(self):
        self.reset_placing()
        self.placing = BufferGate

    def _place_button(self):
        self.reset_placing()
        self.placing_button = True

    def _place_display(self):
        self.reset_placing()
        self.placing_display = True

    def _place_pulser(self):
        self.reset_placing()
        self.placing_pulser = True

    def _clear_interactive(self):
        self.interactive_wires = []
        self.interactive_buttons = []
        self.interactive_gates = []
        self.interactive_displays = []
        self.interactive_pulsers = []

    def _save_interactive(self):
        for item in self.interactive_gates:
            item.disable_font()
        save_array = np.array([self.interactive_wires,
                               self.interactive_buttons,
                               self.interactive_gates,
                               self.interactive_displays,
                               self.interactive_pulsers], dtype = object)
        np.save("saved.npy", save_array)
        for item in self.interactive_gates:
            item.enable_font(self._font_console_bold)

    def _load_interactive(self):
        try:
            global gate_update_chance
            gate_update_chance = 0.5
            self.start_time = time.time()
            load_array = np.load("saved.npy", allow_pickle = True)
            (self.interactive_wires, self.interactive_buttons,
             self.interactive_gates, self.interactive_displays,
             self.interactive_pulsers) = load_array
            for item in self.interactive_gates:
                item.enable_font(self._font_console_bold)
        except IOError as e:
            print("Couldn't load file:", e)

    def _copy_load(self):
        try:
            load_array = np.load("saved.npy", allow_pickle = True)
            (self.add_interactive_wires, self.add_interactive_buttons,
             self.add_interactive_gates, self.add_interactive_displays,
             self.add_interactive_pulsers) = load_array
            for item in self.add_interactive_gates:
                item.enable_font(self._font_console_bold)
            minx = 3000
            maxx = 0
            miny = 3000
            maxy = 0

            for item1 in load_array:
                for item2 in item1:
                    if isinstance(item2, Wire):
                        continue
                    itemx, itemy = item2.cpos
                    if isinstance(item2, BinaryGate):
                        itemx_min = itemx - 30
                        itemx_max = itemx + 30
                        itemy_min = itemy - 15
                        itemy_max = itemy + 15
                    elif isinstance(item2, CircleItem):
                        itemx_min = itemx - 10
                        itemx_max = itemx + 10
                        itemy_min = itemy - 10
                        itemy_max = itemy + 10
                    else:
                        itemx_min = itemx
                        itemx_max = itemx
                        itemy_min = itemy
                        itemy_max = itemy

                    if itemx_min < minx:
                        minx = itemx_min
                    if itemx_max > maxx:
                        maxx = itemx_max
                    if itemy_min < miny:
                        if isinstance(item2, BinaryGate):
                            self._top_is_gate = True
                        else:
                            self._top_is_gate = False
                        miny = itemy_min
                    if itemy_max > maxy:
                        maxy = itemy_max
                    self.copy_origin = (minx, miny)
                    self.copy_size = (maxx - minx, maxy - miny)
            self.placing_copy = True
        except IOError as e:
            print("Couldn't load file:", e)

    def on_event(self, event):
        if event.type == pygame.QUIT:
            self._running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LSHIFT:
                self._grid_snap = True

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_LSHIFT:
                self._grid_snap = False

        mbx = self.mouse_pos[0]
        mby = self.mouse_pos[1]
        if self._grid_snap:
            mbx = round(mbx/10)*10
            mby = round(mby/10)*10
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if mby > 40:
                    for pulser in self.interactive_pulsers:
                        if pulser.mouse_within(self.mouse_pos):
                            pulser.next_interval()

                    if self.placing is not None:
                        self.interactive_gates.append(self.placing(cpos=(mbx, mby),
                                                                font = self._font_console_bold))
                        self.placing = None

                    if self.placing_button:
                        self.interactive_buttons.append(BitButton(cpos = (mbx, mby), toggle = True))
                        self.placing_button = False

                    if self.placing_display:
                        self.interactive_displays.append(OneBitDisplay(cpos = (mbx, mby)))
                        self.placing_display = False

                    if self.placing_pulser:
                        self.interactive_pulsers.append(Pulser(cpos = (mbx, mby)))
                        self.placing_pulser = False

                    if self.placing_copy:
                        if self._top_is_gate:
                            if self._grid_snap:
                                mby += 5
                        origx, origy = self.copy_origin
                        for item in (self.add_interactive_wires + self.add_interactive_buttons +
                                     self.add_interactive_gates + self.add_interactive_displays +
                                     self.add_interactive_pulsers):
                            if isinstance(item, Wire):
                                positions = item.positions
                                for i, pos in enumerate(positions):
                                    pos = (pos[0] - origx + mbx, pos[1] - origy + mby)
                                    positions[i] = pos
                                self.interactive_wires.append(item)
                            else:
                                item.cpos = (item.cpos[0] - origx + mbx, item.cpos[1] - origy + mby)
                                if isinstance(item, BitButton):
                                    self.interactive_buttons.append(item)
                                elif isinstance(item, BinaryGate):
                                    self.interactive_gates.append(item)
                                elif isinstance(item, OneBitDisplay):
                                    self.interactive_displays.append(item)
                                elif isinstance(item, Pulser):
                                    self.interactive_pulsers.append(item)
                        self.reset_placing()

                    if self.placing_wire is not None:
                        connected = False
                        del_inputs = []
                        for gate in self.interactive_gates:
                            if which := gate.mouse_within(self.mouse_pos):
                                gate_inputs = gate.get_inputs()
                                if which == 1:
                                    if gate_inputs[0] is not None:
                                        del_inputs.append(gate_inputs[0])
                                    gate.set_input1(self.placing_wire)
                                    self.placing_wire.add_joint(gate.input_loc1)
                                    connected = True
                                if which == 2:
                                    if gate_inputs[1] is not None:
                                        del_inputs.append(gate_inputs[1])
                                    gate.set_input2(self.placing_wire)
                                    self.placing_wire.add_joint(gate.input_loc2)
                                    connected = True

                        for display in self.interactive_displays:
                            if display.mouse_within(self.mouse_pos):
                                display_input = display.get_input()
                                if display_input is not None:
                                    del_inputs.append(display_input)
                                display.set_input(self.placing_wire)
                                self.placing_wire.add_joint(display.cpos)
                                connected = True

                        for item in del_inputs:
                            self.interactive_wires.remove(item)

                        if not connected:
                            self.placing_wire.add_joint((mbx, mby))
                        else:
                            self.interactive_wires.append(self.placing_wire)
                            self.placing_wire = None

            if event.button == 2:
                for item in self.interactive_buttons + self.interactive_pulsers:
                    if item.mouse_within(self.mouse_pos):
                        del_wires = []
                        for wire in self.interactive_wires:
                            if wire.get_input() == item:
                                del_wires.append(wire)
                        for wire in del_wires:
                            self.remove_wire(wire)
                        if item in self.interactive_buttons:
                            self.interactive_buttons.remove(item)
                        else:
                            self.interactive_pulsers.remove(item)
                        break

                for gate in self.interactive_gates:
                    if gate.mouse_within(self.mouse_pos) == 4:
                        del_wires = []
                        for wire in self.interactive_wires:
                            if wire.get_input() == gate:
                                del_wires.append(wire)                                
                        inp1, inp2 = gate.get_inputs()
                        if not inp1 is None:
                            del_wires.append(inp1)
                        if not inp2 is None:
                            del_wires.append(inp2)
                        for wire in del_wires:
                            self.remove_wire(wire)
                        self.interactive_gates.remove(gate)
                        break

                for display in self.interactive_displays:
                    if display.mouse_within(self.mouse_pos):
                        del_wires = []
                        inp = display.get_input()
                        if not inp is None:
                            del_wires.append(inp)
                        for wire in del_wires:
                            self.remove_wire(wire)
                        self.interactive_displays.remove(display)
                        break

            if event.button == 3:
                self.reset_placing()
                for button in self.interactive_buttons:
                    if button.mouse_within(self.mouse_pos):
                        self.placing_wire = Wire([button.cpos], button)

                for pulser in self.interactive_pulsers:
                    if pulser.mouse_within(self.mouse_pos):
                        self.placing_wire = Wire([pulser.cpos], pulser)

                for gate in self.interactive_gates:
                    if which := gate.mouse_within(self.mouse_pos):
                        if which == 3:
                            self.placing_wire = Wire([gate.output_loc], gate)

    def set_gate_chance(self, chance):
        global gate_update_chance
        gate_update_chance = chance

    def remove_wire(self, wire):
        """ Removes a wire object from the interactive wires list,
        and removes references from other objects.
        """
        for gate in self.interactive_gates:
            inp1, inp2 = gate.get_inputs()
            if inp1 == wire:
                gate.set_input1(None)
            if inp2 == wire:
                gate.set_input2(None)
        for display in self.interactive_displays:
            inp = display.get_input()
            if inp == wire:
                display.set_input(None)
        self.interactive_wires.remove(wire)

    def loop(self):
        self.mouse_pos = np.array(pygame.mouse.get_pos())

        if update_to_1:
            if time.time() - self.start_time > 2:
                self.set_gate_chance(1)

        mb1 = pygame.mouse.get_pressed()[0]
        
        for scene in self.scenes:
            scene.update(self.mouse_pos, mb1)

        if self.interactive:
            for wire in self.interactive_wires:
                wire.update()

            for button in self.interactive_buttons:
                button.update(self.mouse_pos, mb1)

            for pulser in self.interactive_pulsers:
                pulser.update()

            for gate in self.interactive_gates:
                gate.update()

            for display in self.interactive_displays:
                display.update()

            for button in self.interactive_menu:
                button.update(self.mouse_pos, mb1)

        self._clock.tick_busy_loop(200)
        self.fps = self._clock.get_fps()

    def render(self):
        self._screen.blit(self._bg, (0,0))
        mbx = self.mouse_pos[0]
        mby = self.mouse_pos[1]

        fps_text = self._font_console_bold.render(f"{int(self.fps):>3d}", True, (255, 255, 255))
        self._screen.blit(fps_text, (5, self._height - 25))

        for scene in self.scenes:
            scene.render(self._screen)

        if self.interactive:
            for wire in self.interactive_wires:
                wire.render(self._screen)

            if self._grid_snap:
                mbx = round(mbx/10)*10
                mby = round(mby/10)*10
        
            if self.placing_wire is not None:
                self.placing_wire.render(self._screen)
                pygame.draw.line(self._screen, (255, 255, 255),
                                 self.placing_wire.positions[-1], (mbx, mby),
                                 width = 3)

            for button in self.interactive_buttons:
                button.render(self._screen)

            for gate in self.interactive_gates:
                gate.render(self._screen)

            for display in self.interactive_displays:
                display.render(self._screen)

            for button in self.interactive_menu:
                button.render(self._screen)
            
            for pulser in self.interactive_pulsers:
                pulser.render(self._screen)

            if self.placing is not None:
                place_rect = pygame.Rect(mbx - 30, mby - 15, 60, 30)
                pygame.draw.rect(self._screen, (200, 200, 200), place_rect, border_radius = 10)

            if self.placing_button or self.placing_display or self.placing_pulser:
                draw_circle(self._screen, mbx, mby, 10, (200, 200, 200))

            if self.placing_copy:
                if self._top_is_gate:
                    if self._grid_snap:
                        mby += 5
                self.placing_copy_rect = pygame.Rect(mbx, mby, self.copy_size[0], self.copy_size[1])
                pygame.draw.rect(self._screen, (200, 200, 200), self.placing_copy_rect)

        pygame.display.flip()

    def cleanup(self):
        pygame.quit()

    def execute(self):
        if self.init_game() == False:
            self._running = False
 
        while(self._running):
            for event in pygame.event.get():
                self.on_event(event)
            self.loop()
            self.render()
        self.cleanup()


if __name__ == "__main__":
    game = Game()
    game.execute()
    