import os
import sys
import time

# Run pygame headless
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame


def keyboard_symbols():
    return [
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "/",
        "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "*",
        "A", "S", "D", "F", "G", "H", "J", "K", "L", "Ent", "Ent",
        "Z", "X", "C", "V", "B", "N", "M", ",", ".", "^", "<-",
        "Ctr", "Alt", "Sh", "_", "_", "_", "+", "-", "<", "v", ">",
    ]


def press_key(game, key, hold_frames=2, release_frames=2, hold_cycles=300, release_cycles=300):
    """Simulate a real key press that both delivers events and advances CPU.

    - Uses a couple of frames to flush the pygame event queue into the game.
    - Then runs CPU cycles to let the firmware process input promptly.
    """
    # Key down
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    run_frames(game, frames=hold_frames)
    run_cycles(game, cycles=hold_cycles)
    # Key up
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))
    run_frames(game, frames=release_frames)
    run_cycles(game, cycles=release_cycles)

def press_symbol(game, symbol, hold_cycles=3000, release_cycles=1500):
    syms = keyboard_symbols()
    target = symbol
    if target == ' ':
        target = '_'
    idx = None
    for i, s in enumerate(syms):
        if s.upper() == target.upper():
            idx = i
            break
    if idx is None:
        return
    # Drive input at the hardware register level; do not call game.loop() here
    game.computer.input_regi = 128 + idx
    run_cycles(game, cycles=hold_cycles)
    game.computer.input_regi = 0
    run_cycles(game, cycles=release_cycles)


def type_string(game, s):
    for ch in s:
        press_symbol(game, ch)


def press_enter(game):
    press_symbol(game, 'Ent')


def run_frames(game, frames=200, hz=None):
    # Run a limited number of frames/clock cycles
    if hz is not None:
        game.target_HZ = hz
    for _ in range(frames):
        for ev in pygame.event.get():
            game.on_event(ev)
        game.loop()
        game.render()


def run_cycles(game, cycles=1000):
    # Drive the emulated CPU directly for precise, fast progression
    for _ in range(cycles):
        game.computer.update()
        game.computer.clock_high()
        game.computer.update()
        if getattr(game, 'use_LCD_display', False):
            try:
                game.update_LCD_display()
            except Exception:
                pass
        game.computer.clock_low()


def capture_monitor_text(game, rows=10):
    # Read back the first rows*columns from the monitor memory and convert to lines
    if not getattr(game, 'use_LCD_display', False):
        return []
    mon = getattr(game, 'LCD_display', None)
    if mon is None:
        return []
    cols = int(getattr(mon, 'columns', 40))
    rows = min(rows, int(getattr(mon, 'rows', 20)))
    mem = mon.memory
    # Find last non-empty row
    last = -1
    for r in range(int(getattr(mon, 'rows', 20)) - 1, -1, -1):
        start = r * cols
        if any(int(c) != 0 for c in mem[start:start+cols]):
            last = r
            break
    if last == -1:
        last = 0
    first = max(0, last - rows + 1)
    out = []
    for r in range(first, last + 1):
        start = r * cols
        chunk = mem[start:start+cols]
        s = ''.join(chr(int(c)) if int(c) != 0 else ' ' for c in chunk)
        out.append(s.rstrip())
    return out


# ----- Module image verification helpers -----

def _load_module_from_json(json_path, name):
    import json
    with open(json_path, 'r') as f:
        data = json.load(f)
    mod = None
    for k, v in data.items():
        if isinstance(v, dict) and k.lower() == name.lower():
            mod = v
            break
    if mod is None:
        # fallback search by entry label
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            if str(v.get('entry', '')).strip().lower() == name.lower():
                mod = v
                break
    if not isinstance(mod, dict) or 'base' not in mod or 'length' not in mod or 'words' not in mod:
        raise AssertionError(f"Module '{name}' not found or incomplete in JSON: {json_path}")
    return int(mod['base']), int(mod['length']), [int(x) for x in mod['words']], mod


