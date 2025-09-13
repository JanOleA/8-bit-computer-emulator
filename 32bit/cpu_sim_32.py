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
        self.memory = np.zeros(2**bits, dtype = np.uint32)
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
                 LCD_display = False, cpubits = 8, stackbits = 4, json_images=None):
        super().__init__(autorun, target_FPS, target_HZ, draw_mem, draw_ops,
                         progload, LCD_display, json_images)
        self.cpubits = cpubits
        self.stackbits = stackbits
        self._width = 1650
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

        # Optionally load JSON memory images (including program_table)
        if self._json_images:
            import json as _json
            for jf in self._json_images:
                try:
                    with open(jf, "r") as f:
                        data = _json.load(f)
                    limit = getattr(self.computer, "overflow_limit", 2**self.cpubits)
                    mask = limit - 1
                    for name, mod in data.items():
                        if not isinstance(mod, dict):
                            continue
                        base = int(mod.get("base", 0))
                        words = mod.get("words", [])
                        for i, w in enumerate(words):
                            addr = base + i
                            if 0 <= addr < len(self.computer.memory):
                                self.computer.memory[addr] = int(w) & mask
                    print(f"Loaded JSON image: {jf}")
                except Exception as e:
                    print(f"Failed to load JSON image {jf}: {e}")

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
    import argparse, json
    parser = argparse.ArgumentParser(description="32-bit computer emulator")
    parser.add_argument("program", nargs="?", default="program.txt", help="Program file to assemble and load")
    parser.add_argument("--fps", type=int, default=50, help="Target frames per second")
    parser.add_argument("--hz", type=int, default=25, help="Target clock frequency (Hz)")
    parser.add_argument("--lcd", action="store_true", default=False, help="Enable LCD display panel")
    parser.add_argument("--cpubits", type=int, default=32, help="CPU word size in bits")
    parser.add_argument("--stackbits", type=int, default=8, help="Stack pointer width in bits")
    parser.add_argument("--json", action="append", default=[], help="Path to JSON image to write into memory (can be repeated)")
    args = parser.parse_args()

    game = Game_32(True, args.fps, args.hz, progload=args.program, LCD_display=args.lcd,
                   cpubits=args.cpubits, stackbits=args.stackbits, json_images=args.json)
    game.execute()
    
