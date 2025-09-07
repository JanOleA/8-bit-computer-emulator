import json
from pathlib import Path
from typing import List, Dict, Tuple
import sys
import re

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

def parse_headers_and_preprocess(text: str):
    """Parse headers, normalize extern calls, and pre-scan for auto data.

    Returns:
      headers: dict of ;! headers
      lines: preprocessed source lines
      extern_calls: symbols referenced as @name (order)
      auto_ptrs: map varname->offset for auto data (.name = ... without prior definition)
      data_items: list of (name, offset, words)
    """
    headers: Dict[str, str] = {}
    lines: List[str] = []
    extern_calls: List[str] = []  # symbols in textual order

    # First pass: detect explicit pointer vars (name = ...), not starting with dot
    defined_ptrs: Dict[str, int] = {}
    for raw in text.splitlines():
        s = raw.split(';')[0].strip()
        if not s or s.startswith(';'):
            continue
        if (not raw.startswith('  ')) and ('=' in s) and (not s.startswith('.')):
            name = s.split('=', 1)[0].strip()
            defined_ptrs[name] = 1

    # Second pass: preprocess, collect externs and auto data
    data_items: List[Tuple[str, int, List[int]]] = []
    data_cursor = 0
    for raw in text.splitlines():
        if raw.startswith(";!"):
            try:
                k, v = raw[2:].split(":", 1)
                headers[k.strip().lower()] = v.strip()
            except ValueError:
                pass
            continue
        stripped = raw.strip()
        # Detect extern call syntax: "  JSR @name"
        if stripped.upper().startswith("JSR @"):
            sym = stripped.split("@", 1)[1].strip()
            raw = raw.replace("@" + sym, "#0")
            extern_calls.append(sym)
        # Detect auto data assignment: .name = "..." or number, when name not predefined
        if (not raw.startswith(' ')) and ('=' in raw) and raw.strip().startswith('.'):
            try:
                lhs, rhs = raw.split('=', 1)
                varname = lhs.strip()[1:]
                if varname not in defined_ptrs:
                    val = rhs.strip()
                    words: List[int] = []
                    if '"' in val:
                        sval = val.split('"')[1]
                        words = [ord(c) for c in sval]
                        words.append(0)  # null-terminate strings
                    elif "'" in val:
                        sval = val.split("'")[1]
                        words = [ord(c) for c in sval]
                        words.append(0)  # null-terminate strings
                    else:
                        try:
                            words = [int(val.split(';')[0].strip())]
                        except Exception:
                            words = []
                    if words:
                        data_items.append((varname, data_cursor, words))
                        data_cursor += len(words)
            except Exception:
                pass
        # keep raw
        lines.append(raw)

    auto_ptrs = {n: off for n, off, _ in data_items}
    return headers, lines, extern_calls, auto_ptrs, data_items


