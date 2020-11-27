# Emulator architecture
The emulator is heavily inspired and based upon the excellent 8-bit computer built by Ben Eater. If you _really_ want to understand how it works, I recommend checking out his videos on it, which can be found in this YouTube playlist: [here](https://www.youtube.com/playlist?list=PLowKtXNTBypGqImE405J2565dvjafglHU).

What follows here is a brief overview.

## Components
### The clock
The clock is a signal which cycles from low (0) to high (1), and then back to low. Components may do specific actions either when the clock transitions from low to high (high pulse), or when it transitions from high to low (low pulse).

Outputs onto the bus are typically not dependant on the clock, but components reading from the bus usually happens on a clock-high pulse.

### The bus - heart and soul
The computer is built around an 8-bit bus connecting most of the components. With some exceptions, the components can all put a value onto the bus, or read a value from it.

### Control word - brain
The brain of making the computer work is the control word. The computer supports a 32 bit control word.

The state of the control word is determined by the value loaded into the `Instruction A register`, and the operation timestep.
#### Note on IRL implementation.
In real life, this could be implemented with a logic circuit, but the circuit would be massive. A simpler way to implement it would be using ROM chips. See Ben Eater's videos to see details on how this could be implemented.

### Program counter
#### 8-bit counter

The program counter starts at 0 and increments by one on a clock-high pulse if the "counter enable (CE)" control signal is active.

The program counter can also read a value from the bus. This happens on a clock-high pulse if the "counter in (CI)" control signal is active.

### Memory address register
#### 8-bit register
The memory address register directly controls which memory address is being accessed.

The memory address register reads a value from the bus on a clock-high pulse if the "memory in (MI)" control signal is active.

### Memory content
The memory content of the address in the memory address register is always displayed.

The content will be outputted to the bus if the "RAM out (RO)" control signal is active.

The contents of the bus will be written to the selected memory address on a clock-high pulse if the "RAM in (RI)" control signal is active.

### Instruction register A
#### 8-bit register
This register directly controls which control signals are active, based on its value. The [instruction set table](assembler.md) contains a column explaining which value corresponds to which instruction.

Which control signal is active is further determined by the current operation timestep.

The register reads a value from the bus on a clock-high pulse if the "instruction A in (IAI)" control signal is active.

It can also output its contents onto the bus if the "instruction A out (IAO)" control signal is active.

### Operation timestep
As mentioned above, the operation timestep, together with the Instruction register A determines which control signals are active. The operation timestep increases by 1 on each clock-low pulse. It increases up to 8, at which point it resets.

The operation timestep can also be reset on a clock-low pulse if the "operation reset (ORE)" control signal is active.

Also note that the operation timestep is not displayed in binary. Instead the bit itself which is active directly corresponds to which timestep it is currently on.

### Instruction register B
#### 8-bit register
This register is used to store temporary variables. Some instructions require two bytes of memory in the program, and thus will first read the instruction value into instruction register A, and then the second byte into instruction register B.

#### Note
This register is as-of-now not technically necessary. The temporary values could either be loaded directly into the memory address bus, or into the B register directly. I have included it simply for flexibility and to make it easier to expand functionality in the future.

The register reads a value from the bus on a clock-high pulse if the "instruction B in (IBI)" control signal is active.

It can also output its contents onto the bus if the "instruction B out (IBO)" control signal is active.