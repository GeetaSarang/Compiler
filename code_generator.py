"""
code_generator.py  —  SimpleScript AST → VM Code (Stage 4)
============================================================
Walks the AST produced by the Parser and emits stack-based VM instructions.

VM Instruction Reference:
  push <segment> <index>     — push value onto the stack
  pop  <segment> <index>     — pop value from stack into a segment slot
  add / sub / neg            — arithmetic
  and / or / not             — logical/bitwise operations
  lt / gt / eq               — comparisons (-1 = true, 0 = false)
  label <lbl>                — marks a jump target
  goto <lbl>                 — unconditional jump
  if-goto <lbl>              — pop top of stack; jump if it's non-zero
  function <name> <nLocals>  — declare a function and its local count
  call <name> <nArgs>        — call a function
  return                     — return from function

Memory segments used:
  constant   — literal numbers (read-only)
  local      — function's local 'var' variables
  argument   — function parameters
  this       — fields of the current object
  that       — array element being accessed
  static     — class-level static variables
  temp       — temporary scratch registers (temp 0..7)
  pointer    — pointer 0 = THIS base, pointer 1 = THAT base

Usage:
    gen = CodeGenerator()
    vm_code_string = gen.generate(ast_root)
"""

from syntax_tree import (
    ProgramNode, SubroutineNode,
    LetNode, IfNode, WhileNode, DoNode, ReturnNode,
    BinaryOpNode, UnaryOpNode,
    IntegerNode, StringNode, BoolNode, NullNode, ThisNode,
    VarNode, ArrayAccessNode, CallNode,
)

# Maps internal kind strings → VM segment names
_KIND_TO_SEG = {
    'static':   'static',
    'field':    'this',
    'arg':      'argument',
    'var':      'local',
}

# Maps binary operator symbols → VM instructions
_BINARY_OP_VM = {
    '+': 'add',
    '-': 'sub',
    '&': 'and',
    '|': 'or',
    '<': 'lt',
    '>': 'gt',
    '=': 'eq',
    '*': 'call Math.multiply 2',   # multiplication via standard library
    '/': 'call Math.divide 2',     # division via standard library
}


# ── Symbol Table ──────────────────────────────────────────────────────────────

class SymbolTable:
    """
    Keeps track of all variables and their VM addresses.

    Two scopes:
      class scope      → 'static' and 'field' variables
      subroutine scope → 'arg' (parameters) and 'var' (locals)

    Each entry maps:  name → (type, kind, index)

    Example:
        symbols.define('x', 'int', 'var')
        symbols.lookup('x')  →  ('int', 'var', 0)
    """

    def __init__(self):
        self._class_scope: dict = {}
        self._sub_scope:   dict = {}
        # Running index counters for each kind
        self._counts = {'static': 0, 'field': 0, 'arg': 0, 'var': 0}

    def start_subroutine(self):
        """Clear subroutine-level variables. Call at the start of each function."""
        self._sub_scope    = {}
        self._counts['arg'] = 0
        self._counts['var'] = 0

    def define(self, name: str, var_type: str, kind: str):
        """
        Register a variable.
        kind must be 'static', 'field', 'arg', or 'var'.
        """
        idx = self._counts[kind]
        self._counts[kind] += 1

        if kind in ('static', 'field'):
            self._class_scope[name] = (var_type, kind, idx)
        else:
            self._sub_scope[name] = (var_type, kind, idx)

    def lookup(self, name: str):
        """
        Find a variable by name.
        Returns (type, kind, index) or None if not declared.
        Subroutine scope is checked first (inner scope shadows outer).
        """
        if name in self._sub_scope:
            return self._sub_scope[name]
        if name in self._class_scope:
            return self._class_scope[name]
        return None

    def count(self, kind: str) -> int:
        """How many variables of this kind have been registered so far."""
        return self._counts[kind]


# ── Code Generator ────────────────────────────────────────────────────────────

