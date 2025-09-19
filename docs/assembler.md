# Assembler functions and coding for the computer
The assembly language and the assembler for the computer is very basic, but it does have some basic features to help make programming less painful.

## It supports assigning pointer variables:
~~~~
result = 255
~~~~
These can be used for example to load a value from memory into the A register as follows:
~~~~
  LDA .result
~~~~
There are also comments, beginning with `;`
~~~~
  LDA .result ; loads a value from the memory address of .pressing into the A register
~~~~

## Initializing values in memory
The assembler can set designated values in memory to the programmers choice on assembly. This can be done either with a pointer variable, or with a memory address directly:
~~~~
.result = 0   ; make sure the memory location .result points to is zero on startup
254 = 42      ; set memory address 254 to contain 42 on startup
~~~~

This can be useful for example when defining variables which use more than one byte:
~~~~
text = 240

.text      = 72
.text + 1  = 101
.text + 2  = 108
.text + 3  = 108
.text + 4  = 111
.text + 5  = 32
.text + 6  = 119
.text + 7  = 111
.text + 8  = 114
.text + 9  = 108
.text + 10 = 100
~~~~

The assembler can also automatically convert strings to its ascii values and place the characters consecutively in memory:
~~~~
text = 240

.text = "Hello world" ; does same as the code above
~~~~

## Labels may be used to refer to positions in the program:
~~~~
start:
  LDA 255   ; loads a value from memory address 255 into the A register
  ADD 254   ; add the value from memory address 254 to the value in the A register
  STA 255   ; store the result in memory address 255
  OUT       ; display the result
  JMP start ; jump to start
~~~~

Any line containing an instruction must begin with two spaces, and then the instruction. If the instruction requires an operand, it is separated from the instruction by a single space. Instructions may only take a single operand.

## Combining memory addresses
It is possible to use simple operations to add values to a memory address pointer. For example I can define:
~~~~
value = 200   ; assigns value as a pointer which points to memory location 200

start:
  LDI 42          ; load 42 into the A register
  STA .value + 1  ; stores the value of the A register (42) into memory address .value + 1 -> 200 + 1 = 201
~~~~
Currently only addition and subtraction is supported, and bracketing to group operations is not supported (yet).

