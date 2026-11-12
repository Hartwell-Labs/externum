"""Externum v4 — Bytecode compiler: AST → EXBC (Externum Bytecode).

EXBC is a stack-based bytecode format for the Externum VM.  Each instruction
is a 1-byte opcode followed by operand bytes depending on the instruction.

Opcodes:
  NOP=0x00, HALT=0x01, RETURN=0x02, YIELD_VAL=0x03,
  LOAD_CONST=0x10, LOAD_VAR=0x11, STORE_VAR=0x12, STORE_MUT=0x13,
  LOAD_GLOBAL=0x14, STORE_GLOBAL=0x15,
  POP=0x18, DUP=0x19, SWAP=0x1A,
  ADD=0x20, SUB=0x21, MUL=0x22, DIV=0x23, MOD=0x24, POW=0x25, FLOOR_DIV=0x26,
  NEG=0x27, NOT=0x28, BITAND=0x29, BITOR=0x2A, BITXOR=0x2B, BITNOT=0x2C,
  LSHIFT=0x2D, RSHIFT=0x2E,
  EQ=0x30, NEQ=0x31, LT=0x32, GT=0x33, LTE=0x34, GTE=0x35,
  AND=0x38, OR=0x39, IN_OP=0x3A, IS_OP=0x3B,
  JUMP=0x40, JUMP_IF=0x41, JUMP_IF_NOT=0x42, JUMP_IF_POP=0x43,
  CALL=0x50, CALL_KW=0x51, CALL_STAR=0x52, CALL_DSTAR=0x53,
  MAKE_FN=0x54, MAKE_CLASS=0x55,
  GET_ATTR=0x60, SET_ATTR=0x61, GET_INDEX=0x62, SET_INDEX=0x63,
  MAKE_LIST=0x70, MAKE_DICT=0x71, MAKE_TUPLE=0x72, MAKE_SET=0=0x73,
  UNPACK=0x74, SLICE=0x75,
  FOR_ITER=0x80, FOR_NEXT=0x81, LOOP_CONTINUE=0x82, LOOP_BREAK=0x83,
  TRY_BEGIN=0x90, TRY_END=0x91, RAISE=0x92, POP_EXCEPT=0x93,
  IMPORT=0xA0, IMPORT_FROM=0xA1, IMPORT_AS=0xA2,

  ALLOC=0xB0, FREE=0xB1, LOAD_DEREF=0xB2, STORE_DEREF=0xB3,
  SPAWN=0xB4, CHAN_CREATE=0xB5, CHAN_SEND=0xB6, CHAN_RECV=0xB7,
  MATCH_BEGIN=0xB8, MATCH_CASE=0xB9, MATCH_FAIL=0xBA,

  MAKE_STRUCT=0xC0, STRUCT_INIT=0xC1, GET_FIELD=0xC2, SET_FIELD=0xC3,
  MAKE_ENUM=0xC3, ENUM_VARIANT=0xC4, ENUM_IS=0xC5, ENUM_UNWRAP=0xC6,
  PIPE_CALL=0xC7, AWAIT_OP=0xC8, ASYNC_BEGIN=0xC9, ASYNC_END=0xCA,
  DEFER_BEGIN=0xCB, DEFER_END=0xCC,
  OPTION_SOME=0xCD, OPTION_NONE=0xCE, OPTION_UNWRAP=0xCF,
  RESULT_OK=0xD0, RESULT_ERR=0xD1, RESULT_UNWRAP=0xD2,
  COMPTIME_EVAL=0xD3, TYPE_CHECK=0xD4,
  ASSERT_EQ=0xE0, ASSERT_NE=0xE1, PANIC=0xE2, UNREACHABLE=0xE3,
  TRACE_OP=0xE4, DBG_OP=0xE5,
  MAKE_GENERATOR=0xE6, GEN_NEXT=0xE7, GEN_SEND=0xE8,
  # Intrinsics (VM-provided builtins)
  INTRINSIC=0xF0,
"""

import ast as _pyast
import struct
from dataclasses import dataclass, field
from typing import Any

from .parser import ASTNode

# ── opcodes ──────────────────────────────────────────────────────────
NOP = 0x00
HALT = 0x01
RETURN = 0x02
YIELD_VAL = 0x03

LOAD_CONST = 0x10
LOAD_VAR = 0x11
STORE_VAR = 0x12
STORE_MUT = 0x13
LOAD_GLOBAL = 0x14
STORE_GLOBAL = 0x15

POP = 0x18
DUP = 0x19
SWAP = 0x1A

ADD = 0x20
SUB = 0x21
MUL = 0x22
DIV = 0x23
MOD = 0x24
POW = 0x25
FLOOR_DIV = 0x26
NEG = 0x27
NOT = 0x28
BITAND = 0x29
BITOR = 0x2A
BITXOR = 0x2B
BITNOT = 0x2C
LSHIFT = 0x2D
RSHIFT = 0x2E

EQ = 0x30
NEQ = 0x31
LT = 0x32
GT = 0x33
LTE = 0x34
GTE = 0x35
AND = 0x38
OR = 0x39
IN_OP = 0x3A
IS_OP = 0x3B

JUMP = 0x40
JUMP_IF = 0x41
JUMP_IF_NOT = 0x42
JUMP_IF_POP = 0x43

CALL = 0x50
CALL_KW = 0x51
MAKE_FN = 0x54
MAKE_CLASS = 0x55
CALL_EX = 0x56  # fn, args-list, kwargs-dict  (star/kwargs aware call)

GET_ATTR = 0x60
SET_ATTR = 0x61
GET_INDEX = 0x62
SET_INDEX = 0x63
DEL_INDEX = 0x64
DEL_ATTR = 0x65
DEL_NAME = 0x66

MAKE_LIST = 0x70
MAKE_DICT = 0x71
MAKE_TUPLE = 0x72
MAKE_SET = 0x73
UNPACK = 0x74
SLICE = 0x75
LIST_APPEND = 0x76  # container, value -> container
LIST_EXTEND = 0x77  # container, iterable -> container
SET_ADD = 0x78  # container, value -> container
DICT_SET = 0x79  # container, key, value -> container
DICT_UPDATE = 0x7A  # container, mapping -> container
LIST_TO_TUPLE = 0x7B

FOR_ITER = 0x80
LOOP_BREAK = 0x83

TRY_BEGIN = 0x90
TRY_END = 0x91
RAISE_OP = 0x92
POP_EXCEPT = 0x93

IMPORT = 0xA0

ALLOC = 0xB0
FREE = 0xB1
LOAD_DEREF = 0xB2
STORE_DEREF = 0xB3
SPAWN = 0xB4
CHAN_CREATE = 0xB5
CHAN_SEND = 0xB6
CHAN_RECV = 0xB7

MAKE_STRUCT = 0xC0
STRUCT_INIT = 0xC1
GET_FIELD = 0xC2
SET_FIELD = 0xC3
MAKE_ENUM = 0xC4
ENUM_VARIANT = 0xC5
ENUM_IS = 0xC6
ENUM_UNWRAP = 0xC7
PIPE_CALL = 0xC8
AWAIT_OP = 0xC9
DEFER_PUSH = 0xCA

OPTION_SOME = 0xD0
OPTION_NONE = 0xD1
RESULT_OK = 0xD2
RESULT_ERR = 0xD3

ASSERT_EQ = 0xE0
PANIC = 0xE2
UNREACHABLE = 0xE3
TRACE_OP = 0xE4
DBG_OP = 0xE5

INTRINSIC = 0xF0
INTRINSIC_EX = 0xF1  # intrinsic with keyword arguments (print sep/end)

# ── helpers ──────────────────────────────────────────────────────────


@dataclass
class BytecodeFunction:
    """A compiled function: name, bytecode, constants, inner functions."""

    name: str
    arg_names: list[str] = field(default_factory=list)
    kw_defaults: dict[str, Any] = field(default_factory=dict)
    bytecode: bytearray = field(default_factory=bytearray)
    constants: list[Any] = field(default_factory=list)
    inner_fns: list["BytecodeFunction"] = field(default_factory=list)
    is_async: bool = False
    is_generator: bool = False
    upvalues: list[str] = field(default_factory=list)
    line_table: dict[int, int] = field(default_factory=dict)  # bytecode_offset -> line


@dataclass
class BytecodeModule:
    """A compiled module: top-level bytecode, constants, functions."""

    name: str
    bytecode: bytearray = field(default_factory=bytearray)
    constants: list[Any] = field(default_factory=list)
    functions: list[BytecodeFunction] = field(default_factory=list)
    structs: dict[str, dict] = field(default_factory=dict)
    enums: dict[str, dict] = field(default_factory=dict)
    traits: dict[str, dict] = field(default_factory=dict)
    imports: list[str] = field(default_factory=list)
    line_table: dict[int, int] = field(default_factory=dict)  # bytecode_offset -> source line


