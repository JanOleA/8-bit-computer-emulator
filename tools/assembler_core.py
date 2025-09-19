"""
Lightweight assembler helpers that do not import pygame.

Exposes:
- build_instruction_map(): returns mnemonic→opcode mapping
- assemble_lines(lines, memory, instruction_map): assembles the given lines into memory, returns program metadata
"""

from typing import List, Dict, Tuple


def build_instruction_map() -> Dict[str, int]:
    # Keep in sync with cpu_sim.Computer.setup_instructions and get_mnemonic_n.easm
    return {
        "NOP":   0,
        "LDA":   1,
        "ADD":   2,
        "SUB":   3,
        "STA":   4,
        "LDI":   5,
        "JMP":   6,
        "JPC":   7,
        "JPZ":   8,
        "KEI":   9,
        "ADI":   10,
        "SUI":   11,
        "CMP":   12,
        "PHA":   13,
        "PLA":   14,
        "LDS":   15,
        "JSR":   16,
        "RET":   17,
        "SAS":   18,
        "LAS":   19,
        "LDB":   20,
        "CPI":   21,
        "RSA":   22,
        "LSA":   23,
        "DIS":   24,
        "DIC":   25,
        "LDD":   26,
        "JNZ":   27,
        "STB":   28,
        "MOVBA": 29,
        "MOVAB": 30,
        "LSP":   31,
        "MVASP": 32,
        "MVBSP": 33,
        "SUM":   34,
        "LAP":   35,
        "LPA":   36,
        "DIA":   37,
        "OUT":   254,
        "HLT":   255,
    }


def assemble_lines(lines: List[str], memory: List[int], instruction_map: Dict[str, int]):
    addresses: Dict[str, int] = {}
    addresses_line: Dict[int, int] = {}
    variables: Dict[str, int] = {}
    program: List[Tuple[List[str], int]] = []

    address = 0
    progline = 0

    # First pass: collect variables and labels, build program list
    for i, line in enumerate(lines):
        line = line.split(";")[0]
        if line.replace(" ", "") == "":
            continue

        if line.startswith("  ") and line[2] != " " and line[2:] != "\n":
            # Instruction line
            instruction = line.strip().split(" ")
            if len(instruction) > 2:
                operand = "".join(instruction[1:])
                instruction[1] = operand
                instruction = instruction[:2]

            program.append([instruction, address - progline])
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
                    # Variable write into memory
                    line_ = line.strip().split("=")
                    memaddress = line_[0].strip().replace(" ", "")
                    value = line_[1].strip()
                    # Evaluate address expression with + and - and pointer vars
                    terms_pos = memaddress.split("+")
                    val = 0
                    for t1 in terms_pos:
                        terms_neg = t1.split("-")
                        pos_val = terms_neg[0]
                        if pos_val[0] == ".":
                            val += variables[pos_val[1:]]
                        else:
                            val += int(pos_val)
                        for t2 in terms_neg[1:]:
                            if t2[0] == ".":
                                val -= variables[t2[1:]]
                            else:
                                val -= int(t2)
                    memaddress = val

                    if '"' in value:
                        val_string = value.split('"')[1]
                        for i2, item in enumerate(val_string):
                            memory[memaddress + i2] = ord(item)
                    elif "'" in value:
                        val_string = value.split("'")[1]
                        for i2, item in enumerate(val_string):
                            memory[memaddress + i2] = ord(item)
                    else:
                        memory[memaddress] = int(value)
                else:
                    # Pointer variable
                    line_ = line.strip().split("=")
                    varname = line_[0].strip()
                    if line_[1].strip()[0] == ".":
                        varvalue = variables[line_[1].strip()[1:]]
                    else:
                        varvalue = int(line_[1].strip())
                    variables[varname] = varvalue
            elif ":" in line:
                # Label
                address_name = line.strip().split(":")[0]
                addresses[address_name] = address
                addresses_line[address] = progline

    # Second pass: encode program into memory
    memaddress = 0
    for i, line in enumerate(program):
        jump = False
        items = line[0]
        for item in items:
            if item == items[0]:  # mnemonic
                mem_ins = instruction_map[str(item)]
                if 6 <= mem_ins <= 8 or 16 <= mem_ins <= 17 or mem_ins == 27:
                    # Jump or call (JMP/JPZ/JPC/JSR/RET/JNZ (RET has no operand))
                    jump = True
            else:  # operand
                if jump:
                    if item[0] == "#":
                        address_s = item[1:]
                        program[i][0][1] = item[1:]
                        mem_ins = int(address_s)
                    else:
                        address_val = addresses[item]
                        program[i][0][1] = str(addresses_line[address_val])
                        mem_ins = int(address_val)
                else:
                    terms_pos = item.split("+")
                    val = 0
                    for t1 in terms_pos:
                        terms_neg = t1.split("-")
                        pos_val = terms_neg[0]
                        if pos_val[0] == ".":
                            val += variables[pos_val[1:]]
                        else:
                            val += int(pos_val)
                        for t2 in terms_neg[1:]:
                            if t2[0] == ".":
                                val -= variables[t2[1:]]
                            else:
                                val -= int(t2)
                    program[i][0][1] = str(val)
                    mem_ins = int(val)
            memory[memaddress] = mem_ins
            memaddress += 1

    return program