# Instruction set
This is a list of all the instructions currently supported by the assembler and the computer.
| Code  | Description                                                   | Operand                      | Instruction value | Clock cycles | Flags                              | Notes                                                                         |
|:-----:|:--------------------------------------------------------------|:-----------------------------|:-----------------:|:------------:|:-----------------------------------|:-------------------------------------------------------------------------------|
| NOP   | No operation                                                  |                             | 00000000 (0)      | 3            |                                   |                                                                                |
| LDA   | Load value from memory into A                                 | Memory address               | 00000001 (1)      | 5            |                                   |                                                                                |
| ADD   | Add value from memory (B) to A                                | Memory address               | 00000010 (2)      | 6            | C if result > 255; Z if result = 0 |                                                                                |
| SUB   | Subtract value from memory (B) from A                         | Memory address               | 00000011 (3)      | 6            | C if A ≥ B; Z if result = 0        |                                                                                |
| STA   | Store value in A into memory                                  | Memory address               | 00000100 (4)      | 5            |                                   |                                                                                |
| LDI   | Load immediate into A                                         | Immediate value              | 00000101 (5)      | 4            |                                   |                                                                                |
| JMP   | Jump to address                                               | Label or `#` literal         | 00000110 (6)      | 4            |                                   | Prefix numeric addresses with `#` for literals.                                |
| JPC   | Jump if carry flag set                                        | Label or `#` literal         | 00000111 (7)      | 4            |                                   |                                                                                |
| JPZ   | Jump if zero flag set                                         | Label or `#` literal         | 00001000 (8)      | 4            |                                   |                                                                                |
| KEI   | Load keypad input register into A                             |                             | 00001001 (9)      | 3            |                                   |                                                                                |
| ADI   | Add immediate value to A                                      | Immediate value              | 00001010 (10)     | 5            | C if result > 255; Z if result = 0 |                                                                                |
| SUI   | Subtract immediate value from A                               | Immediate value              | 00001011 (11)     | 5            | C if A ≥ B; Z if result = 0        |                                                                                |
| CMP   | Compare value from memory with A                              | Memory address               | 00001100 (12)     | 6            | C if A ≥ B; Z if equal             |                                                                                |
| PHA   | Push A onto stack                                             |                             | 00001101 (13)     | 4            |                                   | Increments stack pointer.                                                     |
| PLA   | Pull stack into A                                             |                             | 00001110 (14)     | 5            |                                   | Decrements stack pointer.                                                     |
| LDS   | Load stack pointer value into A                               |                             | 00001111 (15)     | 3            |                                   |                                                                                |
| JSR   | Jump to subroutine                                            | Label or `#` literal         | 00010000 (16)     | 7            |                                   | Pushes return address; increments stack pointer.                               |
| RET   | Return from subroutine                                        |                             | 00010001 (17)     | 5            |                                   | Pops return address; decrements stack pointer.                                 |
| SAS   | Pop address from stack and store A to it                      |                             | 00010010 (18)     | 6            |                                   | Decrements stack pointer.                                                     |
| LAS   | Pop address from stack and load A from it                     |                             | 00010011 (19)     | 6            |                                   | Decrements stack pointer.                                                     |
| LDB   | Load value from memory into B                                 | Memory address               | 00010100 (20)     | 5            |                                   |                                                                                |
| CPI   | Compare immediate value with A                                | Immediate value              | 00010101 (21)     | 5            | C if A ≥ B; Z if equal             |                                                                                |
| RSA   | Shift A right by one                                          |                             | 00010110 (22)     | 3            | C = shifted-out bit; Z if A == 0   |                                                                                |
| LSA   | Shift A left by one                                           |                             | 00010111 (23)     | 4            | C if result > 255; Z if result = 0 |                                                                                |
| DIS   | Load immediate into display data register                     | Immediate value              | 00011000 (24)     | 5            |                                   |                                                                                |
| DIC   | Load immediate into display control register                  | Immediate value              | 00011001 (25)     | 5            |                                   |                                                                                |
| LDD   | Load memory into display data register                        | Memory address               | 00011010 (26)     | 6            |                                   |                                                                                |
| JNZ   | Jump if zero flag **not** set                                 | Label or `#` literal         | 00011011 (27)     | 4            |                                   |                                                                                |
| STB   | Store value in B into memory                                  | Memory address               | 00011100 (28)     | 5            |                                   |                                                                                |
| MOVBA | Copy register B into A                                        |                             | 00011101 (29)     | 3            |                                   | Flags remain unchanged.                                                        |
| MOVAB | Copy register A into B                                        |                             | 00011110 (30)     | 3            |                                   | Flags remain unchanged.                                                        |
| LSP   | Load stack pointer with immediate value                       | Immediate value              | 00011111 (31)     | 4            |                                   | Value is masked to stack size.                                                |
| MVASP | Move A into stack pointer                                     |                             | 00100000 (32)     | 3            |                                   | Value is masked to stack size.                                                |
| MVBSP | Move B into stack pointer                                     |                             | 00100001 (33)     | 3            |                                   | Value is masked to stack size.                                                |
| SUM   | Move ALU sum (A + B) into A                                   |                             | 00100010 (34)     | 3            | C if result > 255; Z if result = 0 | Performs A + B; SU is not asserted during this instruction.                   |
| LAP   | Load value from memory pointed to by A                         |                             | 00100011 (35)     | 3            |                                   | `A = mem[A]`                                                                  |
| LPA   | Load value from pointer stored at operand                      | Immediate pointer           | 00100100 (36)     | 5            |                                   | `A = mem[mem[arg]]`; operand fetched first, then dereferenced.                |
| OUT   | Display the value in A                                        |                             | 11111110 (254)    | 3            |                                   |                                                                                |
| HLT   | Halt the computer                                             |                             | 11111111 (255)    | 3            |                                   |                                                                                |