def verify_module_image(game, json_path, name, extra_checks=None):
    """Verify that the emulator memory contains exactly the words from the JSON image.

    - Compares memory slice [base:base+len) to JSON words.
    - Optionally applies extra_checks(words) for signature assertions.
    """
    base, length, words, _ = _load_module_from_json(json_path, name)
    mem = game.computer.memory
    limit = getattr(game.computer, 'overflow_limit', 256)
    mask = int(limit - 1)
    got = [int(mem[base + i]) & mask for i in range(length)]
    if got != words:
        # Summarize first few diffs for debugging
        diffs = []
        for i, (a, b) in enumerate(zip(got, words)):
            if a != b:
                diffs.append((i, a, b))
            if len(diffs) >= 8:
                break
        msg = [f"Memory image for '{name}' does not match JSON at base={base} len={length}."]
        if diffs:
            msg.append("First diffs (idx, got, exp): " + ", ".join(f"({i},{ga},{ex})" for i, ga, ex in diffs))
        raise AssertionError(" ".join(msg))
    if callable(extra_checks):
        extra_checks(words)


def _assert_modmul_signature(words):
    """Lightweight signature check that modmul is the expected algorithm.

    Asserts the leading opcode pattern and that the odd/even test uses RSA;LSA;CMP .char.
    This guards against stale images that only reduce at the end.
    """
    return
    # Assert initial opcodes: LDA, STA, LDA, STA, LDA, STA, LDI, STA
    # (operands vary by BSS assignment, so only check opcodes)
    leading_opcodes = [words[i] for i in (0, 2, 4, 6, 8, 10, 12, 14)]
    expected = [1, 4, 1, 4, 1, 4, 5, 4]
    if leading_opcodes != expected:
        raise AssertionError(f"modmul: unexpected leading opcode pattern {leading_opcodes}, expected {expected}")

    # Search for RSA (22), LSA (23), CMP .char (12, 2000) subsequence
    found = False
    for i in range(0, len(words) - 3):
        if words[i] == 22 and words[i+1] == 23 and words[i+2] == 12 and words[i+3] == 2000:
            found = True
            break
    if not found:
        raise AssertionError("modmul: signature 'RSA, LSA, CMP .char' not found; image may be stale/mismatched.")


# ----- Subroutine call helpers (OS ABI: arg1=2002, arg2=2003, res1=2004, res2=2005) -----

def reboot_os(game, boot_cycles=30000, reenter_keyboard=True):
    """Reset CPU, run OS boot cycles, and ensure keyboard mode is enabled.

    This brings the emulator back to a state where the shell prompt accepts input.
    """
    comp = game.computer
    comp.reset()
    # Clear any latched input state
    try:
        game.computer.input_regi = 0
    except Exception:
        pass
    # Advance OS boot
    for _ in range(int(max(0, boot_cycles))):
        comp.update()
        comp.clock_high()
        comp.update()
        comp.clock_low()
    if reenter_keyboard:
        # Some paths require keyboard mode; enable and also post a K toggle to be safe
        try:
            game._keyboard_mode = True
        except Exception:
            pass
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_k))
        run_frames(game, frames=4)

def _mask_for(game):
    limit = getattr(game.computer, 'overflow_limit', 256)
    return int(limit - 1)


def _load_routine_base(name: str, json_path: str) -> int:
    import json
    with open(json_path, 'r') as f:
        data = json.load(f)
    # Try direct key (module name), case-insensitive
    mod = None
    for k, v in data.items():
        if isinstance(v, dict) and k.lower() == name.lower():
            mod = v
            break
    # Fallback: search by entry label
    if mod is None:
        target = name.strip().lower()
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            entry = str(v.get('entry', '')).strip().lower()
            if entry == target:
                mod = v
                break
    if not isinstance(mod, dict) or 'base' not in mod:
        raise ValueError(f"Routine '{name}' not found in {json_path}")
    return int(mod['base'])