class BytecodeCompiler:
    """Compiles Externum AST → EXBC bytecode."""

    def __init__(self, ast: list[ASTNode], module_name: str = "<main>"):
        self.ast = ast
        self.module = BytecodeModule(name=module_name)
        self._current_fn: BytecodeFunction | None = None
        self._scope_stack: list[dict[str, int]] = [{}]  # name -> stack depth
        self._const_pool: list[Any] = self.module.constants
        self._loop_stack: list[list[int]] = []  # stack of (break_patches)
        self._loop_start_stack: list[int] = []  # stack of loop body start offsets
        self._defer_stack: list[list[int]] = []  # stack of defer instruction offsets
        self._try_depth = 0
        self._line = 1
        self._comp_counter = 0
        # Statement lists that must run before leaving a try/finally block
        # (return/break/continue inside `try`). Innermost last.
        self._finally_stack: list[list[ASTNode]] = []

    # ── public API ──────────────────────────────────────────────────
    def compile(self) -> BytecodeModule:
        for node in self.ast:
            self._compile_stmt(node)
        self._emit(HALT)
        return self.module

    # ── bytecode emission ──────────────────────────────────────────
    def _emit(self, op: int, *args: int):
        """Emit opcode + u16 operands (consistent with VM _read_u16)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        for a in args:
            target.extend(struct.pack(">H", a & 0xFFFF))
        if self._current_fn:
            self._current_fn.line_table[offset] = self._line
        else:
            self.module.line_table[offset] = self._line
        return offset

    def _emit1(self, op: int, byte: int):
        """Emit opcode + single u8 byte (for CALL argc, INTRINSIC argc, MAKE_STRUCT fields, etc)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        target.append(byte & 0xFF)
        if self._current_fn:
            self._current_fn.line_table[offset] = self._line
        else:
            self.module.line_table[offset] = self._line
        return offset

    def _emit2(self, op: int, idx: int, byte: int):
        """Emit opcode + u16 index + u8 count (for INTRINSIC, MAKE_STRUCT, MAKE_ENUM)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        target.extend(struct.pack(">H", idx & 0xFFFF))
        target.append(byte & 0xFF)
        if self._current_fn:
            self._current_fn.line_table[offset] = self._line
        else:
            self.module.line_table[offset] = self._line
        return offset

    def _emit3(self, op: int, idx: int, b1: int, b2: int):
        """Emit opcode + u16 index + two u8 bytes (INTRINSIC_EX)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        target.append(op & 0xFF)
        target.extend(struct.pack(">H", idx & 0xFFFF))
        target.append(b1 & 0xFF)
        target.append(b2 & 0xFF)
        return None

    def _emit_jump(self, op: int) -> int:
        """Emit a jump instruction and return the offset of the operand (for patching)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        target.extend(b"\x00\x00")  # placeholder for u16
        return offset + 1

    def _patch_jump(self, jump_offset: int):
        """Patch a jump instruction to point to the current position."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        dest = len(target)
        target[jump_offset] = (dest >> 8) & 0xFF
        target[jump_offset + 1] = dest & 0xFF

    def _patch_jump_to(self, jump_offset: int, target_pos: int):
        """Patch a jump instruction to point to a specific position."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        target[jump_offset] = (target_pos >> 8) & 0xFF
        target[jump_offset + 1] = target_pos & 0xFF

    def _add_const(self, value: Any) -> int:
        pool = self._current_fn.constants if self._current_fn else self._const_pool
        for i, c in enumerate(pool):
            if c == value and type(c) is type(value):
                return i
        pool.append(value)
        return len(pool) - 1

    def _enter_scope(self):
        self._scope_stack.append({})

    def _exit_scope(self):
        self._scope_stack.pop()

    def _resolve(self, name: str) -> tuple[str, int]:
        """Resolve a variable name. Returns ('local', depth) or ('global', 0)."""
        for depth in range(len(self._scope_stack) - 1, -1, -1):
            if name in self._scope_stack[depth]:
                return "local", depth
        return "global", 0

    def _current_depth(self) -> int:
        return len(self._scope_stack) - 1

    def _declare_var(self, name: str, depth: int | None = None):
        if depth is None:
            depth = self._current_depth()
        self._scope_stack[depth][name] = len(self._scope_stack[depth])

    # ── statements ─────────────────────────────────────────────────
    def _compile_stmt(self, node: ASTNode):
        if node is None:
            return
        t = node.type
        if t == "NEWLINE" or t in ("INDENT", "DEDENT"):
            return
        # Track source line for the line_table (diagnostics).
        if getattr(node, "line", 0):
            self._line = node.line
        method = getattr(self, f"_stmt_{t}", None)
        if method:
            method(node)
        elif t == "EXPRESSION" or t == "CALL":
            self._compile_expr(node)
            self._emit(POP)
        elif t == "DEL":
            self._stmt_DEL(node)
        else:
            # generic: compile expression children
            for child in node.children:
                if child and hasattr(child, "type"):
                    self._compile_stmt(child)

    def _stmt_ASSIGN(self, node: ASTNode):
        if node.value:  # tuple unpacking: "a, b = expr"
            names = [n.strip() for n in node.value.split(",") if n.strip()]
            rhs = node.children[0] if node.children else ASTNode("IDENTIFIER", value="None")
            text = str(rhs.value or "")
            items = self._parse_list_items(text) if ("," in text and rhs.type in ("EXPRESSION", "TUPLE")) else None
            if items and len(items) > 1:
                # `a, b = 1, 2` — the RHS arrives as the verbatim text "1, 2".
                for item in items:
                    self._compile_simple_expr(item.strip())
                self._emit(MAKE_TUPLE, len(items))
            else:
                self._compile_expr(rhs)
            self._emit(UNPACK, len(names))
            for name in reversed(names):
                kind, _ = self._resolve(name)
                idx = self._add_const(name)
                if kind == "global":
                    self._emit(STORE_GLOBAL, idx)
                else:
                    self._emit(STORE_VAR, idx)
                self._declare_var(name)
            return
        if not node.children:
            return
        target = node.children[0]
        value = node.children[1] if len(node.children) > 1 else None
        if target.type == "INDEX":
            # obj[i] = val — evaluate receiver and index *before* the value so
            # SET_INDEX sees (obj, idx, val). The old order evaluated the value
            # first, so `d["k"] = 1; d["k"] += 1` wrote into the wrong slot.
            inner = str(target.value)
            bracket = inner.find("[")
            if bracket > 0:
                self._compile_simple_expr(inner[:bracket].strip())
                self._compile_simple_expr(inner[bracket + 1 : -1].strip())
                if value is not None:
                    self._compile_expr(value)
                else:
                    self._emit(LOAD_CONST, self._add_const(None))
                self._emit(SET_INDEX)
                return
        if value is not None:
            self._compile_expr(value)
        else:
            self._emit(LOAD_CONST, self._add_const(None))
        if target.type == "IDENTIFIER":
            name = target.value
            kind, _ = self._resolve(name)
            idx = self._add_const(name)
            if kind == "global" or self._current_fn is None:
                self._emit(STORE_GLOBAL, idx)
            else:
                self._emit(STORE_VAR, idx)
            self._declare_var(name)
        elif target.type == "DOT":
            # obj.attr = val
            parts = target.value.rsplit(".", 1)
            if len(parts) == 2:
                self._compile_name(parts[0])
                # val is already on stack from above, swap
                self._emit(SWAP)
                attr_idx = self._add_const(parts[1])
                self._emit(SET_ATTR, attr_idx)
        elif target.type == "INDEX":
            # Unparseable index target: drop the already-pushed value instead
            # of leaving the stack unbalanced.
            self._emit(POP)
        elif target.type == "DEREF":
            if target.children:
                self._compile_expr(target.children[0])
            self._emit(STORE_DEREF)

    def _stmt_AUG_ASSIGN(self, node: ASTNode):
        target = node.children[0] if node.children else None
        val = node.children[1] if len(node.children) > 1 else None
        op_node = node.children[2] if len(node.children) > 2 else None
        op = str(op_node.value) if op_node is not None else "+"
        # The parser reports augmented operators with their "=" suffix
        # ("+=", "**=", "//=", "<<=").  Strip it so the op_map lookup
        # sees the base binary operator (issue #21).
        base_op = op[:-1] if op.endswith("=") and len(op) > 1 else op
        if target is None:
            return
        if target.type == "IDENTIFIER":
            name = target.value
            self._compile_name(name)
            if val:
                self._compile_expr(val)
            else:
                self._emit(LOAD_CONST, self._add_const(None))
            op_map = {
                "+": ADD,
                "-": SUB,
                "*": MUL,
                "/": DIV,
                "%": MOD,
                "**": POW,
                "//": FLOOR_DIV,
                "&": BITAND,
                "|": BITOR,
                "^": BITXOR,
                "<<": LSHIFT,
                ">>": RSHIFT,
            }
            self._emit(op_map.get(base_op, ADD))
            kind, _ = self._resolve(name)
            idx = self._add_const(name)
            # Module top level has no locals frame: mirror _stmt_ASSIGN and
            # _compile_name, which use the global slot when not inside a
            # function.  Storing to a local here wrote into a frame nothing
            # ever reads (silent infinite loops — issue #21).
            if kind == "global" or self._current_fn is None:
                self._emit(STORE_GLOBAL, idx)
            else:
                self._emit(STORE_VAR, idx)
            self._declare_var(name)
        else:
            # obj.attr += v  /  x[i] += v  /  *p += v: desugar into
            # "target = target <op> v" so the ASSIGN paths (SET_ATTR /
            # SET_INDEX / STORE_DEREF) handle the store.  Previously these
            # targets emitted no store at all (or corrupted the stack).
            rhs = ASTNode(
                "BINOP",
                children=[
                    target,
                    ASTNode("OP", value=base_op),
                    val if val is not None else ASTNode("NUMBER", value=0),
                ],
            )
            self._stmt_ASSIGN(ASTNode("ASSIGN", children=[target, rhs]))

    def _stmt_FUNCTION(self, node: ASTNode):
        self._compile_function_def(node)

    def _compile_function_def(self, node: ASTNode, is_async: bool = False):
        name = node.value
        params_node = node.children[0] if node.children and node.children[0].type == "PARAMS" else None
        body_nodes = node.children[1:] if params_node else node.children

        arg_names = []
        kw_defaults = {}
        if params_node:
            # Parse defaults from the PARAMS string value (e.g. "name='world'")
            params_str = str(params_node.value) if params_node.value else ""
            defaults = {}
            if params_str:
                for part in self._parse_list_items(params_str):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        defaults[k.strip()] = self._eval_const(v.strip())
            for p in params_node.children or []:
                pname = p.value
                pname = pname.lstrip("*")
                if pname in defaults:
                    kw_defaults[pname] = defaults[pname]
                arg_names.append(pname)

        fn = BytecodeFunction(
            name=name,
            arg_names=arg_names,
            kw_defaults=kw_defaults,
            is_async=is_async,
        )
        old_fn = self._current_fn
        self._current_fn = fn
        old_scope = self._scope_stack
        self._scope_stack = [{}]
        for a in arg_names:
            self._declare_var(a)

        old_line = self._line
        old_saw_yield = getattr(self, "_saw_yield", False)
        self._saw_yield = False
        if getattr(node, "line", 0):
            self._line = node.line
        for child in body_nodes:
            self._compile_stmt(child)
        fn.is_generator = self._saw_yield
        self._saw_yield = old_saw_yield
        self._emit(RETURN)
        self._line = old_line

        self._current_fn = old_fn
        self._scope_stack = old_scope

        # Emit MAKE_FN at the call site
        fn_idx = len(self.module.functions)
        self.module.functions.append(fn)
        self._emit(MAKE_FN, fn_idx)
        name_idx = self._add_const(name)
        # At module level, store as global so recursive calls can find it
        if self._current_fn is None:
            self._emit(STORE_GLOBAL, name_idx)
        else:
            self._emit(STORE_VAR, name_idx)
        self._declare_var(name)

    def _stmt_CLASS(self, node: ASTNode):
        name = node.value
        bases = ""
        if node.children and node.children[0].type == "PARAMS":
            bases = str(node.children[0].value or "")
        body = node.children[1:] if node.children and node.children[0].type == "PARAMS" else node.children

        # Compile each method as a function; collect plain class attributes too
        methods = []
        attributes = []
        for child in body:
            if child.type == "FUNCTION":
                self._compile_function_def(child)
                methods.append(child.value)
            elif child.type in ("ASSIGN", "CONST") and child.value:
                attributes.append(child)

        # Base classes are pushed first so MAKE_CLASS can link the MRO.
        base_names = [b.strip().split("[")[0].strip() for b in bases.split(",") if b.strip()]
        for base in base_names:
            self._compile_name(base)
        self._emit2(MAKE_CLASS, self._add_const(name), len(base_names))

        # Store class name
        idx = self._add_const(name)
        # At module level the class lives in VM globals: STORE_VAR at top
        # level lands in the frame's `locals_` dict, which a function body
        # cannot see ("undefined global `X`"). STORE_GLOBAL matches the
        # function path above and the Python backend's semantics.
        if self._current_fn is None:
            self._emit(STORE_GLOBAL, idx)
        else:
            self._emit(STORE_VAR, idx)
        self._declare_var(name)

        # Class-level attributes (evaluated once, at class creation)
        for attr in attributes:
            target = attr.children[0] if attr.children else None
            value = attr.children[1] if len(attr.children) > 1 else None
            aname = str(target.value) if target is not None else None
            if not aname:
                continue
            self._compile_name(name)
            if value is not None:
                self._compile_expr(value)
            else:
                self._emit(LOAD_CONST, self._add_const(None))
            self._emit(SET_ATTR, self._add_const(aname))

        # Now set each method on the class
        for mname in methods:
            self._compile_name(name)  # push class
            self._compile_name(mname)  # push method fn
            self._emit(SET_ATTR, self._add_const(mname))

    def _stmt_IF(self, node: ASTNode):
        if not node.children:
            return
        self._compile_expr(node.children[0])
        end_patches = []
        jf = self._emit_jump(JUMP_IF_NOT)
        # if body
        for child in node.children[1:]:
            if child.type in ("ELIF", "ELSE"):
                break
            self._compile_stmt(child)
        end_patches.append(self._emit_jump(JUMP))
        self._patch_jump(jf)
        for child in node.children[1:]:
            if child.type == "ELIF":
                self._compile_expr(child.children[0])
                jf2 = self._emit_jump(JUMP_IF_NOT)
                for sub in child.children[1:]:
                    if sub.type in ("ELIF", "ELSE"):
                        break
                    self._compile_stmt(sub)
                end_patches.append(self._emit_jump(JUMP))
                self._patch_jump(jf2)
            elif child.type == "ELSE":
                for sub in child.children:
                    self._compile_stmt(sub)
        for p in end_patches:
            self._patch_jump(p)

    def _stmt_FOR(self, node: ASTNode):
        var = node.value or "_"
        iterable = None
        body = list(node.children)
        if node.children and node.children[0].type == "ITERABLE":
            iterable = node.children[0].children[0] if node.children[0].children else None
            body = node.children[1:]

        # push iterator
        if iterable:
            self._compile_expr(iterable)
        else:
            self._emit(LOAD_CONST, self._add_const(range(0)))

        loop_start = len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)
        for_offset = self._emit_jump(FOR_ITER)

        # Handle tuple unpacking: for i, v in ...
        if "," in str(var):
            names = [n.strip() for n in str(var).split(",") if n.strip()]
            # Store to temp, then unpack
            tmp = "__for_tmp__"
            tmp_idx = self._add_const(tmp)
            self._emit(STORE_VAR, tmp_idx)
            self._declare_var(tmp)
            # Load and unpack
            self._compile_name(tmp)
            self._emit(UNPACK, len(names))
            for name in reversed(names):
                self._declare_var(name)
                idx = self._add_const(name)
                self._emit(STORE_VAR, idx)
        else:
            self._declare_var(var)
            var_idx = self._add_const(var)
            self._emit(STORE_VAR, var_idx)

        self._loop_stack.append([])
        self._loop_start_stack.append(loop_start)
        for child in body:
            self._compile_stmt(child)
        # jump back
        jump_off = self._emit_jump(JUMP)
        self._patch_jump_to(jump_off, loop_start)

        self._patch_jump(for_offset)
        # patch breaks
        self._loop_start_stack.pop()
        for bp in self._loop_stack.pop():
            self._patch_jump(bp)

    def _stmt_WHILE(self, node: ASTNode):
        body_start = len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)
        if node.children:
            self._compile_expr(node.children[0])
        jf = self._emit_jump(JUMP_IF_NOT)

        self._loop_stack.append([])
        self._loop_start_stack.append(body_start)
        for child in node.children[1:]:
            self._compile_stmt(child)
        jump_off = self._emit_jump(JUMP)
        self._patch_jump_to(jump_off, body_start)

        self._patch_jump(jf)
        self._loop_start_stack.pop()
        for bp in self._loop_stack.pop():
            self._patch_jump(bp)

    def _stmt_LOOP(self, node: ASTNode):
        """loop: ... break val — infinite loop with value return."""
        loop_start = len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)
        self._loop_stack.append([])
        self._loop_start_stack.append(loop_start)
        for child in node.children:
            self._compile_stmt(child)
        jump_off = self._emit_jump(JUMP)
        self._patch_jump_to(jump_off, loop_start)
        self._loop_start_stack.pop()
        for bp in self._loop_stack.pop():
            self._patch_jump(bp)

    def _stmt_TRY(self, node: ASTNode):
        body = [c for c in node.children if c.type not in ("EXCEPT", "TRY_ELSE", "FINALLY")]
        handlers = [c for c in node.children if c.type == "EXCEPT"]
        else_block = next((c for c in node.children if c.type == "TRY_ELSE"), None)
        finally_block = next((c for c in node.children if c.type == "FINALLY"), None)

        try_start = self._emit_jump(TRY_BEGIN)
        self._finally_stack.append(finally_block.children if finally_block is not None else [])
        for child in body:
            self._compile_stmt(child)
        self._finally_stack.pop()
        self._emit(TRY_END)
        if else_block is not None:
            for sub in else_block.children:
                self._compile_stmt(sub)
        end_patches = [self._emit_jump(JUMP)]

        # Handler chain: the VM unwinds with the exception object on the stack.
        self._patch_jump(try_start)
        for handler in handlers:
            cond = next((c for c in handler.children if c.type == "COND"), None)
            as_var = next((c for c in handler.children if c.type == "AS_VAR"), None)
            hbody = [c for c in handler.children if c.type not in ("COND", "AS_VAR")]
            if cond is not None and cond.children:
                self._compile_exception_test(str(cond.children[0].value))
                skip = self._emit_jump(JUMP_IF_NOT)
            else:
                skip = None
            if as_var is not None:
                self._store_var(str(as_var.value))
            else:
                self._emit(POP)
            self._finally_stack.append(finally_block.children if finally_block is not None else [])
            for sub in hbody:
                self._compile_stmt(sub)
            self._finally_stack.pop()
            end_patches.append(self._emit_jump(JUMP))
            if skip is not None:
                self._patch_jump(skip)
        # No handler matched: re-raise the exception still sitting on the stack.
        self._emit(RAISE_OP)

        for p in end_patches:
            self._patch_jump(p)
        if finally_block is not None:
            for sub in finally_block.children:
                self._compile_stmt(sub)

    def _compile_exception_test(self, type_text: str):
        """Stack: [exc] → [exc, bool] — does exc match the except clause type?"""
        names = [n.strip() for n in type_text.strip().strip("()").split(",") if n.strip()]
        self._emit(DUP)
        self._emit2(INTRINSIC, 6, 1)  # type(exc) -> class name string in the VM
        self._emit(
            LOAD_CONST, self._add_const(tuple(names) if len(names) > 1 else (names[0] if names else "Exception"))
        )
        self._emit(IN_OP)

    def _emit_pending_finalizers(self):
        for block in reversed(self._finally_stack):
            for stmt in block:
                self._compile_stmt(stmt)

    def _stmt_RETURN(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        else:
            self._emit(LOAD_CONST, self._add_const(None))
        self._emit_pending_finalizers()
        self._emit(RETURN)

    def _stmt_BREAK(self, node: ASTNode):
        self._emit_pending_finalizers()
        jf = self._emit_jump(LOOP_BREAK)
        if self._loop_stack:
            self._loop_stack[-1].append(jf)

    def _stmt_CONTINUE(self, node: ASTNode):
        self._emit_pending_finalizers()
        if self._loop_start_stack:
            jf = self._emit_jump(JUMP)
            self._patch_jump_to(jf, self._loop_start_stack[-1])

    def _stmt_PASS(self, node: ASTNode):
        self._emit(NOP)

    def _stmt_DEL(self, node: ASTNode):
        """del name / del obj.attr / del obj[i]"""
        if not node.children:
            return
        target = node.children[0]
        if target.type == "INDEX":
            inner = str(target.value)
            bracket = inner.find("[")
            if bracket > 0:
                self._compile_simple_expr(inner[:bracket].strip())
                self._compile_simple_expr(inner[bracket + 1 : -1].strip())
                self._emit(DEL_INDEX)
                return
        elif target.type == "DOT":
            parts = str(target.value).rsplit(".", 1)
            if len(parts) == 2:
                self._compile_simple_expr(parts[0])
                self._emit(DEL_ATTR, self._add_const(parts[1]))
                return
        elif target.type == "IDENTIFIER":
            self._emit(DEL_NAME, self._add_const(str(target.value)))
            return
        self._compile_expr(target)
        self._emit(POP)

    def _stmt_IMPORT(self, node: ASTNode):
        idx = self._add_const(node.value)
        self._emit(IMPORT, idx)

    def _stmt_RAISE(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        self._emit(RAISE_OP)

    def _stmt_ASSERT(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
            self._emit(ASSERT_EQ)  # simplified: just assert truthiness

    def _stmt_TRAIT(self, node: ASTNode):
        name = node.value
        methods = []
        for child in node.children:
            if child.type == "FUNCTION":
                methods.append(child.value)
        self.module.traits[name] = {"methods": methods}

    def _stmt_IMPL(self, node: ASTNode):
        # Store impl metadata — runtime handles dispatch
        pass

    def _stmt_MATCH(self, node: ASTNode):
        """match expr: case pattern: body — compiled as if/elif chain."""
        if not node.children:
            return
        self._compile_expr(node.children[0])
        subject_name = "__match_subject__"
        idx = self._add_const(subject_name)
        self._emit(STORE_VAR, idx)
        self._declare_var(subject_name)

        end_patches = []
        for child in node.children[1:]:
            if child.type != "CASE":
                continue
            pattern = child.children[0].value if child.children else "_"
            guard = next((c for c in child.children[1:] if c.type == "GUARD"), None)
            body = [c for c in child.children[1:] if c.type != "GUARD"]
            pat = str(pattern).strip()
            skip = None
            bindings: list[str] = []

            if pat in ("_", ""):
                pass  # wildcard: always matches
            elif pat.isidentifier() and pat not in ("True", "False", "None"):
                # binding pattern: `case n:` binds the subject
                self._compile_name(subject_name)
                self._store_var(pat)
                bindings.append(pat)
            elif pat.startswith(("[", "(")) and pat.endswith(("]", ")")):
                # destructuring: `case [a, b]:`
                inner = pat[1:-1]
                names = [n.strip() for n in inner.split(",") if n.strip()]
                self._compile_name(subject_name)
                self._emit(UNPACK, len(names))
                for name in reversed(names):
                    self._store_var(name)
                    bindings.append(name)
            else:
                # literal / alternation: `case 1:` or `case "a" | "b":`
                alternatives = []
                for alt in (a.strip() for a in pat.split("|")):
                    if not alt:
                        continue
                    alt_val = alt
                    try:
                        alt_val = int(alt)
                    except (ValueError, TypeError):
                        try:
                            alt_val = float(alt)
                        except (ValueError, TypeError):
                            if len(alt) >= 2 and alt[0] == alt[-1] and alt[0] in ('"', "'"):
                                alt_val = alt[1:-1]
                    alternatives.append(alt_val)
                self._compile_name(subject_name)
                self._emit(DUP)
                self._emit(
                    LOAD_CONST,
                    self._add_const(tuple(alternatives) if alternatives else (pat,)),
                )
                self._emit(IN_OP)
                skip = self._emit_jump(JUMP_IF_NOT)
                self._emit(POP)  # drop the duplicated subject

            guard_skip = None
            if guard is not None and guard.children:
                self._compile_expr(guard.children[0])
                guard_skip = self._emit_jump(JUMP_IF_NOT)

            for sub in body:
                self._compile_stmt(sub)
            end_patches.append(self._emit_jump(JUMP))
            if guard_skip is not None:
                self._patch_jump(guard_skip)
            if skip is not None:
                self._patch_jump(skip)
        for p in end_patches:
            self._patch_jump(p)

    def _stmt_STRUCT(self, node: ASTNode):
        name = node.value
        fields = []
        for child in node.children:
            if hasattr(child, "value"):
                fields.append(child.value.split(":")[0].strip() if ":" in str(child.value) else str(child.value))
        self.module.structs[name] = {"fields": fields}
        # Pass the real field names so instances expose `P.x`, not `P.field0`.
        self._emit2(MAKE_STRUCT, self._add_const((name, tuple(fields))), len(fields))
        self._store_var(name)

    def _stmt_ENUM(self, node: ASTNode):
        name = node.value
        variants = {}
        for child in node.children:
            vname = child.value if hasattr(child, "value") else "Unknown"
            variants[vname] = []
        self.module.enums[name] = {"variants": variants}
        self._emit2(MAKE_ENUM, self._add_const((name, tuple(variants))), len(variants))
        self._store_var(name)

    def _stmt_CONST(self, node: ASTNode):
        if node.children and len(node.children) >= 1:
            name = node.value
            self._compile_expr(node.children[0])
            idx = self._add_const(name)
            if self._current_fn is None:
                self._emit(STORE_GLOBAL, idx)
            else:
                self._emit(STORE_VAR, idx)
            self._declare_var(name)

    def _stmt_STATIC(self, node: ASTNode):
        self._stmt_CONST(node)  # similar semantics in bytecode

    def _stmt_DEFER(self, node: ASTNode):
        """defer: body — push deferred expressions."""
        # In bytecode we store the function index for deferred code
        fn = BytecodeFunction(name="<defer>", arg_names=[])
        old_fn = self._current_fn
        self._current_fn = fn
        for child in node.children:
            self._compile_stmt(child)
        self._emit(RETURN)
        self._current_fn = old_fn
        fn_idx = len(self.module.functions)
        self.module.functions.append(fn)
        self._emit(DEFER_PUSH, fn_idx)

    def _stmt_YIELD(self, node: ASTNode):
        self._saw_yield = True
        if node.children:
            self._compile_expr(node.children[0])
        self._emit(YIELD_VAL)

    def _stmt_WITH(self, node: ASTNode):
        """with expr as var, ...: body — bind each context and close it after."""
        raw = str(node.value or "")
        items = []
        for part in self._parse_list_items(raw) if raw else []:
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                expr, var = part.rsplit(" as ", 1)
                items.append((expr.strip(), var.strip()))
            else:
                items.append((part, None))
        bound = []
        for i, (expr, var) in enumerate(items):
            if var is None:
                var = f"__with{i}__"
            self._compile_simple_expr(expr)
            self._store_var(var)
            bound.append(var)
        for child in node.children:
            self._compile_stmt(child)
        for var in reversed(bound):
            self._compile_name(var)
            self._emit(GET_ATTR, self._add_const("close"))
            self._emit1(CALL, 0)
            self._emit(POP)

    def _stmt_GLOBAL(self, node: ASTNode):
        pass  # already handled by scope resolution

    def _stmt_NONLOCAL(self, node: ASTNode):
        pass

    # ── expressions ────────────────────────────────────────────────
    def _compile_expr(self, node: ASTNode):
        if node is None:
            self._emit(LOAD_CONST, self._add_const(None))
            return
        t = node.type
        method = getattr(self, f"_expr_{t}", None)
        if method:
            method(node)
        else:
            # fallback for string-rendered expressions
            self._compile_simple_expr(str(node.value) if node.value else "None")

    def _expr_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_BINARY_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_OCTAL_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_HEX_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_HEX_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_CHAR(self, node: ASTNode):
        val = node.value
        if len(val) == 3 and val[0] == "'" and val[-1] == "'":
            val = val[1:-1]
            if val.startswith("\\"):
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", "'": "'"}
                val = escape_map.get(val[1], val[1])
        self._emit(LOAD_CONST, self._add_const(val))

    def _expr_STRING(self, node: ASTNode):
        val = node.value
        # Plain/triple/raw strings: let Python decode escapes (\n, \t, \\, …).
        if isinstance(val, str) and val and val[0] in "'\"":
            try:
                self._emit(LOAD_CONST, self._add_const(_pyast.literal_eval(val)))
                return
            except (ValueError, SyntaxError):
                pass
        if isinstance(val, str) and len(val) >= 6:
            # Triple-quoted strings: the lexer keeps the delimiters
            for q in ('"""', "'''"):
                if val.startswith(q) and val.endswith(q) and len(val) >= 6:
                    self._emit(LOAD_CONST, self._add_const(val[3:-3]))
                    return
                prefixed = val[0] in "fFrRbBuU" and val[1:].startswith(q) and val.endswith(q)
                if prefixed and len(val) >= 7:
                    if val[0] in "fF":
                        self._emit_fstring_body(val[4:-3])
                    else:
                        self._emit(LOAD_CONST, self._add_const(val[4:-3]))
                    return
        if isinstance(val, str) and len(val) >= 2:
            if val[0] in "fF" and len(val) >= 4 and val[1] == val[-1] and val[1] in ('"', "'") and val[2] != val[1]:
                # f-string: emit real interpolation (#24). The Python target
                # passes f-strings through raw to CPython; the VM must do
                # the interpolation itself.
                self._emit_fstring_body(val[2:-1])
                return
            if val[0] in "fFrRbBuU" and val[1] in ('"', "'"):
                val = val[1:]  # strip prefix
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
        self._emit(LOAD_CONST, self._add_const(val))

    def _emit_fstring_body(self, body: str):
        """Emit an f-string body ("x={x}") as str()-joined parts (#24).

        Supports plain ``{expr}`` interpolation plus ``{{`` / ``}}``
        escapes. Format specs (``{x:>5}``) and conversions (``{x!r}``)
        are not supported on the VM backend — keep f-strings plain in
        Externum source (the Python and bash targets handle them).
        """
        parts: list[tuple[bool, str]] = []  # (is_expr, text)
        buf: list[str] = []
        i = 0
        while i < len(body):
            c = body[i]
            if c == "{":
                if i + 1 < len(body) and body[i + 1] == "{":
                    buf.append("{")
                    i += 2
                    continue
                end = body.find("}", i + 1)
                if end == -1:
                    buf.append(c)
                    i += 1
                    continue
                if buf:
                    parts.append((False, "".join(buf)))
                    buf = []
                parts.append((True, body[i + 1 : end]))
                i = end + 1
            elif c == "}":
                if i + 1 < len(body) and body[i + 1] == "}":
                    buf.append("}")
                    i += 2
                    continue
                buf.append(c)
                i += 1
            else:
                buf.append(c)
                i += 1
        if buf:
            parts.append((False, "".join(buf)))
        if not parts:
            self._emit(LOAD_CONST, self._add_const(""))
            return
        for i, (is_expr, text) in enumerate(parts):
            if is_expr:
                expr_text, conv, spec = self._split_fstring_expr(text.strip())
                self._compile_simple_expr(expr_text)
                if spec:
                    # x.__format__(spec) — f"{x:.2f}" and friends
                    self._emit(GET_ATTR, self._add_const("__format__"))
                    self._emit(LOAD_CONST, self._add_const(spec))
                    self._emit1(CALL, 1)
                elif conv in ("r", "a"):
                    self._emit(GET_ATTR, self._add_const("__repr__"))
                    self._emit1(CALL, 0)
                else:
                    self._emit2(INTRINSIC, 2, 1)  # str(x)
            else:
                self._emit(LOAD_CONST, self._add_const(text))
            if i > 0:
                # ADD pops (b, a) -> a + b: both operands are on the stack
                self._emit(ADD)

    def _split_fstring_expr(self, text: str) -> tuple[str, str, str]:
        """Split an f-string field into (expression, conversion, format-spec)."""
        conv = ""
        spec = ""
        depth = 0
        quote = None
        conv_at = None
        spec_at = None
        for i, ch in enumerate(text):
            if quote:
                if ch == quote and (i == 0 or text[i - 1] != "\\"):
                    quote = None
                continue
            if ch in ('"', "'"):
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif depth == 0 and ch == "!" and spec_at is None and conv_at is None:
                conv_at = i
            elif depth == 0 and ch == ":" and spec_at is None:
                spec_at = i
        end = min(x for x in (conv_at, spec_at, len(text)) if x is not None)
        expr = text[:end]
        if conv_at is not None:
            conv_end = spec_at if spec_at is not None else len(text)
            conv = text[conv_at + 1 : conv_end]
        if spec_at is not None:
            spec = text[spec_at + 1 :]
        return expr, conv, spec

    def _expr_INTERP(self, node: ASTNode):
        """$"text {expr} more" → parts joined with str() + ADD.

        Each expression child compiles then passes through the ``str``
        intrinsic (code 2) so ``ADD`` is always string concatenation;
        literal children are pushed as constants. The result matches the
        Python f-string semantics of the transpile target.
        """
        parts = [c for c in node.children if c is not None]
        if not parts:
            self._emit(LOAD_CONST, self._add_const(""))
            return
        for i, child in enumerate(parts):
            if child.type == "EXPRESSION":
                self._compile_simple_expr(str(child.value))
                self._emit2(INTRINSIC, 2, 1)  # str(x)
            else:
                lit = child.value
                if len(lit) >= 2 and lit[0] == lit[-1] and lit[0] in ('"', "'"):
                    lit = lit[1:-1]
                # resolve f-string brace escapes: {{ → {, }} → }
                lit = lit.replace("{{", "{").replace("}}", "}")
                self._emit(LOAD_CONST, self._add_const(lit))
            if i > 0:
                # ADD pops (b, a) → a + b: both operands are on the stack now
                self._emit(ADD)

    def _expr_IDENTIFIER(self, node: ASTNode):
        name = node.value
        if name in ("True",):
            self._emit(LOAD_CONST, self._add_const(True))
            return
        if name in ("False",):
            self._emit(LOAD_CONST, self._add_const(False))
            return
        if name in ("None",):
            self._emit(LOAD_CONST, self._add_const(None))
            return
        self._compile_name(name)

    def _expr_EXPRESSION(self, node: ASTNode):
        self._compile_simple_expr(str(node.value))

    def _expr_WALRUS(self, node: ASTNode):
        """`n := expr` — assign and leave the value on the stack."""
        if len(node.children) < 2:
            self._emit(LOAD_CONST, self._add_const(None))
            return
        name = str(node.children[0].value)
        self._compile_expr(node.children[1])
        self._emit(DUP)
        self._store_var(name)

    def _expr_BINOP(self, node: ASTNode):
        op_node = node.children[1] if len(node.children) > 1 else None
        op = op_node.value if op_node else "+"
        if op == "|>":
            # x |> f(a, b)  →  f(x, a, b): emit [f, x, a, b] then CALL(argc+1);
            # CALL pops argc args then the callee, so x lands as first arg.
            left = node.children[0] if node.children else None
            right = node.children[2] if len(node.children) > 2 else None
            if right is not None and right.type == "CALL":
                self._compile_name(right.value)
                self._compile_expr(left)
                for child in right.children:
                    self._compile_expr(child)
                self._emit1(CALL, len(right.children) + 1)
            elif right is not None:
                self._compile_expr(right)
                self._compile_expr(left)
                self._emit1(CALL, 1)
            return
        if op == "if_else":
            # children: [true_value, OP, condition, false_value]
            self._compile_expr(node.children[2])  # condition
            jfalse = self._emit_jump(JUMP_IF_NOT)
            self._compile_expr(node.children[0])  # true value
            end = self._emit_jump(JUMP)
            self._patch_jump(jfalse)
            self._compile_expr(node.children[3])  # false value
            self._patch_jump(end)
            return
        if op == "not in":
            self._compile_expr(node.children[0])
            self._compile_expr(node.children[2])
            self._emit(IN_OP)
            self._emit(NOT)
            return
        if op == "is not":
            self._compile_expr(node.children[0])
            self._compile_expr(node.children[2])
            self._emit(IS_OP)
            self._emit(NOT)
            return
        self._compile_expr(node.children[0])
        self._compile_expr(node.children[2])
        op_map = {
            "+": ADD,
            "-": SUB,
            "*": MUL,
            "/": DIV,
            "%": MOD,
            "**": POW,
            "//": FLOOR_DIV,
            "&": BITAND,
            "|": BITOR,
            "^": BITXOR,
            "<<": LSHIFT,
            ">>": RSHIFT,
            "==": EQ,
            "!=": NEQ,
            "<": LT,
            ">": GT,
            "<=": LTE,
            ">=": GTE,
            "and": AND,
            "or": OR,
            "in": IN_OP,
            "is": IS_OP,
            "is not": IS_OP,
        }
        self._emit(op_map.get(op, ADD))

    def _expr_UNARYOP(self, node: ASTNode):
        op_node = node.children[0] if node.children else None
        op = op_node.value if op_node else "-"
        operand = node.children[1] if len(node.children) > 1 else None
        self._compile_expr(operand)
        if op == "not":
            self._emit(NOT)
        elif op == "-":
            self._emit(NEG)
        elif op == "+":
            pass
        elif op == "~":
            self._emit(BITNOT)

    def _expr_CALL(self, node: ASTNode):
        fn = node.value
        # Built-in calls
        builtin_map = {
            "print": 0,
            "len": 1,
            "str": 2,
            "int": 3,
            "float": 4,
            "range": 5,
            "type": 6,
            "input": 7,
            "open": 8,
            "alloc": 10,
            "free": 11,
            "addr": 12,
            "sizeof": 13,
            "chan": 14,
            "send": 15,
            "recv": 16,
            "spawn": 17,
            "panic": 20,
            "dbg": 21,
            "trace": 22,
            "assert_eq": 23,
            "unreachable": 24,
            "Result": 30,
            "Option": 31,
            "Ok": 32,
            "Err": 33,
            "Some": 34,
            "Option.None": 35,
            "sorted": 40,
            "enumerate": 41,
            "zip": 42,
            "reversed": 43,
            "min": 44,
            "max": 45,
            "sum": 46,
            "abs": 47,
            "round": 48,
            "chr": 49,
            "ord": 50,
            "hex": 51,
            "oct": 52,
            "bin": 53,
            "hash": 54,
            "isinstance": 55,
            "repr": 56,
            "id": 57,
            "super": 58,
            # Terminal builtins
            "term_init": 60,
            "term_cleanup": 61,
            "term_clear": 62,
            "term_refresh": 63,
            "term_size": 64,
            "term_move": 65,
            "term_write": 66,
            "term_color": 67,
            "term_getkey": 68,
            "term_addstr": 69,
            "term_border": 70,
            "term_hline": 71,
            "term_vline": 72,
            "term_getstr": 73,
            "term_attr": 74,
        }
        kwargs = [c for c in node.children if c.type == "KWARG"]
        starred = [c for c in node.children if c.type in ("STAR", "DSTAR")]
        if fn in builtin_map and not starred:
            positional = [c for c in node.children if c.type != "KWARG"]
            if kwargs:
                # print("a", end="") and friends: values then key/value pairs
                for child in positional:
                    self._compile_expr(child)
                for kw in kwargs:
                    self._emit(LOAD_CONST, self._add_const(str(kw.value)))
                    self._compile_expr(kw.children[0])
                self._emit3(INTRINSIC_EX, builtin_map[fn], len(positional), len(kwargs))
            else:
                for child in positional:
                    self._compile_expr(child)
                self._emit2(INTRINSIC, builtin_map[fn], len(positional))
        else:
            # User function: push fn first, then args (VM pops args then fn)
            # Handle dotted names like g.greet, Color.Red, o.unwrap
            if fn == "super":
                self._compile_name("super")
            elif "." in fn:
                parts = fn.rsplit(".", 1)
                self._compile_simple_expr(parts[0])  # receiver: obj, call, literal…
                self._emit(GET_ATTR, self._add_const(parts[1]))  # pop obj, push bound method
            else:
                self._compile_name(fn)
            if not kwargs and not starred:
                for child in node.children:
                    self._compile_expr(child)
                self._emit1(CALL, len(node.children))
                return
            # Build an explicit arg list + kwargs dict so *args/**kwargs work.
            self._emit(MAKE_LIST, 0)
            kw_started = False
            for child in node.children:
                if child.type == "STAR":
                    self._compile_expr(child.children[0])
                    self._emit(LIST_EXTEND)
                elif child.type == "DSTAR":
                    if not kw_started:
                        self._emit(MAKE_DICT, 0)
                        kw_started = True
                    self._compile_expr(child.children[0])
                    self._emit(DICT_UPDATE)
                elif child.type == "KWARG":
                    if not kw_started:
                        self._emit(MAKE_DICT, 0)
                        kw_started = True
                    self._emit(LOAD_CONST, self._add_const(str(child.value)))
                    self._compile_expr(child.children[0])
                    self._emit(DICT_SET)
                else:
                    self._compile_expr(child)
                    self._emit(LIST_APPEND)
            if not kw_started:
                self._emit(MAKE_DICT, 0)
            self._emit(CALL_EX)

    def _expr_LIST(self, node: ASTNode):
        val = str(node.value or "")
        inner = val[1:-1] if val.startswith("[") and val.endswith("]") else ""
        if self._is_comprehension(inner):
            self._compile_comprehension("list", inner)
            return
        if not inner.strip():
            self._emit(MAKE_LIST, 0)
            return
        items = self._parse_list_items(inner)
        self._emit(MAKE_LIST, 0)
        for item in items:
            item = item.strip()
            if not item:
                continue
            if item.startswith("*"):
                self._compile_simple_expr(item[1:].strip())
                self._emit(LIST_EXTEND)
            else:
                self._compile_simple_expr(item)
                self._emit(LIST_APPEND)

    def _expr_DICT(self, node: ASTNode):
        val = str(node.value or "")
        inner = val[1:-1].strip() if val.startswith("{") and val.endswith("}") else val
        if self._is_comprehension(inner):
            self._compile_comprehension("dict", inner)
            return
        if not inner:
            self._emit(MAKE_DICT, 0)
            return
        self._emit(MAKE_DICT, 0)
        for pair in self._parse_list_items(inner):
            pair = pair.strip()
            if not pair:
                continue
            if pair.startswith("**"):
                self._compile_simple_expr(pair[2:].strip())
                self._emit(DICT_UPDATE)
                continue
            k, v = self._split_top_level_colon(pair)
            if v is None:
                self._compile_simple_expr(k)
                self._emit(LOAD_CONST, self._add_const(None))
            else:
                self._compile_simple_expr(k)
                self._compile_simple_expr(v)
            self._emit(DICT_SET)

    def _expr_SET(self, node: ASTNode):
        val = str(node.value or "")
        inner = val[1:-1] if val.startswith("{") and val.endswith("}") else ""
        if self._is_comprehension(inner):
            self._compile_comprehension("set", inner)
            return
        items = self._parse_list_items(inner) if inner.strip() else []
        self._emit(MAKE_SET, 0)
        for item in items:
            self._compile_simple_expr(item.strip())
            self._emit(SET_ADD)

    # ── comprehensions ─────────────────────────────────────────────
    def _pos(self) -> int:
        return len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)

    def _top_level_keyword(self, text: str, keyword: str) -> "int | None":
        """Index of a whitespace-delimited keyword at bracket/quote depth 0."""
        depth = 0
        quote = None
        klen = len(keyword)
        for i, ch in enumerate(text):
            if quote:
                if ch == quote and (i == 0 or text[i - 1] != "\\"):
                    quote = None
                continue
            if ch in ('"', "'"):
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif depth == 0 and text.startswith(keyword, i):
                before_ok = i == 0 or text[i - 1].isspace()
                after = i + klen
                after_ok = after >= len(text) or text[after].isspace()
                if before_ok and after_ok:
                    return i
        return None

    def _is_comprehension(self, text: str) -> bool:
        return self._top_level_keyword(text, "for") is not None

    def _split_top_level_colon(self, text: str) -> tuple[str, "str | None"]:
        depth = 0
        quote = None
        for i, ch in enumerate(text):
            if quote:
                if ch == quote and (i == 0 or text[i - 1] != "\\"):
                    quote = None
                continue
            if ch in ('"', "'"):
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == ":" and depth == 0:
                return text[:i].strip(), text[i + 1 :].strip()
        return text.strip(), None

    def _parse_comp_clauses(self, text: str) -> list[tuple[str, "str | None", str]]:
        positions: list[tuple[int, str]] = []
        for keyword in ("for", "if"):
            start = 0
            while True:
                pos = self._top_level_keyword(text[start:], keyword)
                if pos is None:
                    break
                positions.append((start + pos, keyword))
                start += pos + len(keyword)
        positions.sort()
        clauses: list[tuple[str, str | None, str]] = []
        for i, (pos, keyword) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            seg = text[pos + len(keyword) : end].strip()
            if keyword == "for":
                in_pos = self._top_level_keyword(seg, "in")
                if in_pos is None:
                    continue
                clauses.append(("for", seg[:in_pos].strip(), seg[in_pos + 2 :].strip()))
            else:
                clauses.append(("if", None, seg))
        return clauses

    def _compile_comprehension(self, kind: str, text: str):
        first = self._top_level_keyword(text, "for")
        if first is None:
            self._compile_simple_expr(text)
            return
        body_text = text[:first].strip()
        clauses = self._parse_comp_clauses(text[first:])
        acc = f"__comp{self._comp_counter}__"
        self._comp_counter += 1
        if kind == "list":
            self._emit(MAKE_LIST, 0)
        elif kind == "set":
            self._emit(MAKE_SET, 0)
        else:
            self._emit(MAKE_DICT, 0)
        self._store_var(acc)
        self._comp_clause(kind, body_text, clauses, 0, acc)
        self._compile_name(acc)

    def _comp_clause(self, kind: str, body_text: str, clauses, idx: int, acc: str):
        if idx >= len(clauses):
            self._comp_accumulate(kind, body_text, acc)
            return
        ckind, var, payload = clauses[idx]
        if ckind == "for":
            self._compile_simple_expr(payload)
            start = self._pos()
            jump_out = self._emit_jump(FOR_ITER)
            if "," in str(var):
                names = [n.strip() for n in str(var).split(",") if n.strip()]
                self._emit(UNPACK, len(names))
                for name in reversed(names):
                    self._store_var(name)
            else:
                self._store_var(str(var))
            self._loop_stack.append([])
            self._loop_start_stack.append(start)
            self._comp_clause(kind, body_text, clauses, idx + 1, acc)
            back = self._emit_jump(JUMP)
            self._patch_jump_to(back, start)
            self._patch_jump(jump_out)
            self._loop_start_stack.pop()
            for bp in self._loop_stack.pop():
                self._patch_jump(bp)
        else:
            self._compile_simple_expr(payload)
            skip = self._emit_jump(JUMP_IF_NOT)
            self._comp_clause(kind, body_text, clauses, idx + 1, acc)
            if self._loop_start_stack:
                self._patch_jump_to(skip, self._loop_start_stack[-1])
            else:
                self._patch_jump(skip)

    def _comp_accumulate(self, kind: str, body_text: str, acc: str):
        if kind == "dict":
            key, val = self._split_top_level_colon(body_text)
            self._compile_name(acc)
            self._compile_simple_expr(key)
            self._compile_simple_expr(val if val is not None else "None")
            self._emit(SET_INDEX)
            return
        self._compile_name(acc)
        self._emit(GET_ATTR, self._add_const("append" if kind == "list" else "add"))
        self._compile_simple_expr(body_text)
        self._emit1(CALL, 1)
        self._emit(POP)

    def _expr_TUPLE(self, node: ASTNode):
        val = str(node.value or "")
        if val == "()":
            self._emit(MAKE_TUPLE, 0)
            return
        inner = val[1:-1] if val.startswith("(") else ""
        items = self._parse_list_items(inner) if inner.strip() else []
        if any(item.strip().startswith("*") for item in items):
            self._emit(MAKE_LIST, 0)
            for item in items:
                item = item.strip()
                if item.startswith("*"):
                    self._compile_simple_expr(item[1:].strip())
                    self._emit(LIST_EXTEND)
                else:
                    self._compile_simple_expr(item)
                    self._emit(LIST_APPEND)
            self._emit(LIST_TO_TUPLE)
            return
        for item in items:
            self._compile_simple_expr(item.strip())
        self._emit(MAKE_TUPLE, len(items))

    def _expr_INDEX(self, node: ASTNode):
        val = str(node.value)
        # Find the first top-level bracket
        depth = 0
        bracket = -1
        for i, ch in enumerate(val):
            if ch == "[" and depth == 0:
                bracket = i
                break
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
        if bracket >= 0:
            obj_name = val[:bracket].strip()
            # The receiver can be a name, a call, a literal or a chain.
            if obj_name:
                self._compile_simple_expr(obj_name)
            # Compile the index expression
            idx_expr = val[bracket + 1 : -1].strip()
            # Slice support: a:b / a:b:c -> build via SLICE opcode with
            # components on the stack (missing parts -> None)
            if ":" in idx_expr and not idx_expr.startswith('"') and not idx_expr.startswith("'"):
                segs = idx_expr.split(":")
                if 2 <= len(segs) <= 3:
                    for seg in segs:
                        seg = seg.strip()
                        if seg:
                            self._compile_simple_expr(seg)
                        else:
                            self._emit(LOAD_CONST, self._add_const(None))
                    # SLICE carries operand = number of pushed values (3 or 4)
                    self._emit(SLICE, len(segs) + 1)
                    return
            self._compile_simple_expr(idx_expr)
            self._emit(GET_INDEX)

    def _expr_DOT(self, node: ASTNode):
        parts = node.value.rsplit(".", 1)
        if len(parts) == 2:
            self._compile_name(parts[0])
            idx = self._add_const(parts[1])
            self._emit(GET_ATTR, idx)

    def _expr_DEREF(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        self._emit(LOAD_DEREF)

    def _expr_LAMBDA(self, node: ASTNode):
        arg_str = node.value
        body = node.children[0] if node.children else None
        fn = BytecodeFunction(name="<lambda>", arg_names=[a.strip() for a in arg_str.split(",") if a.strip()])
        old_fn = self._current_fn
        self._current_fn = fn
        old_scope = self._scope_stack
        self._scope_stack = [{}]
        for a in fn.arg_names:
            self._declare_var(a)
        if body:
            self._compile_expr(body)
        else:
            self._emit(LOAD_CONST, self._add_const(None))
        self._emit(RETURN)
        self._current_fn = old_fn
        self._scope_stack = old_scope
        fn_idx = len(self.module.functions)
        self.module.functions.append(fn)
        self._emit(MAKE_FN, fn_idx)

    def _expr_KWARG(self, node: ASTNode):
        # keyword args are handled by CALL
        if node.children:
            self._compile_expr(node.children[0])

    def _expr_STAR(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])

    def _expr_DSTAR(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])

    def _expr_PIPE(self, node: ASTNode):
        """pipe: a |> f |> g — compiled as g(f(a))."""
        # Simplified: just compile as expression
        self._compile_simple_expr(str(node.value) if node.value else "None")

    def _expr_OPTIONAL_CHAIN(self, node: ASTNode):
        """?. operator — simplified to getattr with None check."""
        self._compile_simple_expr(str(node.value) if node.value else "None")

    def _expr_NULLISH(self, node: ASTNode):
        """?? operator — simplified."""
        self._compile_simple_expr(str(node.value) if node.value else "None")

    def _expr_BANG(self, node: ASTNode):
        """! unwrap operator."""
        if node.children:
            self._compile_expr(node.children[0])

    # ── helpers ─────────────────────────────────────────────────────
    def _store_var(self, name: str):
        """Pop the stack into `name`, choosing the global or local slot."""
        if self._current_fn is None:
            self._emit(STORE_GLOBAL, self._add_const(name))
            self._declare_var(name)
            return
        self._declare_var(name)
        kind, _ = self._resolve(name)
        self._emit(STORE_VAR if kind != "global" else STORE_GLOBAL, self._add_const(name))

    def _compile_name(self, name: str):
        kind, _ = self._resolve(name)
        idx = self._add_const(name)
        if kind == "global" or self._current_fn is None:
            self._emit(LOAD_GLOBAL, idx)
        else:
            self._emit(LOAD_VAR, idx)

    def _compile_simple_expr(self, expr: str):
        """Compile a simple string expression (fallback for complex AST nodes)."""
        expr = expr.strip()
        if not expr:
            self._emit(LOAD_CONST, self._add_const(None))
            return
        # Strip redundant outer parentheses: "((a + b) % c)" → "(a + b) % c".
        # Only strip when the paren at position 0 closes at the LAST character;
        # "(a) + (b)" keeps its top-level binop split (issue #22 — otherwise
        # the whole parenthesized text fell through to _compile_name and the
        # VM raised "undefined global").
        while len(expr) >= 2 and expr[0] == "(" and expr[-1] == ")":
            close = self._find_matching_paren(expr, 0)
            if close == len(expr) - 1:
                expr = expr[1:-1].strip()
            else:
                break
        # literal int
        try:
            self._emit(LOAD_CONST, self._add_const(int(expr)))
            return
        except ValueError:
            pass
        # literal float
        try:
            self._emit(LOAD_CONST, self._add_const(float(expr)))
            return
        except ValueError:
            pass
        # literal string — only match if the ENTIRE expr is a single quoted string
        if len(expr) >= 2 and expr[0] in ('"', "'"):
            quote = expr[0]
            # Scan forward from position 1 to find the matching close quote
            i = 1
            matched_end = -1
            while i < len(expr):
                ch = expr[i]
                if ch == "\\":
                    i += 2  # skip escaped character
                    continue
                if ch == quote:
                    matched_end = i
                    break
                i += 1
            if matched_end == len(expr) - 1:
                inner = expr[1:matched_end]
                self._emit(LOAD_CONST, self._add_const(inner))
                return
        # list literal / comprehension
        if expr.startswith("[") and expr.endswith("]"):
            inner = expr[1:-1]
            if self._is_comprehension(inner):
                self._compile_comprehension("list", inner)
                return
            self._emit(MAKE_LIST, 0)
            for item in self._parse_list_items(inner) if inner.strip() else []:
                item = item.strip()
                if not item:
                    continue
                if item.startswith("*"):
                    self._compile_simple_expr(item[1:].strip())
                    self._emit(LIST_EXTEND)
                else:
                    self._compile_simple_expr(item)
                    self._emit(LIST_APPEND)
            return
        # dict / set literal
        if expr.startswith("{") and expr.endswith("}"):
            inner = expr[1:-1]
            if self._is_comprehension(inner):
                self._compile_comprehension("dict" if ":" in inner.split(" for ")[0] else "set", inner)
                return
            if ":" in inner:
                self._emit(MAKE_DICT, 0)
                for pair in self._parse_list_items(inner) if inner.strip() else []:
                    k, v = self._split_top_level_colon(pair.strip())
                    if v is None:
                        self._compile_simple_expr(k)
                        self._emit(LOAD_CONST, self._add_const(None))
                    else:
                        self._compile_simple_expr(k)
                        self._compile_simple_expr(v)
                    self._emit(DICT_SET)
            else:
                self._emit(MAKE_SET, 0)
                for item in self._parse_list_items(inner) if inner.strip() else []:
                    self._compile_simple_expr(item.strip())
                    self._emit(SET_ADD)
            return
        # True/False/None
        if expr == "True":
            self._emit(LOAD_CONST, self._add_const(True))
            return
        if expr == "False":
            self._emit(LOAD_CONST, self._add_const(False))
            return
        if expr == "None":
            self._emit(LOAD_CONST, self._add_const(None))
            return
        # name
        if expr.isidentifier():
            self._compile_name(expr)
            return
        # function call: name(args) — fn pushed first, then args
        if "(" in expr and expr.endswith(")"):
            paren_idx = self._find_top_level_paren(expr)
            if paren_idx is not None:
                # Find the matching close paren
                close_idx = self._find_matching_paren(expr, paren_idx)
                if close_idx is None or close_idx != len(expr) - 1:
                    paren_idx = None  # Not a top-level function call
            if paren_idx is not None:
                fn_name = expr[:paren_idx].strip()
                dotted_ok = "." in fn_name and all(p.isidentifier() for p in fn_name.split("."))
                if fn_name.isidentifier() or dotted_ok:
                    args_str = expr[paren_idx + 1 : close_idx].strip()
                    args = self._parse_list_items(args_str) if args_str else []
                    builtin_map = {
                        "print": 0,
                        "len": 1,
                        "str": 2,
                        "int": 3,
                        "float": 4,
                        "range": 5,
                        "type": 6,
                        "input": 7,
                        "open": 8,
                        "Ok": 32,
                        "Err": 33,
                        "Some": 34,
                        "alloc": 10,
                        "free": 11,
                        "panic": 20,
                        "dbg": 21,
                        "sorted": 40,
                        "enumerate": 41,
                        "zip": 42,
                        "min": 44,
                        "max": 45,
                        "sum": 46,
                        "abs": 47,
                        "round": 48,
                        "chr": 49,
                        "ord": 50,
                        "hex": 51,
                        "oct": 52,
                        "bin": 53,
                        "hash": 54,
                        "isinstance": 55,
                        "repr": 56,
                        "super": 58,
                        "term_init": 60,
                        "term_cleanup": 61,
                        "term_clear": 62,
                        "term_refresh": 63,
                        "term_size": 64,
                        "term_move": 65,
                        "term_write": 66,
                        "term_color": 67,
                        "term_getkey": 68,
                        "term_addstr": 69,
                        "term_border": 70,
                        "term_hline": 71,
                        "term_vline": 72,
                        "term_getstr": 73,
                        "term_attr": 74,
                    }
                    if fn_name in builtin_map:
                        for a in args:
                            self._compile_simple_expr(a.strip())
                        self._emit2(INTRINSIC, builtin_map[fn_name], len(args))
                    else:
                        if dotted_ok:
                            receiver, attr = fn_name.rsplit(".", 1)
                            self._compile_simple_expr(receiver)
                            self._emit(GET_ATTR, self._add_const(attr))
                        else:
                            self._compile_name(fn_name)
                        for a in args:
                            self._compile_simple_expr(a.strip())
                        self._emit1(CALL, len(args))
                    return
        # walrus: "n := expr"
        walrus = self._split_top_level_walrus(expr)
        if walrus is not None:
            name, right = walrus
            self._compile_simple_expr(right)
            self._emit(DUP)
            self._store_var(name)
            return
        # tuple literal: "1, 2" (top-level commas, no enclosing brackets)
        if self._has_top_level_comma(expr):
            items = self._parse_list_items(expr)
            for item in items:
                self._compile_simple_expr(item.strip())
            self._emit(MAKE_TUPLE, len(items))
            return
        # binary op: find LAST lowest-precedence operator outside parens
        split = self._find_top_level_binop(expr)
        if split is not None:
            op_str, opcode, idx = split
            left = expr[:idx].strip()
            right = expr[idx + len(op_str) :].strip()
            if left and right:
                self._compile_simple_expr(left)
                self._compile_simple_expr(right)
                self._emit(opcode)
                return
        # negative
        if expr.startswith("-") and len(expr) > 1 and expr[1] not in ("-", "+", "("):
            self._compile_simple_expr(expr[1:])
            self._emit(NEG)
            return
        # not
        if expr.startswith("not "):
            self._compile_simple_expr(expr[4:])
            self._emit(NOT)
            return
        # attribute access: a.b
        if "." in expr:
            parts = expr.rsplit(".", 1)
            self._compile_name(parts[0])
            self._emit(GET_ATTR, self._add_const(parts[1]))
            return
        # indexing: a[i]  (receiver may itself be a call or a chain)
        if "[" in expr and expr.endswith("]"):
            inner = expr[: expr.rfind("[")]
            idx_expr = expr[expr.rfind("[") + 1 : -1]
            self._compile_simple_expr(inner)
            self._compile_simple_expr(idx_expr)
            self._emit(GET_INDEX)
            return
        # variable reference (fallback)
        self._compile_name(expr)

    def _split_top_level_walrus(self, expr: str) -> "tuple[str, str] | None":
        depth = 0
        quote = None
        for i, ch in enumerate(expr):
            if quote:
                if ch == quote and (i == 0 or expr[i - 1] != "\\"):
                    quote = None
                continue
            if ch in ('"', "'"):
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif depth == 0 and expr.startswith(":=", i):
                name = expr[:i].strip()
                if name.isidentifier():
                    return name, expr[i + 2 :].strip()
                return None
        return None

    def _has_top_level_comma(self, expr: str) -> bool:
        depth = 0
        quote = None
        for i, ch in enumerate(expr):
            if quote:
                if ch == quote and (i == 0 or expr[i - 1] != "\\"):
                    quote = None
                continue
            if ch in ('"', "'"):
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                return True
        return False

    def _find_top_level_paren(self, expr: str) -> "int | None":
        """Find the position of the first top-level '(' in the expression."""
        depth = 0
        in_string = None
        for i, ch in enumerate(expr):
            if in_string:
                if ch == in_string and (i == 0 or expr[i - 1] != "\\"):
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                continue
            if ch == "(":
                if depth == 0:
                    return i
                depth += 1
            elif ch == ")":
                depth -= 1
        return None

    def _find_matching_paren(self, expr: str, open_pos: int) -> "int | None":
        """Find the matching close paren for an open paren at open_pos."""
        depth = 0
        in_string = None
        for i in range(open_pos, len(expr)):
            ch = expr[i]
            if in_string:
                if ch == in_string and (i == 0 or expr[i - 1] != "\\"):
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        return None

    def _find_top_level_binop(self, expr: str) -> "tuple | None":
        """Find the best binary operator to split on, respecting precedence and parentheses.
        Returns (op_str, opcode, position) or None.
        We scan from right to left at the lowest precedence level first
        to ensure correct left-to-right evaluation order."""
        precedence_groups = [
            (1, [("and", AND), ("or", OR)]),
            (2, [("==", EQ), ("!=", NEQ), ("<", LT), (">", GT), ("<=", LTE), (">=", GTE), ("in", IN_OP)]),
            (3, [("+", ADD), ("-", SUB)]),
            (4, [("*", MUL), ("//", FLOOR_DIV), ("/", DIV), ("%", MOD)]),
            (5, [("**", POW)]),
        ]
        for _prec, ops in precedence_groups:
            # Sort by length descending so we match longest first
            ops_sorted = sorted(ops, key=lambda x: -len(x[0]))
            for i in range(len(expr) - 1, 0, -1):
                if self._in_string_at(expr, i):
                    continue
                depth = self._paren_depth_at(expr, i)
                if depth > 0:
                    continue
                for op_str, opcode in ops_sorted:
                    if expr[i : i + len(op_str)] == op_str:
                        # Verify this isn't part of a longer operator
                        # Check backward: prev char forming longer op
                        if i > 0 and len(op_str) == 1:
                            prev_char = expr[i - 1]
                            if prev_char == op_str[0]:
                                continue
                        # Check forward: next char forming longer op
                        if i + len(op_str) < len(expr) and len(op_str) == 1:
                            next_char = expr[i + len(op_str)]
                            if next_char == op_str[0]:
                                continue
                        left = expr[:i].strip()
                        right = expr[i + len(op_str) :].strip()
                        if left and right:
                            return (op_str, opcode, i)
        return None

    def _in_string_at(self, expr: str, pos: int) -> bool:
        """Check if position is inside a string literal."""
        in_string = None
        for i in range(pos):
            ch = expr[i]
            if in_string:
                if ch == in_string and (i == 0 or expr[i - 1] != "\\"):
                    in_string = None
            elif ch in ('"', "'"):
                in_string = ch
        return in_string is not None

    def _paren_depth_at(self, expr: str, pos: int) -> int:
        """Return the parenthesis depth at the given position."""
        depth = 0
        in_string = None
        for i in range(pos):
            ch = expr[i]
            if in_string:
                if ch == in_string and (i == 0 or expr[i - 1] != "\\"):
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        return depth

    def _parse_list_items(self, s: str) -> list[str]:
        """Parse comma-separated items respecting brackets."""
        items = []
        depth = 0
        current = []
        for ch in s:
            if ch in "([{":
                depth += 1
                current.append(ch)
            elif ch in ")]}":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                items.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            items.append("".join(current))
        return items

    def _eval_const(self, s: str) -> Any:
        """Evaluate a constant expression at compile time."""
        s = s.strip()
        if s == "True":
            return True
        if s == "False":
            return False
        if s == "None":
            return None
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s


