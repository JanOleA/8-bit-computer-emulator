# Using the emulator
## Requirements
To run the emulator, you need Python installed on your system. It has been tested on Python 3.8.3, so I recommend using this or a newer version.

You also need some third-party packages for Python. These are listed in [the requirements file](../requirements.txt).

### Compiled version
I have not made a pre-compiled version yet. I may make one for Windows and/or Linux, at some point.

## Running the emulator
With everything installed, you can run the emulator with the following command:
~~~~
> python 8bitsim.py
~~~~
By default, this attempts to read the program from the file `program.txt`. It will run at 50 FPS, with a clock cycle of 15 Hz.

You can specify the file to read the program from by adding a command-line argument:
~~~~
> python 8bitsim.py fibonacci.txt
~~~~

You can also add an FPS target, if you want to change the FPS the emulator attempts to run at:
~~~~
> python 8bitsim.py fibonacci.txt 100
~~~~

Finally, you can add a clock cycle frequency target, by adding a third command-line argument:
~~~~
> python 8bitsim.py fibonacci.txt 100 200
~~~~
This last example will load the program from [fibonacci.txt](../fibonacci.txt), and attempt to run at 100 FPS with a clock cycle of 200 Hz.

### Note about clock cycle and FPS
If the clock cycle is higher than the frame rate, the emulator will not be able to display every state of the computer (as some of the computation is done between frames), so you may see the it jump between seemingly unrelated states.

### Note about command line arguments
For now, the command line arguments must be provided in order, so if you want to give a Hz target, you must also give the program name and the FPS target. Adding flags for more flexibility is on the to-do list.

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