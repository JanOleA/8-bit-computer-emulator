#!/usr/bin/env python3
"""Mini32 source to .easm compiler.

The Mini32 language is described in docs/mini32_language.md.  This script parses the
structured source, allocates BSS storage, and emits assembly compatible with
`tools/compile_routines.py`.

The code generator performs a lightweight peephole optimization pass on the
final assembly to remove a few common redundant instruction patterns produced
by straightforward code emission. Current optimizations (conservative):
    - STA X; LDA X  -> drop the redundant LDA (A already holds value)
    - STA .__tmp_addr; LPA .__tmp_addr -> replace second with LAP
    - LDI 0; ADI n -> LDI n (constant fold)
    - ADI 0 / SUI 0 -> removed
The pass is textual and order preserving; if in doubt it leaves code unchanged.
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
    # offset can be a compile-time integer or an expression string (for dynamic indices)
    offset: Optional[str] = None
    # number of pointer dereference operations requested via leading '*'
    deref_depth: int = 0

    def immediate_expr(self) -> str:
        assert self.symbol is not None
        base = f".{self.symbol.name}"
        if self.offset is not None and self.offset != "0":
            # offset may be an expression string like 'i' or 'i + 1'
            return f"{base} + {self.offset}"
        return base

    def address_expr(self) -> str:
        assert self.symbol is not None
        base = f".{self.symbol.name}"
        if self.offset is not None and self.offset != "0":
            return f"{base} + {self.offset}"
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
    # offset can be an integer (as string) or an expression string, or None
    offset: Optional[str] = None

    def address_expr(self) -> str:
        base = f".{self.symbol.name}"
        if self.offset is not None and self.offset != "0":
            return f"{base} + {self.offset}"
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
    returns: List[str] = field(default_factory=list) # names of return variables


@dataclass
class ReturnStmt:
    exprs: List[Expression] = field(default_factory=list)


@dataclass
class IfStmt:
    condition: Expression
    then_body: List["Statement"]
    else_body: Optional[List["Statement"]] = None
    invert: bool = False


@dataclass
class WhileStmt:
    condition: Expression
    body: List["Statement"]
    invert: bool = False


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
    args: List[str] = field(default_factory=list)


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
        # scope stack holds dicts mapping local names -> previous Symbol (or None)
        # when entering a function scope we push a new dict so locals can shadow
        # globals and be restored when exiting the scope.
        self._scope_stack: List[Dict[str, Optional[Symbol]]] = []
        self._current_function: Optional[str] = None
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
        # If we're inside a function, allocate as a local variable.
        if self._current_function is not None:
            internal = self._add_var(name, size=size, lineno=lineno, local=True, func_name=self._current_function)
            # store VarDef with the external visible name mapping to internal BSS name
            # but keep program.vars for global emission; locals are still emitted as .<internal>
        else:
            if name in self.symbols:
                raise self._error(lineno, f"Duplicate symbol {name}")
            offset = self.bss_cursor
            self.program.vars.append(VarDef(name=name, offset=offset, size=size))
            self.symbols[name] = Symbol(name=name, kind="var", offset=offset, size=size)
            self.bss_cursor += size
        self.pos += 1

    def _enter_function_scope(self, func_name: Optional[str] = None) -> None:
        # push an empty scope frame; caller should set _current_function
        self._scope_stack.append({})
        if func_name is not None:
            self._current_function = func_name

    def _exit_function_scope(self) -> None:
        # pop scope and restore shadowed symbols
        if not self._scope_stack:
            return
        frame = self._scope_stack.pop()
        for local_name, prev in frame.items():
            if prev is None:
                # remove the local symbol
                self.symbols.pop(local_name, None)
            else:
                # restore previous symbol
                self.symbols[local_name] = prev
        self._current_function = None

    def _add_var(self, name: str, size: int, lineno: int, local: bool, func_name: Optional[str] = None) -> str:
        # create and register a var, local vars get an internal unique name
        if local:
            assert func_name is not None
            internal_name = f"{func_name}.{name}"
            # record previous symbol (if any) so we can restore it on scope exit
            prev = self.symbols.get(name)
            self._scope_stack[-1][name] = prev
            # allocate internal bss slot
            offset = self.bss_cursor
            self.program.vars.append(VarDef(name=internal_name, offset=offset, size=size))
            self.symbols[name] = Symbol(name=internal_name, kind="var", offset=offset, size=size)
            self.bss_cursor += size
            return internal_name
        else:
            if name in self.symbols:
                raise self._error(lineno, f"Duplicate symbol {name}")
            offset = self.bss_cursor
            self.program.vars.append(VarDef(name=name, offset=offset, size=size))
            self.symbols[name] = Symbol(name=name, kind="var", offset=offset, size=size)
            self.bss_cursor += size
            return name

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
        # check if the function has arguments; accept empty parentheses
        raw_args: List[str]
        if "(" in header and header.endswith(")"):
            name_part, args_part = header.split("(", 1)
            header = name_part.strip()
            args_str = args_part[:-1].strip()
            if not args_str:
                raw_args = []
            else:
                raw_args = [a.strip() for a in args_str.split(",") if a.strip()]
                if not raw_args:
                    raise self._error(lineno, "Malformed function argument list")
        else:
            raw_args = []

        _, name = header.split(" ", 1)
        name = name.strip()
        self._ensure_identifier(name, lineno)

        # Now that we know the function name, enter the function-local scope so
        # arguments and any local 'var' declarations do not become global
        # symbols. Locals will be allocated in BSS using an internal name
        # prefixed by the function name (e.g. "func.arg").
        self._enter_function_scope(func_name=name)

        # register arguments as local vars (allocated in BSS with a unique
        # internal name). Store the internal names in the FunctionDef.args
        # so codegen will emit STA .<internal-name> in the prologue.
        internal_args: List[str] = []
        for arg in raw_args:
            self._ensure_identifier(arg, lineno)
            internal = self._add_var(arg, size=1, lineno=lineno, local=True, func_name=name)
            internal_args.append(internal)

        # parse function body (within the current local scope)
        body = self._parse_block(indent + 1)

        # exit function scope, restoring any shadowed symbols
        self._exit_function_scope()

        return FunctionDef(name=name, body=body, args=internal_args)

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
        # support simple == / != comparisons
        m_eq = re.match(r"^(.+)\s*==\s*(.+)$", condition_text)
        m_neq = re.match(r"^(.+)\s*!=\s*(.+)$", condition_text)
        invert_flag = False
        if m_eq:
            left = m_eq.group(1).strip()
            right = m_eq.group(2).strip()
            condition = self._parse_expression(f"{left} - {right}", lineno)
            invert_flag = True
        elif m_neq:
            left = m_neq.group(1).strip()
            right = m_neq.group(2).strip()
            condition = self._parse_expression(f"{left} - {right}", lineno)
            invert_flag = False
        else:
            condition = self._parse_expression(condition_text, lineno)
        then_body = self._parse_block(base_indent + 1)
        else_body: Optional[List[Statement]] = None
        if self.pos < len(self.lines):
            indent2, text2, lineno2 = self._peek()
            if indent2 == base_indent and text2 == "else:":
                self._next()
                else_body = self._parse_block(base_indent + 1)
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body, invert=invert_flag)

    def _parse_while(self, base_indent: int) -> WhileStmt:
        indent, text, lineno = self._next()
        condition_text = text[6:].strip()
        if not condition_text.endswith(":"):
            raise self._error(lineno, "while statement must end with ':'")
        condition_text = condition_text[:-1].strip()
        if not condition_text:
            raise self._error(lineno, "while requires a condition expression")
        # Support simple equality/inequality in conditions like 'a == b' or 'a != b'
        # by translating them into arithmetic expression (a - (b)).
        m_eq = re.match(r"^(.+)\s*==\s*(.+)$", condition_text)
        m_neq = re.match(r"^(.+)\s*!=\s*(.+)$", condition_text)
        invert_flag = False
        if m_eq:
            left = m_eq.group(1).strip()
            right = m_eq.group(2).strip()
            condition = self._parse_expression(f"{left} - {right}", lineno)
            invert_flag = True
        elif m_neq:
            left = m_neq.group(1).strip()
            right = m_neq.group(2).strip()
            condition = self._parse_expression(f"{left} - {right}", lineno)
            invert_flag = False
        else:
            condition = self._parse_expression(condition_text, lineno)
        body = self._parse_block(base_indent + 1)
        return WhileStmt(condition=condition, body=body, invert=invert_flag)

    def _parse_statement(self, base_indent: int) -> Statement:
        indent, text, lineno = self._next()
        if text.startswith("let "):
            return self._parse_let(text, lineno)
        if text.startswith("call "):
            return self._parse_call(text, lineno)
        if text.startswith("return"):
            return self._parse_return(text, lineno)
        # simple 'pass' no-op
        if text == "pass":
            return AsmStmt(payload="")
        # Accept raw assembly-like lines (e.g. 'LDI 46' or 'JSR @echon') as asm statements
        if re.match(r"^[A-Z@][A-Z0-9_\.@ ]*(?:[ \t].*)?$", text):
            return AsmStmt(payload=text)
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
        body, returns = body.split("->", 1) if "->" in body else (body, "")
        # normalize return names (strip whitespace) and ignore empty entries
        if returns:
            returns = [r.strip() for r in returns.strip().split(",") if r.strip()]
        else:
            returns = []
        body = body.strip()
        
        # check that returns are valid identifiers (allow '_' as placeholder)
        for ret in returns:
            if ret == "_":
                continue
            if not IDENT_RE.match(ret):
                raise self._error(lineno, f"Invalid return variable name: {ret}")

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
        # Ensure return variables exist and convert them to internal names
        resolved_returns: List[str] = []
        for ret in returns:
            if ret == "_":
                resolved_returns.append("_")
                continue
            sym = self.symbols.get(ret)
            if not sym:
                if self._current_function is not None:
                    internal = self._add_var(ret, size=1, lineno=lineno, local=True, func_name=self._current_function)
                    resolved_returns.append(internal)
                else:
                    raise self._error(lineno, f"Unknown return variable: {ret}")
            else:
                # use the symbol's internal name (may be same as ret for globals)
                resolved_returns.append(sym.name)

        return CallStmt(callee=callee, args=args, extern=extern, returns=resolved_returns)

    def _parse_return(self, text: str, lineno: int) -> ReturnStmt:
        body = text[6:].strip()
        if not body:
            return ReturnStmt(exprs=[])
        # allow multiple return expressions separated by commas
        parts = [p.strip() for p in body.split(",") if p.strip()]
        if not parts:
            return ReturnStmt(exprs=[])
        exprs: List[Expression] = []
        for part in parts:
            exprs.append(self._parse_expression(part, lineno))
        return ReturnStmt(exprs=exprs)

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
        # Accept name or name[index_expr]. Index_expr may be an integer literal
        # (in which case we perform a static bounds check) or an arbitrary
        # expression string which will be emitted as part of the address_expr().
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(.+)\])?$", text)
        if not match:
            raise self._error(lineno, f"Invalid assignment target '{text}'")
        name = match.group(1)
        offset: Optional[str] = None
        if match.group(2):
            idx_raw = match.group(2).strip()
            # Try to parse integer literal for static bounds checking; otherwise
            # keep the raw expression string so address_expr() can emit it.
            try:
                int_val = int(idx_raw, 0)
            except ValueError:
                offset = idx_raw
            else:
                offset = str(int_val)
        try:
            symbol = self._lookup_symbol(name, lineno)
        except Mini32Error:
            # If we're inside a function, implicitly create a local scalar for
            # simple assignments like 'let r = ...'. For other contexts this
            # remains an error.
            if self._current_function is not None and (match.group(2) is None):
                internal = self._add_var(name, size=1, lineno=lineno, local=True, func_name=self._current_function)
                symbol = self._lookup_symbol(name, lineno)
            else:
                raise
        if not symbol.is_memory:
            raise self._error(lineno, f"Cannot assign to immediate symbol '{name}'")
        # If we have a concrete integer offset and the symbol is a var, perform
        # a static bounds check.
        if symbol.kind == "var":
            if offset is not None:
                try:
                    off_int = int(offset, 0)
                except ValueError:
                    off_int = None
                if off_int is not None and off_int >= symbol.size:
                    raise self._error(lineno, f"Index {off_int} out of bounds for array '{name}'")
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
        # Support leading '*' dereference operators: *name, **name[idx]
        deref_depth = 0
        while text.startswith('*'):
            deref_depth += 1
            text = text[1:].lstrip()
        # allow index to be an expression string inside brackets: name[expr]
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(.+)\])?$", text)
        if match:
            name = match.group(1)
            offset = None
            if match.group(2):
                idx_raw = match.group(2).strip()
                # keep the raw expression (we don't evaluate it here)
                offset = idx_raw
            symbol = self._lookup_symbol(name, lineno)
            return Term(kind="symbol", symbol=symbol, offset=offset, deref_depth=deref_depth)
        # Literal number
        try:
            value = int(text, 0)
        except ValueError as exc:
            raise self._error(lineno, f"Unknown symbol or literal '{text}'") from exc
        if deref_depth:
            raise self._error(lineno, "Cannot dereference a literal")
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
        self.current_function: Optional[str] = None
        # Reserve scratch variables for dynamic / pointer indexing if not already present.
        # We append them at the end so existing offsets remain valid.
        existing = {v.name for v in self.program.vars}
        if "__tmp_addr" not in existing:
            max_off = 0
            for v in self.program.vars:
                end = v.offset + v.size
                if end > max_off:
                    max_off = end
            self.program.vars.append(VarDef(name="__tmp_addr", offset=max_off, size=1))
            existing.add("__tmp_addr")
        if "__tmp_base" not in existing:
            max_off = 0
            for v in self.program.vars:
                end = v.offset + v.size
                if end > max_off:
                    max_off = end
            self.program.vars.append(VarDef(name="__tmp_base", offset=max_off, size=1))

    def generate(self) -> str:
        self._emit_headers()
        self._emit_globals()
        # Emit a startup jump. If the source provided a 'meta entry = NAME'
        # directive use that name; otherwise fall back to 'main' when present.
        entry = None
        if "entry" in self.program.meta:
            raw = self.program.meta["entry"].strip()
            # strip optional surrounding quotes
            if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1]
            entry = raw
        elif any(f.name == "main" for f in self.program.functions):
            entry = "main"
        if entry:
            # Use _emit so the instruction is indented like other instructions
            self._emit(f"JMP {entry}")
        for func in self.program.functions:
            self.current_function = func.name
            if self.lines and self.lines[-1] != "":
                self.lines.append("")
            self._emit_label(f"{func.name}")
            self._emit_function_prologue(func.args)
            self._emit_statements(func.name, func.body)
            self._ensure_function_ret()
        self.current_function = None
        if self.lines and self.lines[-1] != "":
            self.lines.append("")
        # Apply a peephole optimization pass before returning
        optimized = self._peephole_optimize(self.lines)
        return "\n".join(optimized)

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

    def _emit_function_prologue(self, args: List[str]) -> None:
        if not args:
            return
        # first store the return address
        self._emit("PLA")  # pull return address from stack
        self._emit("MOVAB")  # move to B register

        # Pull arguments from stack into bss space
        # Arguments are pushed by the caller left-to-right. The callee must
        # therefore pop them in reverse order so the first argument maps to
        # the first parameter slot.
        for arg in args[::-1]:
            self._emit("PLA")
            self._emit(f"STA .{arg}")

        self._emit("MOVBA") # move return address back to A register
        self._emit("PHA")   # push return address back to stack

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
        # Support direct variable/array element assignment. If target has a dynamic
        # offset expression (contains non-digit / plus/minus) we must compute the
        # effective address and use SAS to store.
        addr_expr = stmt.target.address_expr()
        dynamic_index = ('+' in addr_expr) or any(ch.isalpha() for ch in addr_expr.split() if ch not in {'.', '+'})

        if not dynamic_index:
            # Simple static addressable store.
            if stmt.op == "=":
                self._emit_expression(stmt.expr)
            elif stmt.op == "+=":
                self._emit(f"LDA {addr_expr}")
                self._emit_expression(stmt.expr, initial_loaded=True)
            elif stmt.op == "-=":
                self._emit(f"LDA {addr_expr}")
                self._emit_expression(stmt.expr.negated(), initial_loaded=True)
            else:
                raise Mini32Error(f"Unsupported let operation {stmt.op}")
            self._emit(f"STA {addr_expr}")
            return

        # Dynamic index path: we do not yet support += / -= directly on dynamic
        # indices without an additional load (load current value, adjust, store).
        # Implement both forms.
        if stmt.op in {"+=", "-="}:
            # Load current value first via existing address computation.
            # Strategy: compute address into __tmp_addr then LPA -> value.
            self._emit_indexed_store_address_setup(stmt)
            self._emit("LPA .__tmp_addr")
            if stmt.op == "+=":
                self._emit_expression(stmt.expr, initial_loaded=True)
            else:  # -=
                self._emit_expression(stmt.expr.negated(), initial_loaded=True)
            # A now holds result to store.
            self._emit("STA .__tmp_base")  # save value
            self._emit("LDA .__tmp_addr")  # reload address
            self._emit("PHA")
            self._emit("LDA .__tmp_base")
            self._emit("SAS")
            return

        # '=' dynamic index assignment.
        self._emit_expression(stmt.expr)
        # Save value.
        self._emit("STA .__tmp_base")
        # Compute address into __tmp_addr
        self._emit_indexed_store_address_setup(stmt)
        # Push address and restore value for SAS store.
        self._emit("LDA .__tmp_addr")
        self._emit("PHA")
        self._emit("LDA .__tmp_base")
        self._emit("SAS")

    def _emit_indexed_store_address_setup(self, stmt: LetStmt) -> None:
        """Compute effective address for a dynamic indexed store into .__tmp_addr.

        The target.address_expr() returns patterns like '.arr + i' or '.ptr + idx'.
        We evaluate the offset expression part and add base.
        Assumptions: Only '+' separated base + offset; offset expression limited
        to + / - of symbols and literals. Reuse _emit_compute_simple_expression.
        """
        addr_expr = stmt.target.address_expr()
        # Split at the first '+' into base and offset (base starts with '.').
        if '+' not in addr_expr:
            # Should not happen for dynamic path; fall back to direct store.
            self._emit(f"LDA {addr_expr}")
            self._emit("STA .__tmp_addr")
            return
        base_part, offset_part = addr_expr.split('+', 1)
        base_part = base_part.strip()
        offset_part = offset_part.strip()
        # Compute offset expression into A
        self._emit_compute_simple_expression(offset_part)
        # Add base address
        self._emit(f"ADD {base_part}")
        self._emit("STA .__tmp_addr")

    def _emit_call(self, stmt: CallStmt) -> None:
        """  """
        # Push arguments in left-to-right order so they appear on the stack
        # in the same order as the call syntax. The callee will pop them in
        # reverse order.
        for expr in stmt.args:
            self._emit_expression(expr)
            self._emit(f"PHA")
        callee = stmt.callee
        mnemonic = f"JSR {callee}"
        self._emit(mnemonic)

        if stmt.returns:
            # Multiple returns are delivered on the stack by the callee.
            # Caller must pop them in reverse order. Support '_' as a
            # placeholder to discard a returned value.
            if len(stmt.returns) > 1:
                # Pop returned values in forward order so the first returned value
                # maps to the first variable. The callee pushes values in reverse
                # order so the first logical return is on top of the stack.
                for ret_var in stmt.returns:
                    if ret_var == "_":
                        # discard one value from stack
                        self._emit(f"PLA")
                    else:
                        self._emit(f"PLA")
                        self._emit(f"STA .{ret_var}")
            else:  # single return value: A register contains it
                ret_var = stmt.returns[0]
                if ret_var == "_":
                    # If caller doesn't care about the single return, just ignore A
                    # nothing to emit (value already in A)
                    pass
                else:
                    self._emit(f"STA .{ret_var}")

    def _emit_return(self, stmt: ReturnStmt) -> None:
        # No expressions: normal RET
        if not stmt.exprs:
            self._emit("RET")
            return

        # Single return expression: leave value in A (legacy fast path)
        if len(stmt.exprs) == 1:
            self._emit_expression(stmt.exprs[0])
            self._emit("RET")
            return

        # Multiple return values: use stack-based return sequence.
        # Save return address: pull it from stack and hold it in B
        self._emit("PLA")
        self._emit("MOVAB")

        # Evaluate and push return values in reverse order so that the
        # first listed return value is on top of the stack after push.
        for expr in stmt.exprs[::-1]:
            self._emit_expression(expr)
            self._emit("PHA")

        # Finally push the saved return address back so that RET will pop it.
        self._emit("MOVBA")
        self._emit("PHA")
        self._emit("RET")

    def _emit_if(self, func_name: str, stmt: IfStmt) -> None:
        end_label = self._next_label(func_name, "ENDIF")
        else_label = self._next_label(func_name, "ELSE") if stmt.else_body else end_label
        self._emit_expression(stmt.condition)
        # Original equality-only logic
        self._emit("CPI 0")
        jump_op = "JPZ" if not getattr(stmt, "invert", False) else "JNZ"
        self._emit(f"{jump_op} {else_label}")
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
        self._emit("CPI 0")
        jump_op = "JPZ" if not getattr(stmt, "invert", False) else "JNZ"
        self._emit(f"{jump_op} {end_label}")
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
            # If an offset is present, treat as indexing (array or pointer semantics)
            if t.offset is not None:
                self._emit_indexed_symbol_term(term, first_term=True)
            else:
                if term.sign == 1:
                    self._emit(f"LDA {t.address_expr()}")
                else:
                    self._emit("LDI 0")
                    self._emit(f"SUB {t.address_expr()}")
            # Apply dereferencing if requested
            if t.deref_depth:
                self._emit_dereference_chain(t.deref_depth)
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
            if t.offset is not None:
                self._emit_indexed_symbol_term(term, first_term=False)
            else:
                if term.sign == 1:
                    self._emit(f"ADD {t.address_expr()}")
                else:
                    self._emit(f"SUB {t.address_expr()}")
                if t.deref_depth:
                    raise Mini32Error("Dereferenced term not allowed as follow-up (split expression)")
        else:
            if term.sign == 1:
                self._emit(f"ADI {t.immediate_expr()}")
            else:
                self._emit(f"SUI {t.immediate_expr()}")

    def _emit_dereference_chain(self, depth: int) -> None:
        """Apply one or more pointer dereferences to current A value.
        A holds a base address (or value). For each depth level:
          - Store A into __tmp_addr
          - LPA __tmp_addr (A = mem[mem[__tmp_addr]])
        """
        for _ in range(depth):
            self._emit("STA .__tmp_addr")
            self._emit("LPA .__tmp_addr                ; deref *")

    def _emit_indexed_symbol_term(self, expr_term: ExprTerm, first_term: bool) -> None:
        """Emit code for symbol[offset].

        Heuristic:
          - symbol.size > 1 => direct array: element = mem[ base + offset ]
          - symbol.size == 1 => pointer: element = mem[ mem[symbol] + offset ]

        Dynamic offsets (non-integer) require computing offset, adding base/pointer, storing
        effective address into __tmp_addr and then using LPA to load value.
        """
        term = expr_term.term
        sym = term.symbol  # type: ignore[assignment]
        offset_expr = term.offset or "0"
        sign = expr_term.sign
        tmp_addr = ".__tmp_addr"
        tmp_base = ".__tmp_base"

        # Try parse static integer offset
        static_int: Optional[int] = None
        try:
            static_int = int(offset_expr, 0)
        except Exception:
            static_int = None

        if sym.size > 1:
            # Array semantics
            if static_int is not None:
                # Simple static offset: just load LDA base+offset
                base_expr = f".{sym.name} + {static_int}" if static_int else f".{sym.name}"
                if first_term:
                    if sign == 1:
                        self._emit(f"LDA {base_expr}")
                    else:
                        self._emit("LDI 0")
                        self._emit(f"SUB {base_expr}")
                else:
                    if sign == 1:
                        self._emit(f"ADD {base_expr}")
                    else:
                        self._emit(f"SUB {base_expr}")
                return
            # Dynamic offset: compute base+offset into A then indirect load
            # Strategy: compute offset into A, add base address (as immediate via ADI) then build effective pointer.
            self._emit_compute_simple_expression(offset_expr)
            # Add base address immediate (we know base symbol absolute address is known via its name)
            # We can't ADI with symbolic address; so load base into B via LDA then ADD pattern:
            self._emit(f"ADD .{sym.name}")
            # Store effective address
            self._emit(f"STA {tmp_addr}")
            # Indirect load
            self._emit(f"LPA {tmp_addr}                ; array element load")
        else:
            # Pointer semantics: pointer variable holds address of array
            # Load pointer value
            self._emit(f"LDA .{sym.name}")
            self._emit(f"STA {tmp_base}")
            if static_int is not None and static_int == 0:
                # No offset
                self._emit(f"STA {tmp_addr}")  # reuse A value as base
            else:
                if static_int is not None:
                    # Add constant offset
                    if static_int != 0:
                        self._emit(f"ADI {static_int}")
                else:
                    # Dynamic offset expression: compute into A then add saved base
                    self._emit_compute_simple_expression(offset_expr)
                    self._emit(f"ADD {tmp_base}")
                self._emit(f"STA {tmp_addr}")
            # Now tmp_addr holds effective element address
            self._emit(f"LPA {tmp_addr}                ; pointer element load")

        if sign == -1:
            # Negate A (A = -A)
            self._emit("STA .__tmp_base")  # reuse tmp_base for value
            self._emit("LDI 0")
            self._emit("SUB .__tmp_base")

        # If this is a follow-up term in an expression (not first) and sign was +/- we already produced the value.
        # For follow-up addition/subtraction we needed ADD/SUB sequences, but we turned the term into a standalone value in A.
        # To integrate into ongoing expression (when not first_term), we convert it into ADD/SUB relative to previous A:
        if not first_term:
            # Value of indexed term currently in A. We need to combine with previous accumulator value which we lost.
            # Simpler fallback (limitation): For now, only support indexed term as first term or raise.
            # Proper implementation would require saving previous A, loading term, then performing ADD.
            raise Mini32Error("Indexed terms currently only supported as the first term in an expression or alone")

    def _emit_compute_simple_expression(self, text: str) -> None:
        """Compute a simple + / - expression of literals or memory symbols into A.
        This is a limited helper (no nested brackets)."""
        # Split while keeping delimiters
        tokens: List[str] = []
        cur = []
        for ch in text:
            if ch in "+-":
                if cur:
                    tokens.append(''.join(cur).strip())
                    cur = []
                tokens.append(ch)
            else:
                cur.append(ch)
        if cur:
            tokens.append(''.join(cur).strip())
        first = True
        pending_sign = 1
        for tok in tokens:
            if tok == '+':
                pending_sign = 1
                continue
            if tok == '-':
                pending_sign = -1
                continue
            # term token
            try:
                val = int(tok, 0)
                if first:
                    self._emit(f"LDI {val if pending_sign==1 else -val}")
                else:
                    if pending_sign == 1:
                        self._emit(f"ADI {val}")
                    else:
                        self._emit(f"SUI {val}")
            except Exception:
                # symbol token; resolve local vs global internal name
                sym_ref = self._resolve_symbol_token(tok)
                if first:
                    if pending_sign == 1:
                        self._emit(f"LDA {sym_ref}")
                    else:
                        self._emit("LDI 0")
                        self._emit(f"SUB {sym_ref}")
                else:
                    if pending_sign == 1:
                        self._emit(f"ADD {sym_ref}")
                    else:
                        self._emit(f"SUB {sym_ref}")
            first = False

    def _resolve_symbol_token(self, token: str) -> str:
        """Map a user-level variable name in an offset expression to its internal symbol.

        Preference order:
          1. Exact match of internal name (already contains a dot or unique) -> .token
          2. Current function local (.func.token) if exists
          3. Fallback to .token (may produce assembler error if truly undefined)
        """
        # Gather sets lazily
        var_names = {v.name for v in self.program.vars}
        # If token already exactly matches a var name
        if token in var_names:
            return f".{token}"
        # If current function context and composed name exists
        if self.current_function:
            candidate = f"{self.current_function}.{token}"
            if candidate in var_names:
                return f".{candidate}"
        # Fallback
        return f".{token}"

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

    # --- Peephole Optimization -------------------------------------------------
    def _peephole_optimize(self, lines: List[str]) -> List[str]:
        """Perform local peephole optimizations on the emitted assembly.

        Patterns implemented (conservative, order preserving):
          1. Redundant reload after store:
                STA <addr>; LDA <addr>  -->  STA <addr>
             (Only when no label or blank between and <addr> textual match.)
          2. Store then indirect load via temp address:
                STA .__tmp_addr; LPA .__tmp_addr  -->  STA .__tmp_addr; LAP
             Rationale: LAP already performs stack push of address + load.
          3. Neutral arithmetic removal:
                ADI 0 / SUI 0  --> (removed)
          4. Combine immediate zero + add immediate:
                LDI 0; ADI n  --> LDI n
             (n integer literal)
          5. Remove add/sub zero on memory:
                ADD <addr> where <addr> is a constant zero symbol not currently tracked is skipped (not applied now to avoid risk).

        Additional patterns can be appended easily; we keep this pass simple
        and purely textual with minimal regex to avoid altering semantics.
        """
        optimized: List[str] = []
        i = 0
        # Precompile regexes
        r_sta = re.compile(r"^\s*STA\s+(.+?)\s*(;.*)?$")
        r_lda = re.compile(r"^\s*LDA\s+(.+?)\s*(;.*)?$")
        r_lpa = re.compile(r"^\s*LPA\s+(.+?)\s*(;.*)?$")
        r_adi = re.compile(r"^\s*ADI\s+(-?\d+)\s*(;.*)?$")
        r_sui = re.compile(r"^\s*SUI\s+(-?\d+)\s*(;.*)?$")
        r_ldi = re.compile(r"^\s*LDI\s+(-?\d+)\s*(;.*)?$")
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            # Skip empty lines or labels (ending with ':') unchanged
            if not stripped or stripped.endswith(":") or stripped.startswith(";!") or stripped.startswith(";"):
                optimized.append(line)
                i += 1
                continue

            # Pattern 1: STA X followed immediately by LDA X
            m_sta = r_sta.match(line)
            if m_sta and i + 1 < len(lines):
                next_line = lines[i + 1]
                m_lda = r_lda.match(next_line)
                if m_lda and m_lda.group(1) == m_sta.group(1):
                    # Drop the LDA (comment if any retained via appended comment)
                    optimized.append(line)  # keep STA
                    # Optionally we could merge comments; for simplicity discard redundant LDA line
                    i += 2
                    continue

            # Pattern 2: STA .__tmp_addr; LPA .__tmp_addr -> STA .__tmp_addr; LAP
            if m_sta and m_sta.group(1).strip() == ".__tmp_addr" and i + 1 < len(lines):
                next_line = lines[i + 1]
                m_lpa = r_lpa.match(next_line)
                if m_lpa and m_lpa.group(1).strip() == ".__tmp_addr":
                    # Replace next line with LAP (preserve any trailing comment after LPA)
                    comment = next_line.split(";", 1)[1] if ";" in next_line else ""
                    optimized.append(line)
                    lap_line = "  LAP" + (" ;" + comment if comment else "")
                    optimized.append(lap_line.rstrip())
                    i += 2
                    continue

            # Pattern 4: LDI 0 ; ADI n -> LDI n
            m_ldi = r_ldi.match(line)
            if m_ldi and m_ldi.group(1) == '0' and i + 1 < len(lines):
                m_adi_next = r_adi.match(lines[i + 1])
                if m_adi_next:
                    n_val = m_adi_next.group(1)
                    optimized.append(re.sub(r"LDI\s+0", f"LDI {n_val}", line))
                    i += 2
                    continue

            # Pattern 3: Remove ADI 0 / SUI 0
            m_adi = r_adi.match(line)
            if m_adi and m_adi.group(1) == '0':
                i += 1
                continue
            m_sui = r_sui.match(line)
            if m_sui and m_sui.group(1) == '0':
                i += 1
                continue

            optimized.append(line)
            i += 1

        return optimized


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
