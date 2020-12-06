import time
import os
import sys

import pygame
from pygame.locals import *
import numpy as np


class Computer:
    def __init__(self, progload):
        self.memory = np.zeros(256, dtype = np.uint16)
        self.get_mem_strings()
        self.overflow_limit = 256
        self.stackpointer_start = 224
        self.bits_stackpointer = 4

        print(f"Stack range: {hex(self.stackpointer_start)} : {hex(self.stackpointer_start+ 2**self.bits_stackpointer)}")
        print(f"Stack size: {2**self.bits_stackpointer}")

        self.setup_instructions()
        self.assembler(progload)
        self.reset()

    def setup_instructions(self):
        """ Sets up control signals, microcode definitions and instruction
        definitions
        """
        # control signal definitions
        HLT = self.HLT = 0b10000000000000000000000000000000 # Halt
        MI  = self.MI  = 0b01000000000000000000000000000000 # Memory address in
        RI  = self.RI  = 0b00100000000000000000000000000000 # RAM in
        RO  = self.RO  = 0b00010000000000000000000000000000 # RAM out
        IAO = self.IAO = 0b00001000000000000000000000000000 # Instruction A out
        IAI = self.IAI = 0b00000100000000000000000000000000 # Instruction A in
        IBO = self.IBO = 0b00000010000000000000000000000000 # Instruction B out
        IBI = self.IBI = 0b00000001000000000000000000000000 # Instruction B in
        AI  = self.AI  = 0b00000000100000000000000000000000 # Register A in
        AO  = self.AO  = 0b00000000010000000000000000000000 # Register A out
        EO  = self.EO  = 0b00000000001000000000000000000000 # Sum register out
        SU  = self.SU  = 0b00000000000100000000000000000000 # Subtract
        BI  = self.BI  = 0b00000000000010000000000000000000 # Register B in
        OI  = self.OI  = 0b00000000000001000000000000000000 # Output in
        CE  = self.CE  = 0b00000000000000100000000000000000 # Counter enable
        CO  = self.CO  = 0b00000000000000010000000000000000 # Counter out
        JMP = self.JMP = 0b00000000000000001000000000000000 # Jump
        FI  = self.FI  = 0b00000000000000000100000000000000 # Flags in
        JC  = self.JC  = 0b00000000000000000010000000000000 # Jump on carry
        JZ  = self.JZ  = 0b00000000000000000001000000000000 # Jump on zero
        KEO = self.KEO = 0b00000000000000000000100000000000 # Keypad register out
        ORE = self.ORE = 0b00000000000000000000010000000000 # Reset operation counter
        INS = self.INS = 0b00000000000000000000001000000000 # Increment stack pointer
        DES = self.DES = 0b00000000000000000000000100000000 # Decrement stack pointer
        STO = self.STO = 0b00000000000000000000000010000000 # Stack pointer out
        RSA = self.RSA = 0b00000000000000000000000001000000 # Shift A right one time
        LSA = self.LSA = 0b00000000000000000000000000100000 # Shift A left one time
        DDI = self.DDI = 0b00000000000000000000000000010000 # LCD screen (Display) data in
        DCI = self.DCI = 0b00000000000000000000000000001000 # LCD screen (Display) control signals in


        self.microcodes = [HLT, MI, RI, RO, IAO, IAI, IBO, IBI, AI, AO, EO, SU, BI,
                           OI, CE, CO, JMP, FI, JC, JZ, KEO, ORE, INS, DES, STO,
                           RSA, LSA, DDI, DCI]
        self.microcode_labels = ["Halt", "M.Ad. in", "RAM in", "RAM out", "InstA O", "InstA I", "InstB O",
                                 "InstB I", "A in", "A out", "Sum out", "Sub", "B in",
                                 "Disp. I", "Counter", "Cntr. O", "Jump", "Flg. in", "Jmp Cry",
                                 "Jmp 0", "Inpt. O", "OpT rst", "Inc stk", "Dec stk", "Stk O",
                                 "Shft A-", "Shft A+", "DispD I", "DispC I"]
        
        self.assembly = {}
        for i in range(255):
            self.assembly[i] = []

        # instruction definitions
        """ All operations begin with CO|MI -> RO|IAI|CE """
        self.assembly[0b00000000] = [ORE] # NOP, 0
        self.assembly[0b00000001] = [CO|MI,         RO|MI|CE,       RO|AI|ORE]                                              # LDA   1       load into A from mem
        self.assembly[0b00000010] = [CO|MI,         RO|MI|CE,       RO|BI,              EO|AI|FI|ORE]                       # ADD   2       add to A
        self.assembly[0b00000011] = [CO|MI,         RO|MI|CE,       RO|BI,              EO|AI|FI|SU|ORE]                    # SUB   3       subtract from A
        self.assembly[0b00000100] = [CO|MI,         RO|MI|CE,       AO|RI|ORE]                                              # STA   4       store A to mem
        self.assembly[0b00000101] = [CO|MI,         RO|AI|CE|ORE]                                                           # LDI   5       load immediate (into A)
        self.assembly[0b00000110] = [CO|MI,         RO|JMP|CE|ORE]                                                          # JMP   6       jump
        self.assembly[0b00000111] = [CO|MI,         RO|JC|CE|ORE]                                                           # JPC   7       jump on carry
        self.assembly[0b00001000] = [CO|MI,         RO|JZ|CE|ORE]                                                           # JPZ   8       jump on zero
        self.assembly[0b00001001] = [KEO|AI|ORE]                                                                            # KEI   9       loads keyboard input into A
        self.assembly[0b00001010] = [CO|MI,         RO|BI|CE,       EO|AI|FI|ORE]                                           # ADI   10      add immediate to A
        self.assembly[0b00001011] = [CO|MI,         RO|BI|CE,       EO|AI|FI|SU|ORE]                                        # SUI   11      sub immediate from A
        self.assembly[0b00001100] = [CO|MI,         RO|MI|CE,       RO|BI,              FI|SU|ORE]                          # CMP   12      compare value from memory with A register. Set zf if equal, cf if A is GEQ
        self.assembly[0b00001101] = [STO|MI,        AO|RI|INS|ORE]                                                          # PHA   13      push value from A onto the stack                                                NOTE: increments the stack pointer
        self.assembly[0b00001110] = [DES,           STO|MI,         AI|RO|ORE]                                              # PLA   14      pull value from stack onto A                                                    NOTE: decrements the stack pointer
        self.assembly[0b00001111] = [STO|AI|ORE]                                                                            # LDS   15      load the value of the stack pointer into A
        self.assembly[0b00010000] = [CO|MI,         RO|IBI|CE,      STO|MI,         CO|RI|INS,          IBO|JMP|ORE]        # JSR   16      jump to subroutine                                                              NOTE: increments the stack pointer
        self.assembly[0b00010001] = [DES,           STO|MI,         RO|JMP|ORE]                                             # RET   17      return from subroutine                                                          NOTE: decrements the stack pointer
        self.assembly[0b00010010] = [DES,           STO|MI,         RO|MI,          AO|RI|ORE]                              # SAS   18      retrieve a memory address from stack and store the value of A into mem          NOTE: decrements the stack pointer
        self.assembly[0b00010011] = [DES,           STO|MI,         RO|MI,          AI|RO|ORE]                              # LAS   19      retrieve a memory address from stack and load the value from mem into A         NOTE: decrements the stack pointer
        self.assembly[0b00010100] = [CO|MI,         RO|MI|CE,       RO|BI|ORE]                                              # LDB   20      load into B from mem
        self.assembly[0b00010101] = [CO|MI,         RO|BI|CE,       FI|SU|ORE]                                              # CPI   21      compare immediate value with A register. Set zf if equal, cf if A is GEQ
        self.assembly[0b00010110] = [RSA|ORE]                                                                               # RSA   22      Shift A one position to the right (A = A//2)
        self.assembly[0b00010111] = [AO|BI,         EO|AI|FI|ORE]                                                           # LSA   23      Shift A one position to the left (A = A*2)
        self.assembly[0b00011000] = [CO|MI,         RO|IBI|CE,      IBO|DDI|ORE]                                            # DIS   24      load immediate (into display data)
        self.assembly[0b00011001] = [CO|MI,         RO|IBI|CE,      IBO|DCI|ORE]                                            # DIC   25      load immediate (into display control)
        self.assembly[0b00011010] = [CO|MI,         RO|IBI|CE,      IBO|MI,         RO|DDI|ORE]                             # LDD   26      load from mem (into display data)
        self.assembly[0b11111110] = [AO|OI|ORE]                                                                             # OUT   254     display the value from A on the output display
        self.assembly[0b11111111] = [HLT]                                                                                   # HLT   255     halt operation

        self.instruction_map = {"NOP": 0,
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
                                "CMP": 12,
                                "PHA": 13,
                                "PLA": 14,
                                "LDS": 15,
                                "JSR": 16,
                                "RET": 17,
                                "SAS": 18,
                                "LAS": 19,
                                "LDB": 20,
                                "CPI": 21,
                                "RSA": 22,
                                "LSA": 23,
                                "DIS": 24,
                                "DIC": 25,
                                "LDD": 26,
                                "OUT": 254,
                                "HLT": 255,}

    def assembler(self, progload):
        """ Assembles a program file into values in memory for the computer to
        run. See assembler docs for more info.

        Arguments:
        progload    -   filename to read program from, string
        """
        if not os.path.isfile(progload):
            print("Enter a valid file to read the program from.")
            raise IOError(f"Couldn't locate file: {progload}")

        try:
            with open(progload, "r") as infile:
                lines = infile.readlines()
        except Exception as e:
            print("Assembler couldn't read file:")
            raise e

        print(f"Assembling: {progload}")

        addresses = {}
        addresses_line = {}
        variables = {}
        program = []

        address = 0
        progline = 0
        s = ""
        print("First pass...")
        for i, line in enumerate(lines):
            line = line.split(";")[0]
            if line.startswith("  ") and line[2] != " " and line[2:] != "\n":
                """ Instruction line """
                instruction = line.strip().split(" ")
                if len(instruction) > 2:
                    operand = "".join(instruction[1:])
                    instruction[1] = operand
                    instruction = instruction[:2]

                program.append([instruction, address - progline])
                print(len(s)*" ", end = "\r")
                s = f"{instruction[0]} in address {address}"
                print(s, end = "\r")
                for item in instruction:
                    address += 1
                progline += 1
            elif not line.startswith(" "):
                if "=" in line:
                    var = False
                    try:
                        if line[0] == ".":
                            var = True
                        elif int(line[0]) in range(0, 10):
                            var = True
                    except ValueError:
                        pass

                    if var:
                        """ Variable """
                        line_ = line.strip().split("=")
                        memaddress = line_[0].strip()
                        memaddress = memaddress.replace(" ", "")
                        value = line_[1].strip()
                        terms_pos = memaddress.split("+")
                        val = 0
                        for t1 in terms_pos:
                            terms_neg = t1.split("-")
                            pos_val = terms_neg[0]
                            if pos_val[0] == ".":
                                """ Pointer variable """
                                val += variables[pos_val[1:]]
                            else:
                                val += int(pos_val)
                            for t2 in terms_neg[1:]:
                                if t2[0] == ".":
                                    """ Pointer variable """
                                    val -= variables[t2[1:]]
                                else:
                                    val -= int(t2)
                        memaddress = val

                        if '"' in value:
                            val_string = value.split('"')[1]
                            for i, item in enumerate(val_string):
                                self.memory[memaddress + i] = ord(item)
                        elif "'" in value:
                            val_string = value.split("'")[1]
                            for i, item in enumerate(val_string):
                                self.memory[memaddress + i] = ord(item)
                        else:
                            self.memory[memaddress] = int(value)
                    else:
                        """ Pointer variable """
                        line_ = line.strip().split("=")
                        varname = line_[0].strip()
                        if line_[1].strip()[0] == ".":
                            varvalue = variables[line_[1].strip()[1:]]
                        else:
                            varvalue = int(line_[1].strip())
                        variables[varname] = varvalue
                        print(len(s)*" ", end = "\r")
                        s = f"Pointer variable {varname:>20s} = {varvalue:>5d}"
                        print(s)
                elif ":" in line:
                    """ Labels """
                    address_name = line.strip().split(":")[0]
                    addresses[address_name] = address
                    addresses_line[address] = progline
                    print(len(s)*" ", end = "\r")
                    s = f"label {address_name:>20s} | address {address:>5d} | progline {progline:>5d}"
                    print(s)

        print(len(s)*" ", end = "\r")
        print("Second pass...")
        print("[" + " "*50 + "]", end = "\r")
        memaddress = 0
        for i, line in enumerate(program):
            jump = False
            items = line[0]
            for item in items:
                if item == items[0]: # item is instruction code
                    mem_ins = self.instruction_map[str(item)]
                    if 6 <= mem_ins <= 8 or 16 <= mem_ins <= 17:
                        # Jump instruction
                        jump = True
                else:                # item is operand
                    if jump:
                        if item[0] == "#":
                            address = item[1:]
                            program[i][0][1] = item[1:]
                        else:
                            address = addresses[item]
                            program[i][0][1] = str(addresses_line[addresses[item]])
                        mem_ins = int(address)
                    else:
                        terms_pos = item.split("+")
                        val = 0
                        for t1 in terms_pos:
                            terms_neg = t1.split("-")
                            pos_val = terms_neg[0]
                            if pos_val[0] == ".":
                                """ Pointer variable """
                                val += variables[pos_val[1:]]
                            else:
                                val += int(pos_val)
                            for t2 in terms_neg[1:]:
                                if t2[0] == ".":
                                    """ Pointer variable """
                                    val -= variables[t2[1:]]
                                else:
                                    val -= int(t2)
                        program[i][0][1] = str(val)
                        mem_ins = int(val)
                self.memory[memaddress] = mem_ins
                memaddress += 1
            half_pct = min(int((i + 1)/len(program)*50), 50)
            print("[" + "#"*half_pct + " "*(50 - half_pct) + "]", end = "\r")
        print("\nProgram assembled.")

        print(f"{memaddress} bytes of memory used for program.")
        self.program = program
    
    def get_mem_strings(self, rows = 16, rowlength = 16, space = True, textlength = 2):
        """ Compiles a list of strings with the memory contents of the computer
        for easy printing.

        Each element of the list is a string containing the first 16 bytes of
        memory.

        Returns:
        mem_strings -   list containing memory strings
        """
        mem_strings = []
        for i in range(rows):
            line = self.memory[i*rowlength:i*rowlength + rowlength]
            s = ""
            for j, item in enumerate(line):
                item = hex(item).replace("0x", "")
                while len(item) < textlength:
                    item = "0" + item
                s += f"{item} "
                if j == 7 and space:
                    s += " "

            mem_strings.append(s)
        self.mem_strings = mem_strings
        return mem_strings

    def reset(self):
        """ Initialize/reset registers """
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
        self.op_timestep = 0
        self.controlword = 0
        self.halting = 0
        self.carry = 0
        self.zero = 0
        self.stackpointer = 0
        self.timer_indicator = 0
        self.clockcycles_ran = 0
        self.screen_data = 0
        self.screen_control = 0

        self.memaddress = self.bus
        self.memcontent = self.memory[self.memaddress]

    def update_ALU(self):
        """ Updates the value stored in the ALU based on the current values in
        the A and B registers, and the subtract control signal.
        """
        self.carry = 0
        self.zero = 0
        a = int(self.areg)
        b = int(self.breg)

        maximum = self.overflow_limit

        if self.controlword&self.SU:
            self.sumreg = a + (maximum - b) # two's complement subtraction
                                            # in order to set carry flag
                                            # for subtractions where a >= b
        else:
            self.sumreg = a + b

        while self.sumreg >= maximum:
            self.sumreg -= maximum
            self.carry = 1
        while self.sumreg < 0:
            self.sumreg += maximum
            self.carry = 1
        if self.sumreg == 0:
            self.zero = 1

        self.flags = 0b0
        if self.carry:
            self.flags = self.flags|0b10
        if self.zero:
            self.flags = self.flags|0b01

    def update(self):
        """ Updates the value on the appropriate registers and bus.

        Any states that would update regardless of what the clock is doing
        should be updated here.
        """

        # get the appropriate control word based on the current instruction
        # and operation timestep
        if self.op_timestep == 0:
            operation = self.MI|self.CO
        elif self.op_timestep == 1:
            operation = self.RO|self.IAI|self.CE
        else:
            operation_ID = self.inst_reg_a
            operations = self.assembly[operation_ID]
            if self.op_timestep - 2 >= len(operations):
                operation = 0
            else:
                operation = operations[self.op_timestep - 2]
        self.controlword = operation

        if operation&self.IAO:
            self.bus = self.inst_reg_a

        if operation&self.IBO:
            self.bus = self.inst_reg_b

        if operation&self.RO:
            self.bus = self.memcontent

        if operation&self.AO:
            self.bus = self.areg
        
        self.update_ALU()

        if operation&self.KEO:
            self.bus = self.input_regi

        if operation&self.EO:
            self.bus = self.sumreg

        if operation&self.CO:
            self.bus = self.prog_count

        if operation&self.STO:
            self.bus = self.stackpointer + self.stackpointer_start

    def clock_high(self):
        """ Updates states that should update on clock-high pulse """
        if self.halting:
            return False
        self.timer_indicator = 1
        self.clockcycles_ran += 1

        operation = self.controlword

        if operation&self.HLT:
            self.halting = 1
        else:
            self.halting = 0

        if operation&self.FI:
            self.flagreg = self.flags

        if operation&self.MI:
            self.memaddress = self.bus
            self.memcontent = self.memory[int(self.memaddress)]

        if operation&self.RI:
            self.memcontent = self.bus
            self.memory[self.memaddress] = self.memcontent

        if operation&self.IAI:
            self.inst_reg_a = self.bus

        if operation&self.IBI:
            self.inst_reg_b = self.bus

        if operation&self.AI:
            self.areg = self.bus

        if operation&self.RSA:
            self.areg = self.areg // 2

        if operation&self.BI:
            self.breg = self.bus

        if operation&self.OI:
            self.out_regist = self.bus

        if operation&self.CE:
            self.prog_count += 1

        if operation&self.DDI:
            self.screen_data = self.bus

        if operation&self.DCI:
            self.screen_control = self.bus//(2**5)

        if operation&self.JMP:
            self.prog_count = self.bus

        if operation&self.JC:
            if self.flagreg&0b10:
                self.prog_count = self.bus

        if operation&self.JZ:
            if self.flagreg&0b01:
                self.prog_count = self.bus

        if operation&self.INS:
            self.stackpointer += 1
            if self.stackpointer >= 2**self.bits_stackpointer:
                self.stackpointer = 0

        if operation&self.DES:
            self.stackpointer -= 1
            if self.stackpointer < 0:
                self.stackpointer = 2**self.bits_stackpointer - 1

        return True

    def clock_low(self):
        """ Updates states that should update on clock-low pulse """
        if self.halting:
            return
        self.timer_indicator = 0
        self.op_timestep += 1
        if self.op_timestep >= 8 or self.controlword&self.ORE:
            self.op_timestep = 0

        if self.prog_count >= self.overflow_limit:
            self.halting = True

    def step(self):
        """ Steps the CPU one clock cycle forward """
        self.update()
        result = self.clock_high()
        self.update()
        self.clock_low()
        self.update()

        return result


