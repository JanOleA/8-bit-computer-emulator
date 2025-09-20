# Mini32 Language

Mini32 is a small, structured language that compiles into the 32-bit emulator assembly (`.easm`) used in this project.  The goal is to offer a friendlier syntax for simple routines while keeping a transparent mapping to the underlying machine instructions.

## Module Structure

A Mini32 source file is a sequence of top-level directives followed by one or more function definitions.

```
# Comments start with '#'
meta name = Counter
meta entry = main
meta abi = os
depends write_char, newline

const ZERO = 0
var counter
var counter2
var result

data digits = "0123456789"

func main:
    let counter = 5
    let counter2 = 2
    while counter:
        let counter -= 1
        call @multiply(counter, counter2) -> result
        call @display_number(result)
    call @newline()
    return

```

### Module metadata

- `meta key = value` &rarr; becomes `;! key: value` in the generated assembly header.
- `depends name1, name2, ...` adds to the dependency list (`;! deps: ...`).
  Dependencies are comma-separated identifiers and are emitted exactly in the provided order.

### Global definitions

- `const NAME = <number>` defines a constant. Use it in expressions as `NAME` (compiles to an immediate value).
- `var NAME` allocates one word in the module's BSS block and defines `NAME = .bss + offset` in the output assembly.
- `var NAME[SIZE]` allocates `SIZE` consecutive words in BSS. Use `NAME[index]` to address individual slots.
- `data NAME = "string"` emits a null-terminated string via the assembler's auto-data facility. The identifier can be used as an immediate pointer (`NAME`).

## Functions

Functions start with `func name:` and contain an indented block of statements (indentation must be multiples of four spaces). Each function translates into a label and ends with `RET` unless the body already returns.

Available statements inside a function:

- `let target = expr` assigns the evaluated expression to a variable.
- `let target += expr`, `let target -= expr` perform in-place addition or subtraction.
  - `target` can be `name` or `name[index]` for array slots.
- `call callee(args...)` calls a routine. Before the `JSR`, arguments are pushed to the stack (in reverse order) automatically. Use `call @name(...)` for extern calls so the assembler emits `JSR @name` (recognized by `compile_routines.py`). Parentheses are optional when there are no arguments.
- `return` / `return expr` emits an optional expression evaluation followed by `RET`.
- Control flow:
  - `if expr:` followed by a block and optional `else:` block.
  - `while expr:` loops while the expression is non-zero.
  - `break` and `continue` behave as usual within loops.
- `asm "..."` inlines raw assembly. Multiline strings are allowed and inserted verbatim.

## Expressions

Expressions are limited to addition and subtraction of terms:

```
expr := term {("+"|"-") term}
term := literal | IDENT | IDENT[NUMBER]
```

- Literals can be decimal (`42`), hexadecimal (`0x2A`), or binary (`0b101010`).
- `IDENT` refers to:
  - a `var` (loads from/stores to memory),
  - a `const` / `data` / known ABI symbol (used as an immediate value), or
  - `.bss` and other injected symbols supplied by `compile_routines.py`.

During code generation:

- The first term of an expression loads the accumulator (`LDA` for variables, `LDI` for immediates).
- Subsequent terms use `ADD`/`SUB` for memory operands or `ADI`/`SUI` for immediates.

## Generated Assembly Outline

The compiler emits:

1. Header lines derived from `meta` and `depends`.
2. Pointer definitions for constants and variables.
3. Auto-data blocks for `data` strings.
4. Function bodies translated into `.easm` instructions with two-space indent.

The resulting `.easm` file can be fed directly into `tools/compile_routines.py` alongside other hand-written modules.

## Limitations

- Expressions are intentionally simple (only `+`/`-`). Use `asm` for advanced instruction sequences.
- All variables live in the module's BSS. Stack usage, advanced addressing modes, and custom calling conventions must be written in raw assembly.
- Argument passing always uses `.arg1`, `.arg2`, ... regardless of callee expectations; ensure dependencies follow the OS ABI conventions.

## Example

```
meta name = Counter
meta entry = main
meta abi = os
depends write_char, newline

const ZERO = 0
var counter
var counter2
var result

data digits = "0123456789"

func main:
    let counter = 5
    let counter2 = 2
    while counter:
        let counter -= 1
        call @multiply(counter, counter2) -> result
        call @display_number(result)
    call @newline()
    return
```

Compiling this module will generate `.easm` code that decrements a counter, prints digits, and returns via the OS ABI.

## Compiling

Use `tools/mini32_compiler.py` to translate a Mini32 source file into assembly:

```
python tools/mini32_compiler.py my_program.m32 -o my_program.easm
```

The resulting `.easm` file can be dropped next to the existing assembly modules and processed by `tools/compile_routines.py` as usual.
