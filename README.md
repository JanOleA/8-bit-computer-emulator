# 8 bit computer emulator
Inspired by Ben Eater's 8-bit computer project.

Check out his excellent series on how to build this in real life [here](https://www.youtube.com/playlist?list=PLowKtXNTBypGqImE405J2565dvjafglHU).

## Quickstart
To run the fibonacci program, run:
~~~~
> python 8bitsim.py fibonacci.txt
~~~~
The program looks like this:
~~~~
x = 255
y = 254

start:
  LDI 1       ; Load (immediate) a value of 1 into the A register
  STA .x      ; Store A in the memory address x points to
  STA .y      ; Store A in the memory address y points to
  OUT         ; Display A
add:
  LDA .x      ; Load the value from the memory address x points to, into A
  ADD .y      ; Add the value from the memroy address y points to, to A
  JPC start   ; If the result > 255, return to start
  OUT         ; If not, continue, and display the result
  STA .x      ; Store the result in the memory address x points to
  ADD .y      ; Add the value from the memory address y points to, to A
  JPC start   ; If the result > 255, return to start
  OUT         ; Display the result
  STA .y      ; Store the result in the memory address y points to
  JMP add     ; Jump to the start of the "add" loop
~~~~
The program outputs the successive fibonacci numbers (1, 2, 3, 5, 8, 13, ...) up to 233, and then starts over.

More examples of programs can be found in the root directory.

## Documentation
[Emulator usage](docs/usage.md)  
[Computer architecture](docs/architecture.md)  
[Assembler usage and instruction set](docs/assembler.md)  
