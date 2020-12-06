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
| Code 	|                           Description                          	|           Operand           	| Instruction value 	| Clock cycles 	|                Flags               	|                                    Notes                                   	|
|:----:	|:--------------------------------------------------------------:	|:---------------------------:	|:-----------------:	|:------------:	|:----------------------------------:	|:--------------------------------------------------------------------------:	|
|  NOP 	|                          No operation                          	|                             	|    00000000 (0)   	|       3      	|                                    	|                                                                            	|
|  LDA 	|                Loads a value from memory into A                	| Memory address to read from 	|    00000001 (1)   	|       5      	|                                    	|                                                                            	|
|  ADD 	|                Adds a value (B) from memory to A               	| Memory address to read from 	|    00000010 (2)   	|       6      	| C if result > 255, Z if result = 0 	|                                                                            	|
|  SUB 	|            Subtracts a value (B) from memory from A            	| Memory address to read from 	|    00000011 (3)   	|       6      	|    C if A >= B, Z if result = 0    	|                                                                            	|
|  STA 	|                  Store value in A into memory                  	|  Memory address to store to 	|    00000100 (4)   	|       5      	|                                    	|                                                                            	|
|  LDI 	|                      Load immediate into A                     	|     Value to load into A    	|    00000101 (5)   	|       4      	|                                    	|                                                                            	|
|  JMP 	|                   Jump to address in program                   	|   label or memory address   	|    00000110 (6)   	|       4      	|                                    	| If providing a memory address directly, the number must be preceded by a # 	|
|  JPC 	|          Jump to address in program if carry flag set          	|   label or memory address   	|    00000111 (7)   	|       4      	|                                    	|         Only jumps if the carry flag is set, otherwise does nothing        	|
|  JPZ 	|           Jump to address in program if zero flag set          	|   label or memory address   	|    00001000 (8)   	|       4      	|                                    	|         Only jumps if the zero flag is set, otherwise does nothing         	|
|  KEI 	|        Loads the contents of the "Input register" into A       	|                             	|    00001001 (9)   	|       3      	|                                    	|                                                                            	|
|  ADI 	|                   Add an immediate value to A                  	|         Value to add        	|   00001010 (10)   	|       5      	| C if result > 255, Z if result = 0 	|                                                                            	|
|  SUI 	|             Subtract an immediate value (B) from A             	|      Value to subtract      	|   00001011 (11)   	|       5      	|    C if A >= B, Z if result = 0    	|                                                                            	|
|  CMP 	|              Compare value from memory (B) with A              	| Memory address to read from 	|   00001100 (12)   	|       6      	|       C if A >= B, Z if equal      	|                                                                            	|
|  PHA 	|               Push the value of A onto the stack               	|                             	|   00001101 (13)   	|       4      	|                                    	|                        Increments the stack pointer                        	|
|  PLA 	|               Pull a value from the stack into A               	|                             	|   00001110 (14)   	|       5      	|                                    	|                        Decrements the stack pointer                        	|
|  LDS 	|           Load the value of the stack pointer into A           	|                             	|   00001111 (15)   	|       3      	|                                    	|                                                                            	|
|  JSR 	|                      Jump to a subroutine                      	|   label or memory address   	|   00010000 (16)   	|       7      	|                                    	|                        Increments the stack pointer                        	|
|  RET 	|                    Return from a subroutine                    	|                             	|   00010001 (17)   	|       5      	|                                    	|                        Decrements the stack pointer                        	|
|  SAS 	|  Pull a memory address from stack to store the value of A into 	|                             	|   00010010 (18)   	|       6      	|                                    	|                        Decrements the stack pointer                        	|
|  LAS 	| Pull a memory address from stack to load the value from into A 	|                             	|   00010011 (19)   	|       6      	|                                    	|                        Decrements the stack pointer                        	|
|  LDB 	|                Loads a value from memory into B                	| Memory address to read from 	|   00010100 (20)   	|       5      	|                                    	|                                                                            	|
|  CPI 	|              Compare an immediate value (B) with A             	|   Value to compare with A   	|   00010101 (21)   	|       5      	|       C if A >= B, Z if equal      	|                                                                            	|
|  RSA 	|                Shift the A register to the right               	|                             	|   00010110 (22)   	|       3      	|                                    	|                Equivalent to A = A/2, ignoring the remainder               	|
|  LSA 	|                Shift the A register to the left                	|                             	|   00010111 (23)   	|       4      	| C if result > 255, Z if result = 0 	|      Equivalent to A = A*2, but any bits larger than 2^8 is discarded      	|
|  OUT 	|            Display the contents of A on the display            	|                             	|   11111110 (254)  	|       3      	|                                    	|                                                                            	|
|  HLT 	|                        Halt the computer                       	|                             	|   11111111 (255)  	|       3      	|                                    	|                                                                            	|