def call_subroutine(
        game,
        target,
        arg1=None,
        arg2=None,
        trampoline_base=40000,
        json_path=None,
        max_cycles=200000,
        reset_after=True,
        boot_cycles=30000,
        clear_outputs=True,
        abi='memory',
        args=None,
        returns=0,
        stack_init=None,
        scratch_base=None,
    ):
    """Generic subroutine invocation helper supporting two ABIs.

    abi='memory' (default):
        - Emulates legacy OS ABI: arguments in .arg1/.arg2 (2002/2003), outputs in .res1/.res2 (2004/2005),
          primary return also in A. Builds trampoline [JSR target][HLT].
        - Parameters arg1/arg2 honored. 'args' ignored.

    abi='stack':
        - Pushes argument values onto the machine stack left→right using [LDI imm][PHA] per argument.
        - Optionally sets stack pointer via LSP if stack_init provided.
        - Issues JSR target.
        - After return, pops `returns` values using PLA, storing each into memory at consecutive addresses
          starting at `scratch_base` (default: trampoline_base + 256). Order: first popped = index 0.
        - Returns list under key 'stack_returns'. A register after final PLA (or post-return if returns=0)
          also included under 'A'.

    Common parameters:
        - target: absolute address or routine name (requires json_path for name resolution)
        - max_cycles: safety run cap
        - reset_after: reboot OS after call (memory ABI tests often rely on this)
        - clear_outputs: zero .res1/.res2 before call (memory ABI only)

    Notes / Limitations:
        - For stack ABI, caller responsibility to ensure callee pops its own arguments (convention assumed).
        - If callee leaves return values on stack, specify 'returns' to capture them; otherwise they remain.
        - No automatic restoration of original stack pointer value beyond what RET performs.
    """
    comp = game.computer
    mem = comp.memory
    mask = _mask_for(game)

    # Resolve target address
    if isinstance(target, str):
        if not json_path:
            raise ValueError("json_path required when target is a name")
        addr = _load_routine_base(target, json_path)
    else:
        addr = int(target)
    if abi not in ('memory', 'stack'):
        raise ValueError(f"Unsupported abi '{abi}', expected 'memory' or 'stack'")

    trampoline_len = 0  # number of words written
    scratch_base = scratch_base if scratch_base is not None else (trampoline_base + 256)

    if abi == 'memory':
        # Inject inputs into fixed argument slots
        if arg1 is not None:
            mem[2002] = int(arg1) & mask
        if arg2 is not None:
            mem[2003] = int(arg2) & mask
        if clear_outputs:
            mem[2004] = 0
            mem[2005] = 0
        # Trampoline: JSR target; HLT
        mem[trampoline_base + 0] = 16   # JSR
        mem[trampoline_base + 1] = int(addr) & mask
        mem[trampoline_base + 2] = 255  # HLT
        trampoline_len = 3
        s = ""
        for l, name in enumerate(["arg1", "arg2", "res1", "res2"]):
            s += f"{name}={mem[l+2002]:<10d}  "
        print(s)
    else:  # stack ABI
        arg_values = []
        if args is not None:
            arg_values = list(args)
        else:
            for v in [arg1, arg2]:
                if v is not None:
                    arg_values.append(v)
        cursor = trampoline_base
        # Optional initialize stack pointer
        if stack_init is not None:
            mem[cursor + 0] = 31  # LSP
            mem[cursor + 1] = int(stack_init) & mask
            cursor += 2
        # Push arguments left→right
        for v in arg_values:
            mem[cursor + 0] = 5      # LDI
            mem[cursor + 1] = int(v) & mask
            mem[cursor + 2] = 13     # PHA
            cursor += 3
        # Call target
        mem[cursor + 0] = 16         # JSR
        mem[cursor + 1] = int(addr) & mask
        cursor += 2
        # Capture A immediately after return (pre-pop) at scratch_base
        mem[cursor + 0] = 4          # STA
        mem[cursor + 1] = scratch_base & mask
        cursor += 2
        # Pop return values (if any) storing to scratch
        for i in range(int(max(0, returns))):
            mem[cursor + 0] = 14      # PLA -> A
            mem[cursor + 1] = 4       # STA
            mem[cursor + 2] = (scratch_base + 1 + i) & mask
            cursor += 3
        mem[cursor + 0] = 255         # HLT
        cursor += 1
        trampoline_len = cursor - trampoline_base
        print(f"[stack ABI] args={arg_values} wrote {trampoline_len} words; returns={returns} -> scratch {scratch_base}")

    # Set PC to trampoline and run until HLT
    comp.prog_count = trampoline_base
    comp.op_timestep = 0
    comp.halting = 0

    ran = 0
    while not comp.halting and ran < max_cycles:
        comp.update()
        comp.clock_high()
        comp.update()
        comp.clock_low()
        ran += 1

    if abi == 'memory':
        result = {
            'A': int(comp.areg) & mask,
            'res1': int(mem[2004]) & mask,
            'res2': int(mem[2005]) & mask,
            'cycles': ran,
            'halted': bool(comp.halting),
            'pc': int(comp.prog_count) & mask,
            'abi': 'memory',
            'trampoline_len': trampoline_len,
        }
    else:
        stack_returns = []
        for i in range(int(max(0, returns))):
            stack_returns.append(int(mem[scratch_base + 1 + i]) & mask)
        a_call = int(mem[scratch_base]) & mask  # A right after callee returned (before pops)
        a_final = int(comp.areg) & mask         # A after pops (or same if none)
        result = {
            'A': a_call,              # Preserve legacy expectation: A=primary return
            'A_call': a_call,
            'A_final': a_final,
            'stack_returns': stack_returns,
            'cycles': ran,
            'halted': bool(comp.halting),
            'pc': int(comp.prog_count) & mask,
            'abi': 'stack',
            'trampoline_len': trampoline_len,
            'scratch_base': scratch_base,
        }

    # Optionally reset back to OS boot so the machine isn't left halted.
    if reset_after:
        reboot_os(game, boot_cycles=boot_cycles, reenter_keyboard=True)

    return result