class CodeGenerator:
    """
    Converts a SimpleScript AST into VM code.

    Usage:
        gen     = CodeGenerator()
        vm_code = gen.generate(program_node)
    """

    def __init__(self):
        self._out:        list        = []    # list of output lines
        self._symbols:    SymbolTable = SymbolTable()
        self._label_cnt:  int         = 0     # counter for unique labels
        self._class_name: str         = ''

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _emit(self, *lines: str):
        """Add one or more lines to the output."""
        self._out.extend(lines)

    def _new_label(self) -> str:
        """Generate a fresh unique label string."""
        lbl = f'SS_L{self._label_cnt}'
        self._label_cnt += 1
        return lbl

    def _push_var(self, name: str):
        """Emit a push instruction for a variable looked up in the symbol table."""
        sym = self._symbols.lookup(name)
        if sym is None:
            raise NameError(f"Undefined variable: '{name}'")
        _, kind, idx = sym
        self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')

    def _pop_var(self, name: str):
        """Emit a pop instruction for a variable looked up in the symbol table."""
        sym = self._symbols.lookup(name)
        if sym is None:
            raise NameError(f"Undefined variable: '{name}'")
        _, kind, idx = sym
        self._emit(f'pop {_KIND_TO_SEG[kind]} {idx}')

    # ── Public interface ──────────────────────────────────────────────────────

    def generate(self, program: ProgramNode) -> str:
        """
        Main entry point.
        Walks the entire AST and returns VM source code as a string.
        """
        self._class_name = program.name

        # Register all class-level static variables
        for (kind, vtype, vname) in program.static_vars:
            self._symbols.define(vname, vtype, kind)

        # Generate VM code for each subroutine
        for sub in program.subroutines:
            self._gen_subroutine(sub)

        return '\n'.join(self._out)

    # ── Subroutines ───────────────────────────────────────────────────────────

    def _gen_subroutine(self, sub: SubroutineNode):
        """Generate code for one function / method / constructor."""
        self._symbols.start_subroutine()

        # Methods receive 'this' as a hidden first argument
        if sub.kind == 'method':
            self._symbols.define('this', self._class_name, 'arg')

        # Register parameters
        for (ptype, pname) in sub.params:
            self._symbols.define(pname, ptype, 'arg')

        # Register local variables
        for (_, vtype, vname) in sub.local_vars:
            self._symbols.define(vname, vtype, 'var')

        n_locals = self._symbols.count('var')

        self._emit(
            f'// ---- {sub.kind} {self._class_name}.{sub.name} ----',
            f'function {self._class_name}.{sub.name} {n_locals}',
        )

        if sub.kind == 'constructor':
            # Allocate heap memory for the new object
            n_fields = self._symbols.count('field')
            self._emit(
                f'push constant {n_fields}',
                'call Memory.alloc 1',    # returns a pointer to allocated block
                'pop pointer 0',          # set THIS to point at the new object
            )
        elif sub.kind == 'method':
            # Set THIS to the object that was passed as the first argument
            self._emit('push argument 0', 'pop pointer 0')

        # Generate code for each statement in the body
        for stmt in sub.body:
            self._gen_statement(stmt)

    # ── Statements ────────────────────────────────────────────────────────────

    def _gen_statement(self, stmt):
        """Dispatch to the correct statement code-gen method."""
        if   isinstance(stmt, LetNode):    self._gen_let(stmt)
        elif isinstance(stmt, IfNode):     self._gen_if(stmt)
        elif isinstance(stmt, WhileNode):  self._gen_while(stmt)
        elif isinstance(stmt, DoNode):     self._gen_do(stmt)
        elif isinstance(stmt, ReturnNode): self._gen_return(stmt)
        else:
            raise TypeError(f"Unknown statement type: {type(stmt)}")

    def _gen_let(self, stmt: LetNode):
        """let name = expr;   or   let name[index] = expr;"""
        if stmt.index is not None:
            # ── Array write:  name[index] = expr ──
            # We need to compute the target address first, then write.
            sym = self._symbols.lookup(stmt.name)
            if sym is None:
                raise NameError(f"Undefined array: '{stmt.name}'")
            _, kind, idx = sym

            self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')  # base address
            self._gen_expr(stmt.index)                        # + index
            self._emit('add')                                 # = target address

            self._gen_expr(stmt.expr)                        # value to store
            self._emit(
                'pop temp 0',     # save value in temp register
                'pop pointer 1',  # THAT = target address
                'push temp 0',    # retrieve value
                'pop that 0',     # store at *THAT
            )
        else:
            # ── Simple assignment:  name = expr ──
            self._gen_expr(stmt.expr)
            self._pop_var(stmt.name)

    def _gen_if(self, stmt: IfNode):
        """
        if (cond) { ... } [else { ... }]

        VM pattern:
            evaluate condition
            not              ← flip: jump when condition is FALSE
            if-goto ELSE
            ... then branch ...
            goto END
          label ELSE
            ... else branch ...
          label END
        """
        else_lbl = self._new_label()
        end_lbl  = self._new_label()

        self._gen_expr(stmt.condition)
        self._emit('not', f'if-goto {else_lbl}')   # jump over then-branch if false

        for s in stmt.then_stmts:
            self._gen_statement(s)

        self._emit(f'goto {end_lbl}', f'label {else_lbl}')

        if stmt.else_stmts:
            for s in stmt.else_stmts:
                self._gen_statement(s)

        self._emit(f'label {end_lbl}')

    def _gen_while(self, stmt: WhileNode):
        """
        while (cond) { body }

        VM pattern:
          label TOP
            evaluate condition
            not
            if-goto END      ← exit when condition is false
            ... body ...
            goto TOP
          label END
        """
        top_lbl = self._new_label()
        end_lbl = self._new_label()

        self._emit(f'label {top_lbl}')
        self._gen_expr(stmt.condition)
        self._emit('not', f'if-goto {end_lbl}')

        for s in stmt.body:
            self._gen_statement(s)

        self._emit(f'goto {top_lbl}', f'label {end_lbl}')

    def _gen_do(self, stmt: DoNode):
        """do call;  — generate the call but throw away the return value."""
        self._gen_expr(stmt.call)
        self._emit('pop temp 0')   # discard return value (all calls must return something)

    def _gen_return(self, stmt: ReturnNode):
        """return [expr];"""
        if stmt.expr is not None:
            self._gen_expr(stmt.expr)
        else:
            # Void functions still need to push a dummy value (convention)
            self._emit('push constant 0')
        self._emit('return')

    # ── Expressions ───────────────────────────────────────────────────────────

    def _gen_expr(self, node):
        """Recursively generate code for any expression node."""

        if isinstance(node, IntegerNode):
            self._emit(f'push constant {node.value}')

        elif isinstance(node, BoolNode):
            self._emit('push constant 0')
            if node.value:
                self._emit('not')   # ~0 = -1 in two's complement = "true"

        elif isinstance(node, NullNode):
            self._emit('push constant 0')

        elif isinstance(node, ThisNode):
            self._emit('push pointer 0')   # pointer 0 always holds the THIS address

        elif isinstance(node, StringNode):
            # Strings live on the heap. Build char-by-char using String library.
            self._emit(
                f'push constant {len(node.value)}',
                'call String.new 1',               # allocate a string of that length
            )
            for ch in node.value:
                self._emit(
                    f'push constant {ord(ch)}',
                    'call String.appendChar 2',    # append one character
                )

        elif isinstance(node, VarNode):
            self._push_var(node.name)

        elif isinstance(node, ArrayAccessNode):
            # Compute base_address + index → use THAT segment to read
            sym = self._symbols.lookup(node.name)
            if sym is None:
                raise NameError(f"Undefined array: '{node.name}'")
            _, kind, idx = sym
            self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')
            self._gen_expr(node.index)
            self._emit(
                'add',          # target address on stack
                'pop pointer 1', # THAT = target address
                'push that 0',   # push *THAT (the element value)
            )

        elif isinstance(node, BinaryOpNode):
            self._gen_expr(node.left)
            self._gen_expr(node.right)
            self._emit(_BINARY_OP_VM[node.op])

        elif isinstance(node, UnaryOpNode):
            self._gen_expr(node.operand)
            self._emit('neg' if node.op == '-' else 'not')

        elif isinstance(node, CallNode):
            self._gen_call(node)

        else:
            raise TypeError(f"Unknown expression node type: {type(node)}")

    def _gen_call(self, node: CallNode):
        """
        Generate code for a function/method call.

        Three cases:
          1. No object prefix   → same-class method call (push this, then args)
          2. Object prefix is a variable   → method call on an object
          3. Object prefix is a class name → static function call
        """
        n_args = len(node.args)

        if node.obj is None:
            # Case 1: call within same class — push THIS as hidden first arg
            self._emit('push pointer 0')
            for arg in node.args:
                self._gen_expr(arg)
            self._emit(f'call {self._class_name}.{node.method} {n_args + 1}')

        else:
            sym = self._symbols.lookup(node.obj)
            if sym is not None:
                # Case 2: node.obj is a variable → method call on an object instance
                var_type, kind, idx = sym
                self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')  # push the object
                for arg in node.args:
                    self._gen_expr(arg)
                self._emit(f'call {var_type}.{node.method} {n_args + 1}')
            else:
                # Case 3: node.obj is a class name → static function call (no hidden arg)
                for arg in node.args:
                    self._gen_expr(arg)
                self._emit(f'call {node.obj}.{node.method} {n_args}')