class BitDisplay:
    """ Class for making LED displays """
    def __init__(self, oncolor = (0, 255, 0), offcolor = (0, 50, 0),
                 cpos = (0,0), length = 8, text = "Display",
                 font = None, textcolor = (255, 255, 255),
                 radius = 10):
        """ LED Display.
        If a Pygame font provided, the text to display above the LED's will be 
        rendered. LED's will be drawn with 5 pixels of separation between them.

        Arguments:
        oncolor     -   color of an LED when on     (R,G,B)
        offcolor    -   color of an LED when off    (R,G,B)
        cpos        -   center position of display  (x,y)
        length      -   number of LED's
        text        -   text to display above the LED display
        font        -   pygame font object
        textcolor   -   color of title text
        radius      -   radius of the LED's

        Attributes:
        length      -   see arguments
        text        -   see arguments
        x           -   center x position
        y           -   center y position
        cpos        -   see arguments
        oncolor     -   see arguments
        offcolor    -   see arguments
        radius      -   see arguments
        reg_bg      -   pygame rectangle object extending 5 pixels outside the
                        display on each side
        text_rendered - the rendered pygame text, if a font is provided
                        otherwise None


        """
        self.length = length
        self.text = text
        self.x = cpos[0]
        self.y = cpos[1]
        self.cpos = cpos
        self.oncolor = oncolor
        self.offcolor = offcolor

        self.radius = radius
        self._separation = 5
        if length > 8 and radius < 8:
            self._separation = 4
        if length > 16 and radius < 6:
            self._separation = 1
        self._width = length*self.radius*2 + (length - 1)*self._separation

        self.reg_bg = pygame.Rect(int(self.x - self._width/2 - 5),
                                  int(self.y - self.radius - 5),
                                  int(self._width + 10), int(self.radius*2 + 10))
        
        if not font is None:
            self.text_rendered = font.render(self.text, True, textcolor)
        else:
            self.text_rendered = None

    def draw_bits(self, int_in, screen):
        """ Draws the LED's with the bits on corresponding to the 1's in an
        integer. I.e. if the integer passed is 10000001, the first and last
        LED will be on and the others will be off (for length = 8).

        Also draws the title if self.text_rendered is not None.

        Arguments:
        int_in      -   The integer determining which LED's are on.
        screen      -   The Pygame surface to draw to.
        """
        self.xvalues = []
        bitstring = f"{int_in:d}"
        while len(bitstring) < self.length:
            bitstring = "0" + bitstring
        bitstring = bitstring[-self.length:]
        
        y = int(self.y)
        x = int(self.x - self._width/2 + self.radius)

        for bit_value in bitstring:
            if bit_value == "1":
                color = self.oncolor
            else:
                color = self.offcolor
            pygame.draw.circle(screen, color, (x,y), self.radius)
            self.xvalues.append(x)
            x += self.radius*2 + self._separation

        if self.text_rendered is not None:
            textwidth = self.text_rendered.get_width()
            textheight = self.text_rendered.get_height()
            text_x = int(self.x - textwidth/2)
            text_y = int((self.y - textheight/2 - self.radius - 20))
            screen.blit(self.text_rendered, (text_x, text_y))

    def draw_number(self, num_in, screen):
        """ Draws the LED screen with the bits on corresponding to a decimal
        value. I.e. if 170 is passed (10101010 in binary), every other LED
        will be on, beginning with the topmost bit (for length = 8).

        Arguments:
        num_in      -   The number determining which LED's are on.
        screen      -   The Pygame surface to draw to.        
        """
        bin_out = int(bin(int(num_in)).replace("0b", ""))
        self.draw_bits(bin_out, screen)

    @property
    def width(self):
        return self._width