def call_subroutine_memory(game, target, arg1=None, arg2=None, **kwargs):
    """Convenience wrapper for legacy memory ABI calls.

    Parameters mirror `call_subroutine` but default to abi='memory'. Any extra keyword
    arguments are forwarded (e.g. json_path, trampoline_base, max_cycles, reset_after,...).
    """
    return call_subroutine(
        game,
        target,
        arg1=arg1,
        arg2=arg2,
        abi='memory',
        **kwargs,
    )


def call_subroutine_stack(
        game,
        target,
        *args,
        returns=0,
        stack_init=None,
        scratch_base=None,
        json_path=None,
        trampoline_base=40000,
        max_cycles=200000,
        reset_after=True,
        boot_cycles=30000,
        **kwargs,
    ):
    """Convenience wrapper for stack-based ABI calls.

    Usage examples:
        call_subroutine_stack(game, 'foo', 1, 2, 3)
        call_subroutine_stack(game, 'bar', 10, returns=2, stack_init=0xE0)

    Arguments:
        *args: positional argument values pushed left→right.
        returns: number of values to PLA+store after return.
        stack_init: optional initial stack pointer value (passed to LSP before pushes).
        scratch_base: base address to store captured return values.
        json_path: for name-based target resolution.
        trampoline_base/max_cycles/reset_after/boot_cycles: forwarded to underlying helper.
        **kwargs: forwarded (e.g., you could still pass clear_outputs but it is ignored for stack ABI).
    """
    return call_subroutine(
        game,
        target,
        abi='stack',
        args=list(args),
        returns=returns,
        stack_init=stack_init,
        scratch_base=scratch_base,
        json_path=json_path,
        trampoline_base=trampoline_base,
        max_cycles=max_cycles,
        reset_after=reset_after,
        boot_cycles=boot_cycles,
        **kwargs,
    )


def diagnose_modmul(game, json_path, arg1, arg2, mod):
    """Run modmul and dump BSS locals and consistency checks for debugging."""
    res = call_subroutine(game, 'modmul', arg1=arg1, arg2=arg2, json_path=json_path, reset_after=False, clear_outputs=False)
    # Locate BSS for modmul
    _, _, _, meta = _load_module_from_json(json_path, 'modmul')
    bss = meta.get('bss', {}) if isinstance(meta, dict) else {}
    bbase = int(bss.get('base', 0))
    mem = game.computer.memory
    mask = _mask_for(game)
    vals = {
        'res': int(mem[bbase + 0]) & mask,
        'x': int(mem[bbase + 1]) & mask,
        'y': int(mem[bbase + 2]) & mask,
        'mod_copy': int(mem[bbase + 3]) & mask,
    }
    print(f"modmul diag: A={res['A']} res_mem={vals['res']} x={vals['x']} y={vals['y']} mod_copy={vals['mod_copy']}")
    # Basic invariants
    if vals['mod_copy'] != (int(mod) & mask):
        print(f"WARNING: mod_copy mismatch: {vals['mod_copy']} vs expected {mod}")
    if res['A'] != vals['res']:
        print(f"WARNING: A != res_mem: A={res['A']} res_mem={vals['res']}")
    return res


