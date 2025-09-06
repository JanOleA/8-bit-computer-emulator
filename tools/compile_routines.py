import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cpu_sim import Computer



def assemble_snippet(lines, memory_size=8192):
    memory = [0] * memory_size
    comp = Computer.__new__(Computer)
    Computer.setup_instructions(comp)
    instruction_map = comp.instruction_map
    program = Computer.assemble_lines(lines, memory, instruction_map)
    code_len = sum(len(ins[0]) for ins in program)
    code = [int(x) for x in memory[:code_len]]
    return code, program, instruction_map


def relocate_jumps_in_place(code_words, program, instruction_map, base_addr,
                            relocate_jsr=False):
    J_OPS = {
        instruction_map["JMP"],
        instruction_map["JPZ"],
        instruction_map["JPC"],
    }
    if relocate_jsr:
        J_OPS.add(instruction_map["JSR"])

    idx = 0
    for ins in program:
        mnemonic = ins[0][0]
        opcode = instruction_map[mnemonic]
        if len(ins[0]) > 1:
            if opcode in J_OPS:
                code_words[idx + 1] = int(code_words[idx + 1]) + int(base_addr)
            idx += 2
        else:
            idx += 1


def main():
    # OS ABI pointers
    vars_header = [
        "arg1 = 4002",
        "arg2 = 4003",
        "res1 = 4004",
        "res2 = 4005",
        "pow2 = 4006",
        "num_digits = 4007",
        "char = 4000",
    ]

    # Choose fixed bases in RAM for insertion
    MULTIPLY_BASE = 50000
    DIVIDE_BASE = 50100
    DISPLAY_NUMBER_BASE = 50200
    LIST_BASE = 50300
    PEEK_BASE = 50450
    POKE_BASE = 50600

    multiply_lines = vars_header + [
        "multiply:",
        "  LDA .arg1",
        "  CPI 0",
        "  JPZ mult_zero",
        "  LDA .arg2",
        "  CPI 0",
        "  JPZ mult_zero",
        "  LDA .arg1",
        "  CMP .arg2",
        "  JPC mult_begin",
        "  PHA",
        "  LDA .arg2",
        "  STA .arg1",
        "  PLA",
        "  STA .arg2",
        "  LDA .arg1",
        "mult_begin:",
        "  STA .res1",
        "mult_loop:",
        "  LDA .arg2",
        "  SUI 1",
        "  JPZ mult_end",
        "  STA .arg2",
        "  LDA .res1",
        "  ADD .arg1",
        "  STA .res1",
        "  JMP mult_loop",
        "mult_end:",
        "  LDA .res1",
        "  RET",
        "mult_zero:",
        "  LDI 0",
        "  STA .res1",
        "  LDA .res1",
        "  RET",
    ]

    divide_lines = vars_header + [
        "divide:",
        "  LDI 0",
        "  STA .res1",
        "  LDI 1",
        "  STA .pow2",
        "  LDA .arg2",
        "  CPI 0",
        "  JPZ div_end",
        "inc_b:",
        "  LDA .arg2",
        "  LSA",
        "  JPC div_loop",
        "  CMP .arg1",
        "  JPZ pass",
        "  JPC div_loop",
        "pass:",
        "  STA .arg2",
        "  LDA .pow2",
        "  LSA",
        "  STA .pow2",
        "  JMP inc_b",
        "div_loop:",
        "  LDA .pow2",
        "  CPI 0",
        "  JPZ div_end",
        "  LDA .arg1",
        "  CMP .arg2",
        "  JPC a_geq_b",
        "  JMP continue",
        "a_geq_b:",
        "  LDA .res1",
        "  ADD .pow2",
        "  STA .res1",
        "  LDA .arg1",
        "  SUB .arg2",
        "  STA .arg1",
        "continue:",
        "  LDA .arg2",
        "  RSA",
        "  STA .arg2",
        "  LDA .pow2",
        "  RSA",
        "  STA .pow2",
        "  JMP div_loop",
        "div_end:",
        "  LDA .arg1",
        "  STA .res2",
        "  LDA .res1",
        "  RET",
    ]

    display_number_lines = vars_header + [
        "display_number:",
        "  LDI 0",            # ensure fresh counter
        "  STA .num_digits",
        "  LDA .arg1",
        "  CMP 0",
        "calc_next_val:",
        "  LDI 10",
        "  STA .arg2",
        f"  JSR #{DIVIDE_BASE}",
        "  STA .arg1",
        "  LDA .res2",
        "  ADI 48",
        "  PHA",
        "  LDA .num_digits",
        "  ADI 1",
        "  STA .num_digits",
        "  LDA .arg1",
        "  CPI 0",
        "  JPZ print_stack",
        "  JMP calc_next_val",
        "print_stack:",
        "  PLA",
        "  STA .char",
        # inline write_char
        "  LDD .char",
        "  DIC 0",
        "  DIC 64",
        "  DIC 192",
        "  DIC 0",
        "  LDA .num_digits",
        "  SUI 1",
        "  STA .num_digits",
        "  JPZ dn_done",
        "  JMP print_stack",
        "dn_done:",
        "  RET",
    ]

    # LIST command program: prints names from prog_table in three columns
    list_vars = [
        "prog_table = 4300",
    ]
    list_lines = vars_header + list_vars + [
        "list_commands:",
        "  LDI .prog_table",
        "  STA .arg2",
        "  LDI 0",
        "  STA .res1",
        "lc_next:",
        "  LDA .arg2",
        "  PHA",
        "  LAS",
        "  CPI 0",
        "  JPZ lc_end",
        "  LDA .arg2",
        "  STA .res2",
        "  LDI 0",
        "  STA .num_digits",
        "lc_printchar:",
        "  LDA .num_digits",
        "  CPI 8",
        "  JPZ lc_pad",
        "  LDA .res2",
        "  PHA",
        "  LAS",
        "  CPI 0",
        "  JPZ lc_pad",
        "  STA .char",
        # inline write_char
        "  LDD .char",
        "  DIC 0",
        "  DIC 64",
        "  DIC 192",
        "  DIC 0",
        "  LDA .res2",
        "  ADI 1",
        "  STA .res2",
        "  LDA .num_digits",
        "  ADI 1",
        "  STA .num_digits",
        "  JMP lc_printchar",
        "lc_pad:",
        "  LDA .num_digits",
        "  CPI 10",
        "  JPZ lc_aftercol",
        "  LDI 32",
        "  STA .char",
        # inline write_char
        "  LDD .char",
        "  DIC 0",
        "  DIC 64",
        "  DIC 192",
        "  DIC 0",
        "  LDA .num_digits",
        "  ADI 1",
        "  STA .num_digits",
        "  JMP lc_pad",
        "lc_aftercol:",
        "  LDA .res1",
        "  ADI 1",
        "  STA .res1",
        "  CPI 3",
        "  JPZ lc_newline",
        "  JMP lc_advance",
        "lc_newline:",
        # inline newline
        "  DIS 32",
        "  DIC 0",
        "  DIC 128",
        "  DIC 0",
        "  LDI 0",
        "  STA .res1",
        "lc_advance:",
        "  LDA .arg2",
        "  ADI 10",
        "  STA .arg2",
        "  JMP lc_next",
        "lc_end:",
        "  LDA .res1",
        "  CPI 0",
        "  JPZ lc_done",
        # inline newline
        "  DIS 32",
        "  DIC 0",
        "  DIC 128",
        "  DIC 0",
        "lc_done:",
        "  RET",
    ]

    # POKE <addr> <val>: write decimal value into memory[address]
    poke_vars = [
        "argv_base = 4400",
    ]
    poke_lines = vars_header + poke_vars + [
        "poke:",
        # argc >= 2?
        "  LDI .argv_base",
        "  PHA",
        "  LAS",
        "  CPI 2",
        "  JPC pk_ok",
        "  RET",
        "pk_ok:",
        # parse address from argv[0] -> res1
        "  LDI .argv_base",
        "  ADI 1",
        "  PHA",
        "  LAS",
        "  STA .res2",
        "  LDI 0",
        "  STA .res1",
        "pk_paddr:",
        "  LDA .res2",
        "  PHA",
        "  LAS",
        "  CPI 0",
        "  JPZ pk_paddr_done",
        "  CPI 32",
        "  JPZ pk_paddr_done",
        "  SUI 48",
        "  STA .char",
        "  LDA .res1",
        "  LSA",
        "  STA .pow2",
        "  LSA",
        "  LSA",
        "  ADD .pow2",
        "  STA .res1",
        "  LDA .res1",
        "  ADD .char",
        "  STA .res1",
        "  LDA .res2",
        "  ADI 1",
        "  STA .res2",
        "  JMP pk_paddr",
        "pk_paddr_done:",
        # parse value from argv[1] -> arg1
        "  LDI .argv_base",
        "  ADI 2",
        "  PHA",
        "  LAS",
        "  STA .res2",
        "  LDI 0",
        "  STA .arg1",
        "pk_pval:",
        "  LDA .res2",
        "  PHA",
        "  LAS",
        "  CPI 0",
        "  JPZ pk_pval_done",
        "  CPI 32",
        "  JPZ pk_pval_done",
        "  SUI 48",
        "  STA .char",
        "  LDA .arg1",
        "  LSA",
        "  STA .pow2",
        "  LSA",
        "  LSA",
        "  ADD .pow2",
        "  STA .arg1",
        "  LDA .arg1",
        "  ADD .char",
        "  STA .arg1",
        "  LDA .res2",
        "  ADI 1",
        "  STA .res2",
        "  JMP pk_pval",
        "pk_pval_done:",
        # store: *addr = val
        "  LDA .res1",
        "  PHA",
        "  LDA .arg1",
        "  SAS",
        # newline
        "  DIS 32",
        "  DIC 0",
        "  DIC 128",
        "  DIC 0",
        "  RET",
    ]

    # PEEK <addr>: reads argv[1] as decimal address, prints memory[addr]
    peek_vars = [
        "argv_base = 4400",
    ]
    peek_lines = vars_header + peek_vars + [
        "peek:",
        # argc at [argv_base]
        "  LDI .argv_base",
        "  PHA",
        "  LAS",
        "  CPI 0",
        "  JPZ pk_end",
        # load argv[0] pointer at [argv_base+1]
        "  LDI .argv_base",
        "  ADI 1",
        "  PHA",
        "  LAS",
        "  STA .res2",        # res2 = pointer to string
        # parse number in res2 -> res1
        "  LDI 0",
        "  STA .res1",
        "pk_pn_loop:",
        "  LDA .res2",
        "  PHA",
        "  LAS",
        "  CPI 0",
        "  JPZ pk_pn_done",
        "  CPI 32",
        "  JPZ pk_pn_done",
        "  SUI 48",
        "  STA .char",
        "  LDA .res1",
        "  LSA",
        "  STA .pow2",
        "  LSA",
        "  LSA",
        "  ADD .pow2",
        "  STA .res1",
        "  LDA .res1",
        "  ADD .char",
        "  STA .res1",
        "  LDA .res2",
        "  ADI 1",
        "  STA .res2",
        "  JMP pk_pn_loop",
        "pk_pn_done:",
        # read memory at [res1]
        "  LDA .res1",
        "  PHA",
        "  LAS",
        "  STA .arg1",
        # print value via display_number
        f"  JSR #{DISPLAY_NUMBER_BASE}",
        # newline
        "  DIS 32",
        "  DIC 0",
        "  DIC 128",
        "  DIC 0",
        "pk_end:",
        "  RET",
    ]

    # Assemble and relocate
    mul_code, mul_prog, ins_map = assemble_snippet(multiply_lines)
    relocate_jumps_in_place(mul_code, mul_prog, ins_map, MULTIPLY_BASE, relocate_jsr=False)

    div_code, div_prog, _ = assemble_snippet(divide_lines)
    relocate_jumps_in_place(div_code, div_prog, ins_map, DIVIDE_BASE, relocate_jsr=False)

    disp_code, disp_prog, _ = assemble_snippet(display_number_lines)
    relocate_jumps_in_place(disp_code, disp_prog, ins_map, DISPLAY_NUMBER_BASE, relocate_jsr=False)

    list_code, list_prog, _ = assemble_snippet(list_lines)
    relocate_jumps_in_place(list_code, list_prog, ins_map, LIST_BASE, relocate_jsr=False)

    peek_code, peek_prog, _ = assemble_snippet(peek_lines)
    relocate_jumps_in_place(peek_code, peek_prog, ins_map, PEEK_BASE, relocate_jsr=False)

    # Assemble POKE after others (uses no deps)
    poke_code, poke_prog, _ = assemble_snippet(poke_lines)
    relocate_jumps_in_place(poke_code, poke_prog, ins_map, POKE_BASE, relocate_jsr=False)

    data = {
        "multiply": {"base": MULTIPLY_BASE, "length": len(mul_code), "words": mul_code},
        "divide": {"base": DIVIDE_BASE, "length": len(div_code), "words": div_code},
        "display_number": {
            "base": DISPLAY_NUMBER_BASE,
            "length": len(disp_code),
            "words": disp_code,
            "deps": {"divide": DIVIDE_BASE},
        },
        "list": {"base": LIST_BASE, "length": len(list_code), "words": list_code},
        "peek": {"base": PEEK_BASE, "length": len(peek_code), "words": peek_code, "deps": {"display_number": DISPLAY_NUMBER_BASE}},
        "poke": {"base": POKE_BASE, "length": len(poke_code), "words": poke_code},
    }

    out_path = Path(__file__).parent.parent / "32bit" / "compiled_routines.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