class Game:
    """ Main control class. Handles rendering, timing control and user input. """
    def __init__(self, autorun = True, target_FPS = 300, target_HZ = None,
                 draw_mem = False, draw_ops = False, progload = "program.txt",
                 LCD_display = False):
        self._running = True
        self._screen = None
        self._width = 1600
        self._height = 900
        self._size = (self._width, self._height)
        self.fps = 0
        self.step = 0
        self.cyclecounts = 0
        self.progload = progload
        self.use_LCD_display = LCD_display
        self.cpubits = 8
        self.stackbits = 4

        self.autorun = autorun
        self.target_FPS = target_FPS
        if target_HZ is None:
            self.target_HZ = target_FPS
        else:
            self.target_HZ = target_HZ
        self.HZ_multiplier = max(int(target_HZ/target_FPS), 0)
        self.draw_mem = draw_mem
        self.draw_ops = draw_ops
        self.op_address_draw = 0

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

    def make_static_graphics(self):
        # Draw line connections
        self.simple_line(self.bus_display, (self.bus_display.x, self.inpt_display.y), self.DARKRED)
        self.simple_line(self.madd_display, (self.bus_display.x, self.madd_display.y), self.DARKRED)
        self.simple_line(self.mcon_display, (self.bus_display.x, self.mcon_display.y), self.DARKRED)
        self.simple_line(self.insa_display, (self.bus_display.x, self.insa_display.y), self.DARKRED)
        self.simple_line(self.insb_display, (self.bus_display.x, self.insb_display.y), self.DARKRED)
        self.simple_line(self.oprt_display, (self.bus_display.x, self.oprt_display.y), self.DARKRED)
        self.simple_line(self.inpt_display, (self.bus_display.x + 2, self.inpt_display.y), self.DARKRED)
        self.simple_line(self.cnt_display, (self.bus_display.x, self.cnt_display.y), self.DARKRED)
        self.simple_line(self.areg_display, (self.bus_display.x, self.areg_display.y), self.DARKRED)
        self.simple_line(self.breg_display, (self.bus_display.x, self.breg_display.y), self.DARKRED)
        self.simple_line(self.sreg_display, (self.bus_display.x, self.sreg_display.y), self.DARKRED)
        self.simple_line(self.outp_display, (self.bus_display.x, self.outp_display.y), self.DARKRED)
        self.simple_line(self.stap_display, (self.bus_display.x, self.stap_display.y), self.DARKRED)
        self.simple_line(self.flag_display, self.flgr_display, self.DARKRED)

        self.simple_line(self.madd_display, self.mcon_display, self.DARKBLUE, (85,0), (85,0))
        self.simple_line(self.areg_display, self.breg_display, self.DARKBLUE, (65,0), (65,0))
        self.simple_line(self.sreg_display, self.flag_display, self.DARKBLUE)
        self.simple_line(self.outp_display, self.outp_display, self.DARKBLUE, (200, 0))

        self.simple_line(self.oprt_display, self.oprt_display, self.PURPLEISH, (-130, 0))
        self.simple_line(self.insa_display, self.insa_display, self.PURPLEISH, (-130, 0))
        self.simple_line(self.insa_display, (self.insa_display.x - 130, self.ctrl_display.y), self.PURPLEISH, (-130, -2))
        self.simple_line((self.insa_display.x - 132, self.ctrl_display.y), self.ctrl_display, self.PURPLEISH)

        self.simple_line(self.ctrl_display, self.madd_display, self.DARKKGREEN, (-650, -47), (-140, -2))
        self.simple_line(self.ctrl_display, self.ctrl_display, self.DARKKGREEN, (-652, -47), (-240, -47))
        self.simple_line(self.madd_display, self.madd_display, self.DARKKGREEN, (-140, 0))
        self.simple_line(self.mcon_display, self.mcon_display, self.DARKKGREEN, (-140, 0))
        self.simple_line(self.insa_display, self.insa_display, self.DARKKGREEN, (-140, -5), (0, -5))
        self.simple_line(self.insb_display, self.insb_display, self.DARKKGREEN, (-140, 0))
        self.simple_line(self.inpt_display, self.inpt_display, self.DARKKGREEN, (-140, 0))
        self.simple_line(self.oprt_display, self.oprt_display, self.DARKKGREEN, (-140, -5), (0, -5))
        
        self.simple_line(self.ctrl_display, self.cnt_display, self.DARKKGREEN, (-240, 0), (-130, -7))
        self.simple_line(self.cnt_display, self.cnt_display, self.DARKKGREEN, (0, -5), (-130, -5))
        self.simple_line(self.areg_display, self.areg_display, self.DARKKGREEN, (0, -5), (-130, -5))
        self.simple_line(self.breg_display, self.breg_display, self.DARKKGREEN, (0, -5), (-130, -5))
        self.simple_line(self.sreg_display, self.sreg_display, self.DARKKGREEN, (0, -5), (-130, -5))
        self.simple_line(self.outp_display, self.outp_display, self.DARKKGREEN, (0, -5), (-130, -5))
        self.simple_line(self.stap_display, self.stap_display, self.DARKKGREEN, (0, -5), (-130, -5))

        self.simple_line(self.flgr_display, self.flgr_display, self.DARKKGREEN, (0, 0), (52, 0))
        self.simple_line(self.flgr_display, (self.flgr_display.x + 50, self.ctrl_display.y), self.DARKKGREEN, (50, 0))

        pygame.draw.rect(self._bg, (0,0,0), self.bus_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.cnt_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.areg_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.breg_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.sreg_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.flgr_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.flag_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.madd_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.mcon_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.insa_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.insb_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.inpt_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.oprt_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.outp_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.ctrl_display.reg_bg, border_radius = 12)
        pygame.draw.rect(self._bg, (0,0,0), self.stap_display.reg_bg, border_radius = 12)
        if self.use_LCD_display: 
            pygame.draw.rect(self._bg, (0,0,0), self.disd_display.reg_bg, border_radius = 12)
            pygame.draw.rect(self._bg, (0,0,0), self.disc_display.reg_bg, border_radius = 12)
        #pygame.draw.rect(self._bg, (0,0,0), self.clk_display.reg_bg, border_radius = 10)

        self.keypad1 = BitDisplay(cpos = (1100, 50), length = 3, radius = 15,
                                  offcolor = (40, 40, 40), oncolor = (80, 120, 80))
        self.keypad2 = BitDisplay(cpos = (1100, 85), length = 3, radius = 15,
                                  offcolor = (40, 40, 40), oncolor = (80, 120, 80))
        self.keypad3 = BitDisplay(cpos = (1100, 120), length = 3, radius = 15,
                                  offcolor = (40, 40, 40), oncolor = (80, 120, 80))
        self.keypad4 = BitDisplay(cpos = (1100, 165), length = 3, radius = 15,
                                  offcolor = (40, 40, 40), oncolor = (80, 120, 80))
        self.keypad0 = BitDisplay(cpos = (1030, 120), length = 1, radius = 15,
                                  offcolor = (40, 40, 40), oncolor = (80, 120, 80))
        self.keypad_div = BitDisplay(cpos = (1030, 165), length = 1, radius = 15,
                                  offcolor = (40, 40, 40), oncolor = (80, 120, 80))

        keypad_bg = pygame.Rect(self.keypad_div.x - 30, self.keypad1.y - 30,
                                self.keypad1.width + self.keypad_div.width + 35,
                                self.keypad_div.y - self.keypad1.y + 60)
        pygame.draw.rect(self._bg, self.BLACK, keypad_bg, border_radius = 30)

        self.keypad_rows = [self.keypad1, self.keypad2, self.keypad3, self.keypad4]
        self.keypad_numbers = [0, 0, 0, 0]
        self.keypad = np.zeros((4,3))
        self.keypad_zero_pressed = 0
        self.keypad_div_pressed = 0

        keypad_symbols = ["7", "8", "9", "4", "5", "6", "1", "2", "3", "+", "-", "*"]
        self.keypad_texts_rendered = []
        for text in keypad_symbols:
            self.keypad_texts_rendered.append(self._font_small.render(text,
                                                                      True,
                                                                      self.WHITE))
        self.keypad_texts_0 = self._font_small.render("0", True, self.WHITE)
        self.keypad_texts_div = self._font_small.render("/", True, self.WHITE)

        ctrl_word_text = ["HLT", "MI", "RI", "RO", "IAO", "IAI", "IBO", "IBI",
                          "AI", "AO", "EO", "SU", "BI", "OI", "CE", "CO", "JMP",
                          "FI", "JC", "JZ", "KEO", "ORE", "INS", "DES", "STO",
                          "RSA", "LSA", "DDI", "DCI"]

        self.ctrl_word_text_rendered = []
        for text in ctrl_word_text:
            self.ctrl_word_text_rendered.append(self._font_small.render(text,
                                                                        True,
                                                                        self.TEXTGREY))

        prog_texts_black = []
        prog_texts_green = []
        prog_offsets = []

        for i, instruction in enumerate(self.computer.program):
            if len(instruction[0]) == 1:
                instruction[0].append("")
            text = f"{i:>03d} {instruction[0][0]:>3s} {instruction[0][1]:>3s}"
            prog_texts_black.append(self._font_small_console.render(text,
                                                                    True,
                                                                    self.GREY))
            prog_texts_green.append(self._font_small_console.render(text,
                                                                    True,
                                                                    self.DARKGREEN))
            prog_offsets.append(instruction[1])

        self.prog_texts_black = prog_texts_black
        self.prog_texts_green = prog_texts_green
        self.prog_offsets = prog_offsets
        self.display_op = 0

        self.memory_title = self._font_exobold.render("Memory:", True, self.TEXTGREY)
        self.microins_title = self._font_exobold.render("Current instruction:", True, self.TEXTGREY)

        self.helptext_1 = "Press 'D' for debug mode.   Press 'C' to end debug mode.   Press 'M' to show/hide memory.   Press 'N' to show/hide microinstruction list.   Press 'R' for reset (won't clear RAM)."
        self.helptext_rendered = self._font_exobold_small.render(self.helptext_1, True, self.TEXTGREY)
        self._bg.blit(self.helptext_rendered, (300, self._height - 50))
        self.helptext_2 = "Press the spacebar to stop automatic execution.   Press the enter key to cycle the clock manually when automatic execution is stopped.   Press the numbers on your numpad to change the HZ target."
        self.helptext_rendered = self._font_exobold_small.render(self.helptext_2, True, self.TEXTGREY)
        self._bg.blit(self.helptext_rendered, (300, self._height - 30))

        self.LCD_display = LCD_display(self._font_console_bold, position = (1210, 500))

        prog_text = "".join(self.progload.split('.')[:-1])
        if prog_text[:1] == "\\":
            prog_text = prog_text[1:]
        self._loaded_program_text = self._font.render(f"Loaded program: {prog_text}", True, self.TEXTGREY)

    def init_game(self):
        pygame.init()
        pygame.display.set_caption("8 bit computer")

        self._screen = pygame.display.set_mode(self._size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self._running = True
        
        self.setup_fonts()

        self._bg = pygame.Surface(self._size)
        self._bg.fill((20, 20, 20))
        self._clock = pygame.time.Clock()

        self.computer = Computer(self.progload)

        self.bus_display = BitDisplay(cpos = (640, 50),
                                      font = self._font_exobold,
                                      textcolor = self.TEXTGREY,
                                      text = "Bus",
                                      oncolor = self.RED,
                                      offcolor = self.DARKERRED)

        self.cnt_display = BitDisplay(cpos = (840, 150),
                                      font = self._font_exobold,
                                      textcolor = self.TEXTGREY,
                                      text = "Program counter",
                                      oncolor = self.GREEN,
                                      offcolor = self.DARKERGREEN)

        self.areg_display = BitDisplay(cpos = (840, 250),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "A register",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.breg_display = BitDisplay(cpos = (840, 450),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "B register",
                                       oncolor = self.RED,
                                       offcolor = self.DARKERRED)

        self.sreg_display = BitDisplay(cpos = (840, 350),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "ALU (sum)",
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
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.mcon_display = BitDisplay(cpos = (440, 250),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Memory content",
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
                                       oncolor = self.GREEN,
                                       offcolor = self.DARKERGREEN)

        self.stap_display = BitDisplay(cpos = (840, 650),
                                       font = self._font_exobold,
                                       textcolor = self.TEXTGREY,
                                       text = "Stack pointer",
                                       length = 4,
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
        for i in range(16):
            text = f"{i:>02d} "
            if i == 7:
                text += " "
            memcolumn += text

            rowtext = f"{i*16:>03d}"
            self.memrows.append(self._font_small_console_bold.render(rowtext, True, self.TEXTGREY))
        
        self.memcolumn = self._font_small_console_bold.render(memcolumn, True, self.TEXTGREY)

        self._start_time = time.time()

    def simple_line(self, pos1, pos2, color, shift1 = (0,0), shift2 = (0,0), width = 5):
        """ Draws a simple line to display connections between registers to the
        background image.

        pos1 and pos2 can be either a position (iterable with length 2), or an
        instance of BitDisplay, in which case the center position of the
        display will be used.
        """
        if isinstance(pos1, BitDisplay):
            pos1 = pos1.cpos
        if isinstance(pos2, BitDisplay):
            pos2 = pos2.cpos

        pygame.draw.line(self._bg, color,
                         np.array(pos1) + shift1,
                         np.array(pos2) + shift2,
                         width = width)

    def check_display_press(self, display, overlaytext):
        """ Checks if a (1 length) LED display object is pressed with the left
        mouse button. Also displays the LED.
        Returns 1 if pressed, 0 if not.
        """
        pressed = 0
        x = display.x
        y = display.y
        mouse_dist = (self.mouse_pos[0] - x)**2 + (self.mouse_pos[1] - y)**2
        if mouse_dist < self.keypad0.radius**2:
            if pygame.mouse.get_pressed()[0]:
                pressed = 1
        text_x = x - overlaytext.get_width() / 2
        text_y = y - overlaytext.get_height() / 2
        display.draw_number(pressed, self._screen)
        self._screen.blit(overlaytext, (text_x, text_y))

        return pressed

    def update_LCD_display(self):
        self.LCD_display.set_data_lines(self.computer.screen_data)
        self.LCD_display.set_control_bits(self.computer.screen_control*2**5)

    def on_event(self, event):
        if event.type == pygame.QUIT:
            self._running = False

        self.keys_pressed = list(pygame.key.get_pressed())

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.computer.reset()
            if event.key == pygame.K_m:
                if self.draw_mem:
                    self.draw_mem = False
                else:
                    self.draw_mem = True
            if event.key == pygame.K_n:
                if self.draw_ops:
                    self.draw_ops = False
                else:
                    self.draw_ops = True
            if event.key == pygame.K_d:
                # debug mode
                self.draw_mem = True
                self.draw_ops = True
            if event.key == pygame.K_c:
                # clean mode (no debug)
                self.draw_mem = False
                self.draw_ops = False

            if event.key == pygame.K_KP_PLUS:
                self.target_HZ = int(self.target_HZ*2)
            if event.key == pygame.K_KP_MINUS:
                self.target_HZ = max(int(self.target_HZ/2), 1)
            if event.key == pygame.K_KP1:
                self.target_HZ = int(target_fps/5)
            elif event.key == pygame.K_KP2:
                self.target_HZ = int(target_fps/4)
            elif event.key == pygame.K_KP3:
                self.target_HZ = int(target_fps/3)
            elif event.key == pygame.K_KP4:
                self.target_HZ = int(target_fps/2)
            elif event.key == pygame.K_KP5:
                self.target_HZ = int(target_fps)
            elif event.key == pygame.K_KP6:
                self.target_HZ = int(target_fps*2)
            elif event.key == pygame.K_KP7:
                self.target_HZ = int(target_fps*4)
            elif event.key == pygame.K_KP8:
                self.target_HZ = int(target_fps*10)
            elif event.key == pygame.K_KP9:
                self.target_HZ = int(target_fps*100)
            elif event.key == pygame.K_KP0:
                self.target_HZ = int(target_fps*100000)

            if not self.autorun:
                if event.key == pygame.K_RETURN:
                    self.computer.update()
                    self.computer.clock_high()
                    if self.use_LCD_display: self.update_LCD_display()

                if event.key == pygame.K_SPACE:
                    self.autorun = True
            else:
                if event.key == pygame.K_SPACE:
                    self.autorun = False

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_RETURN and not self.autorun:
                self.computer.clock_low()
                self.computer.update()
                if self.use_LCD_display: self.update_LCD_display()

    def loop(self):
        self.mouse_pos = np.array(pygame.mouse.get_pos())
        keypressed = np.where(self.keypad == 1)

        input_val = 0
        if np.sum(self.keypad) != 0:
            rowpressed = keypressed[0][0]
            colpressed = keypressed[1][0]
            if rowpressed < 3:
                input_val = 3*(2 - rowpressed) + colpressed + 1
            else:
                input_val = 2**(6 - colpressed)

            input_val += 128

        if self.keypad_zero_pressed:
            input_val = 128

        if self.keypad_div_pressed:
            input_val = 224

        self.computer.input_regi = input_val

        HZ_multiplier = self.HZ_multiplier
        if self.target_HZ >= self.target_FPS:
            for i in range(HZ_multiplier):
                self.computer.update()
                if self.autorun:
                    self.computer.clock_high()
                    self.computer.update()
                    if self.use_LCD_display: self.update_LCD_display()
                    self.computer.clock_low()
        else:
            frames_per_cycle = self.target_FPS/self.target_HZ
            self.computer.update()
            if self.step%int(frames_per_cycle) == 0:
                if self.autorun:
                    self.computer.clock_high()
                    self.computer.update()
                    if self.use_LCD_display: self.update_LCD_display()
                    self.computer.clock_low()
                    self.cyclecounts += 1
        
        if self.draw_mem:
            self.computer.get_mem_strings()

        self.step += 1
        if self.step >= self.fps:
            self.step = 0
            if self.target_HZ < self.target_FPS:
                self.clockrate = self._font.render(f"{int(self.cyclecounts):d} Hz", True, self.TEXTGREY)
            self.cyclecounts = 0

        """ Adjust multiplier to reach FPS and as good as possible HZ """
        self._clock.tick_busy_loop(self.target_FPS)
        self.fps = self._clock.get_fps()
        HZ = self.fps*HZ_multiplier
        if self.fps < self.target_FPS or HZ > self.target_HZ:
            if HZ_multiplier > 1:
                HZ_multiplier -= 1
        elif HZ < self.target_HZ:
            HZ_multiplier += 1

        self.HZ_multiplier = HZ_multiplier
        if self.target_HZ >= self.target_FPS:
            self.clockrate = self._font.render(f"{int(self.fps*HZ_multiplier):d} Hz", True, self.TEXTGREY)
        self.fpstext = self._font.render(f"{int(self.fps):d} FPS", True, self.TEXTGREY)

    def draw_memory(self):
        memwidth = self.memcolumn.get_width()
        titlewidth = self.memory_title.get_width()
        x = 1240
        y = 57
        self._screen.blit(self.memory_title, (x + memwidth/2 - titlewidth/2, 5))
        self._screen.blit(self.memcolumn, (x, y - 18))
        for i, item in enumerate(self.computer.mem_strings):
            out_text = self._font_small_console.render(item, True, self.TEXTGREY)
            self._screen.blit(out_text, (x, y))
            self._screen.blit(self.memrows[i], (x - 32, y))
            y += 15

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

        """ Draw and check the numpad buttons for input """
        i = 0
        for kp, num in zip(self.keypad_rows, self.keypad_numbers):
            kp.draw_number(num, self._screen)
            self.keypad_numbers[i] = 0
            i += 1

        self.keypad_zero_pressed = self.check_display_press(self.keypad0,
                                                            self.keypad_texts_0)
        self.keypad_div_pressed = self.check_display_press(self.keypad_div,
                                                           self.keypad_texts_div)
        
        self.keypad[:,:] = 0
        for i, kp_text in enumerate(self.keypad_texts_rendered):
            column = i%3
            row = i//3
            kp = self.keypad_rows[row]
            x = kp.xvalues[column]
            y = kp.y
            mouse_dist = (self.mouse_pos[0] - x)**2 + (self.mouse_pos[1] - y)**2
            if mouse_dist < kp.radius**2:
                if pygame.mouse.get_pressed()[0]:
                    self.keypad_numbers[row] = 2**(2 - column)
                    self.keypad[row, column] = 1
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

        """ Draw the program """
        x = 10
        y = 30
        for i, item in enumerate(self.prog_texts_black):
            if self.display_op == i + self.prog_offsets[i]:
                item = self.prog_texts_green[i]
            self._screen.blit(item, (x, y))
            y += 15
            if y >= self._height - 20:
                y = 30
                x += 95

        """ Draw the memory """
        if self.draw_mem:
            self.draw_memory()

        """ Draw the operations included in the current instruction """
        if self.draw_ops:
            self._screen.blit(self.microins_title, (1180, 620))
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
                    self._screen.blit(self.arrow, (1170, 650 + i*15))
                out_text = self._font_small_console.render(s[:-2], True, self.TEXTGREY)
                self._screen.blit(out_text, (1180, 650 + i*15))

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


class LCD_display:
    def __init__(self, font, position = (0, 0)):
        self.size = np.array((16, 2))
        self.data = 0
        self.control = 0
        self.previous_enable = 0
        self.cursor_pos = 0
        self.cursoron = False
        self.cursordraw = False
        self.cursorblink = False
        self.position = position # top left
        self.font = font
        self.time = time.time()
        self.cursor_dir = 1
        self.shift = 0
        self.shifting = 0

        self.lettercolor = (0, 0, 0)
        self.bgcolor = (210, 235, 100)

        self.cursor = self.font.render("_", True, self.lettercolor)

        symbol = font.render("0", True, self.lettercolor)
        self.symbolheight = symbol.get_height()
        self.symbolwidth = symbol.get_width()

        self.pixelsize = self.size*(self.symbolwidth + 4, self.symbolheight + 4)
        
        self.bg_rect = pygame.Rect(self.position[0], self.position[1],
                                   self.pixelsize[0], self.pixelsize[1])

        self.bg_border = pygame.Rect(self.position[0] - 5, self.position[1] - 5,
                                     self.pixelsize[0] + 10, self.pixelsize[1] + 10)

        self.memory = np.zeros(128, dtype = int)

    def enable_set(self):
        if 0b01000000 & self.control:
            if 0b10000000 & self.control:
                """ Read """
                self.memory[self.cursor_pos] = self.data
                if self.cursor_dir == 1:
                    self.cursor_pos += 1
                    if self.shifting:
                        self.shift += 1
                else:
                    self.cursor_pos -= 1
                    if self.shifting:
                        self.shift -= 1
        else:
            if   0b10000000 & self.data:
                pass
            elif 0b01000000 & self.data:
                pass
            elif 0b00100000 & self.data:
                pass
            elif 0b00010000 & self.data:
                """ Cursor and shift control """
                if int(bin(self.data)[-4]):
                    if int(bin(self.data)[-3]):
                        self.shift += 1
                    else:
                        self.shift -= 1
                else:
                    if self.cursor_dir == 1:
                        self.cursor_pos += 1
                    else:
                        self.cursor_pos -= 1
            elif 0b00001000 & self.data:
                """ Display on/off control
                    Always on
                """
                self.cursoron = int(bin(self.data)[-2])
                self.cursorblink = int(bin(self.data)[-1])
            elif 0b00000100 & self.data:
                """ Entry mode set """
                self.cursor_dir = int(bin(self.data)[-2])
                self.shifting = int(bin(self.data)[-1])
            elif 0b00000010 & self.data:
                """ Return home """
                self.cursor_pos = 0
                self.shift = 0
            elif 0b00000001 & self.data:
                """ Clear display """

                self.memory[:] = 0
                self.cursor_pos = 0
                self.shift = 0

    def set_data_lines(self, value):
        self.data = value

    def set_control_bits(self, value):
        self.control = value

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

        row1 = self.memory[0:40]
        row2 = self.memory[64:104]

        row1 = np.roll(row1, self.shift)
        row2 = np.roll(row2, self.shift)

        for i, val1 in enumerate(row1[:16]):
            val2 = row2[i]
            vals = [val1, val2]
            x = 1 + (self.symbolwidth + 4)*i + self.position[0]
            for j, val in enumerate(vals):
                y = 2 + (self.symbolheight + 4)*j + self.position[1]

                character = chr(val)
                try:
                    text = self.font.render(character, True, self.lettercolor)
                    screen.blit(text, (x, y))
                except ValueError as e:
                    pass # null characters aren't drawn

                if self.cursordraw and self.cursoron:
                    if (self.cursor_pos + self.shift) == i + 64*j:
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
        if sys.argv[4].lower() == "true":
            lcd = True
        else:
            lcd = False
    else:
        lcd = False

    game = Game(True, target_fps, target_HZ, progload = progload, LCD_display = lcd)
    game.execute()
    