def assemble_dynamic_module(src_path: Path,
                            used_bases: List[Tuple[int, int]],
                            base_cursor: int,
                            abi_inject: bool,
                            bss_auto_start: int,
                            known_symbols: Dict[str, int],
                            data_auto_start: int) -> Tuple[Dict, int, List[Tuple[int, int]], int, int]:
    text = src_path.read_text()
    headers, raw_lines, extern_calls, auto_ptrs, data_items = parse_headers_and_preprocess(text)

    name = headers.get("name", src_path.stem).lower()
    entry = headers.get("entry", "start")
    align = int(headers.get("align", "100"))
    deps = [d.strip().lower() for d in headers.get("deps", "").split(",") if d.strip()]
    abi = headers.get("abi", "os").lower()
    bss = headers.get("bss", "auto").lower()
    bss_align = int(headers.get("bss_align", "16"))
    base = headers.get("base")

    # Inject OS ABI if requested
    lines = []
    if abi == "os":
        lines += [
            "char = 4000",
            "textloc = 4001",
            "arg1 = 4002",
            "arg2 = 4003",
            "res1 = 4004",
            "res2 = 4005",
            "pow2 = 4006",
            "num_digits = 4007",
            "ascii_start = 4008",
            "work1 = 4010",
            "work2 = 4011",
            "work3 = 4012",
            "work4 = 4013",
            "argv_base = 4400",
            "argv_buf  = 4500",
            "prog_table = 10000",
        ]

    # BSS injection with size/overlap checks
    bss_info: Tuple[int, int] | None = None
    def _scan_bss_required(src_lines: List[str]) -> int:
        max_off = -1
        for ln in src_lines:
            s = ln.split(';')[0]
            if '.bss' not in s:
                continue
            t = s.replace(' ', '')
            idx = 0
            while True:
                j = t.find('.bss+', idx)
                if j == -1:
                    break
                k = j + len('.bss+')
                n = ''
                while k < len(t) and t[k].isdigit():
                    n += t[k]
                    k += 1
                if n:
                    try:
                        off = int(n)
                        if off > max_off:
                            max_off = off
                    except Exception:
                        pass
                idx = k
        # If '.bss' occurs at all, ensure at least 1 word
        if max_off < 0:
            for ln in src_lines:
                if '.bss' in ln.split(';')[0]:
                    return 1
            return 0
        return max_off + 1

    bss_required = _scan_bss_required(raw_lines)
    default_bss_size = 512
    if bss == "auto":
        bss_base = ((bss_auto_start + bss_align - 1) // bss_align) * bss_align
        bss_size = max(default_bss_size, bss_required)
        lines.append(f"bss = {bss_base}")
        # Reserve BSS region to avoid overlaps with other modules' code/data
        used_bases.append((bss_base, bss_base + bss_size))
        bss_auto_start = bss_base + bss_size
        bss_info = (bss_base, bss_size)
    elif bss.isdigit():
        bss_base = int(bss)
        bss_size = max(default_bss_size, bss_required) if bss_required else default_bss_size
        lines.append(f"bss = {bss_base}")
        used_bases.append((bss_base, bss_base + bss_size))
        bss_info = (bss_base, bss_size)
    else:
        # none; warn if usage detected
        if bss_required:
            print(f"Warning: {src_path.name} references .bss but 'bss' is 'none'.")

    # DATA injection (auto variables)
    data_base = None
    data_len = sum(len(words) for _, _, words in data_items)
    if data_len > 0:
        # allocate aligned data region
        data_base = ((data_auto_start + 16 - 1) // 16) * 16
        for ap_name, off in auto_ptrs.items():
            lines.append(f"{ap_name} = {data_base + off}")
        data_auto_start = data_base + data_len + 16

    # Append preprocessed source
    lines += raw_lines

    # Assemble with larger memory to allow high addresses
    mem_cap = max(200000, (data_base or 0) + data_len + 64)
    code, program, ins_map = assemble_snippet(lines, memory_size=mem_cap)

    # Determine base after we know code length, to avoid overlaps
    code_len = len(code)
    if base is not None:
        base_addr = int(base)
    else:
        # Find first aligned gap where [addr, addr+code_len) does not overlap any used range
        ranges = sorted(used_bases)
        addr = ((base_cursor + align - 1) // align) * align
        i = 0
        while True:
            overlapped = False
            for s, e in ranges:
                if not (addr + code_len <= s or addr >= e):
                    # bump addr to end of this range, keep alignment
                    addr = ((e + align - 1) // align) * align
                    overlapped = True
                    break
            if not overlapped:
                break
        base_addr = addr

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

    # Relocate internal jumps to chosen base
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
    if bss_info is not None:
        mod["bss"] = {"base": bss_info[0], "size": bss_info[1]}
    # Update used ranges and cursor (approximate range: base..base+len)
    used_bases.append((base_addr, base_addr + len(code)))
    base_cursor = base_addr + len(code)

    out = {name: mod}
    # Emit data module if present
    if data_base is not None and data_len > 0:
        words: List[int] = [0] * data_len
        for _, off, w in data_items:
            for i, b in enumerate(w):
                if 0 <= off + i < data_len:
                    words[off + i] = int(b)
        d_start, d_end = data_base, data_base + len(words)
        for s, e in used_bases:
            if not (d_end <= s or d_start >= e):
                raise ValueError(f"Overlap: data for {src_path.name} [{d_start},{d_end}) conflicts with [{s},{e})")
        used_bases.append((d_start, d_end))
        out[f"{name}_data"] = {"base": data_base, "length": len(words), "words": words}

    return out, base_cursor, used_bases, data_auto_start, bss_auto_start


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
    # Replace block (legacy path): keep existing text, but replace the table block with the provided lines
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
    # Prefer an explicit module named 'shell'. Do NOT heuristically use entry=='start',
    # because many modules use 'start' and that can mispatch the boot target.
    shell_base = None
    for k, v in data.items():
        if k.lower() == 'shell':
            shell_base = int(v.get('base', 0))
            break
    if shell_base is not None and call_stub_base is not None:
        for i, ln in enumerate(new_text):
            s = ln.replace(" ", "")
            if s.startswith(f"{call_stub_base+1}="):
                new_text[i] = f"{call_stub_base+1} = {shell_base}"

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
    print(f"Applied call stub and (legacy) table to {os_path}")
    return True


def main(apply_table: bool = False):
    data: Dict[str, Dict] = {}
    known_symbols: Dict[str, int] = {}
    used_ranges: List[Tuple[int, int]] = []
    base_cursor = 20000

    # Optionally scan 32bit/routines for extra modules
    routines_dir = Path(__file__).parent.parent / "32bit" / "routines"
    bss_auto_start = 120000  # keep above OS/history
    data_auto_start = 130000
    modules_to_patch: List[Tuple[str, Dict]] = []
    if routines_dir.exists():
        # First pass: assemble modules, assign bases, collect extern sites
        # Support new .easm extension (preferred), while keeping .txt during transition
        srcs = list(routines_dir.glob("*.easm")) + list(routines_dir.glob("*.txt"))
        # Order: modules with explicit ;! base first, then auto-base, both alphabetically
        def has_base(p: Path) -> bool:
            try:
                txt = p.read_text()
                for ln in txt.splitlines():
                    if ln.startswith(';!'):
                        k, _, v = ln[2:].partition(':')
                        if k.strip().lower() == 'base' and v.strip() != '':
                            return True
                return False
            except Exception:
                return False
        srcs.sort(key=lambda p: (1 if not has_base(p) else 0, p.name.lower()))
        for src in srcs:
            try:
                mod_map, base_cursor, used_ranges, data_auto_start, bss_auto_start = assemble_dynamic_module(
                    src,
                    used_bases=used_ranges,
                    base_cursor=base_cursor,
                    abi_inject=True,
                    bss_auto_start=bss_auto_start,
                    known_symbols=known_symbols,
                    data_auto_start=data_auto_start,
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

    # Build and embed program table into JSON image
    # Determine program table base: prefer reading from OS file, else default 10000
    pt_base = 10000
    try:
        os_text = (Path(__file__).parent.parent / "32bit" / "emulator_os.txt").read_text().splitlines()
        for ln in os_text:
            s = ln.strip().replace(" ", "")
            if s.startswith("prog_table="):
                pt_base = int(s.split("=", 1)[1])
                break
    except Exception:
        pass

    # Compose program table bytes: 10-byte entries: name[0..7], addr[8], reserved[9]
    entries = [kv for kv in sorted(data.items(), key=lambda kv: int(kv[1].get("base", 0))) if isinstance(kv[1], dict) and "base" in kv[1] and "entry" in kv[1]]
    table_words: list[int] = []
    for name, mod in entries:
        nm = str(name).upper()[:8]
        # Name bytes (padded with zeros so the OS matcher sees terminators)
        for i in range(8):
            ch = ord(nm[i]) if i < len(nm) else 0
            table_words.append(ch)
        # Address
        table_words.append(int(mod.get("base", 0)))
        # Reserved
        table_words.append(0)
    # Sentinel: a single zero at the next name[0]
    table_words.append(0)
    data["program_table"] = {"base": pt_base, "length": len(table_words), "words": table_words}

    out_path = Path(__file__).parent.parent / "32bit" / "compiled_routines.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out_path}")

    # Emit a human-readable overview (optional legacy helper)
    overview_lines = [
        f"Program table base: {pt_base}",
        "Entries (NAME → BASE):",
    ]
    for name, mod in entries:
        overview_lines.append(f"  {str(name).upper():8} → {int(mod.get('base', 0))}")
    suggest_path = Path(__file__).parent.parent / "32bit" / "prog_table_suggest.txt"
    suggest_path.write_text("\n".join(overview_lines) + "\n")
    print("\nProgram table overview (written to 32bit/prog_table_suggest.txt):\n")
    print("\n".join(overview_lines))

    # Emit BSS map overview (console + file)
    bss_lines = [
        "BSS regions:",
    ]
    for name, mod in sorted(data.items(), key=lambda kv: int(kv[1].get("base", 0)) if isinstance(kv[1], dict) else 0):
        if not isinstance(mod, dict):
            continue
        bss = mod.get("bss")
        if isinstance(bss, dict):
            bbase = int(bss.get("base", 0))
            bsize = int(bss.get("size", 0))
            bend = bbase + bsize
            bss_lines.append(f"  {name.upper():8} BSS [{bbase},{bend}) size={bsize}")
    if len(bss_lines) > 1:
        print("\n" + "\n".join(bss_lines))
        bss_path = Path(__file__).parent.parent / "32bit" / "bss_map.txt"
        bss_path.write_text("\n".join(bss_lines) + "\n")
        print(f"Wrote BSS map to {bss_path}")

    # Always patch the ECHON call site in emulator_os.txt if present
    try:
        echon_base = None
        for k, v in data.items():
            if isinstance(v, dict) and k.lower() == 'echon' and 'base' in v:
                echon_base = int(v['base'])
                break
        if echon_base is not None:
            os_path = Path(__file__).parent.parent / "32bit" / "emulator_os.txt"
            if os_path.exists():
                lines = os_path.read_text().splitlines()
                did = False
                pat = re.compile(r'(\bJSR\s+#)\d+')
                for i, ln in enumerate(lines):
                    # Only patch the JSR line that mentions ECHON in its comment
                    if 'ECHON' not in ln.upper():
                        continue
                    if pat.search(ln):
                        # Safe replacement using a function to avoid octal escapes
                        lines[i] = pat.sub(lambda m: f"{m.group(1)}{echon_base}", ln)
                        did = True
                        break
                    # Fallback: previous bad state like "  \122800  ; ..." or other formats
                    # Reconstruct the instruction preserving indentation and comment
                    m_ws = re.match(r'^(\s*)', ln)
                    prefix = m_ws.group(1) if m_ws else ''
                    comment_idx = ln.find(';')
                    comment = ln[comment_idx:] if comment_idx != -1 else ''
                    lines[i] = f"{prefix}JSR #{echon_base}" + (" " + comment.lstrip() if comment else '')
                    did = True
                    break
                if did:
                    os_path.write_text("\n".join(lines) + "\n")
                    print(f"Patched ECHON call in {os_path} to base {echon_base}")
                else:
                    print("ECHON call site not found for patching (skipped)")
    except Exception as e:
        print(f"Warning: failed to patch ECHON call: {e}")

    # Always patch CALL_STUB operand to SHELL base in emulator_os.txt
    try:
        shell_base = None
        for k, v in data.items():
            if isinstance(v, dict) and k.lower() == 'shell' and 'base' in v:
                shell_base = int(v['base'])
                break
        if shell_base is not None:
            os_path = Path(__file__).parent.parent / "32bit" / "emulator_os.txt"
            if os_path.exists():
                lines = os_path.read_text().splitlines()
                # Find CALL_STUB base
                call_stub_base = None
                for ln in lines:
                    s = ln.strip().replace(" ", "")
                    if s.startswith('CALL_STUB='):
                        try:
                            call_stub_base = int(s.split('=', 1)[1])
                        except Exception:
                            pass
                        break
                did = False
                if call_stub_base is not None:
                    target = call_stub_base + 1
                    for i, ln in enumerate(lines):
                        s = ln.replace(" ", "")
                        if s.startswith(f"{target}="):
                            comment_idx = ln.find(';')
                            comment = ln[comment_idx:] if comment_idx != -1 else ''
                            lines[i] = f"{target} = {shell_base}" + (" " + comment.lstrip() if comment else '')
                            did = True
                            break
                if not did:
                    # Fallback heuristic: patch the line following the ' = 16' (JSR) in the call stub region
                    for i in range(len(lines) - 1):
                        if '= 16' in lines[i]:
                            # next line should be operand
                            parts = lines[i+1].split(';', 1)
                            left = parts[0]
                            comment = ';' + parts[1] if len(parts) > 1 else ''
                            # Replace right-hand side after '=' with shell_base
                            if '=' in left:
                                addr = left.split('=')[0].rstrip()
                                lines[i+1] = f"{addr}= {shell_base}{comment}"
                                did = True
                                break
                if did:
                    os_path.write_text("\n".join(lines) + "\n")
                    print(f"Patched CALL_STUB operand in {os_path} to SHELL base {shell_base}")
                else:
                    print("CALL_STUB operand not found for patching (skipped)")
    except Exception as e:
        print(f"Warning: failed to patch CALL_STUB to SHELL: {e}")

    if apply_table:
        # Legacy: still allow patching OS file on request (kept for compatibility)
        table_lines = [f"prog_table = {pt_base}", "; Command/program table entries: name[0..7], addr[8], reserved[9]"]
        for i, (name, mod) in enumerate(entries):
            off = i * 10
            nm = str(name).upper()[:8]
            base = int(mod.get("base", 0))
            table_lines.append(f".prog_table + {off}  = \"{nm}\"")
            table_lines.append(f".prog_table + {off+8} = {base}")
            table_lines.append(f".prog_table + {off+9} = 0")
        table_lines.append(f".prog_table + {len(entries)*10} = 0    ; sentinel")
        apply_prog_table_to_os(table_lines, data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Assemble routines and emit program table")
    parser.add_argument("--apply-table", action="store_true", help="Apply the generated program table into 32bit/emulator_os.txt")
    args = parser.parse_args()
    main(apply_table=args.apply_table)
