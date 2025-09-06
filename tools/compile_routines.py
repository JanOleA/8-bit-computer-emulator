import json
from pathlib import Path
from typing import List, Dict, Tuple
import sys

# Ensure project root is importable so we can import tools.assembler_core
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Use the lightweight assembler to avoid pygame dependency
from tools.assembler_core import build_instruction_map, assemble_lines as asm_assemble_lines



def assemble_snippet(lines, memory_size=8192):
    memory = [0] * memory_size
    instruction_map = build_instruction_map()
    program = asm_assemble_lines(lines, memory, instruction_map)
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
    code_len = len(code_words)
    for ins in program:
        mnemonic = ins[0][0]
        opcode = instruction_map[mnemonic]
        if len(ins[0]) > 1:
            if opcode in J_OPS:
                # For JSR, only relocate if operand targets inside this module
                if relocate_jsr and opcode == instruction_map["JSR"]:
                    operand = int(code_words[idx + 1])
                    if operand < code_len:
                        code_words[idx + 1] = operand + int(base_addr)
                else:
                    code_words[idx + 1] = int(code_words[idx + 1]) + int(base_addr)
            idx += 2
        else:
            idx += 1


# ----------
# Dynamic routines loader from folder
# ----------

def parse_headers_and_preprocess(text: str) -> Tuple[Dict[str, str], List[str], List[str]]:
    headers: Dict[str, str] = {}
    lines: List[str] = []
    extern_calls: List[str] = []  # symbols in textual order
    for raw in text.splitlines():
        if raw.startswith(";!"):
            try:
                k, v = raw[2:].split(":", 1)
                headers[k.strip().lower()] = v.strip()
            except ValueError:
                pass
            continue
        # Detect extern call syntax: "  JSR @name"
        stripped = raw.strip()
        if stripped.upper().startswith("JSR @"):
            sym = stripped.split("@", 1)[1].strip()
            # Replace with immediate zero placeholder
            raw = raw.replace("@" + sym, "#0")
            extern_calls.append(sym)
        elif stripped and not stripped.startswith(";") and not raw.startswith(" "):
            # Non-instruction line (var/label) — don't count
            pass
        # keep raw
        lines.append(raw)
    return headers, lines, extern_calls


