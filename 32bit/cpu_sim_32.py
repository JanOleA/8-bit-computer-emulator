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
                 LCD_display = False, cpubits = 8, stackbits = 4):
        super().__init__(autorun, target_FPS, target_HZ, draw_mem, draw_ops,
                         progload, LCD_display)
        self.cpubits = cpubits
        self.stackbits = stackbits
        self._width = 1650
        self._size = (self._width, self._height)

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
        if sys.argv[4].lower() == "true":
            lcd = True
        else:
            lcd = False
    else:
        lcd = False

    game = Game_32(True, target_fps, target_HZ, progload = progload, LCD_display = lcd,
                   cpubits = 32, stackbits = 8)
    game.execute()
    