# Call / return convention in .easm

These are general conventions for call/return constructions in the .easm language.  
Prefer these conventions to using OS ABI variables.
The convention also allows for arbitrary amounts of arguments and return values (but it's up to the user to make sure the correct number of arguments are pushed to the stack, and the correct number popped on return). Otherwise there _will_ be weird bugs.

## Order of arguments
Arguments are pushed to the stack in the order they appear in the call, with the first argument (leftmost) being pushed first, and the last argument being pushed last (so it will be popped first in the callee).

## Order of return values
Return values are pushed to the stack (by the callee) in the reverse order, with the first return value (leftmost) being pushed last (so it will be popped first in the caller).

## Subroutines that only return one value
These return the value in the A register, avoiding using the stack on return.

## Subroutines that return multiple values
These can return values in the stack, but the caller _must_ remember to pop all of them for bookkeeping to be intact.

## WARNING
READ SUBROUTINE DOCS when using them. All of them should have a string at the top that specifies how many arguments it expects on the stack, as well as how many values it returns.

## Exceptions:
- [write_char.easm](../32bit/routines/utils/write_char.easm) displays the ascii character corresponding to the value stored in the A register.
  - The reason for this is that this needs to be performant, as it's used often for updating the display.

# Convention
## When there's only one return value
### Push arguments to stack before calling a subroutine
[calc.easm](../32bit/routines/programs/calc.easm)
```
do_mul:
  LDA .work1
  PHA                       ; push the first value for multiply to the stack
  LDA .work2
  PHA                       ; push the second value for multiply to the stack
  JSR @multiply
  JMP do_print
```

### Pop the return address first, then pop the arguments
- Remember that arguments pushed last will be popped first  

[multiply.easm](../32bit/routines/math/multiply.easm)
```
...

multiply:
  PLA                     ; get return address from stack
  MOVAB                   ; move return address to B for now

  ; m1 = bss + 1, m2 = bss + 2
  PLA                     ; arg2
  STA .bss + 2
  PLA                     ; arg1
  STA .bss + 1
  
  MOVBA                   ; move return address back to A
  PHA                     ; push it back to stack

...
```
The stack is now cleared of the arguments, and the return address is the first value in it.

## When there are multiple return values
### Push arguments to stack, and pop returns from stack afterwards
- Pop ALL values from the stack, even if you don't use all of them. 

[calc.easm](../32bit/routines/programs/calc.easm)
```
...
do_sqrt:
  LDA .work1
  PHA           ; push the argument to sqrt to the stack
  JSR @sqrt
  ; Returns values on stack after return -> [ ..., floor(sqrt(n)), residual, gap_to_next_square ]
  PLA           ; gap
  STA .work3
  PLA           ; residual
  STA .work4
  PLA           ; result
...
```

[puzzle.easm](/32bit/routines/programs/puzzle.easm)
```
...
check_prime_os:
  LDA .bss
  PHA
  JSR @sqrt
  PLA
  PLA
  PLA                   ; only the result is used, but the rest must be popped as well
  STA .bss + 2          ; sqrt_n
...
```

### Store return address on entry, push it back right before return
[sqrt.easm](/32bit/routines/math/sqrt.easm)
```
sqrt:
  PLA                       ; get return address from stack
  STA .bss + 3              ; move return address to bss + 3 for now

  PLA
  STA .bss                  ; argument

...

sqrt_done:
  LDA .bss + 2
  PHA                       ; result
  LDA .bss
  PHA                       ; residual
  LDA .bss + 1
  SUB .bss
  PHA                       ; gap to next square
  LDA .bss + 3
  PHA                       ; return address
  RET
```