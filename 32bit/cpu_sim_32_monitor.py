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
            stackpointer_start = 2**bits - 2**bits_stackpointer - 1
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
                 LCD_display = True, cpubits = 8, stackbits = 4, json_images=None):
        super().__init__(autorun, target_FPS, target_HZ, draw_mem, draw_ops,
                         progload, LCD_display, json_images)
        self.cpubits = cpubits
        self.stackbits = stackbits
        self._width = 1900
        self._height = 1000
        self._size = (self._width, self._height)

    def setup_fonts(self):
        pygame.font.init()
        self._font_exobold = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "ExoBold-qxl5.otf"), 19)
        self._font_exobold_small = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "ExoBold-qxl5.otf"), 13)
        self._font_brush = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "BrushSpidol.otf"), 25)
        self._font_segmentdisplay = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "28segment.ttf"), 80)
        self._font_console_bold = pygame.font.SysFont("Cascadia Mono", 17, bold = True)
        self._font_small_console = pygame.font.SysFont("Cascadia Mono", 11)
        self._font_small_console_bold = pygame.font.SysFont("Cascadia Mono", 11, bold = True, italic = True)
        self._font_small_console_bold2 = pygame.font.SysFont("Cascadia Mono", 12, bold = True)
        self._font_verysmall_console = pygame.font.SysFont("Cascadia Mono", 10)
        self._font_verysmall_console_bold = pygame.font.SysFont("Cascadia Mono", 10, bold = True)
        self._font_veryverysmall_console = pygame.font.SysFont("Cascadia Mono", 9)
        self._font_veryverysmall_console_bold = pygame.font.SysFont("Cascadia Mono", 9, bold = True)
        self._font_small = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 11)
        self._font = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 16)
        self._font_large = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 25)
        self._font_larger = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 45)
        self._font_verylarge = pygame.font.Font(os.path.join(os.getcwd(), "..", "font", "Amble-Bold.ttf"), 64)

    def init_game(self):
        pygame.init()
        pygame.display.set_caption("32 bit computer")

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
        self.LCD_display = Monitor(self._font_small_console_bold2, position = (1210, 25))
        self.keyboard_numbers = [0, 0, 0, 0, 0]
        self.keyboard = np.zeros((5, 11))

        self.keyboard_rows_list = []
        for i in range(5):
            kbr = BitDisplay(cpos = (1410, 520 + i*41), length = 11, radius = 18,
                             offcolor = (40, 40, 40), oncolor = (80, 120, 80))
            self.keyboard_rows_list.append(kbr)

        
        keyboard_symbols = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "/",
                            "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "*",
                            "A", "S", "D", "F", "G", "H", "J", "K", "L", "Ent", "Ent",
                            "Z", "X", "C", "V", "B", "N", "M", ",", ".", "^", "<-",
                            "Ctr", "Alt", "Sh", "_", "_", "_", "+", "-", "<", "v", ">",]
        
        self._pygame_keyboard_mapping = [
            39, 30, 31, 32, 33, 34, 35, 36, 37, 38, 84,
            20, 26, 8, 21, 23, 28, 24, 12, 18, 19, 85,
            4, 22, 7, 9, 10, 11, 13, 14, 15, 40, 40,
            29, 27, 6, 25, 5, 17, 16, 54, 55, 82, 42,
            224, 226, 225, 44, 44, 44, 45, 56, 80, 81, 79
        ]
        

        self.kbrow = 0
        self.kbcol = 0        
        self.keyboard_texts_rendered = []
        for text in keyboard_symbols:
            self.keyboard_texts_rendered.append(self._font_small.render(text,
                                                                        True,
                                                                        self.WHITE))

        memcolumn = ""
        self.memrows = []
        ncols = 2
        nrows = 60
        for i in range(ncols):
            text = f"{i:>08d} "
            memcolumn += text

        for i in range(nrows):
            rowtext = f"{i*ncols:>03d}"
            self.memrows.append(self._font_verysmall_console_bold.render(rowtext, True, self.TEXTGREY))
        
        self.memcolumn = self._font_verysmall_console_bold.render(memcolumn, True, self.TEXTGREY)
        self.memory_title = self._font_exobold.render("Memory:", True, self.TEXTGREY)

        self._start_time = time.time()

    def draw_memory(self):
        memwidth = self.memcolumn.get_width()
        titlewidth = self.memory_title.get_width()
        self.computer.get_mem_strings(60, 2, False, 8)
        x = 1740
        y = 57
        self._screen.blit(self.memory_title, (x + memwidth/2 - titlewidth/2, 5))
        self._screen.blit(self.memcolumn, (x, y - 18))
        for i, item in enumerate(self.computer.mem_strings):
            out_text = self._font_verysmall_console.render(item, True, self.TEXTGREY)
            self._screen.blit(out_text, (x, y))
            self._screen.blit(self.memrows[i], (x - 32, y))
            y += 15

    def loop(self):        
        kb_input = (self.kbrow-1)*11 + self.kbcol
        if self._keyboard_mode:
            for i, key_id in enumerate(self._pygame_keyboard_mapping):
                if self.keys_pressed[key_id]:
                    kb_input = i
                    break
        if kb_input != -11:
            self.computer.input_regi = kb_input + 128
        else:
            self.computer.input_regi = 0
        super().loop()

    def render(self):
        self._screen.blit(self._bg, (0,0))

        """ Draw LED displays """
        #self.clk_display.draw_number(self.computer.timer_indicator, self._screen)
        self.bus_display.draw_number(self.computer.bus, self._screen)
        self.cnt_display.draw_number(self.computer.prog_count, self._screen)
        self.areg_display.draw_number(self.computer.areg, self._screen)
        self.breg_display.draw_number(self.computer.breg, self._screen)
        self.sreg_display.draw_number(self.computer.sumreg, self._screen)
        self.flag_display.draw_number(self.computer.flags, self._screen)
        self.flgr_display.draw_number(self.computer.flagreg, self._screen)
        self.madd_display.draw_number(self.computer.memaddress, self._screen)
        self.mcon_display.draw_number(self.computer.memcontent, self._screen)
        self.insa_display.draw_number(self.computer.inst_reg_a, self._screen)
        self.insb_display.draw_number(self.computer.inst_reg_b, self._screen)
        self.outp_display.draw_number(self.computer.out_regist, self._screen)
        self.inpt_display.draw_number(self.computer.input_regi, self._screen)
        self.stap_display.draw_number(self.computer.stackpointer, self._screen)

        """ LCD display registers """
        if self.use_LCD_display:
            self.disd_display.draw_number(self.computer.screen_data, self._screen)
            self.disc_display.draw_number(self.computer.screen_control, self._screen)

        """ Draw and check the keyboard buttons for input """
        i = 0
        for kp, num in zip(self.keyboard_rows_list, self.keyboard_numbers):
            kp.draw_number(num, self._screen)
            self.keyboard_numbers[i] = 0
            i += 1
        
        self.keyboard[:,:] = 0
        self.kbrow = 0
        self.kbcol = 0
        for i, kp_text in enumerate(self.keyboard_texts_rendered):
            column = i%11
            row = i//11
            kp = self.keyboard_rows_list[row]
            x = kp.xvalues[column]
            y = kp.y
            mouse_dist = (self.mouse_pos[0] - x)**2 + (self.mouse_pos[1] - y)**2
            if mouse_dist < kp.radius**2:
                if pygame.mouse.get_pressed()[0]:
                    self.keyboard_numbers[row] = 2**(10 - column)
                    self.keyboard[row, column] = 1
                    self.kbrow = row + 1
                    self.kbcol = column

            text_x = x - kp_text.get_width() / 2
            text_y = y - kp_text.get_height() / 2
            self._screen.blit(kp_text, (text_x, text_y))

        """ Draw the output display """
        out_string = f"{self.computer.out_regist:>03d}"
        out_text = self._font_segmentdisplay.render(out_string, True, self.BRIGHTRED)
        screen_bg = pygame.Rect(980, 480, out_text.get_width() + 35, out_text.get_height() + 25)
        pygame.draw.rect(self._screen, self.BLACK, screen_bg, border_radius = 10)
        self._screen.blit(out_text, (1000, 500))

        """ Draw the control word LED display, and the labels """
        self.ctrl_display.draw_number(self.computer.controlword, self._screen)
        for text, x_center in zip(self.ctrl_word_text_rendered, self.ctrl_display.xvalues):
            text_x = int(x_center - text.get_width()/2)
            text_y = int(self.ctrl_display.y + text.get_height()) + 5
            self._screen.blit(text, (text_x, text_y))

        """ Draw the operation timestep LED display """
        operation = int("1" + "0"*self.computer.op_timestep)
        self.oprt_display.draw_bits(operation, self._screen)

        """ If the timestep is zero, update which instruction from the program
        is the active one (to draw with green)
        """
        if self.computer.op_timestep == 0:
            self.display_op = self.computer.prog_count

        """ Draw the memory """
        if self.draw_mem:
            self.draw_memory()
        else:
            """ Draw the program """
            x = 1710
            y = 30
            for i, item in enumerate(self.prog_texts_black):
                if self.display_op == i + self.prog_offsets[i]:
                    item = self.prog_texts_green[i]
                self._screen.blit(item, (x, y))
                y += 15
                if y >= self._height - 20:
                    y = 30
                    x += 115

        """ Draw the operations included in the current instruction """
        if self.draw_ops:
            x = 1360
            y = 860
            self._screen.blit(self.microins_title, (x, y))
            if self.computer.op_timestep >= 2:
                self.op_address_draw = self.computer.inst_reg_a
            operations = self.computer.assembly[self.op_address_draw].copy()
            operations.insert(0, self.computer.RO|self.computer.IAI|self.computer.CE)
            operations.insert(0, self.computer.CO|self.computer.MI)
            for i, operation in enumerate(operations):
                if (i >= 2 and self.computer.op_timestep < 2):
                    continue
                s = ""
                for instruction, label in zip(self.computer.microcodes, self.computer.microcode_labels):
                    if instruction & operation:
                        s += f"{label:>8s} | "
                self.arrow = self._font_small_console_bold.render("> " + "_"*(len(s) - 4), "True", self.DARKKGREEN)
                if i == self.computer.op_timestep:
                    self._screen.blit(self.arrow, (x - 10, y + 30 + i*15))
                out_text = self._font_small_console.render(s[:-2], True, self.TEXTGREY)
                self._screen.blit(out_text, (x, y + 30 + i*15))

        self._text_cycles_ran = self._font.render(f"Clock cycles ran: {self.computer.clockcycles_ran:>10d}", True, self.TEXTGREY)

        uptime = time.time() - self._start_time
        hours = uptime/3600
        minutes = (hours - np.floor(hours))*60
        seconds = (minutes - np.floor(minutes))*60

        hours = int(np.floor(hours))
        minutes = int(np.floor(minutes))
        seconds = int(np.floor(seconds))

        self._text_uptime = self._font.render(f"Uptime: {hours:>02d}:{minutes:>02d}:{seconds:>02d}", True, self.TEXTGREY)

        self._screen.blit(self.clockrate, (5,5))
        self._screen.blit(self.fpstext, (100,5))
        self._screen.blit(self._text_cycles_ran, (280,5))
        self._screen.blit(self._loaded_program_text, (280,25))
        self._screen.blit(self._text_uptime, (280,45))

        if self.use_LCD_display: self.LCD_display.render(self._screen)

        pygame.display.flip()


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

        self.lettercolor = (220, 255, 220)
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
    import argparse, json
    parser = argparse.ArgumentParser(description="32-bit computer emulator (monitor UI)")
    parser.add_argument("program", nargs="?", default="program.txt", help="Program file to assemble and load")
    parser.add_argument("--fps", type=int, default=50, help="Target frames per second")
    parser.add_argument("--hz", type=int, default=25, help="Target clock frequency (Hz)")
    parser.add_argument("--lcd", action="store_true", default=True, help="Enable monitor display panel")
    parser.add_argument("--cpubits", type=int, default=32, help="CPU word size in bits")
    parser.add_argument("--stackbits", type=int, default=8, help="Stack pointer width in bits")
    parser.add_argument("--json", action="append", default=[], help="Path to JSON image to write into memory (can be repeated)")
    args = parser.parse_args()

    game = Game_32(True, args.fps, args.hz, progload=args.program, LCD_display=args.lcd,
                   cpubits=args.cpubits, stackbits=args.stackbits, json_images=args.json)
    game.execute()
    
