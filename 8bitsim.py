import time
import os
import sys

import pygame
from pygame.locals import *
import numpy as np


class Computer:
    def __init__(self):
        self.memory = np.zeros(256, dtype = np.uint16)

        # microcode definitions
        HLT = self.HLT = 0b100000000000000000000000 # Halt
        MI  = self.MI  = 0b010000000000000000000000 # Memory address in
        RI  = self.RI  = 0b001000000000000000000000 # RAM in
        RO  = self.RO  = 0b000100000000000000000000 # RAM out
        IAO = self.IAO = 0b000010000000000000000000 # Instruction A out
        IAI = self.IAI = 0b000001000000000000000000 # Instruction A in
        IBO = self.IBO = 0b000000100000000000000000 # Instruction B out
        IBI = self.IBI = 0b000000010000000000000000 # Instruction B in
        AI  = self.AI  = 0b000000001000000000000000 # Register A in
        AO  = self.AO  = 0b000000000100000000000000 # Register A out
        EO  = self.EO  = 0b000000000010000000000000 # Sum register out
        SU  = self.SU  = 0b000000000001000000000000 # Subtract
        BI  = self.BI  = 0b000000000000100000000000 # Register B in
        OI  = self.OI  = 0b000000000000010000000000 # Output in
        CE  = self.CE  = 0b000000000000001000000000 # Counter enable
        CO  = self.CO  = 0b000000000000000100000000 # Counter out
        JMP = self.JMP = 0b000000000000000010000000 # Jump
        FI  = self.FI  = 0b000000000000000001000000 # Flags in
        JC  = self.JC  = 0b000000000000000000100000 # Jump on carry
        JZ  = self.JZ  = 0b000000000000000000010000 # Jump on zero
        KEI = self.KEI = 0b000000000000000000001000 # Keyboard in

        self.assembly = {}
        for i in range(255):
            self.assembly[i] = []

        """ All operations begin with CO|MI -> RO|IAI|CE """
        self.assembly[0b00000000] = [] # NOP, 0
        self.assembly[0b00000001] = [CO|MI, RO|IBI|CE, IBO|MI, RO|AI]               # LDA, 1, load into A from mem
        self.assembly[0b00000010] = [CO|MI, RO|IBI|CE, IBO|MI, RO|BI, EO|AI|FI]     # ADD, 2, add to A
        self.assembly[0b00000011] = [CO|MI, RO|IBI|CE, IBO|MI, RO|BI, EO|AI|FI|SU]  # SUB, 3, subtract from A
        self.assembly[0b00000100] = [CO|MI, RO|IBI|CE, IBO|MI, AO|RI]               # STA, 4, store A to mem
        self.assembly[0b00000101] = [CO|MI, RO|IBI|CE, IBO|AI]                      # LDI, 5, load immediate (into A)
        self.assembly[0b00000110] = [CO|MI, RO|IBI|CE, IBO|JMP]                     # JMP, 6, jump
        self.assembly[0b00000111] = [CO|MI, RO|IBI|CE, IBO|JC]                      # JPC, 7, jump on carry
        self.assembly[0b00001000] = [CO|MI, RO|IBI|CE, IBO|JZ]                      # JPZ, 8, jump on zero
        self.assembly[0b00001001] = [KEI|AI]                                        # KEI, 9, loads keyboard input into A
        self.assembly[0b00001010] = [CO|MI, RO|IBI|CE, IBO|BI, EO|AI|FI]            # ADI, 10, add immediate to A
        self.assembly[0b00001011] = [CO|MI, RO|IBI|CE, IBO|BI, EO|AI|FI|SU]         # SUI, 11, sub immediate from A
        self.assembly[0b11111110] = [AO|OI]                                         # OUT, 254
        self.assembly[0b11111111] = [HLT]                                           # HLT, 255

        self.opcode_map = {"NOP": 0,
                           "LDA": 1,
                           "ADD": 2,
                           "SUB": 3,
                           "STA": 4,
                           "LDI": 5,
                           "JMP": 6,
                           "JPC": 7,
                           "JPZ": 8,
                           "KEI": 9,
                           "ADI": 10,
                           "SUI": 11,
                           "OUT": 254,
                           "HLT": 255,}

        self.programmer()
        self.reset()

    def programmer(self):
        with open("program.txt", "r") as infile:
            lines = infile.readlines()
        
        i = 0
        lines_history = []
        for k, line in enumerate(lines):
            line = line.strip().split("#")[0]
            items = line.strip().split(" ")[:2]
            lines_history.append([items, i - k])
            j = 0
            for item in items:
                j += 1
                i += 1

        i = 0
        for k, line in enumerate(lines):
            line = line.strip().split("#")[0]
            items = line.strip().split(" ")[:2]
            j = 0
            jump = False
            for item in items:
                if j == 0:
                    mem_ins = self.opcode_map[str(item)]
                    if 6 <= mem_ins <= 8:
                        # Jump instruction
                        jump = True
                else:
                    mem_ins = int(item)
                    if jump:
                        # shift jump x number of lines to account for
                        # instructions which take two memory locations
                        mem_ins += lines_history[mem_ins][1]
                self.memory[i] = mem_ins
                j += 1
                i += 1

        self.program = lines_history
        print(f"{i} words of memory used for program")
    
    def printstate(self, debug = True):
        d2b = self.dec2bin
        print(f"\n{self.prog_count}.{self.opcode}")
        if not debug:
            return
        print(f"         Bus: {d2b(self.bus)       :>08d} | Prog count: {d2b(self.prog_count):>08d}")
        print(f"Mem. address: {d2b(self.memaddress):>08d} |      A reg: {d2b(self.areg):>08d}")
        print(f"Mem. content: {d2b(self.memcontent):>08d} |    Sum reg: {d2b(self.sumreg):>08d} | Flag reg: {d2b(self.flagreg):>02d}")
        print(f"Inst. reg. A: {d2b(self.inst_reg_a):>08d} |      B reg: {d2b(self.breg):>08d}")
        print(f"Inst. reg. B: {d2b(self.inst_reg_b):>08d} |    Out reg: {d2b(self.out_regist):>08d}")
        print(f"Opcode:       {d2b(self.opcode)    :>08d} |  Ctrl word: {d2b(self.controlword):>024d}")
        print(f"                                     HMRRIIIIAAESBOCCJF")
        print(f"                                     LIIOAABBIOOUIIEOMI")
        print(f"                                     T   OIOI        P ")

    def reset(self):
        """ Initialize storage and registers """
        self.bus = 0
        self.areg = 0
        self.breg = 0
        self.sumreg = 0
        self.flagreg = 0
        self.flags = 0
        self.memaddress = 0
        self.memcontent = 0
        self.inst_reg_a = 0
        self.inst_reg_b = 0
        self.out_regist = 0
        self.prog_count = 0
        self.input_regi = 0
        self.opcode = 0
        self.controlword = 0
        self.halting = 0
        self.carry = 0
        self.zero = 0
        self.timer_indicator = 0

        self.memaddress = self.bus
        self.memcontent = self.memory[self.memaddress]

    def update_ALU(self, subtract = False):
        self.carry = 0
        self.zero = 0
        a = int(self.areg)
        b = int(self.breg)
        if subtract:
            self.sumreg = a - b
        else:
            self.sumreg = a + b

        while self.sumreg >= 256:
            self.sumreg -= 256
            self.carry = 1
        while self.sumreg < 0:
            self.sumreg += 256
            self.carry = 1
        if self.sumreg == 0:
            self.zero = 1

        self.flags = 0b0
        if self.carry:
            self.flags = self.flags|0b10
        if self.zero:
            self.flags = self.flags|0b01

    def update(self):
        """ Standard update cycle """
        if self.opcode == 0:
            operation = self.MI|self.CO
        elif self.opcode == 1:
            operation = self.RO|self.IAI|self.CE
        else:
            operation_ID = self.inst_reg_a
            operations = self.assembly[operation_ID]
            if self.opcode - 2 >= len(operations):
                operation = 0
            else:
                operation = operations[self.opcode - 2]

        self.controlword = operation

        if operation&self.IAO:
            self.bus = self.inst_reg_a

        if operation&self.IBO:
            self.bus = self.inst_reg_b

        if operation&self.RO:
            self.bus = self.memcontent

        if operation&self.AO:
            self.bus = self.areg

        if operation&self.SU:
            subtract = 1
        else:
            subtract = 0
        
        self.update_ALU(subtract)

        if operation&self.KEI:
            self.bus = self.input_regi

        if operation&self.EO:
            self.bus = self.sumreg

        if operation&self.CO:
            self.bus = self.prog_count

    def clock_high(self):
        """ Things that happen when the clock transitions to high """
        self.timer_indicator = 1
        if self.halting:
            return False

        operation = self.controlword

        if operation&self.HLT:
            self.halting = 1
        else:
            self.halting = 0

        if operation&self.FI:
            self.flagreg = self.flags

        if operation&self.MI:
            self.memaddress = self.bus
            self.memcontent = self.memory[self.memaddress]

        if operation&self.RI:
            self.memcontent = self.bus
            self.memory[self.memaddress] = self.memcontent

        if operation&self.IAI:
            self.inst_reg_a = self.bus

        if operation&self.IBI:
            self.inst_reg_b = self.bus

        if operation&self.AI:
            self.areg = self.bus

        if operation&self.BI:
            self.breg = self.bus

        if operation&self.OI:
            self.out_regist = self.bus

        if operation&self.CE:
            self.prog_count += 1

        if operation&self.JMP:
            self.prog_count = self.bus

        if operation&self.JC:
            if self.flagreg&0b10:
                self.prog_count = self.bus

        if operation&self.JZ:
            if self.flagreg&0b01:
                self.prog_count = self.bus

        return True

    def clock_low(self):
        """ Things that happen when the clock transitions to low """
        if self.halting:
            return
        self.timer_indicator = 0
        self.opcode += 1
        if self.opcode >= 8:
            self.opcode = 0

        if self.prog_count >= 256:
            self.halting = True

    def step(self):
        self.update()
        result = self.clock_high()
        self.printstate()
        self.clock_low()
        self.update()

        return result

    def dec2bin(self, dec_in):
        """ Takes a decimal number in and converts to binary integer """
        bin_out = int(bin(dec_in).replace("0b", ""))
        return bin_out

    def bin2dec(self, binary_in):
        """ Takes a binary integer in and converts to decimal number """
        dec_out = int(str(binary_in), 2)
        return dec_out


