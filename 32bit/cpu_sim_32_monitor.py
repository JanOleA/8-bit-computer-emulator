import time
import os
import sys
sys.path.insert(1, '..')

import pygame
from pygame.locals import *
import numpy as np

from cpu_sim import Computer, BitDisplay, Game


class Computer_32(Computer):
    """ A version of the Computer class which allows for changing the number of
    bits used for the registers and the bus.
    """
    def __init__(self, progload, bits = 8,
                 bits_stackpointer = 4,
                 stackpointer_start = None):
        self.bits = bits
        self.bits_stackpointer = bits_stackpointer
        self.memory = np.zeros(2**bits, dtype = np.uint64)
        self.get_mem_strings()
        self.overflow_limit = 2**bits

        if stackpointer_start is None:
            stackpointer_start = 2**(bits - 1)
        self.stackpointer_start = stackpointer_start

        print(f"Stack range: {hex(stackpointer_start)} : {hex(stackpointer_start + 2**bits_stackpointer)}")
        print(f"Stack size: {2**bits_stackpointer}")

        self.setup_instructions()
        self.assembler(progload)
        self.reset()


class Game_32(Game):
    """ Main control class. Handles rendering, timing control and user input. """
    def __init__(self, autorun = True, target_FPS = 300, target_HZ = None,
                 draw_mem = False, draw_ops = False, progload = "program.txt",
                 LCD_display = True, cpubits = 8, stackbits = 4):
        super().__init__(autorun, target_FPS, target_HZ, draw_mem, draw_ops,
                         progload, LCD_display)
        self.cpubits = cpubits
        self.stackbits = stackbits
        self._width = 1680
        self._size = (self._width, self._height)

    def setup_fonts(self):
        pygame.font.init()
        self._font_exobold = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "ExoBold-qxl5.otf"), 19)
        self._font_exobold_small = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "ExoBold-qxl5.otf"), 13)
        self._font_brush = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "BrushSpidol.otf"), 25)
        self._font_segmentdisplay = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "28segment.ttf"), 80)
        self._font_console_bold = pygame.font.SysFont("monospace", 17, bold = True)
        self._font_small_console = pygame.font.SysFont("monospace", 11)
        self._font_small_console_bold = pygame.font.SysFont("monospace", 11, bold = True, italic = True)
        self._font_small_console_bold2 = pygame.font.SysFont("monospace", 11, bold = True)
        self._font_verysmall_console = pygame.font.SysFont("monospace", 10)
        self._font_verysmall_console_bold = pygame.font.SysFont("monospace", 10, bold = True)
        self._font_veryverysmall_console = pygame.font.SysFont("monospace", 9)
        self._font_veryverysmall_console_bold = pygame.font.SysFont("monospace", 9, bold = True)
        self._font_small = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 11)
        self._font = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 16)
        self._font_large = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 25)
        self._font_larger = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 45)
        self._font_verylarge = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 64)

    def init_game(self):
        pygame.init()
        pygame.display.set_caption("8 bit computer")

        self._screen = pygame.display.set_mode(self._size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self._running = True

        self.setup_fonts()

        self._bg = pygame.Surface(self._size)
        self._bg.fill((20, 20, 20))
        self._clock = pygame.time.Clock()

        self.computer = Computer_32(self.progload, bits = self.cpubits,
                                    bits_stackpointer = self.stackbits)

        self.bus_display = BitDisplay(cpos = (640, 50),
                                      font = self._font_exobold,
                                      textcolor = self.TEXTGREY,
                                      text = "Bus",
                                      length = self.cpubits,
                                      radius = 3,
                                      oncolor = self.RED,
                                      offcolor = self.DARKERRED)

        self.cnt_display = BitDisplay(cpos = (840, 150),
                                      font = self._font_exobold,
                                      textcolor = self.TEXTGREY,
                                      text = "Program counter",
                                      length = self.cpubits,
                                      radius = 3,
                                      oncolor = self.GREEN,
                                      offcolor = self.DARKERGREEN)

        self.areg_display = BitDisplay(cpos = (840, 250),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "A register",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.breg_display = BitDisplay(cpos = (840, 450),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "B register",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.sreg_display = BitDisplay(cpos = (840, 350),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "ALU (sum)",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.flgr_display = BitDisplay(cpos = (1110, 350),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Flags register",
                                       length = 2,
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.flag_display = BitDisplay(cpos = (1000, 350),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Flags",
                                       length = 2,
                                       oncolor = self.BLUE,
                                       offcolor = self.DARKERBLUE)

        self.madd_display = BitDisplay(cpos = (440, 150),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Memory address",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.mcon_display = BitDisplay(cpos = (440, 250),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Memory content",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)
        
        self.insa_display = BitDisplay(cpos = (440, 350),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Instruction register A",
                                       oncolor = self.BLUE,
                                       offcolor = self.DARKERBLUE)

        self.insb_display = BitDisplay(cpos = (440, 450),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Instruction register B",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.oprt_display = BitDisplay(cpos = (440, 550),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Operation timestep",
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.inpt_display = BitDisplay(cpos = (440, 650),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Input register",
                                       oncolor = self.PURPLEISH,
                                       offcolor = self.DARKERPURPLEISH)

        self.outp_display = BitDisplay(cpos = (840, 550),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Output register",
                                       length = self.cpubits,
                                       radius = 3,
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.stap_display = BitDisplay(cpos = (840, 650),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Stack pointer",
                                       length = self.stackbits,
                                       radius = 6,
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.disd_display = BitDisplay(cpos = (1310, 450),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Display data register",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.disc_display = BitDisplay(cpos = (1500, 450),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Control register",
                                       length = 3,
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.ctrl_display = BitDisplay(cpos = (950, 800),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Control word",
                                       oncolor = self.BLUE,
                                       offcolor = self.DARKERBLUE,
                                       length = 32)

        self.clk_display = BitDisplay(cpos = (50, 60),
                                      font = self._font_exobold,
                                      textcolor = self.TEXTGREY,
                                      text = "Clock",
                                      length = 1,
                                      oncolor = self.GREEN,
                                      offcolor = self.DARKERGREEN)

        self.make_static_graphics()
        self.LCD_display = Monitor(self._font_small_console_bold2, position = (1210, 25))

        memcolumn = ""
        self.memrows = []
        for i in range(8):
            text = f"{i:>08d} "
            memcolumn += text

        for i in range(32):
            rowtext = f"{i*8:>03d}"
            self.memrows.append(self._font_verysmall_console_bold.render(rowtext, True, self.TEXTGREY))
        
        self.memcolumn = self._font_verysmall_console_bold.render(memcolumn, True, self.TEXTGREY)
        self.memory_title = self._font_exobold.render("Memory:", True, self.TEXTGREY)

        self._start_time = time.time()

    def draw_memory(self):
        memwidth = self.memcolumn.get_width()
        titlewidth = self.memory_title.get_width()
        self.computer.get_mem_strings(32, 8, False, 8)
        x = 1210
        y = 57
        self._screen.blit(self.memory_title, (x + memwidth/2 - titlewidth/2, 5))
        self._screen.blit(self.memcolumn, (x, y - 18))
        for i, item in enumerate(self.computer.mem_strings):
            out_text = self._font_verysmall_console.render(item, True, self.TEXTGREY)
            self._screen.blit(out_text, (x, y))
            self._screen.blit(self.memrows[i], (x - 22, y))
            y += 15


class Monitor:
    """ Bigger LCD display. Custom shift functions. No real-life equivalent. """
    def __init__(self, font, position = (0, 0), columns = 40, rows = 20):
        self.columns = columns
        self.rows = rows
        self.size = np.array((columns, rows))
        self.data = 0
        self.control = 0
        self.previous_enable = 0
        self.cursoron = False
        self.cursordraw = False
        self.cursorblink = False
        self.position = position # top left
        self.font = font
        self.time = time.time()
        self.cursor_pos = np.zeros(2)
        self.cursor_dir = 1

        self.lettercolor = (0, 255, 0)
        self.bgcolor = (6, 6, 6)

        self.cursor = self.font.render("_", True, self.lettercolor)

        symbol = font.render("0", True, self.lettercolor)
        self.symbolheight = symbol.get_height()
        self.symbolwidth = symbol.get_width()

        self.pixelsize = self.size*(self.symbolwidth + 4, self.symbolheight + 4)
        
        self.bg_rect = pygame.Rect(self.position[0], self.position[1],
                                   self.pixelsize[0], self.pixelsize[1])

        self.bg_border = pygame.Rect(self.position[0] - 5, self.position[1] - 5,
                                     self.pixelsize[0] + 10, self.pixelsize[1] + 10)

        self.memory = np.zeros(columns*rows, dtype = int)

    def shift_up(self):
        memsize = self.memory.size
        self.memory[:memsize - self.columns] = self.memory[self.columns:]
        self.memory[memsize - self.columns:] = 0

    def limit_cursor(self):
        # limit cursor to screen bounds
        if self.cursor_pos[1] >= self.rows:
            # in this case also shift screen up
            self.cursor_pos[1] = self.rows - 1
            self.shift_up()

        if self.cursor_pos[0] >= self.columns:
            self.cursor_pos[0] = self.columns - 1
        if self.cursor_pos[0] < 0:
            self.cursor_pos[0] = 0
        if self.cursor_pos[1] < 0:
            self.cursor_pos[1] = 0

    def enable_set(self):
        if 0b01000000 & self.control:
            if 0b10000000 & self.control:
                """ Read """
                cursor_mem = int(self.cursor_pos[0] + self.cursor_pos[1]*self.columns)
                self.memory[cursor_mem] = self.data
                if self.cursor_dir == 1:
                    self.cursor_pos += (1, 0)
                else:
                    self.cursor_pos -= (1, 0)
                self.limit_cursor()
        else:
            if   0b10000000 & self.data:
                pass
            elif 0b01000000 & self.data:
                pass
            elif 0b00100000 & self.data:
                """ Next line, return to start """
                self.cursor_pos[0] = 0
                self.cursor_pos[1] += 1
                if self.cursor_pos[1] >= self.rows:
                    # in this case also shift screen up
                    self.cursor_pos[1] = self.rows - 1
                    self.shift_up()
            elif 0b00010000 & self.data:
                """ Cursor control """
                if 0b00000001 & self.data: # cursor right
                    self.cursor_pos += (1, 0)
                if 0b00000010 & self.data: # cursor left
                    self.cursor_pos -= (1, 0)
                if 0b00000100 & self.data: # cursor down
                    self.cursor_pos += (0, 1)
                if 0b00001000 & self.data: # cursor up
                    self.cursor_pos -= (0, 1)
                self.limit_cursor()

            elif 0b00001000 & self.data:
                """ Display on/off control
                    Always on
                """
                self.cursoron = int(bin(self.data)[-2])
                self.cursorblink = int(bin(self.data)[-1])
            elif 0b00000100 & self.data:
                pass
            elif 0b00000010 & self.data:
                """ Return home """
                self.cursor_pos = np.zeros(2)
                self.shift = 0
            elif 0b00000001 & self.data:
                """ Clear display """

                self.memory[:] = 0
                self.cursor_pos = np.zeros(2)

    def set_data_lines(self, value):
        self.data = int(value)

    def set_control_bits(self, value):
        self.control = int(value)

        if self.control&0b10000000:
            if not self.previous_enable:
                """ enable bit toggled high """
                self.enable_set()

            self.previous_enable = True
        else:
            self.previous_enable = False
                
    def render(self, screen):
        pygame.draw.rect(screen, (0, 0, 0), self.bg_border, border_radius = 10)
        pygame.draw.rect(screen, self.bgcolor, self.bg_rect, border_radius = 5)

        cursor = self.cursor

        if time.time() - self.time > 0.5:
            if self.cursordraw:
                self.cursordraw = False
            else:
                self.cursordraw = True
            self.time = time.time()

        for i, val in enumerate(self.memory):
            col = i%self.columns
            row = i//self.columns

            x = 1 + (self.symbolwidth + 4)*col + self.position[0]
            y = 2 + (self.symbolheight + 4)*row + self.position[1]
            character = chr(val)
            try:
                text = self.font.render(character, True, self.lettercolor)
                screen.blit(text, (x, y))
            except ValueError as e:
                pass # null characters aren't drawn
                
            if self.cursordraw and self.cursoron:
                if col == self.cursor_pos[0] and row == self.cursor_pos[1]:
                    screen.blit(cursor, (x, y))

            


if __name__ == "__main__":
    if len(sys.argv) > 1:
        progload = str(sys.argv[1])
    else:
        progload = "program.txt"

    if len(sys.argv) > 2:
        target_fps = int(sys.argv[2])
    else:
        target_fps = 50

    if len(sys.argv) > 3:
        target_HZ = int(sys.argv[3])
    else:
        target_HZ = 25

    if len(sys.argv) > 4:
        if sys.argv[4].lower() == "false":
            lcd = False
        else:
            lcd = True
    else:
        lcd = True

    game = Game_32(True, target_fps, target_HZ, progload = progload, LCD_display = lcd,
                   cpubits = 32, stackbits = 8)
    game.execute()
    