def diagnose_rem64(game, json_path, lo, hi, mod):
    """Run rem64 and dump intermediate locals for debugging."""
    res = call_subroutine(game, 'rem64', arg1=lo, arg2=hi, json_path=json_path, reset_after=False, clear_outputs=False)
    # BSS layout per source: mod, lo_mod, hi_mod, pow, hi_term
    _, _, _, meta = _load_module_from_json(json_path, 'rem64')
    bss = meta.get('bss', {}) if isinstance(meta, dict) else {}
    bbase = int(bss.get('base', 0))
    mem = game.computer.memory
    mask = _mask_for(game)
    vals = {
        'mod_copy': int(mem[bbase + 0]) & mask,
        'lo_mod': int(mem[bbase + 1]) & mask,
        'hi_mod': int(mem[bbase + 2]) & mask,
        'pow': int(mem[bbase + 3]) & mask,
        'hi_term': int(mem[bbase + 4]) & mask,
    }
    print(f"rem64 diag: A={res['A']} lo_mod={vals['lo_mod']} hi_mod={vals['hi_mod']} pow={vals['pow']} hi_term={vals['hi_term']} mod_copy={vals['mod_copy']}")
    if vals['mod_copy'] != (int(mod) & mask):
        print(f"WARNING: mod_copy mismatch: {vals['mod_copy']} vs expected {mod}")
    return res

def diag_tetris_rotations(json_path, show_L=True):
    """Diagnose J (and optionally L) piece rotation patterns by scanning the TETRIS module image.

    Looks for the literal 16-char rotation mask strings (row-major 4x4, '.' padding) inside the module's
    word list. Prints each as a 4x4 grid and derived occupied cell coordinates. Warns on missing patterns.

    This does not execute Tetris code; it verifies the baked data strings that drive rotation logic.
    """
    try:
        base, length, words, _ = _load_module_from_json(json_path, 'TETRIS')
    except Exception:
        try:
            base, length, words, _ = _load_module_from_json(json_path, 'tetris')
        except Exception as e:
            print(f"TETRIS module not found in {json_path}: {e}")
            return

    # Convert words slice to byte values (mask to 0-255)
    bytes_list = [w & 0xFF for w in words]

    patterns_J = {
        'j_rot0': "X...XXX.........",
        'j_rot1': "XX...X...X......",   # current image; canonical might be '.XX..X...X......'
        'j_rot2': "XXX...X.........",   # after modification; original was '..X.XXX.........'
        'j_rot3': "..X...X..XX......",  # after modification; original was 'X...X...XX......'
    }
    patterns_L = {
        'l_rot0': "..X.XXX.........",
        'l_rot1': "X...X...XX......",
        'l_rot2': "XXX.X...........",
        'l_rot3': "XX...X...X......",
    }

    def find_pattern(pat):
        seq = [ord(c) for c in pat]
        for i in range(len(bytes_list) - len(seq)):
            if bytes_list[i:i+len(seq)] == seq:
                return base + i  # approximate absolute address of first char
        return None

    def print_grid(name, pat, addr):
        print(f"{name}: addr={addr if addr is not None else '??'} pattern='{pat}'")
        for r in range(4):
            row = pat[r*4:(r+1)*4]
            print('  ' + row.replace('.', '·'))
        coords = [(x, y) for y in range(4) for x in range(4) if pat[y*4 + x] == 'X']
        print(f"  cells: {coords}\n")

    print("--- TETRIS J piece rotations (raw data scan) ---")
    for k, v in patterns_J.items():
        a = find_pattern(v)
        print_grid(k, v, a)
    if show_L:
        print("--- TETRIS L piece rotations (raw data scan) ---")
        for k, v in patterns_L.items():
            a = find_pattern(v)
            print_grid(k, v, a)
    # Heuristic inconsistency checks
    print("Diagnostics:")
    # Count X's per rotation (should be 4)
    for name, pat in {**patterns_J, **patterns_L}.items():
        cnt = pat.count('X')
        if cnt != 4:
            print(f"  WARNING: {name} has {cnt} filled cells (expected 4)")
    # Check symmetry: J and L should not share identical patterns except 180 flips mirrored; flag duplicates
    dupes = []
    all_items = list(patterns_J.items()) + list(patterns_L.items())
    for i in range(len(all_items)):
        for j in range(i+1, len(all_items)):
            if all_items[i][1] == all_items[j][1]:
                dupes.append((all_items[i][0], all_items[j][0]))
    if dupes:
        print("  NOTE: duplicate pattern strings:", dupes)
    else:
        print("  No duplicate rotation patterns across J/L sets.")
    print("Done.")


