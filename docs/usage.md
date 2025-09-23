# Using the emulator
## Requirements
To run the emulator, you need Python installed on your system. It has been tested on Python 3.8.3, so I recommend using this or a newer version.

You also need some third-party packages for Python. These are listed in [the requirements file](../requirements.txt).

### Compiled version
I have not made a pre-compiled version yet. I may make one for Windows and/or Linux, at some point.

## Running the emulator
The emulator now uses `argparse` and supports optional flags. Run without arguments:
```
python cpu_sim.py
```
Defaults:
* Program file: `program.txt`
* Target FPS: 50 (`--fps`)
* Target clock frequency: 25 Hz (`--hz`)
* LCD panel: disabled (enable with `--lcd`)

### Command line arguments
```
python cpu_sim.py [program] [--fps N] [--hz N] [--lcd] [--json file.json ...]
```

Argument / Flag | Description | Default
----------------|-------------|--------
`program`       | Optional positional path to a program text file to assemble | `program.txt`
`--fps N`       | Target render frames per second (visual update rate) | 50
`--hz N`        | Target CPU clock frequency in Hertz | 25
`--lcd`         | Enable the LCD peripheral panel in the UI | off
`--json FILE`   | Inject a JSON memory image (repeatable) | none

You can repeat `--json` to layer multiple memory images (later images overwrite earlier addresses they touch):
```
python cpu_sim.py program.txt --json bootmap.json --json sprites.json
```

### Examples
Run Fibonacci demo at higher visual refresh (100 FPS) while keeping a modest clock:
```
python cpu_sim.py fibonacci.txt --fps 100 --hz 50
```

Run a program headless-ish with a very fast clock (render still caps visual updates):
```
python cpu_sim.py primes.txt --hz 500 --fps 60
```

Enable LCD panel and load default program:
```
python cpu_sim.py --lcd
```

Layer two memory images then start with a slow, inspectable clock:
```
python cpu_sim.py program.txt --json devmap.json --json testdata.json --hz 5 --fps 30
```

### Clock vs FPS
If the target clock (`--hz`) exceeds the frame rate (`--fps`), multiple CPU cycles occur between redraws. This is expected; you will see state "jump". Lower `--hz` or raise `--fps` for more granular visual tracing.

### Multiple JSON memory images
Each JSON file should map named modules to objects with at least a `base` and `words` list, e.g.
```json
{
    "vectors": {"base": 0, "words": [1,2,3,4]},
    "patch": {"base": 32, "words": [10,11]}
}
```
Words are masked to the machine's memory word width. Invalid entries are skipped with a warning.

### Backwards compatibility note
Older positional forms like `python cpu_sim.py fibonacci.txt 100 200` are no longer supported. Use flags: `python cpu_sim.py fibonacci.txt --fps 100 --hz 200`.

## Once running
Once the emulator is running, there are a few options available to the user by pressing keys on the keyboard:

* The "D" key will enable the debug mode. This displays the current state of the computer's memory, as well as a list of the microinstructions that the currently loaded instruction contains.
* The "C" key will disable the debug mode.
* The "M" key will show or hide the computer's memory.
* The "N" key will show or hide the microinstruction list.
* The "R" key will reset the state of the computer. It will however not reset the memory, so this is akin to pressing a reset switch on the IRL computer.
* Pressing the spacebar will stop automatic execution.
* Pressing the "Enter"/"Return" key will step the clock one cycle forward, if the automatic execution is stopped.
    - The clock goes "high" on key press, and "low" on key release.
* The numpad keys (not the on-screen ones) can be used to control the clock cycle target.
    - `1`: Sets the target frequency to 1/5 of the FPS
    - `2`: Sets the target frequency to 1/4 of the FPS
    - `3`: Sets the target frequency to 1/3 of the FPS
    - `4`: Sets the target frequency to 1/2 of the FPS
    - `5`: Sets the target frequency to equal the FPS
    - `6`: Sets the target frequency to 2x the FPS
    - `7`: Sets the target frequency to 4x the FPS
    - `8`: Sets the target frequency to 10x the FPS
    - `9`: Sets the target frequency to 100x the FPS
    - `0`: Sets the target frequency to 100000x the FPS, in effect gradually increasing the clock rate until the FPS can no longer be maintained with further increases.
    - `+`: Multiplies the target frequency by 2.
    - `-`: Divides the target frequency by 2 (rounds down).

### On-screen numpad
The computer has an on-screen numpad that can be used to control the computer, if the computer is programmed to read from it. More detail can be seen in the docs on how the registers work, but essentially the buttons each set the input register to a unique state as follows:
- `0`: `[1000 0000]`
- `1`: `[1000 0001]`
- `2`: `[1000 0010]`
- `3`: `[1000 0011]`
- `4`: `[1000 0100]`
- `5`: `[1000 0101]`
- `6`: `[1000 0110]`
- `7`: `[1000 0111]`
- `8`: `[1000 1000]`
- `9`: `[1000 1001]`
- `/`: `[1110 0000]`
- `+`: `[1100 0000]`
- `-`: `[1010 0000]`
- `*`: `[1001 0000]`

With a little bit of math, this can be used by any program to branch to a specific address depending on what button was pressed. See [calculator.txt](../calculator.txt) and [programmer.txt](../programmer.txt) for examples.

---
Last updated: Updated for argparse interface (`--fps`, `--hz`, `--lcd`, `--json`).
