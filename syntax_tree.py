"""
syntax_tree.py  —  SimpleScript AST Node Definitions (Stage 2)
===============================================================
Defines all Abstract Syntax Tree (AST) node classes.
The Parser (Stage 3) builds these nodes.
The Code Generator (Stage 4) reads them.

Tree structure:
  ProgramNode
  └── SubroutineNode  (function / method / constructor)
       ├── params:     [(type_str, name_str), ...]
       ├── local_vars: [('var', type_str, name_str), ...]
       └── body:       [Statement, ...]

Statement nodes:
  LetNode, IfNode, WhileNode, DoNode, ReturnNode

Expression nodes:
  IntegerNode, StringNode, BoolNode, NullNode, ThisNode,
  VarNode, ArrayAccessNode, CallNode,
  BinaryOpNode, UnaryOpNode
"""


# ── Base node ────────────────────────────────────────────────────────────────

class Node:
    """Every AST node inherits from this. Gives a nice repr for debugging."""

    def __repr__(self):
        attrs = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'{self.__class__.__name__}({attrs})'


# ── Top-level ─────────────────────────────────────────────────────────────────

class ProgramNode(Node):
    """
    Represents one complete SimpleScript class.

    Attributes:
        name        (str)   Class name, e.g. 'Calculator'
        static_vars (list)  Static field declarations [('static', type, name), ...]
        subroutines (list)  List of SubroutineNode objects
    """
    def __init__(self, name: str, static_vars: list, subroutines: list):
        self.name        = name
        self.static_vars = static_vars
        self.subroutines = subroutines


class SubroutineNode(Node):
    """
    Represents one function, method, or constructor.

    Attributes:
        kind        (str)   'function' | 'method' | 'constructor'
        return_type (str)   e.g. 'int', 'void', or a class name
        name        (str)   Subroutine name
        params      (list)  [(type, name), ...]
        local_vars  (list)  [('var', type, name), ...]
        body        (list)  [Statement, ...]
    """
    def __init__(self, kind: str, return_type: str, name: str,
                 params: list, local_vars: list, body: list):
        self.kind        = kind
        self.return_type = return_type
        self.name        = name
        self.params      = params
        self.local_vars  = local_vars
        self.body        = body


# ── Statement nodes ───────────────────────────────────────────────────────────

class LetNode(Node):
    """
    let <name>[<index>] = <expr>;

    Examples:
        let x = 5;
        let arr[i] = 10;
    """
    def __init__(self, name: str, index, expr):
        self.name  = name    # variable being assigned
        self.index = index   # array index expression (or None for plain variables)
        self.expr  = expr    # right-hand side


class IfNode(Node):
    """
    if (<condition>) { <then_stmts> } [else { <else_stmts> }]
    """
    def __init__(self, condition, then_stmts: list, else_stmts):
        self.condition  = condition
        self.then_stmts = then_stmts
        self.else_stmts = else_stmts   # None if no else branch


class WhileNode(Node):
    """
    while (<condition>) { <body> }
    """
    def __init__(self, condition, body: list):
        self.condition = condition
        self.body      = body


class DoNode(Node):
    """
    do <call>;   — call a subroutine and throw away the return value
    """
    def __init__(self, call):
        self.call = call   # a CallNode


class ReturnNode(Node):
    """
    return [<expr>];

    Void functions use  return;  with no expression.
    """
    def __init__(self, expr):
        self.expr = expr   # None for void returns


# ── Expression nodes ──────────────────────────────────────────────────────────

class BinaryOpNode(Node):
    """
    <left> <op> <right>

    op is one of: + - * / & | < > =
    """
    def __init__(self, op: str, left, right):
        self.op    = op
        self.left  = left
        self.right = right


class UnaryOpNode(Node):
    """
    <op><operand>

    op is one of:
        -   negate (e.g. -x)
        ~   bitwise NOT
    """
    def __init__(self, op: str, operand):
        self.op      = op
        self.operand = operand


class IntegerNode(Node):
    """An integer constant: 0 to 32767."""
    def __init__(self, value: int):
        self.value = value


class StringNode(Node):
    """A string literal, without the surrounding quotes."""
    def __init__(self, value: str):
        self.value = value


class BoolNode(Node):
    """A boolean literal: true or false."""
    def __init__(self, value: bool):
        self.value = value


class NullNode(Node):
    """The null pointer constant."""
    pass


class ThisNode(Node):
    """Reference to the current object (used inside methods)."""
    pass


class VarNode(Node):
    """A reference to a variable by name."""
    def __init__(self, name: str):
        self.name = name


class ArrayAccessNode(Node):
    """
    <name>[<index>]  — read one element of an array.
    Example: arr[i]
    """
    def __init__(self, name: str, index):
        self.name  = name
        self.index = index


class CallNode(Node):
    """
    A subroutine call.

    Attributes:
        obj    (str | None)  Object/class before the dot. None = same-class call.
        method (str)         Function/method name.
        args   (list)        Argument expressions.

    Examples:
        Calculator.add(a, b)   →  obj='Calculator', method='add'
        myObj.print()          →  obj='myObj',       method='print'
        compute(x)             →  obj=None,           method='compute'
    """
    def __init__(self, obj, method: str, args: list):
        self.obj    = obj
        self.method = method
        self.args   = args