class BitDisplay:
    def __init__(self, oncolor = (0, 255, 0), offcolor = (0, 50, 0),
                 cpos = (0,0), length = 8, text = "Display",
                 font = None, textcolor = (255, 255, 255)):
        self.length = length
        self.text = text
        self.x = cpos[0]
        self.y = cpos[1]
        self.oncolor = oncolor
        self.offcolor = offcolor

        self.radius = 10
        self.separation = 5
        self.width = length*self.radius*2 + (length - 1)*self.separation

        if not font is None:
            self.text_rendered = font.render(self.text, True, textcolor)
        else:
            self.text_rendered = None

    def draw_bits(self, int_in, screen):
        self.xvalues = []
        bitstring = f"{int_in:d}"
        while len(bitstring) < self.length:
            bitstring = "0" + bitstring
        bitstring = bitstring[-self.length:]
        
        y = int(self.y)
        x = int(self.x - self.width/2 + self.radius)

        for bit_value in bitstring:
            if bit_value == "1":
                color = self.oncolor
            else:
                color = self.offcolor
            pygame.draw.circle(screen, color, (x,y), self.radius)
            self.xvalues.append(x)
            x += self.radius*2 + self.separation

        if self.text_rendered is not None:
            textwidth = self.text_rendered.get_width()
            textheight = self.text_rendered.get_height()
            text_x = int(self.x - textwidth/2)
            text_y = int((self.y - textheight/2 - self.radius - 10))
            screen.blit(self.text_rendered, (text_x, text_y))

    def draw_number(self, num_in, screen):
        bin_out = int(bin(num_in).replace("0b", ""))
        self.draw_bits(bin_out, screen)


