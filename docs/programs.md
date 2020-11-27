# Included programs
There are a few programs included by default. This is how they work.

## Calculator
Filename: `calculator.txt`

The calculator allows performing the four standard mathematical operations, addition, subtraction, multiplication and division.

It stores a "result" in memory, which is initialized as zero. Operations are performed by inserting a number, and then pressing the desired operation.  
When an operation is pressed, the inputted value will be applied to what is currently stored in the "result", using the chosen operation.  
The result of the calculation will then be displayed, and the user's inputted value reset to 0.

### Addition
Thus, to add two numbers the operation is as follows:  
- Enter the first number.
- Press the `+` key. The number will now be added to the "result", meaning the "result" will equal whatever was inputted.
- Enter the second number.
- Press the `+` key again. The numbers will now be added and displayed.

### Subtraction
Subtraction works very similarly to addition:  
- Enter the first number.
- Press the `+` key. The number will now be added to the "result", meaning the "result" will equal whatever was inputted.
- Enter the second number.
- Press the `-` key. The second number will be subtracted from the first and the result displayed.

### Multiplication
- Enter the first number.
- Press the `+` key.
- Enter the second number.
- Press the `*` key. The numbers will be multiplied and the result displayed.

#### Note regarding performance.
Entering the largest number first will complete the calculation faster, because the second number entered will be used as the multiplier (i.e. how many times the first number (multiplicand) is added to itself to get the result).

### Division
- Enter the first number.
- Press the `+` key.
- Enter the second number.
- Press the `/` key. The numbers will be divided and the quotient displayed.

#### Note on remainder.
The remainder can be retrieved by pressing the `/` key again after the quotient is displayed.

Attempting to divide by zero will also display the remainder from any previous division.

## Programmer
Filename: `programmer.txt`

The programmer allows programming the computer by using the built-in keypad. In essence this is just a program which allows you to write new data into the memory.

When not running an entered program, and no number has been inputted, the computer will display the currently selected memory address. I.e. the memory address which will be written to on next input.  
On startup, this memory address will be `128`.

To write a value to memory, enter a value and then press the `+` key. This will write the input to the current memory address and increment the selected address.

The selected memory address can be decremented by hitting the `-` key or reset to `128` by pressing the `/` key. It can never be set lower than `128`.

The entered program can be executed by pressing the `*` key, which will set the program counter to 128, and continue executing code from there.

## Fibonacci
Filename: `fibonacci.txt`

Calculates and displays numbers in the Fibonacci sequence.

## Primes
Filename: `primes.txt`

Calculates and displays prime numbers.