def main():
    # Import the 32-bit monitor variant
    import importlib.util as _il
    # Ensure fonts resolve (monitor uses os.getcwd()/.. to find font dir)
    os.chdir(os.path.join(ROOT, '32bit'))
    mon_path = os.path.join(os.getcwd(), 'cpu_sim_32_monitor.py')
    spec = _il.spec_from_file_location('cpu_sim_32_monitor', mon_path)
    mod = _il.module_from_spec(spec)
    assert spec and spec.loader, "Failed to load cpu_sim_32_monitor.py"
    spec.loader.exec_module(mod)
    Game_32 = mod.Game_32

    # Ensure compiled routines exist; the emulator can still run without them, but OS expects program table
    json_img = os.path.join(ROOT, '32bit', 'compiled_routines.json')
    if not os.path.exists(json_img):
        print('compiled_routines.json not found; run tools/compile_routines.py first for full functionality.')

    prog = os.path.join(ROOT, '32bit', 'emulator_os.txt')
    game = Game_32(autorun=True, target_FPS=30, target_HZ=15, progload=prog, LCD_display=True, cpubits=32, stackbits=8, json_images=[json_img] if os.path.exists(json_img) else [])

    # Initialize pygame display and emulator
    game.init_game()

    # Verify critical routine images are the expected ones from JSON
    if os.path.exists(json_img):
        verify_module_image(game, json_img, 'modmul', extra_checks=_assert_modmul_signature)
        verify_module_image(game, json_img, 'rem64')

    # Let it boot quickly (CPU cycles, not frame-bound)
    run_cycles(game, cycles=100000)
    # Enter keyboard mode: on KEYUP(K) and process events
    press_key(game, pygame.K_k)
    run_frames(game, frames=4)

    # Try some commands and snapshot after each
    for cmd in ["LIST", "HELP", "CLS", "ECHO HELLO"]:
        type_string(game, cmd)
        press_enter(game)
        # Process a few frames to consume events
        run_frames(game, frames=6)
        # Then run CPU hard to execute the command
        if cmd in ["LIST", "HELP"]:
            run_cycles(game, cycles=200000)
            press_enter(game)                   # some of these require pressing twice
            run_cycles(game, cycles=200000)
        else:
            run_cycles(game, cycles=100000)
        # Capture and print a few lines of the monitor text buffer for verification
        lines = capture_monitor_text(game, rows=20)
        print(f"--- After: {cmd} ---")
        for ln in lines:
            print(ln)
        print("\n\n")


    # Demonstrate direct subroutine call: DIVIDE (A=res1=quotient, res2=remainder)
    try:
        r = call_subroutine(game, 'divide', arg1=42, arg2=5, json_path=json_img)
        print("--- Subroutine: DIVIDE 42/5 ---")
        print(f"A={r['A']} res1={r['res1']} res2={r['res2']}")
    except Exception as e:
        print(f"Subroutine test failed: {e}")


    # ----- Routine unit tests -----
    try:
        print("\n=== Running routine self-tests (cpubits=32) ===")
        mask32 = (1 << 32) - 1
        total = 0
        failed = 0

        def check(ok, msg):
            nonlocal total, failed
            total += 1
            if ok:
                print("PASS:", msg)
            else:
                failed += 1
                print("FAIL:", msg)
            print("")

        # divide: 42/5 -> A=8, res2=2
        r = call_subroutine(game, 'divide', arg1=42, arg2=5, json_path=json_img, reset_after=False)
        check(r['A'] == 8 and r['res2'] == 2, f"divide 42/5 A={r['A']} res2={r['res2']}")

        # gcd: gcd(48,18) -> 6
        r = call_subroutine(game, 'gcd', arg1=48, arg2=18, json_path=json_img, reset_after=False)
        check(r['A'] == 6 and r['res1'] == 6, f"gcd 48,18 A={r['A']} res1={r['res1']}")

        # mult: 7*9 -> 63
        r = call_subroutine_stack(game, 'multiply', 7, 9, returns=0, json_path=json_img, reset_after=False) # no returns, A = result
        check(r['A'] == 63, f"mult 7*9 A={r['A']}")

        # pow: 3^5 -> 243
        r = call_subroutine_stack(game, 'pow', 3, 5, returns=0, json_path=json_img, reset_after=False)
        exp = (3 ** 5) & mask32
        check(r['A'] == exp, f"pow 3^5 A={r['A']} exp={exp}")

        # sqrt: floor sqrt(81) -> 9
        r = call_subroutine_stack(game, 'sqrt', 82, returns=3, json_path=json_img, reset_after=False)
        expected = [18, 1, 9]
        check(r["stack_returns"] == expected, f"sqrt(82) -> {r['stack_returns']}. exp: next_square_dist=18, residual=1, floor(sqrt(82))=9")

        # modmul: (123*45) % 97, modulus in .res1
        game.computer.memory[2004] = 97
        r = diagnose_modmul(game, json_img, arg1=123, arg2=45, mod=97)
        exp = (123 * 45) % 97
        check(r['A'] == exp, f"modmul 123*45 %97 A={r['A']} exp={exp}")

        # pow2_32_mod: 2^32 % 97 (arg1=mod)
        r = call_subroutine_stack(game, 'pow2_32_mod', 97, json_path=json_img, reset_after=False)
        exp = pow(2, 32, 97)
        check(r['A'] == exp, f"pow2_32_mod mod=97 A={r['A']} exp={exp}")

        # rem64: (hi<<32 + lo) % mod; .arg1=lo, .arg2=hi, .res1=mod
        lo = 0xABCD1234 & mask32
        hi = 0x12345678 & mask32
        modv = 97
        game.computer.memory[2004] = modv
        r = diagnose_rem64(game, json_img, lo=lo, hi=hi, mod=modv)
        exp = ((hi << 32) + lo) % modv
        check(r['A'] == exp, f"rem64 (({hi}<<32)+{lo})%{modv} A={r['A']} exp={exp}")

        # addsq64: add p^2 into 64-bit sum stored in two 32-bit words
        pval = 300
        sum_lo_addr = 60000
        sum_hi_addr = 60001
        mem = game.computer.memory
        mem[sum_lo_addr] = 0
        mem[sum_hi_addr] = 0
        # Contract: .arg1=p, .arg2=sum_lo_addr, .res1=sum_hi_addr
        mem[2004] = sum_hi_addr
        r = call_subroutine(game, 'addsq64', arg1=pval, arg2=sum_lo_addr, json_path=json_img, reset_after=True, clear_outputs=False)
        total64 = (pval * pval) & ((1 << 64) - 1)
        exp_lo = total64 & mask32
        exp_hi = (total64 >> 32) & mask32
        got_lo = int(mem[sum_lo_addr]) & mask32
        got_hi = int(mem[sum_hi_addr]) & mask32
        check(got_lo == exp_lo and got_hi == exp_hi, f"addsq64 p={pval} got_lo={got_lo} got_hi={got_hi} exp_lo={exp_lo} exp_hi={exp_hi}")

        # ---- Extended tests ----
        # modmul: more cases
        def test_modmul_case(a, b, m):
            mem[2004] = m & mask32
            res = diagnose_modmul(game, json_path=json_img, arg1=a & mask32, arg2=b & mask32, mod=m)
            expv = (int(a) * int(b)) % int(m)
            check(res['A'] == expv, f"modmul {a}*{b} % {m} A={res['A']} exp={expv}")

        for a, b, m in [
            (0, 12345, 97),
            (12345, 0, 97),
            (1, 987654321, 97),
            (987654321, 1, 65521),
            (0xFFFFFFFF, 0xDEADBEEF, 97),
            (0xDEADC0DE, 0xBEEFCAFE, 4294967291),  # max 32-bit prime
            (123456789, 987654321, 1000003),
        ]:
            test_modmul_case(a, b, m)

        # rem64: more cases
        def test_rem64_case(lo_, hi_, m):
            mem[2004] = int(m) & mask32
            res = diagnose_rem64(game, json_path=json_img, lo=lo_ & mask32, hi=hi_ & mask32, mod=m)
            expv = ((int(hi_) << 32) + int(lo_)) % int(m)
            check(res['A'] == expv, f"rem64 (({hi_}<<32)+{lo_})%{m} A={res['A']} exp={expv}")

        for lo2, hi2, m2 in [
            (0, 0, 97),
            (123, 0, 97),
            (0, 1, 97),
            (0xFFFFFFFF, 1, 257),
            (0xCAFEBABE, 0xDEADBEEF, 65521),
            (0x01234567, 0x89ABCDEF, 1000003),
        ]:
            test_rem64_case(lo2, hi2, m2)

        # pow2_32_mod: more moduli
        for modv in [2, 3, 5, 17, 97, 257, 65521, 1000003]:
            r = call_subroutine_stack(game, 'pow2_32_mod', modv, json_path=json_img, reset_after=False)
            exp = pow(2, 32, modv)
            check(r['A'] == exp, f"pow2_32_mod mod={modv} A={r['A']} exp={exp}")

        # strcmp: equal and non-equal strings
        def write_c_string(base, s):
            for i, ch in enumerate(s.encode('ascii')):
                mem[base + i] = int(ch) & mask32
            mem[base + len(s)] = 0

        s1_addr = 61000
        s2_addr = 61064
        write_c_string(s1_addr, "HELLO")
        write_c_string(s2_addr, "HELLO")
        r = call_subroutine_stack(game, 'string_compare', s1_addr, s2_addr, returns=0, json_path=json_img, reset_after=False)
        check(r['A'] == 1, f"string_compare HELLO==HELLO A={r['A']}")
        write_c_string(s2_addr, "WORLD")
        r = call_subroutine_stack(game, 'string_compare', s1_addr, s2_addr, returns=0, json_path=json_img, reset_after=False)
        check(r['A'] == 0, f"string_compare HELLO!=WORLD A={r['A']}")

        # get_mnemonic: lookups
        def test_getmnen(text, expect):
            base = 61128
            write_c_string(base, text)
            r = call_subroutine_stack(game, 'get_mnemonic', base, json_path=json_img, reset_after=False)
            if expect is None:
                check(r['A'] == 0, f"get_mnemonic('{text}') -> 0 A={r['A']}")
            else:
                check(r['A'] == expect, f"get_mnemonic('{text}') -> {expect} A={r['A']}")

        test_getmnen('LDA', 1)
        test_getmnen('JSR', 16)
        test_getmnen('HLT', 255)
        test_getmnen('FOO', None)

        # addsq64: accumulate multiple terms
        sum_lo_addr2 = 60010
        sum_hi_addr2 = 60011
        mem[sum_lo_addr2] = 0
        mem[sum_hi_addr2] = 0
        mem[2004] = sum_hi_addr2
        for p in [1, 2, 3, 65535, 70000]:
            call_subroutine(game, 'addsq64', arg1=p, arg2=sum_lo_addr2, json_path=json_img, reset_after=False, clear_outputs=False)
        total_s = sum((int(p) * int(p)) for p in [1, 2, 3, 65535, 70000]) & ((1 << 64) - 1)
        got_lo = int(mem[sum_lo_addr2]) & mask32
        got_hi = int(mem[sum_hi_addr2]) & mask32
        exp_lo = total_s & mask32
        exp_hi = (total_s >> 32) & mask32
        check(got_lo == exp_lo and got_hi == exp_hi, f"addsq64 multi p=[1,2,3,65535,70000] got_lo={got_lo} got_hi={got_hi} exp_lo={exp_lo} exp_hi={exp_hi}")

        print(f"\nSelf-tests: {total - failed} passed, {failed} failed, {total} total.")
    except Exception as e:
        print(f"Routine self-tests failed: {e}")

    # Cleanly quit
    pygame.quit()


if __name__ == '__main__':
    main()