# ── EXBC artifact serialization ──────────────────────────────────────
# A .exbc artifact is a self-contained, source-free representation of a
# BytecodeModule: magic header + version + pickle payload. The VM can run
# it directly (externum run app.exbc) without lexing/parsing/compiling —
# the same mechanism that backs the DRM story (source never ships).

EXBC_MAGIC = b"EXBC"
EXBC_FORMAT_VERSION = 1


def module_to_bytes(module: BytecodeModule) -> bytes:
    """Serialize a BytecodeModule to an .exbc artifact."""
    import pickle

    payload = pickle.dumps(module, protocol=pickle.HIGHEST_PROTOCOL)
    header = EXBC_MAGIC + EXBC_FORMAT_VERSION.to_bytes(2, "big") + len(payload).to_bytes(8, "big")
    return header + payload


def module_from_bytes(data: bytes) -> BytecodeModule:
    """Deserialize an .exbc artifact back into a BytecodeModule."""
    import pickle

    if len(data) < 14 or data[:4] != EXBC_MAGIC:
        raise ValueError("not an EXBC artifact (bad magic)")
    version = int.from_bytes(data[4:6], "big")
    if version != EXBC_FORMAT_VERSION:
        raise ValueError(f"unsupported EXBC artifact version: {version}")
    payload_len = int.from_bytes(data[6:14], "big")
    payload = data[14:]
    if len(payload) != payload_len:
        raise ValueError(f"corrupt EXBC artifact: expected {payload_len} bytes, got {len(payload)}")
    module = pickle.loads(payload)
    if not isinstance(module, BytecodeModule):
        raise ValueError("corrupt EXBC artifact: wrong payload type")
    return module


def save_module(module: BytecodeModule, path: str) -> None:
    with open(path, "wb") as fh:
        fh.write(module_to_bytes(module))


def load_module(path: str) -> BytecodeModule:
    with open(path, "rb") as fh:
        return module_from_bytes(fh.read())
