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


def assemble_lines(lines: List[str], memory: List[int], instruction_map: Dict[str, int], verbose: bool = False, name: str = "<module>") -> List[Tuple[List[str], int]]:
    addresses: Dict[str, int] = {}
    addresses_line: Dict[int, int] = {}
    variables: Dict[str, int] = {}
    program: List[Tuple[List[str], int]] = []
    varnames_check_used = set()
    original_lines: dict[int, str] = {}

    address = 0
    progline = 0

    if verbose:
        print(f"\n--- Assembling {name} ---\n")
    # First pass: collect variables and labels, build program list
    for i, line in enumerate(lines):
        oline = line
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
            original_lines[i] = oline
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
                        # Support '.name', bare name, or integer literal
                        if pos_val.startswith('.'):
                            val += variables.get(pos_val[1:], 0)
                        else:
                            try:
                                val += int(pos_val)
                            except Exception:
                                val += variables.get(pos_val, 0)
                        for t2 in terms_neg[1:]:
                            if t2.startswith('.'):
                                val -= variables.get(t2[1:], 0)
                            else:
                                try:
                                    val -= int(t2)
                                except Exception:
                                    val -= variables.get(t2, 0)
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
                    # Pointer variable (alias). RHS can be an expression like
                    # 'bss + 2' or '.bss + 2' or a single integer.
                    line_ = line.strip().split("=")
                    varname = line_[0].strip()
                    rhs = line_[1].strip()
                    # Evaluate RHS expression supporting + and - and names
                    terms_pos = rhs.replace(' ', '').split('+')
                    val = 0
                    for t1 in terms_pos:
                        terms_neg = t1.split('-')
                        pos_val = terms_neg[0]
                        if pos_val.startswith('.'):
                            val += variables.get(pos_val[1:], 0)
                        else:
                            try:
                                val += int(pos_val)
                            except Exception:
                                val += variables.get(pos_val, 0)
                        for t2 in terms_neg[1:]:
                            if t2.startswith('.'):
                                val -= variables.get(t2[1:], 0)
                            else:
                                try:
                                    val -= int(t2)
                                except Exception:
                                    val -= variables.get(t2, 0)
                    variables[varname] = val
                    varnames_check_used.add(varname)
            elif ":" in line:
                # Label
                address_name = line.strip().split(":")[0]
                addresses[address_name] = address
                addresses_line[address] = progline

        if verbose:
            print(line)

    if verbose:
        print("\n--- Encode into memory ---\n")
    # Second pass: encode program into memory
    memaddress = 0
    for i, line in enumerate(program):
        jump = False
        items = line[0]

        original_line = list(original_lines.values())[i]
        original_line_linenumber = list(original_lines.keys())[i] + 1

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
                    # Evaluate operand expressions: support '.name', 'name', or integer
                    terms_pos = item.split("+")
                    val = 0
                    for t1 in terms_pos:
                        terms_neg = t1.split("-")
                        pos_val = terms_neg[0]
                        if pos_val.startswith('.'):
                            if not pos_val[1:] in variables:
                                print(f"Warning: undefined pointer variable '{pos_val[1:]}' used in line: {original_line}:{original_line_linenumber}. Program: {name}. Verify all variables are defined and required ABI entries are present.")
                            val += variables.get(pos_val[1:], 0)
                            if pos_val[1:] in varnames_check_used:
                                varnames_check_used.remove(pos_val[1:])
                        else:
                            try:
                                val += int(pos_val)
                            except Exception:
                                if not pos_val in variables:
                                    print(f"Warning: undefined pointer variable '{pos_val}' used in line: {original_line}:{original_line_linenumber}. Program: {name}. Verify all variables are defined and required ABI entries are present.")
                                val += variables.get(pos_val, 0)
                                if pos_val in varnames_check_used:
                                    varnames_check_used.remove(pos_val)
                        for t2 in terms_neg[1:]:
                            if t2.startswith('.'):
                                if not t2[1:] in variables:
                                    print(f"Warning: undefined pointer variable '{t2[1:]}' used in line: {original_line}:{original_line_linenumber}. Program: {name}. Verify all variables are defined and required ABI entries are present.")
                                val -= variables.get(t2[1:], 0)
                                if t2[1:] in varnames_check_used:
                                    varnames_check_used.remove(t2[1:])
                            else:
                                try:
                                    val -= int(t2)
                                except Exception:
                                    val -= variables.get(t2, 0)
                    program[i][0][1] = str(val)
                    mem_ins = int(val)
                    if mem_ins == 0 and "." in original_line:
                        print(f"{name} | {original_line}:{original_line_linenumber}, mem_ins == 0, check if correct")
            memory[memaddress] = mem_ins
            memaddress += 1

    if verbose:
        print(f"\n--- Assembled program {name} ---\n")

        if len(varnames_check_used) > 0:
            for varname in varnames_check_used:
                print(f"Warning: variable '{varname}' defined but not used")

    return program