def assemble_dynamic_module(src_path: Path,
                            used_bases: List[Tuple[int, int]],
                            base_cursor: int,
                            abi_inject: bool,
                            bss_auto_start: int,
                            known_symbols: Dict[str, int]) -> Tuple[Dict, int, List[Tuple[int, int]]]:
    text = src_path.read_text()
    headers, raw_lines, extern_calls = parse_headers_and_preprocess(text)

    name = headers.get("name", src_path.stem).lower()
    entry = headers.get("entry", "start")
    align = int(headers.get("align", "100"))
    deps = [d.strip().lower() for d in headers.get("deps", "").split(",") if d.strip()]
    abi = headers.get("abi", "os").lower()
    bss = headers.get("bss", "auto").lower()
    bss_align = int(headers.get("bss_align", "16"))
    base = headers.get("base")

    # Determine base
    if base is not None:
        base_addr = int(base)
    else:
        # allocate next aligned base not overlapping used_bases
        def fits(addr: int) -> bool:
            # unknown length yet; just ensure addr not inside existing ranges starts
            for s, e in used_bases:
                if s <= addr < e:
                    return False
            return True

        addr = ((base_cursor + align - 1) // align) * align
        while not fits(addr):
            addr += align
        base_addr = addr

    # Inject OS ABI if requested
    lines = []
    if abi == "os":
        lines += [
            "arg1 = 4002",
            "arg2 = 4003",
            "res1 = 4004",
            "res2 = 4005",
            "pow2 = 4006",
            "num_digits = 4007",
            "char = 4000",
        ]

    # BSS injection
    if bss == "auto":
        # allocate aligned bss region; keep it above history base by default
        bss_base = ((bss_auto_start + bss_align - 1) // bss_align) * bss_align
        lines.append(f"bss = {bss_base}")
        # Update bss_auto_start for next module
        bss_auto_start = bss_base + 512  # reserve a page for vars
    elif bss.isdigit():
        lines.append(f"bss = {int(bss)}")
    else:
        # none
        pass

    # Append preprocessed source
    lines += raw_lines

    # Assemble
    code, program, ins_map = assemble_snippet(lines)

    # Collect extern patch sites but do not resolve yet; we'll patch after all modules are placed
    jsr_zero_code_indexes: List[int] = []
    code_index = 0
    for ins in program:
        tokens = ins[0]
        if len(tokens) == 2 and tokens[0] == 'JSR' and tokens[1] == '0':
            jsr_zero_code_indexes.append(code_index)
        code_index += len(tokens)

    if len(jsr_zero_code_indexes) != len(extern_calls):
        raise ValueError(f"Extern calls count mismatch in {src_path.name}: found {len(jsr_zero_code_indexes)} JSR #0, headers referenced {len(extern_calls)} symbols")

    # Relocate internal jumps
    relocate_jumps_in_place(code, program, ins_map, base_addr, relocate_jsr=True)

    # Validate no overlap with existing used ranges now that we know length
    new_start, new_end = base_addr, base_addr + len(code)
    for s, e in used_bases:
        if not (new_end <= s or new_start >= e):
            raise ValueError(f"Overlap: {src_path.name} [{new_start},{new_end}) conflicts with [{s},{e})")

    mod = {
        "base": base_addr,
        "length": len(code),
        "words": code,
        "deps": {d: known_symbols.get(d) for d in deps if d in known_symbols},
        "entry": entry,
        "externs": [{"code_index": ci, "symbol": sym} for ci, sym in zip(jsr_zero_code_indexes, extern_calls)],
    }
    # Update used ranges and cursor (approximate range: base..base+len)
    used_bases.append((base_addr, base_addr + len(code)))
    base_cursor = base_addr + len(code)
    return {name: mod}, base_cursor, used_bases


def apply_prog_table_to_os(table_lines: List[str], data: Dict[str, Dict]) -> bool:
    os_path = Path(__file__).parent.parent / "32bit" / "emulator_os.txt"
    if not os_path.exists():
        print(f"OS file not found: {os_path}")
        return False
    text = os_path.read_text().splitlines()
    # Find start of table
    start_idx = None
    for i, ln in enumerate(text):
        if ln.strip().startswith("prog_table ="):
            start_idx = i
            break
    if start_idx is None:
        print("Could not locate 'prog_table =' in emulator_os.txt; skipping apply.")
        return False
    # Find last .prog_table line after start
    end_idx = start_idx
    for i in range(start_idx + 1, len(text)):
        if text[i].strip().startswith('.prog_table'):
            end_idx = i
        elif end_idx != start_idx and not text[i].strip().startswith(';') and text[i].strip() != "":
            # Stop when we hit the next non-comment, non-empty line after the block
            break
    # Replace block
    new_block = table_lines
    new_text = text[:start_idx] + new_block + text[end_idx + 1:]
    # Discover CALL_STUB base
    call_stub_base = None
    for ln in new_text:
        s = ln.strip().replace(" ", "")
        if s.startswith('CALL_STUB='):
            try:
                call_stub_base = int(s.split('=', 1)[1])
            except Exception:
                pass
            break
    # Patch CALL_STUB operand (CALL_STUB+1) to SHELL base, if present
    shell_base = None
    for k, v in data.items():
        if k.lower() == 'shell' or str(v.get('entry','')).lower() == 'start':
            shell_base = int(v.get('base', 0))
            break
    if shell_base is not None and call_stub_base is not None:
        for i, ln in enumerate(new_text):
            s = ln.replace(" ", "")
            if s.startswith(f"{call_stub_base+1}="):
                new_text[i] = f"{call_stub_base+1} = {shell_base}"
            if ln.strip().startswith('JMP start_shell') or ln.strip().startswith('JSR #'):
                new_text[i] = f'  JSR #{call_stub_base}'

    # Fill OS API vector with label addresses (simple first pass label indexer)
    # Build label->address mapping based on assembled instruction layout
    addr = 0
    labels: Dict[str, int] = {}
    for ln in new_text:
        line = ln.split(';')[0]
        if line.replace(' ', '') == '':
            continue
        if line.startswith('  ') and (len(line) < 3 or line[2] != ' '):
            parts = line.strip().split(' ')
            if len(parts) > 2:
                # normalize to at most 2 tokens
                parts = [parts[0], ''.join(parts[1:])]
            addr += len(parts)
        elif not line.startswith(' '):
            if ':' in line:
                name = line.strip().split(':')[0]
                labels[name] = addr

    # Target API names in order
    api_names = [
        ('dispatch_program', 0),
        ('build_argv', 1),
        ('parse_number', 2),
        ('skip_spaces', 3),
        ('write_char', 4),
        ('newline', 5),
        ('ret_home', 6),
        ('cursor_left', 7),
        ('enter', 8),
        ('print_prompt', 9),
    ]
    # Patch .os_api + idx lines
    for i, ln in enumerate(new_text):
        s = ln.strip().replace(' ', '')
        for name, idx in api_names:
            if s.startswith(f'.os_api+{idx}='):
                val = labels.get(name)
                if val is not None:
                    new_text[i] = f'.os_api + {idx} = {val}'
    os_path.write_text("\n".join(new_text) + "\n")
    print(f"Applied program table to {os_path}")
    return True


def main(apply_table: bool = False):
    data: Dict[str, Dict] = {}
    known_symbols: Dict[str, int] = {}
    used_ranges: List[Tuple[int, int]] = []
    base_cursor = 20000

    # Optionally scan 32bit/routines for extra modules
    routines_dir = Path(__file__).parent.parent / "32bit" / "routines"
    bss_auto_start = 120000  # keep above OS/history
    modules_to_patch: List[Tuple[str, Dict]] = []
    if routines_dir.exists():
        # First pass: assemble modules, assign bases, collect extern sites
        for src in sorted(routines_dir.glob("*.txt")):
            try:
                mod_map, base_cursor, used_ranges = assemble_dynamic_module(
                    src,
                    used_bases=used_ranges,
                    base_cursor=base_cursor,
                    abi_inject=True,
                    bss_auto_start=bss_auto_start,
                    known_symbols=known_symbols,
                )
                # Merge module and record symbol
                for k, v in mod_map.items():
                    data[k] = v
                    known_symbols[k] = v["base"]
                    # Also export by entry label for @entry symbol references
                    if "entry" in v and isinstance(v["entry"], str):
                        known_symbols[v["entry"].lower()] = v["base"]
                    modules_to_patch.append((k, v))
            except Exception as e:
                print(f"Skipping {src.name}: {e}")

        # Second pass: resolve externs now that all bases are known
        for name, mod in modules_to_patch:
            externs = mod.get("externs", [])
            if not externs:
                continue
            words = mod["words"]
            for ex in externs:
                ci = ex["code_index"]
                sym = ex["symbol"].lower()
                target = known_symbols.get(sym)
                if target is None:
                    raise ValueError(f"Module {name} references unknown symbol @{sym}")
                if ci + 1 >= len(words):
                    raise ValueError(f"Module {name} extern site out of range at {ci}")
                words[ci + 1] = int(target)
            # remove externs from output metadata
            del mod["externs"]

        # Third pass: comprehensive overlap check across all modules
        ranges = []
        for k, v in data.items():
            try:
                b = int(v.get("base", 0))
                l = int(v.get("length", 0))
            except Exception:
                continue
            ranges.append((k, b, b + l))
        ranges.sort(key=lambda t: t[1])
        overlaps = []
        for i in range(1, len(ranges)):
            prev_name, prev_s, prev_e = ranges[i - 1]
            name, s, e = ranges[i]
            if s < prev_e:
                overlaps.append((prev_name, prev_s, prev_e, name, s, e))
        if overlaps:
            print("Error: program base ranges overlap:")
            for a, as_, ae, b, bs, be in overlaps:
                print(f"  {a} [{as_},{ae}) overlaps {b} [{bs},{be})")
            raise SystemExit(1)

        # Report free gaps between written programs (unused words)
        gaps = []
        for i in range(len(ranges) - 1):
            cur_name, cur_s, cur_e = ranges[i]
            nxt_name, nxt_s, nxt_e = ranges[i + 1]
            if nxt_s > cur_e:
                gaps.append((cur_name, cur_e, nxt_s, nxt_name, nxt_s - cur_e))
        if gaps:
            print("\nFree gaps between modules:")
            for prev_name, gap_start, gap_end, next_name, gap_len in gaps:
                print(f"  {prev_name} -> {next_name}: [{gap_start},{gap_end})  words={gap_len}")
            # Write a helper file with the gaps
            gap_lines = ["; Free gaps between modules (start,end,words)"]
            for prev_name, gap_start, gap_end, next_name, gap_len in gaps:
                gap_lines.append(f"{gap_start},{gap_end},{gap_len} ; between {prev_name} and {next_name}")
            gaps_path = Path(__file__).parent.parent / "32bit" / "free_gaps.txt"
            gaps_path.write_text("\n".join(gap_lines) + "\n")

    out_path = Path(__file__).parent.parent / "32bit" / "compiled_routines.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out_path}")

    # Emit a handy program table overview to help update the OS dispatch table
    # Read current prog_table base from OS file (fallback 4300)
    pt_base = 4300
    try:
        os_text = (Path(__file__).parent.parent / "32bit" / "emulator_os.txt").read_text().splitlines()
        for ln in os_text:
            s = ln.strip().replace(" ", "")
            if s.startswith("prog_table="):
                pt_base = int(s.split("=", 1)[1])
                break
    except Exception:
        pass

    table_lines = []
    table_lines.append(f"prog_table = {pt_base}")
    table_lines.append("; Command/program table entries: name[0..7], addr[8], reserved[9]")
    entries = [kv for kv in sorted(data.items(), key=lambda kv: int(kv[1].get("base", 0)))]
    for i, (name, mod) in enumerate(entries):
        off = i * 10
        nm = str(name).upper()[:8]
        base = int(mod.get("base", 0))
        table_lines.append(f".prog_table + {off}  = \"{nm}\"")
        table_lines.append(f".prog_table + {off+8} = {base}")
        table_lines.append(f".prog_table + {off+9} = 0")
    table_lines.append(f".prog_table + {len(entries)*10} = 0    ; sentinel")

    suggest_path = Path(__file__).parent.parent / "32bit" / "prog_table_suggest.txt"
    suggest_path.write_text("\n".join(table_lines) + "\n")
    print("\nSuggested OS program table (written to 32bit/prog_table_suggest.txt):\n")
    print("\n".join(table_lines))

    if apply_table:
        apply_prog_table_to_os(table_lines, data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Assemble routines and emit program table")
    parser.add_argument("--apply-table", action="store_true", help="Apply the generated program table into 32bit/emulator_os.txt")
    args = parser.parse_args()
    main(apply_table=args.apply_table)
