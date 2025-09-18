"""Minimal compiler for the toy 'MINI' language.

The language keeps the syntax deliberately tiny so it can be translated
straight into the emulator's assembly.  Statements are one per line and are
case-insensitive.  Comments start with `#` and continue to the end of the line.

Grammar (BNF-ish):

    program      ::= { stmt }
    stmt         ::= const_decl | var_decl | label | assign | add | sub
                    | print | iflt | goto | ret

    const_decl   ::= "CONST" NAME NUMBER
    var_decl     ::= "VAR" NAME [NUMBER]
    label        ::= NAME ':' | "LABEL" NAME
    assign       ::= "SET" NAME value
    add          ::= "ADD" NAME value
    sub          ::= "SUB" NAME value
    print        ::= "PRINT" value
    iflt         ::= "IFLT" NAME value NAME
    goto         ::= "GOTO" NAME
    ret          ::= "RET"

    value        ::= NUMBER | NAME

Numbers accept decimal or python-style prefixes (e.g. 0x10).  Names map to
either constants, variables, or labels depending on context.

The generated assembly:
  * injects pointer aliases for each variable (`foo = .bss + offset`)
  * zeroes or pre-initialises variables with `.foo = value`
  * emits the program body starting at `mini_start`
  * depends only on `display_number` and `newline`

Example input (demo.mini):

    CONST LIMIT 10
    VAR counter 0

    loop:
      PRINT counter
      ADD counter 1
      IFLT counter LIMIT end
      GOTO loop

    LABEL end
    RET

Pipe the output into an `.easm` file and assemble it with the existing tools:

    python tools/simple_lang_compiler.py demo.mini > demo.easm
    python tools/compile_routines.py  # picks up demo.easm if added as routine

"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import pathlib
import re
from typing import Dict, List, Sequence, Tuple


@dataclass
class Variable:
    name: str
    symbol: str
    offset: int
    initial: int | None


class MiniCompilerError(RuntimeError):
    """Raised for user-facing compilation errors."""


class MiniCompiler:
    def __init__(self, lines: Sequence[str]) -> None:
        self.lines = list(lines)
        self.consts: Dict[str, int] = {}
        self.vars: Dict[str, Variable] = {}
        self.labels: Dict[str, str] = {}
        self.body: List[str] = []
        self.var_order: List[str] = []
        self.next_offset = 0

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _sanitize(name: str, kind: str) -> str:
        if not name:
            raise MiniCompilerError(f"{kind} name must not be empty")
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if not cleaned or cleaned[0].isdigit():
            cleaned = f"_{cleaned}"
        return cleaned.lower()

    @staticmethod
    def _parse_number(token: str) -> int:
        try:
            return int(token, 0)
        except ValueError as exc:
            raise MiniCompilerError(f"Invalid number: {token}") from exc

    def _resolve_value(self, token: str) -> Tuple[str, str | int]:
        upper = token.upper()
        if upper in self.consts:
            return "imm", self.consts[upper]
        if upper in self.vars:
            return "var", self.vars[upper].symbol
        # allow raw numbers
        try:
            return "imm", self._parse_number(token)
        except MiniCompilerError:
            pass
        raise MiniCompilerError(f"Unknown value '{token}' (not a const/var/number)")

    def _label_symbol(self, name: str) -> str:
        upper = name.upper()
        if upper not in self.labels:
            self.labels[upper] = f"lbl_{self._sanitize(name, 'label')}"
        return self.labels[upper]

    def _require_var(self, name: str) -> Variable:
        upper = name.upper()
        if upper not in self.vars:
            raise MiniCompilerError(f"Unknown variable '{name}'")
        return self.vars[upper]

    # ------------------------------------------------------------- declarations
    def _handle_const(self, parts: Sequence[str]) -> None:
        if len(parts) != 3:
            raise MiniCompilerError("CONST expects: CONST name value")
        name = parts[1].upper()
        if name in self.consts:
            raise MiniCompilerError(f"CONST '{name}' already defined")
        value = self._parse_number(parts[2])
        self.consts[name] = value

    def _handle_var(self, parts: Sequence[str]) -> None:
        if len(parts) not in (2, 3):
            raise MiniCompilerError("VAR expects: VAR name [initial]")
        upper = parts[1].upper()
        if upper in self.vars:
            raise MiniCompilerError(f"VAR '{upper}' already defined")
        symbol = f"var_{self._sanitize(parts[1], 'var')}"
        initial = None
        if len(parts) == 3:
            initial = self._parse_number(parts[2])
        self.vars[upper] = Variable(parts[1], symbol, self.next_offset, initial)
        self.var_order.append(upper)
        self.next_offset += 1

    # --------------------------------------------------------------- statements
    def _emit(self, line: str) -> None:
        self.body.append(line)

    def _emit_comment(self, text: str) -> None:
        self.body.append(f"  ; {text}")

    def _stmt_set(self, parts: Sequence[str]) -> None:
        if len(parts) != 3:
            raise MiniCompilerError("SET expects: SET var value")
        var = self._require_var(parts[1])
        mode, value = self._resolve_value(parts[2])
        self._emit_comment(f"{var.name} = {parts[2]}")
        if mode == "imm":
            self._emit(f"  LDI {value}")
        else:
            self._emit(f"  LDA {value}")
        self._emit(f"  STA {var.symbol}")

    def _stmt_add(self, parts: Sequence[str]) -> None:
        if len(parts) != 3:
            raise MiniCompilerError("ADD expects: ADD var value")
        var = self._require_var(parts[1])
        mode, value = self._resolve_value(parts[2])
        self._emit_comment(f"{var.name} += {parts[2]}")
        self._emit(f"  LDA {var.symbol}")
        if mode == "imm":
            self._emit(f"  ADI {value}")
        else:
            self._emit(f"  ADD {value}")
        self._emit(f"  STA {var.symbol}")

    def _stmt_sub(self, parts: Sequence[str]) -> None:
        if len(parts) != 3:
            raise MiniCompilerError("SUB expects: SUB var value")
        var = self._require_var(parts[1])
        mode, value = self._resolve_value(parts[2])
        self._emit_comment(f"{var.name} -= {parts[2]}")
        self._emit(f"  LDA {var.symbol}")
        if mode == "imm":
            self._emit(f"  SUI {value}")
        else:
            self._emit(f"  SUB {value}")
        self._emit(f"  STA {var.symbol}")

    def _stmt_print(self, parts: Sequence[str]) -> None:
        if len(parts) != 2:
            raise MiniCompilerError("PRINT expects: PRINT value")
        mode, value = self._resolve_value(parts[1])
        self._emit_comment(f"print {parts[1]}")
        if mode == "imm":
            self._emit(f"  LDI {value}")
        else:
            self._emit(f"  LDA {value}")
        self._emit("  STA .arg1")
        self._emit("  JSR @display_number")
        self._emit("  JSR @newline")

    def _stmt_iflt(self, parts: Sequence[str]) -> None:
        if len(parts) != 4:
            raise MiniCompilerError("IFLT expects: IFLT var value label")
        var = self._require_var(parts[1])
        mode, value = self._resolve_value(parts[2])
        target = self._label_symbol(parts[3])
        temp = f"skip_{len(self.body)}"
        self._emit_comment(f"if {var.name} < {parts[2]} goto {parts[3]}")
        self._emit(f"  LDA {var.symbol}")
        if mode == "imm":
            self._emit(f"  CPI {value}")
        else:
            self._emit(f"  CMP {value}")
        self._emit(f"  JPC {temp}")
        self._emit(f"  JMP {target}")
        self._emit(f"{temp}:")

    def _stmt_goto(self, parts: Sequence[str]) -> None:
        if len(parts) != 2:
            raise MiniCompilerError("GOTO expects: GOTO label")
        target = self._label_symbol(parts[1])
        self._emit_comment(f"goto {parts[1]}")
        self._emit(f"  JMP {target}")

    def _stmt_ret(self, parts: Sequence[str]) -> None:
        if len(parts) != 1:
            raise MiniCompilerError("RET takes no arguments")
        self._emit("  RET")

    # -------------------------------------------------------------- main pass
    def compile(self) -> str:
        for line_no, raw in enumerate(self.lines, start=1):
            stripped = raw.split('#', 1)[0].strip()
            if not stripped:
                continue
            parts = stripped.replace(',', ' ').split()
            head = parts[0]
            # label forms: "foo:" or "LABEL foo"
            if head.endswith(':'):
                label = head[:-1]
                symbol = self._label_symbol(label)
                self._emit(f"{symbol}:")
                continue
            upper = head.upper()
            if upper == "LABEL":
                if len(parts) != 2:
                    raise MiniCompilerError("LABEL expects: LABEL name")
                symbol = self._label_symbol(parts[1])
                self._emit(f"{symbol}:")
                continue
            try:
                handler = {
                    "CONST": self._handle_const,
                    "VAR": self._handle_var,
                    "SET": self._stmt_set,
                    "ADD": self._stmt_add,
                    "SUB": self._stmt_sub,
                    "PRINT": self._stmt_print,
                    "IFLT": self._stmt_iflt,
                    "GOTO": self._stmt_goto,
                    "RET": self._stmt_ret,
                }[upper]
            except KeyError as exc:
                raise MiniCompilerError(f"Unknown keyword '{head}' on line {line_no}") from exc
            handler(parts)

        if not any(line.strip().startswith("RET") for line in self.body):
            self._emit_comment("implicit RET")
            self._emit("  RET")

        header = [
            ";! name: MINI",
            ";! entry: mini_start",
            ";! deps: display_number, newline",
            ";! abi: os",
            ";! bss: auto",
            ";! align: 4",
            "",
            "; generated by tools/simple_lang_compiler.py",
            "; language reference: see file docstring",
            "",
        ]

        # emit BSS aliases and optional initialisers
        bss_lines: List[str] = []
        init_lines: List[str] = []
        for var_name in self.var_order:
            var = self.vars[var_name]
            bss_lines.append(f"{var.symbol} = .bss + {var.offset}")
            if var.initial is not None:
                init_lines.append(f".{var.symbol} = {var.initial}")

        output: List[str] = []
        output.extend(header)
        if bss_lines:
            output.append("; --- variable slots ---")
            output.extend(bss_lines)
            output.append("")
        if init_lines:
            output.append("; --- initial values ---")
            output.extend(init_lines)
            output.append("")

        output.append("mini_start:")
        if not self.body:
            output.append("  RET")
        else:
            output.extend(self.body)
        output.append("")
        return "\n".join(output)


def compile_text(text: str) -> str:
    compiler = MiniCompiler(text.splitlines())
    return compiler.compile()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile MINI source to EASM")
    parser.add_argument("source", type=pathlib.Path, help="Input .mini source file")
    parser.add_argument("-o", "--output", type=pathlib.Path, help="Output .easm file")
    args = parser.parse_args(argv)

    text = args.source.read_text()
    try:
        asm = compile_text(text)
    except MiniCompilerError as exc:
        raise SystemExit(f"error: {exc}") from exc

    if args.output:
        args.output.write_text(asm + "\n")
    else:
        print(asm)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())

