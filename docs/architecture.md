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

The program counter can also read a value from the bus. This happens on a clock-high pulse if the "jump (JMP)" control signal is active.

There are also conditional jump signals. These are the "jump if carry (JC)" and "jump if zero (JZ)" control signals.

The program counter will read a value from the bus on a clock-high pulse if both the "jump if carry" control signal is active _and_ the carry bit of the flags register is active.

The program counter will read a value from the bus on a clock-high pulse if both the "jump if zero" control signal is active _and_ the zero bit of the flags register is active.

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

### A register
#### 8-bit register
The A register is one of the registers (together with the B register), which is used for mathematical operations.

The register reads a value from the bus on a clock-high pulse if the "A register in (AI)" control signal is active.

It can also output its contents onto the bus if the "A register out (AO)" control signal is active.

It is also possible to shift the values of the A register either to the right or the left. The values will be shifted on a clock-high pulse if either the "right shift A (RSA)" or the "left shift A (LSA)" control signal is active.

Right shift example: `[0110 1001]` -> `[0011 0100]`  
Left shift example: `[1001 1001]` -> `[0011 0010]`

### B register
#### 8-bit register
The B register is one of the registers (together with the A register), which is used for mathematical operations.

The register reads a value from the bus on a clock-high pulse if the "B register in (BI)" control signal is active.

It can also place its contents on the bus when the "B register out (BO)" control signal is enabled, allowing direct stores from B or fast register swaps.

### ALU (sum)
#### 8-bit adder
The ALU adds or subtracts the values in the A and B registers. This operation is continuous (not dependent on the clock cycle).

If the "subtract (SU)" control signal is active, the result will be A - B. Otherwise the result is A + B.

The flags bits directly correspond to the result of the calculation. If the calculation results in an overflow, the first bit will be active. If the result of the calculation is zero, the second bit will be active.

For subtraction, any subtraction where A >= B will result in the carry bit being active. This is because subtraction is done by two's complement. See Ben Eater's video on the subject if interested in detail.

The ALU can put its value onto the bus if the "sum out (EO)" control signal is active.

### Flags register
#### 2-bit register
The function of the flags register is to remember which flag bits were active during the previous calculation.

It reads and stores the value of the flags on a clock-high pulse if the "flags in (FI)" control signal is active.

### Output register
#### 8-bit register
The output register is directly connected to a segment display which is decoded in some fashion to display the value of the register in decimal numbers.

See Ben Eater's video on it to see how a decoder may function-

The output register can read a value from the bus on a clock-high pulse if the "output in (OI)" control signal is active.

### Input register
#### 8-bit "register"
The input register is not a true register. Instead its value depends entirely on which button on the on-screen numpad is pressed. And the values are as follows:
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

The register outputs this value onto the bus if the "keypad out (KEO)" control signal is active.

### Stack pointer
#### 4-bit counter
The stack pointer is a four bit counter used to keep track of how many values have been added to the stack.
The stack is a reserved part of memory from address 224 to 239.

The stack pointer will increment by 1 on a clock-high pulse if the "increment stack (INS)" control signal is active.

The stack pointer will decrement by 1 on a clock-high pulse if the "decrement stack (DES)" control signal is active.

The stack pointer can output its value to the bus if the "stack out (STO)" control signal is active. When the stack pointer outputs its value to the bus, 224 `[1110 0000]` is added to the value, so that the actual values put onto the bus will range from 224 to 239.

Finally, the pointer can be loaded from the bus via the "stack pointer in (SPI)" control signal. Values written through SPI are masked to the configured stack size, so you can reposition the stack in a single micro-step.

## Drawn connections
The drawn connections and their colors represent different things. The "wires" connect components which are connected to eachother in some way.

The connection from the numpad to the input register is not drawn.

### Red wires:
Represents connections that are active only when some control signal allows it.

### Blue wires:
Represents connections that are always active.

### Green wires:
Represents connections from the control word to components which may in some way be affected by any of the control signals.

### Purple wires:
Control signal connections from the instruction A register and the operation timestep. Always active, but drawn separate from blue because these require some control word decoding to function.
