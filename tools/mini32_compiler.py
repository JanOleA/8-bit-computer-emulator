#!/usr/bin/env python3
"""Mini32 source to .easm compiler.

The Mini32 language is described in docs/mini32_language.md.  This script parses the
structured source, allocates BSS storage, and emits assembly compatible with
`tools/compile_routines.py`.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, List, Optional, Sequence, Tuple


class Mini32Error(Exception):
    """Raised when Mini32 source cannot be parsed or compiled."""


# Known symbols injected by compile_routines.py when ABI=os
# char/textloc/... are memory-mapped locations, bss is the base pointer.
PREDEFINED_SYMBOLS: Dict[str, str] = {
    "char": "memory",
    "textloc": "memory",
    "arg1": "memory",
    "arg2": "memory",
    "res1": "memory",
    "res2": "memory",
    "res3": "memory",
    "pow2": "memory",
    "num_digits": "memory",
    "ascii_start": "memory",
    "no_input": "memory",
    "work1": "memory",
    "work2": "memory",
    "work3": "memory",
    "work4": "memory",
    "input_buf": "memory",
    "input_ptr": "memory",
    "cmd_len": "memory",
    "cmd_ready": "memory",
    "argv_base": "memory",
    "argv_buf": "memory",
    "random_seed": "memory",
    "inc_random_seed": "memory",
    "bits_avail": "memory",
    "prog_table": "memory",
    "bss": "const",
}

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CALL_RE = re.compile(r"^[A-Za-z_@][A-Za-z0-9_@]*$")


@dataclass
class Symbol:
    name: str
    kind: str  # 'var', 'const', 'data', 'abi_mem', 'abi_const'
    offset: int = 0
    size: int = 1
    value: Optional[str] = None  # for const/data textual value

    @property
    def is_memory(self) -> bool:
        return self.kind in {"var", "abi_mem"}

    @property
    def is_immediate(self) -> bool:
        return self.kind in {"const", "data", "abi_const"}


@dataclass
class ConstDef:
    name: str
    value: str


@dataclass
class VarDef:
    name: str
    offset: int
    size: int


@dataclass
class DataDef:
    name: str
    literal: str


@dataclass
class ExprTerm:
    sign: int
    term: "Term"


@dataclass
class Term:
    kind: str  # 'literal' or 'symbol'
    value: Optional[int] = None
    symbol: Optional[Symbol] = None
    offset: int = 0

    def immediate_expr(self) -> str:
        assert self.symbol is not None
        base = f".{self.symbol.name}"
        if self.offset:
            op = "+" if self.offset >= 0 else "-"
            return f"{base} {op} {abs(self.offset)}"
        return base

    def address_expr(self) -> str:
        assert self.symbol is not None
        base = f".{self.symbol.name}"
        if self.offset:
            op = "+" if self.offset >= 0 else "-"
            return f"{base} {op} {abs(self.offset)}"
        return base


@dataclass
class Expression:
    terms: List[ExprTerm]
    source: str

    def negated(self) -> "Expression":
        return Expression([ExprTerm(-t.sign, t.term) for t in self.terms], f"-({self.source})")


@dataclass
class TargetRef:
    name: str
    symbol: Symbol
    offset: int

    def address_expr(self) -> str:
        base = f".{self.symbol.name}"
        if self.offset:
            op = "+" if self.offset >= 0 else "-"
            return f"{base} {op} {abs(self.offset)}"
        return base


@dataclass
class LetStmt:
    target: TargetRef
    op: str  # '=', '+=', '-='
    expr: Expression


@dataclass
class CallStmt:
    callee: str
    args: List[Expression]
    extern: bool


@dataclass
class ReturnStmt:
    expr: Optional[Expression]


@dataclass
class IfStmt:
    condition: Expression
    then_body: List["Statement"]
    else_body: Optional[List["Statement"]] = None


@dataclass
class WhileStmt:
    condition: Expression
    body: List["Statement"]


@dataclass
class BreakStmt:
    pass


@dataclass
class ContinueStmt:
    pass


@dataclass
class AsmStmt:
    payload: str


Statement = (LetStmt | CallStmt | ReturnStmt | IfStmt | WhileStmt |
             BreakStmt | ContinueStmt | AsmStmt)


@dataclass
class FunctionDef:
    name: str
    body: List[Statement]


@dataclass
class Program:
    meta: Dict[str, str] = field(default_factory=dict)
    deps: List[str] = field(default_factory=list)
    consts: List[ConstDef] = field(default_factory=list)
    vars: List[VarDef] = field(default_factory=list)
    data: List[DataDef] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)


class Mini32Parser:
    def __init__(self, text: str, source_name: str = "<string>") -> None:
        self.text = text
        self.source_name = source_name
        self.lines: List[Tuple[int, str, int]] = []
        self.pos = 0
        self.program = Program()
        self.bss_cursor = 0
        self.symbols: Dict[str, Symbol] = {}
        for name, kind in PREDEFINED_SYMBOLS.items():
            mapped_kind = "abi_mem" if kind == "memory" else "abi_const"
            self.symbols[name] = Symbol(name=name, kind=mapped_kind)

    def parse(self) -> Program:
        self._preprocess_lines()
        while self.pos < len(self.lines):
            indent, text, lineno = self._peek()
            if indent != 0:
                raise self._error(lineno, "Top-level statements must not be indented")
            if text.startswith("meta "):
                self._parse_meta(text, lineno)
            elif text.startswith("depends "):
                self._parse_depends(text, lineno)
            elif text.startswith("const "):
                self._parse_const(text, lineno)
            elif text.startswith("var "):
                self._parse_var(text, lineno)
            elif text.startswith("data "):
                self._parse_data(text, lineno)
            elif text.startswith("func "):
                self.program.functions.append(self._parse_function())
            else:
                raise self._error(lineno, f"Unknown top-level directive: {text}")
        return self.program

    def _preprocess_lines(self) -> None:
        for lineno, raw in enumerate(self.text.splitlines(), start=1):
            line = self._strip_comment(raw)
            if line.strip() == "":
                continue
            if "\t" in line:
                raise self._error(lineno, "Tabs are not allowed in indentation")
            indent_spaces = len(line) - len(line.lstrip(" "))
            if indent_spaces % 4 != 0:
                raise self._error(lineno, "Indentation must be multiples of four spaces")
            indent = indent_spaces // 4
            text = line.strip()
            self.lines.append((indent, text, lineno))

    @staticmethod
    def _strip_comment(line: str) -> str:
        result = []
        in_single = False
        in_double = False
        prev = ""
        for ch in line:
            if ch == "'" and not in_double and prev != "\\":
                in_single = not in_single
            elif ch == '"' and not in_single and prev != "\\":
                in_double = not in_double
            if ch == '#' and not in_single and not in_double:
                break
            result.append(ch)
            prev = ch
        return ''.join(result)

    def _peek(self) -> Tuple[int, str, int]:
        return self.lines[self.pos]

    def _next(self) -> Tuple[int, str, int]:
        line = self.lines[self.pos]
        self.pos += 1
        return line

    def _parse_meta(self, text: str, lineno: int) -> None:
        try:
            _, rest = text.split(" ", 1)
            key, value = rest.split("=", 1)
        except ValueError as exc:
            raise self._error(lineno, "meta expects 'meta key = value'") from exc
        key = key.strip().lower()
        value = value.strip()
        self.program.meta[key] = value
        self.pos += 1

    def _parse_depends(self, text: str, lineno: int) -> None:
        _, rest = text.split(" ", 1)
        deps = [d.strip() for d in rest.split(",") if d.strip()]
        if not deps:
            raise self._error(lineno, "depends requires at least one identifier")
        self.program.deps.extend(deps)
        self.pos += 1

    def _parse_const(self, text: str, lineno: int) -> None:
        try:
            _, rest = text.split(" ", 1)
            name_part, value_part = rest.split("=", 1)
        except ValueError as exc:
            raise self._error(lineno, "const expects 'const NAME = value'") from exc
        name = name_part.strip()
        value = value_part.strip()
        self._ensure_identifier(name, lineno)
        if name in self.symbols:
            raise self._error(lineno, f"Duplicate symbol {name}")
        self.program.consts.append(ConstDef(name=name, value=value))
        self.symbols[name] = Symbol(name=name, kind="const", value=value)
        self.pos += 1

    def _parse_var(self, text: str, lineno: int) -> None:
        body = text[4:].strip()
        name: str
        size = 1
        if '[' in body:
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\[(.+)\]$", body)
            if not match:
                raise self._error(lineno, "Invalid var declaration; expected var NAME or var NAME[SIZE]")
            name = match.group(1)
            size_str = match.group(2).strip()
            try:
                size = int(size_str, 0)
            except ValueError as exc:
                raise self._error(lineno, f"Invalid array size: {size_str}") from exc
            if size <= 0:
                raise self._error(lineno, "Array size must be positive")
        else:
            name = body
        self._ensure_identifier(name, lineno)
        if name in self.symbols:
            raise self._error(lineno, f"Duplicate symbol {name}")
        offset = self.bss_cursor
        self.program.vars.append(VarDef(name=name, offset=offset, size=size))
        self.symbols[name] = Symbol(name=name, kind="var", offset=offset, size=size)
        self.bss_cursor += size
        self.pos += 1

    def _parse_data(self, text: str, lineno: int) -> None:
        try:
            _, rest = text.split(" ", 1)
            name_part, literal_part = rest.split("=", 1)
        except ValueError as exc:
            raise self._error(lineno, 'data expects "data NAME = \"...\""') from exc
        name = name_part.strip()
        literal_raw = literal_part.strip()
        self._ensure_identifier(name, lineno)
        if name in self.symbols:
            raise self._error(lineno, f"Duplicate symbol {name}")
        try:
            literal = ast.literal_eval(literal_raw)
        except Exception as exc:  # noqa: BLE001 - surface parsing error
            raise self._error(lineno, "data literal must be a Python string literal") from exc
        if not isinstance(literal, str):
            raise self._error(lineno, "data literal must evaluate to a string")
        try:
            literal.encode("ascii")
        except UnicodeEncodeError as exc:
            raise self._error(lineno, "data literal must contain ASCII characters only") from exc
        literal_text = json.dumps(literal)
        self.program.data.append(DataDef(name=name, literal=literal_text))
        self.symbols[name] = Symbol(name=name, kind="data", value=literal_text)
        self.pos += 1

    def _parse_function(self) -> FunctionDef:
        indent, text, lineno = self._next()
        header = text.rstrip(":")
        if header == text:
            raise self._error(lineno, "func header must end with ':'")
        _, name = header.split(" ", 1)
        name = name.strip()
        self._ensure_identifier(name, lineno)
        body = self._parse_block(indent + 1)
        return FunctionDef(name=name, body=body)

    def _parse_block(self, base_indent: int) -> List[Statement]:
        statements: List[Statement] = []
        while self.pos < len(self.lines):
            indent, text, lineno = self._peek()
            if indent < base_indent:
                break
            if indent > base_indent:
                raise self._error(lineno, "Unexpected indentation")
            if text.startswith("if "):
                statements.append(self._parse_if(base_indent))
                continue
            if text.startswith("while "):
                statements.append(self._parse_while(base_indent))
                continue
            if text == "else:":
                break
            statements.append(self._parse_statement(base_indent))
        return statements

    def _parse_if(self, base_indent: int) -> IfStmt:
        indent, text, lineno = self._next()
        condition_text = text[3:].strip()
        if not condition_text.endswith(":"):
            raise self._error(lineno, "if statement must end with ':'")
        condition_text = condition_text[:-1].strip()
        if not condition_text:
            raise self._error(lineno, "if requires a condition expression")
        condition = self._parse_expression(condition_text, lineno)
        then_body = self._parse_block(base_indent + 1)
        else_body: Optional[List[Statement]] = None
        if self.pos < len(self.lines):
            indent2, text2, lineno2 = self._peek()
            if indent2 == base_indent and text2 == "else:":
                self._next()
                else_body = self._parse_block(base_indent + 1)
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body)

    def _parse_while(self, base_indent: int) -> WhileStmt:
        indent, text, lineno = self._next()
        condition_text = text[6:].strip()
        if not condition_text.endswith(":"):
            raise self._error(lineno, "while statement must end with ':'")
        condition_text = condition_text[:-1].strip()
        if not condition_text:
            raise self._error(lineno, "while requires a condition expression")
        condition = self._parse_expression(condition_text, lineno)
        body = self._parse_block(base_indent + 1)
        return WhileStmt(condition=condition, body=body)

    def _parse_statement(self, base_indent: int) -> Statement:
        indent, text, lineno = self._next()
        if text.startswith("let "):
            return self._parse_let(text, lineno)
        if text.startswith("call "):
            return self._parse_call(text, lineno)
        if text.startswith("return"):
            return self._parse_return(text, lineno)
        if text == "break":
            return BreakStmt()
        if text == "continue":
            return ContinueStmt()
        if text.startswith("asm "):
            return self._parse_asm(text, lineno)
        raise self._error(lineno, f"Unknown statement: {text}")

    def _parse_let(self, text: str, lineno: int) -> LetStmt:
        body = text[4:].strip()
        if "+=" in body:
            target_part, expr_part = body.split("+=", 1)
            op = "+="
        elif "-=" in body:
            target_part, expr_part = body.split("-=", 1)
            op = "-="
        elif "=" in body:
            target_part, expr_part = body.split("=", 1)
            op = "="
        else:
            raise self._error(lineno, "let statement is missing '='")
        target = self._parse_target(target_part.strip(), lineno)
        expr = self._parse_expression(expr_part.strip(), lineno)
        return LetStmt(target=target, op=op, expr=expr)

    def _parse_call(self, text: str, lineno: int) -> CallStmt:
        body = text[5:].strip()
        if not body:
            raise self._error(lineno, "call requires a target")
        if body.endswith(")") and "(" in body:
            name_part, args_part = body.split("(", 1)
            callee = name_part.strip()
            args_str = args_part[:-1].strip()
        else:
            callee = body
            args_str = ""
        if not CALL_RE.match(callee):
            raise self._error(lineno, f"Invalid callee name: {callee}")
        args: List[Expression] = []
        if args_str:
            raw_args = [a.strip() for a in args_str.split(",") if a.strip()]
            if not raw_args:
                raise self._error(lineno, "Malformed call argument list")
            for arg in raw_args:
                args.append(self._parse_expression(arg, lineno))
        extern = callee.startswith("@")
        return CallStmt(callee=callee, args=args, extern=extern)

    def _parse_return(self, text: str, lineno: int) -> ReturnStmt:
        body = text[6:].strip()
        if not body:
            return ReturnStmt(expr=None)
        expr = self._parse_expression(body, lineno)
        return ReturnStmt(expr=expr)

    def _parse_asm(self, text: str, lineno: int) -> AsmStmt:
        payload = text[4:].strip()
        if not payload:
            raise self._error(lineno, "asm requires a string literal")
        try:
            literal = ast.literal_eval(payload)
        except Exception as exc:  # noqa: BLE001
            raise self._error(lineno, "asm payload must be a Python string literal") from exc
        if not isinstance(literal, str):
            raise self._error(lineno, "asm payload must evaluate to a string")
        return AsmStmt(payload=literal)

    def _parse_target(self, text: str, lineno: int) -> TargetRef:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\[(.+)\])?$", text)
        if not match:
            raise self._error(lineno, f"Invalid assignment target '{text}'")
        name = match.group(1)
        offset = 0
        if match.group(3):
            idx_str = match.group(3).strip()
            try:
                offset = int(idx_str, 0)
            except ValueError as exc:
                raise self._error(lineno, f"Invalid target index: {idx_str}") from exc
        symbol = self._lookup_symbol(name, lineno)
        if not symbol.is_memory:
            raise self._error(lineno, f"Cannot assign to immediate symbol '{name}'")
        if symbol.kind == "var" and offset >= symbol.size:
            raise self._error(lineno, f"Index {offset} out of bounds for array '{name}'")
        return TargetRef(name=name, symbol=symbol, offset=offset)

    def _parse_expression(self, text: str, lineno: int) -> Expression:
        if not text:
            raise self._error(lineno, "Empty expression")
        terms: List[ExprTerm] = []
        current = []
        sign = 1
        depth = 0
        idx = 0
        while idx < len(text):
            ch = text[idx]
            if ch in "+-" and depth == 0:
                if not current:
                    sign = 1 if ch == "+" else -1
                else:
                    term_str = ''.join(current).strip()
                    if term_str:
                        terms.append(ExprTerm(sign, self._parse_term(term_str, lineno)))
                    current = []
                    sign = 1 if ch == "+" else -1
            else:
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth = max(0, depth - 1)
                current.append(ch)
            idx += 1
        term_str = ''.join(current).strip()
        if term_str:
            terms.append(ExprTerm(sign, self._parse_term(term_str, lineno)))
        if not terms:
            raise self._error(lineno, "Expression has no terms")
        return Expression(terms=terms, source=text)

    def _parse_term(self, text: str, lineno: int) -> Term:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\[(.+)\])?$", text)
        if match:
            name = match.group(1)
            offset = 0
            if match.group(3):
                idx_str = match.group(3).strip()
                try:
                    offset = int(idx_str, 0)
                except ValueError as exc:
                    raise self._error(lineno, f"Invalid index '{idx_str}' in term '{text}'") from exc
            symbol = self._lookup_symbol(name, lineno)
            return Term(kind="symbol", symbol=symbol, offset=offset)
        # Literal number
        try:
            value = int(text, 0)
        except ValueError as exc:
            raise self._error(lineno, f"Unknown symbol or literal '{text}'") from exc
        return Term(kind="literal", value=value)

    def _lookup_symbol(self, name: str, lineno: int) -> Symbol:
        sym = self.symbols.get(name)
        if not sym:
            raise self._error(lineno, f"Unknown symbol '{name}'")
        return sym

    @staticmethod
    def _ensure_identifier(name: str, lineno: int) -> None:
        if not IDENT_RE.match(name):
            raise Mini32Error(f"Line {lineno}: Invalid identifier '{name}'")

    def _error(self, lineno: int, message: str) -> Mini32Error:
        return Mini32Error(f"{self.source_name}:{lineno}: {message}")


@dataclass
class LoopContext:
    start_label: str
    end_label: str


class CodeGenerator:
    def __init__(self, program: Program) -> None:
        self.program = program
        self.lines: List[str] = []
        self.label_counter = 0
        self.loop_stack: List[LoopContext] = []

    def generate(self) -> str:
        self._emit_headers()
        self._emit_globals()
        for func in self.program.functions:
            if self.lines and self.lines[-1] != "":
                self.lines.append("")
            self._emit_label(f"{func.name}")
            self._emit_statements(func.name, func.body)
            self._ensure_function_ret()
        if self.lines and self.lines[-1] != "":
            self.lines.append("")
        return "\n".join(self.lines)

    def _emit_headers(self) -> None:
        meta_items = self.program.meta.copy()
        if self.program.deps:
            existing = meta_items.get("deps")
            deps_str = ", ".join(self.program.deps)
            if existing:
                deps_str = f"{existing}, {deps_str}"
            meta_items["deps"] = deps_str
        for key, value in meta_items.items():
            self.lines.append(f";! {key}: {value}")
        if meta_items:
            self.lines.append("")

    def _emit_globals(self) -> None:
        for const in self.program.consts:
            self.lines.append(f"{const.name} = {const.value}")
        for var in self.program.vars:
            base = f".bss + {var.offset}" if var.offset else ".bss"
            self.lines.append(f"{var.name} = {base}")
        for data in self.program.data:
            self.lines.append(f".{data.name} = {data.literal}")
        if self.program.consts or self.program.vars or self.program.data:
            self.lines.append("")

    def _emit_label(self, name: str) -> None:
        self.lines.append(f"{name}:")

    def _emit(self, line: str) -> None:
        self.lines.append(f"  {line}")

    def _emit_statements(self, func_name: str, statements: List[Statement]) -> None:
        for stmt in statements:
            if isinstance(stmt, LetStmt):
                self._emit_let(stmt)
            elif isinstance(stmt, CallStmt):
                self._emit_call(stmt)
            elif isinstance(stmt, ReturnStmt):
                self._emit_return(stmt)
            elif isinstance(stmt, IfStmt):
                self._emit_if(func_name, stmt)
            elif isinstance(stmt, WhileStmt):
                self._emit_while(func_name, stmt)
            elif isinstance(stmt, BreakStmt):
                self._emit_break()
            elif isinstance(stmt, ContinueStmt):
                self._emit_continue()
            elif isinstance(stmt, AsmStmt):
                self._emit_asm(stmt)
            else:  # pragma: no cover - defensive
                raise Mini32Error(f"Unhandled statement type: {stmt}")

    def _emit_let(self, stmt: LetStmt) -> None:
        if stmt.op == "=":
            self._emit_expression(stmt.expr)
        elif stmt.op == "+=":
            self._emit(f"LDA {stmt.target.address_expr()}")
            self._emit_expression(stmt.expr, initial_loaded=True)
        elif stmt.op == "-=":
            self._emit(f"LDA {stmt.target.address_expr()}")
            self._emit_expression(stmt.expr.negated(), initial_loaded=True)
        else:
            raise Mini32Error(f"Unsupported let operation {stmt.op}")
        self._emit(f"STA {stmt.target.address_expr()}")

    def _emit_call(self, stmt: CallStmt) -> None:
        for index, expr in enumerate(stmt.args, start=1):
            if index > 8:
                raise Mini32Error("Calls support at most 8 arguments")
            arg_name = f".arg{index}"
            self._emit_expression(expr)
            self._emit(f"STA {arg_name}")
        callee = stmt.callee
        mnemonic = f"JSR {callee}"
        self._emit(mnemonic)

    def _emit_return(self, stmt: ReturnStmt) -> None:
        if stmt.expr is not None:
            self._emit_expression(stmt.expr)
        self._emit("RET")

    def _emit_if(self, func_name: str, stmt: IfStmt) -> None:
        end_label = self._next_label(func_name, "ENDIF")
        else_label = self._next_label(func_name, "ELSE") if stmt.else_body else end_label
        self._emit_expression(stmt.condition)
        self._emit(f"JPZ {else_label}")
        self._emit_nested_statements(func_name, stmt.then_body)
        if stmt.else_body:
            self._emit(f"JMP {end_label}")
            self.lines.append(f"{else_label}:")
            self._emit_nested_statements(func_name, stmt.else_body)
        if stmt.else_body:
            self.lines.append(f"{end_label}:")
        else:
            self.lines.append(f"{else_label}:")

    def _emit_while(self, func_name: str, stmt: WhileStmt) -> None:
        start_label = self._next_label(func_name, "WHILE_START")
        end_label = self._next_label(func_name, "WHILE_END")
        self.lines.append(f"{start_label}:")
        self._emit_expression(stmt.condition)
        self._emit(f"JPZ {end_label}")
        self.loop_stack.append(LoopContext(start_label=start_label, end_label=end_label))
        self._emit_nested_statements(func_name, stmt.body)
        self.loop_stack.pop()
        self._emit(f"JMP {start_label}")
        self.lines.append(f"{end_label}:")

    def _emit_break(self) -> None:
        if not self.loop_stack:
            raise Mini32Error("'break' used outside of a loop")
        self._emit(f"JMP {self.loop_stack[-1].end_label}")

    def _emit_continue(self) -> None:
        if not self.loop_stack:
            raise Mini32Error("'continue' used outside of a loop")
        self._emit(f"JMP {self.loop_stack[-1].start_label}")

    def _emit_asm(self, stmt: AsmStmt) -> None:
        for line in stmt.payload.splitlines():
            if line.strip() == "":
                self.lines.append("")
            elif line.startswith("  "):
                self.lines.append(line)
            else:
                self._emit(line)

    def _emit_nested_statements(self, func_name: str, statements: List[Statement]) -> None:
        self._emit_statements(func_name, statements)

    def _emit_expression(self, expr: Expression, initial_loaded: bool = False) -> None:
        terms = expr.terms
        if not terms:
            raise Mini32Error("cannot emit empty expression")
        idx = 0
        if not initial_loaded:
            first = terms[0]
            self._emit_first_term(first)
            idx = 1
        for term in terms[idx:]:
            self._emit_followup_term(term)

    def _emit_first_term(self, term: ExprTerm) -> None:
        t = term.term
        if t.kind == "literal":
            value = term.sign * (t.value or 0)
            self._emit(f"LDI {value}")
            return
        if not t.symbol:
            raise Mini32Error("Symbol term missing symbol")
        if t.symbol.is_memory:
            if term.sign == 1:
                self._emit(f"LDA {t.address_expr()}")
            else:
                self._emit("LDI 0")
                self._emit(f"SUB {t.address_expr()}")
        else:
            if term.sign == 1:
                self._emit(f"LDI {t.immediate_expr()}")
            else:
                self._emit("LDI 0")
                self._emit(f"SUI {t.immediate_expr()}")

    def _emit_followup_term(self, term: ExprTerm) -> None:
        t = term.term
        if t.kind == "literal":
            value = term.sign * (t.value or 0)
            if value >= 0:
                self._emit(f"ADI {value}")
            else:
                self._emit(f"SUI {abs(value)}")
            return
        if not t.symbol:
            raise Mini32Error("Symbol term missing symbol")
        if t.symbol.is_memory:
            if term.sign == 1:
                self._emit(f"ADD {t.address_expr()}")
            else:
                self._emit(f"SUB {t.address_expr()}")
        else:
            if term.sign == 1:
                self._emit(f"ADI {t.immediate_expr()}")
            else:
                self._emit(f"SUI {t.immediate_expr()}")

    def _ensure_function_ret(self) -> None:
        # Ensure functions end with RET to match assembly expectations.
        for idx in range(len(self.lines) - 1, -1, -1):
            line = self.lines[idx]
            if line.strip() == "":
                continue
            if line.endswith(":"):
                self._emit("RET")
            elif line.strip().upper() != "RET":
                self._emit("RET")
            return
        self._emit("RET")

    def _next_label(self, func_name: str, hint: str) -> str:
        self.label_counter += 1
        return f"{func_name.upper()}__{hint}_{self.label_counter}"


def compile_text(text: str, source_name: str = "<string>") -> str:
    parser = Mini32Parser(text, source_name)
    program = parser.parse()
    generator = CodeGenerator(program)
    return generator.generate() + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    argp = argparse.ArgumentParser(description="Compile Mini32 source into .easm")
    argp.add_argument("input", help="Path to Mini32 source file")
    argp.add_argument("-o", "--output", help="Destination .easm file (defaults to stdout)")
    args = argp.parse_args(argv)

    src_path = Path(args.input)
    text = src_path.read_text()
    asm = compile_text(text, str(src_path))
    if args.output:
        dest = Path(args.output)
        dest.write_text(asm)
    else:
        print(asm, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