class Game:
    def __init__(self, autorun = True, target_HZ = 300):
        self._running = True
        self._screen = None
        self._width = 1280
        self._height = 800
        self._size = (self._width, self._height)
        self.fps = 0
        self.step = 0

        self.autorun = autorun
        self.target_HZ = target_HZ # max ~ 400
        
        self.WHITE = (255, 255, 255)
        self.GREY = (115, 115, 115)
        self.DARKGREY = (20, 20, 20)
        self.RED = (255, 0, 0)
        self.DARKRED = (200, 0, 0)
        self.DARKERRED = (30, 0, 0)
        self.PURPLEISH = (150, 0, 255)
        self.DARKPURPLEISH = (50, 0, 150)
        self.DARKERPURPLEISH = (5, 0, 15)
        self.GREEN = (0, 255, 0)
        self.DARKGREEN = (0, 200, 0)
        self.DARKERGREEN = (0, 30, 0)
        self.BLUE = (0, 0, 255)
        self.DARKBLUE = (0, 0, 200)
        self.DARKERBLUE = (0, 0, 30)
        self.BLACK = (0, 0, 0)

    def init_game(self):
        pygame.init()
        pygame.display.set_caption("8 bit computer")

        self._screen = pygame.display.set_mode(self._size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self._running = True

        pygame.font.init()
        self._font_segmentdisplay = pygame.font.Font(os.path.join(os.getcwd(), "font", "28segment.ttf"), 80)
        self._font_small_console = pygame.font.SysFont("monospace", 11)
        self._font_small = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 11)
        self._font = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 16)
        self._font_large = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 25)
        self._font_larger = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 45)
        self._font_verylarge = pygame.font.Font(os.path.join(os.getcwd(), "font", "Amble-Bold.ttf"), 64)

        self._bg = pygame.Rect(0, 0, self._width, self._height)
        self._clock = pygame.time.Clock()

        self.computer = Computer()

        self.bus_display = BitDisplay(cpos = (640, 50),
                                      font = self._font,
                                      textcolor = self.BLACK,
                                      text = "Bus",
                                      oncolor = self.RED,
                                      offcolor = self.DARKERRED)
        
        self.cnt_display = BitDisplay(cpos = (840, 150),
                                      font = self._font,
                                      textcolor = self.BLACK,
                                      text = "Program counter",
                                      oncolor = self.GREEN,
                                      offcolor = self.DARKERGREEN)

        self.areg_display = BitDisplay(cpos = (840, 250),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "A register",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.breg_display = BitDisplay(cpos = (840, 450),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "B register",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.sreg_display = BitDisplay(cpos = (840, 350),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "ALU (sum)",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.flgr_display = BitDisplay(cpos = (1100, 350),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Flags register",
                                       length = 2,
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.flag_display = BitDisplay(cpos = (1000, 350),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Flags",
                                       length = 2,
                                       oncolor = self.BLUE,
                                       offcolor = self.DARKERBLUE)

        self.madd_display = BitDisplay(cpos = (440, 150),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Memory address",
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.mcon_display = BitDisplay(cpos = (440, 250),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Memory content",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.insa_display = BitDisplay(cpos = (440, 350),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Instruction register A",
                                       oncolor = self.BLUE,
                                       offcolor = self.DARKERBLUE)
        
        self.insb_display = BitDisplay(cpos = (440, 450),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Instruction register B",
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.oprt_display = BitDisplay(cpos = (440, 550),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Operation timestep",
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)
        
        self.inpt_display = BitDisplay(cpos = (440, 650),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Input register",
                                       oncolor = self.PURPLEISH,
                                       offcolor = self.DARKERPURPLEISH)

        self.outp_display = BitDisplay(cpos = (840, 550),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Output register",
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.ctrl_display = BitDisplay(cpos = (840, 700),
                                       font = self._font,
                                       textcolor = self.BLACK,
                                       text = "Control word",
                                       oncolor = self.BLUE,
                                       offcolor = self.DARKERBLUE,
                                       length = 24)

        self.clk_display = BitDisplay(cpos = (50, 50),
                                      font = self._font,
                                      textcolor = self.BLACK,
                                      text = "Clock",
                                      length = 1,
                                      oncolor = self.GREEN,
                                      offcolor = self.DARKERGREEN)

        ctrl_word_text = ["HLT", "MI", "RI", "RO", "IAO", "IAI", "IBO", "IBI",
                          "AI", "AO", "EO", "SU", "BI", "OI", "CE", "CO", "JMP",
                          "FI", "JC", "JZ", "KEI"]

        self.ctrl_word_text_rendered = []
        for text in ctrl_word_text:
            self.ctrl_word_text_rendered.append(self._font_small.render(text,
                                                                                True,
                                                                                self.BLACK))

        prog_texts_black = []
        prog_texts_green = []
        prog_offsets = []

        for i, instruction in enumerate(self.computer.program):
            if len(instruction[0]) == 1:
                instruction[0].append("")
            text = f"{i:>03d} {instruction[0][0]:>3s} {instruction[0][1]:>3s}"
            prog_texts_black.append(self._font_small_console.render(text, True, self.BLACK))
            prog_texts_green.append(self._font_small_console.render(text, True, self.DARKGREEN))
            prog_offsets.append(instruction[1])

        self.prog_texts_black = prog_texts_black
        self.prog_texts_green = prog_texts_green
        self.prog_offsets = prog_offsets
        self.display_op = 0
        
    def on_event(self, event):
        if event.type == pygame.QUIT:
            self._running = False

        self.keys_pressed = list(pygame.key.get_pressed())

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.computer.update()
                self.computer.clock_high()
                self.computer.printstate()

            if event.key == pygame.K_r:
                self.computer.reset()

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_RETURN:
                self.computer.clock_low()
                self.computer.update()

    def loop(self):
        numpad = self.keys_pressed[256:266]
        operators = self.keys_pressed[268:271]
        input_val = 0
        pressed = False
        if sum(numpad) > 0:
            key = np.argmax(numpad)
            input_val += key
            pressed = True
        if sum(operators) > 0:
            key = np.argmax(operators) + 4
            key = 2**key
            input_val += key
            pressed = True

        if pressed:
            input_val += 128

        self.computer.input_regi = input_val

        self.computer.update()
        if self.autorun:
            if self.step == 0:
                self.computer.clock_high()
            elif self.step == 1:
                self.computer.clock_low()

        self.step += 1
        if self.step == 2:
            self.step = 0

        self._clock.tick_busy_loop(int(self.target_HZ * 2))
        self.fps = self._clock.get_fps()
        self.clockrate = self._font.render(f"{int(self.fps/2):d} Hz", True, self.BLACK)

    def render(self):
        pygame.draw.rect(self._screen, self.WHITE, self._bg)
        self.clk_display.draw_number(self.computer.timer_indicator, self._screen)
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

        out_string = f"{self.computer.out_regist:>03d}"
        out_text = self._font_segmentdisplay.render(out_string, True, self.RED)
        screen_bg = pygame.Rect(980, 480, out_text.get_width() + 35, out_text.get_height() + 25)
        pygame.draw.rect(self._screen, self.DARKGREY, screen_bg, border_radius = 10)
        self._screen.blit(out_text, (1000, 500))

        self.ctrl_display.draw_number(self.computer.controlword, self._screen)
        for text, x_center in zip(self.ctrl_word_text_rendered, self.ctrl_display.xvalues):
            text_x = int(x_center - text.get_width()/2)
            text_y = int(self.ctrl_display.y + text.get_height())
            self._screen.blit(text, (text_x, text_y))

        operation = int("1" + "0"*self.computer.opcode)
        self.oprt_display.draw_bits(operation, self._screen)
        self._screen.blit(self.clockrate, (5,5))

        if self.computer.opcode == 0:
            self.display_op = self.computer.prog_count

        x = 10
        y = 80
        for i, item in enumerate(self.prog_texts_black):
            if self.display_op == i + self.prog_offsets[i]:
                item = self.prog_texts_green[i]
            self._screen.blit(item, (x, y))
            y += 15
            if y >= self._height - 20:
                y = 80
                x += 100

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
    if len(sys.argv) > 1:
        autorun = sys.argv[1]
        if autorun == "False":
            autorun = False
        else:
            autorun = True
    else:
        autorun = True
    if len(sys.argv) > 2:
        target_hz = int(sys.argv[2])
    else:
        target_hz = 200
    game = Game(autorun, target_hz)
    game.execute()
    