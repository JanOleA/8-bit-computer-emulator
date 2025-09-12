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
    mod = data.get(name)
    if not isinstance(mod, dict) or 'base' not in mod:
        raise ValueError(f"Routine '{name}' not found in {json_path}")
    return int(mod['base'])


def call_subroutine(game, target, arg1=None, arg2=None, trampoline_base=15000, json_path=None,
                    max_cycles=200000, reset_after=True, boot_cycles=30000):
    """Inject .arg1/.arg2, JSR to target, run until HLT, return A, .res1, .res2.

    - target: int absolute address or str routine name (requires json_path).
    - Writes a tiny trampoline: [JSR target][HLT] at trampoline_base.
    - Returns a dict: { 'A': areg, 'res1': mem[2004], 'res2': mem[2005] }.
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

    # Inject inputs
    if arg1 is not None:
        mem[2002] = int(arg1) & mask
    if arg2 is not None:
        mem[2003] = int(arg2) & mask
    # Clear outputs
    mem[2004] = 0
    mem[2005] = 0

    # Build trampoline: JSR #addr; HLT
    mem[trampoline_base + 0] = 16   # JSR
    mem[trampoline_base + 1] = int(addr) & mask
    mem[trampoline_base + 2] = 255  # HLT

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

    result = {
        'A': int(comp.areg) & mask,
        'res1': int(mem[2004]) & mask,
        'res2': int(mem[2005]) & mask,
        'cycles': ran,
        'halted': bool(comp.halting),
        'pc': int(comp.prog_count) & mask,
    }

    # Optionally reset back to OS boot so the machine isn't left halted.
    if reset_after:
        reboot_os(game, boot_cycles=boot_cycles, reenter_keyboard=True)

    return result


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

    # Let it boot quickly (CPU cycles, not frame-bound)
    run_cycles(game, cycles=30000)
    # Enter keyboard mode: on KEYUP(K) and process events
    press_key(game, pygame.K_k)
    run_frames(game, frames=4)

    # Try some commands and snapshot after each
    for cmd in ["LIST", "HELP", "ECHO HELLO", "CLS"]:
        type_string(game, cmd)
        press_enter(game)
        # Process a few frames to consume events
        run_frames(game, frames=6)
        # Then run CPU hard to execute the command
        run_cycles(game, cycles=80000)
        # Capture and print a few lines of the monitor text buffer for verification
        lines = capture_monitor_text(game, rows=20)
        print(f"--- After: {cmd} ---")
        for ln in lines:
            print(ln)

    # Demonstrate direct subroutine call: DIVIDE (A=res1=quotient, res2=remainder)
    try:
        json_img_path = json_img if os.path.exists(json_img) else None
        # Fresh instance to avoid halting state from trampoline
        game2 = Game_32(autorun=True, target_FPS=30, target_HZ=15, progload=prog, LCD_display=False, cpubits=32, stackbits=8, json_images=[json_img] if json_img_path else [])
        game2.init_game()
        # Run a small boot to ensure machine initialized
        run_cycles(game2, cycles=1000)
        r = call_subroutine(game2, 'divide', arg1=42, arg2=5, json_path=json_img)
        print("--- Subroutine: DIVIDE 42/5 ---")
        print(f"A={r['A']} res1={r['res1']} res2={r['res2']} cycles={r['cycles']} halted={r['halted']}")
        type_string(game, "LIST")
        press_enter(game)
        # Process a few frames to consume events
        run_frames(game, frames=6)
        # Then run CPU hard to execute the command
        run_cycles(game, cycles=80000)
        lines = capture_monitor_text(game, rows=20)
        for ln in lines:
            print(ln)
    except Exception as e:
        print(f"Subroutine test failed: {e}")

    # Cleanly quit
    pygame.quit()


if __name__ == '__main__':
    main()
