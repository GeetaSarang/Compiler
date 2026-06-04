"""
parser.py  —  SimpleScript Recursive-Descent Parser (Stage 3)
==============================================================
Reads the token stream from the Tokenizer and builds an AST.

Grammar (simplified):
  program       := 'class' ID '{' staticDec* subroutine* '}'
  subroutine    := ('function'|'method'|'constructor') type ID '(' params ')' body
  params        := ((type ID) (',' type ID)*)?
  body          := '{' varDec* statement* '}'
  varDec        := 'var' type ID (',' ID)* ';'
  staticDec     := 'static' type ID (',' ID)* ';'

  statement     := letStmt | ifStmt | whileStmt | doStmt | returnStmt
  letStmt       := 'let' ID ('[' expr ']')? '=' expr ';'
  ifStmt        := 'if' '(' expr ')' '{' statement* '}' ('else' '{' statement* '}')?
  whileStmt     := 'while' '(' expr ')' '{' statement* '}'
  doStmt        := 'do' call ';'
  returnStmt    := 'return' expr? ';'

  expr          := term (op term)*
  term          := INTEGER | STRING | 'true' | 'false' | 'null' | 'this'
                 | ID '[' expr ']' | call | ID
                 | '(' expr ')' | unaryOp term
  op            := '+' | '-' | '*' | '/' | '&' | '|' | '<' | '>' | '='
  unaryOp       := '-' | '~'

Usage:
    tokenizer = Tokenizer(source_code)
    ast       = Parser(tokenizer).parse()
"""

from tokenizer import Tokenizer, TokenType
from syntax_tree import (
    ProgramNode, SubroutineNode,
    LetNode, IfNode, WhileNode, DoNode, ReturnNode,
    BinaryOpNode, UnaryOpNode,
    IntegerNode, StringNode, BoolNode, NullNode, ThisNode,
    VarNode, ArrayAccessNode, CallNode,
)


class ParseError(Exception):
    """Raised when the source code violates the grammar."""
    pass


# Sets used for quick membership checks
_BINARY_OPS  = set('+-*/&|<>=')
_UNARY_OPS   = {'-', '~'}
_SUB_KINDS   = {'function', 'method', 'constructor'}


class Parser:
    """
    Recursive-descent parser for SimpleScript.

    Each parse method corresponds to one grammar rule.
    Call  parse()  to get the full ProgramNode (AST root).
    """

    def __init__(self, tokenizer: Tokenizer):
        self._t = tokenizer   # the token stream

    # ── Entry point ──────────────────────────────────────────────────────────

    def parse(self) -> ProgramNode:
        """Parse the full source and return the root AST node."""
        node = self._parse_class()
        self._t.expect(TokenType.EOF)   # nothing should be left over
        return node

    # ── Class (top level) ────────────────────────────────────────────────────

    def _parse_class(self) -> ProgramNode:
        """
        class ID { staticDec* subroutine* }
        """
        self._t.expect(TokenType.KEYWORD, 'class')
        name = self._t.expect(TokenType.IDENTIFIER).value
        self._t.expect(TokenType.SYMBOL, '{')

        static_vars  = []
        subroutines  = []

        while not self._t.match(TokenType.SYMBOL, '}'):
            tok = self._t.peek()

            if tok.value == 'static':
                static_vars.extend(self._parse_static_dec())
            elif tok.value in _SUB_KINDS:
                subroutines.append(self._parse_subroutine())
            else:
                raise ParseError(
                    f"Unexpected '{tok.value}' inside class at line {tok.line}. "
                    f"Expected 'static', 'function', 'method', or 'constructor'."
                )

        self._t.expect(TokenType.SYMBOL, '}')
        return ProgramNode(name, static_vars, subroutines)

    # ── Variable declarations ─────────────────────────────────────────────────

    def _parse_static_dec(self) -> list:
        """
        static <type> <name>, <name>, ... ;
        Returns a list of ('static', type, name) tuples.
        """
        self._t.expect(TokenType.KEYWORD, 'static')
        var_type = self._t.advance().value                    # int, boolean, ClassName …
        names    = [self._t.expect(TokenType.IDENTIFIER).value]

        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            names.append(self._t.expect(TokenType.IDENTIFIER).value)

        self._t.expect(TokenType.SYMBOL, ';')
        return [('static', var_type, n) for n in names]

    def _parse_local_dec(self) -> list:
        """
        var <type> <name>, <name>, ... ;
        Returns a list of ('var', type, name) tuples.
        """
        self._t.expect(TokenType.KEYWORD, 'var')
        var_type = self._t.advance().value
        names    = [self._t.expect(TokenType.IDENTIFIER).value]

        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            names.append(self._t.expect(TokenType.IDENTIFIER).value)

        self._t.expect(TokenType.SYMBOL, ';')
        return [('var', var_type, n) for n in names]

    # ── Subroutine ────────────────────────────────────────────────────────────

    def _parse_subroutine(self) -> SubroutineNode:
        """
        (function|method|constructor) returnType name ( params ) { varDec* stmts }
        """
        kind        = self._t.advance().value    # function / method / constructor
        return_type = self._t.advance().value    # void / int / ClassName …
        name        = self._t.expect(TokenType.IDENTIFIER).value

        self._t.expect(TokenType.SYMBOL, '(')
        params = self._parse_param_list()
        self._t.expect(TokenType.SYMBOL, ')')

        self._t.expect(TokenType.SYMBOL, '{')
        local_vars = []
        while self._t.match(TokenType.KEYWORD, 'var'):
            local_vars.extend(self._parse_local_dec())

        body = self._parse_statements()
        self._t.expect(TokenType.SYMBOL, '}')

        return SubroutineNode(kind, return_type, name, params, local_vars, body)

    def _parse_param_list(self) -> list:
        """
        Parse zero or more  type name  separated by commas.
        Returns [(type, name), ...]
        """
        params = []
        if self._t.match(TokenType.SYMBOL, ')'):   # empty parameter list
            return params

        ptype = self._t.advance().value
        pname = self._t.expect(TokenType.IDENTIFIER).value
        params.append((ptype, pname))

        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            ptype = self._t.advance().value
            pname = self._t.expect(TokenType.IDENTIFIER).value
            params.append((ptype, pname))

        return params

    # ── Statements ────────────────────────────────────────────────────────────

    def _parse_statements(self) -> list:
        """Parse zero or more statements until we hit something that isn't one."""
        stmts = []
        stmt_starters = {'let', 'if', 'while', 'do', 'return'}
        while self._t.peek().value in stmt_starters:
            stmts.append(self._parse_statement())
        return stmts

    def _parse_statement(self):
        """Dispatch to the right statement parser based on keyword."""
        kw = self._t.peek().value
        if kw == 'let':    return self._parse_let()
        if kw == 'if':     return self._parse_if()
        if kw == 'while':  return self._parse_while()
        if kw == 'do':     return self._parse_do()
        if kw == 'return': return self._parse_return()
        tok = self._t.peek()
        raise ParseError(f"Unknown statement keyword '{kw}' at line {tok.line}")

    def _parse_let(self) -> LetNode:
        """let name [= expr] = expr;"""
        self._t.expect(TokenType.KEYWORD, 'let')
        name  = self._t.expect(TokenType.IDENTIFIER).value
        index = None

        # Optional array index:  name[expr]
        if self._t.match(TokenType.SYMBOL, '['):
            self._t.advance()
            index = self._parse_expression()
            self._t.expect(TokenType.SYMBOL, ']')

        self._t.expect(TokenType.SYMBOL, '=')
        expr = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ';')
        return LetNode(name, index, expr)

    def _parse_if(self) -> IfNode:
        """if (condition) { ... } [else { ... }]"""
        self._t.expect(TokenType.KEYWORD, 'if')
        self._t.expect(TokenType.SYMBOL, '(')
        cond = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ')')
        self._t.expect(TokenType.SYMBOL, '{')
        then_stmts = self._parse_statements()
        self._t.expect(TokenType.SYMBOL, '}')

        else_stmts = None
        if self._t.match(TokenType.KEYWORD, 'else'):
            self._t.advance()
            self._t.expect(TokenType.SYMBOL, '{')
            else_stmts = self._parse_statements()
            self._t.expect(TokenType.SYMBOL, '}')

        return IfNode(cond, then_stmts, else_stmts)

    def _parse_while(self) -> WhileNode:
        """while (condition) { ... }"""
        self._t.expect(TokenType.KEYWORD, 'while')
        self._t.expect(TokenType.SYMBOL, '(')
        cond = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ')')
        self._t.expect(TokenType.SYMBOL, '{')
        body = self._parse_statements()
        self._t.expect(TokenType.SYMBOL, '}')
        return WhileNode(cond, body)

    def _parse_do(self) -> DoNode:
        """do subroutineCall;  (return value is discarded)"""
        self._t.expect(TokenType.KEYWORD, 'do')
        call = self._parse_call()
        self._t.expect(TokenType.SYMBOL, ';')
        return DoNode(call)

    def _parse_return(self) -> ReturnNode:
        """return [expr];"""
        self._t.expect(TokenType.KEYWORD, 'return')
        expr = None
        if not self._t.match(TokenType.SYMBOL, ';'):
            expr = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ';')
        return ReturnNode(expr)

    # ── Expressions ───────────────────────────────────────────────────────────

    def _parse_expression(self):
        """
        expr := term (op term)*
        Handles binary operators: + - * / & | < > =
        """
        left = self._parse_term()
        while (self._t.match(TokenType.SYMBOL)
               and self._t.peek().value in _BINARY_OPS):
            op    = self._t.advance().value
            right = self._parse_term()
            left  = BinaryOpNode(op, left, right)
        return left

    def _parse_term(self):
        """
        Parse one atomic unit of an expression:
        integer, string, boolean, null, this, variable, array access, or call.
        """
        tok = self._t.peek()

        # Integer constant
        if tok.type == TokenType.INTEGER:
            self._t.advance()
            return IntegerNode(tok.value)

        # String constant
        if tok.type == TokenType.STRING:
            self._t.advance()
            return StringNode(tok.value)

        # true / false / null / this
        if tok.value == 'true':
            self._t.advance(); return BoolNode(True)
        if tok.value == 'false':
            self._t.advance(); return BoolNode(False)
        if tok.value == 'null':
            self._t.advance(); return NullNode()
        if tok.value == 'this':
            self._t.advance(); return ThisNode()

        # Parenthesised sub-expression:  ( expr )
        if tok.type == TokenType.SYMBOL and tok.value == '(':
            self._t.advance()
            expr = self._parse_expression()
            self._t.expect(TokenType.SYMBOL, ')')
            return expr

        # Unary operator:  -expr  or  ~expr
        if tok.type == TokenType.SYMBOL and tok.value in _UNARY_OPS:
            self._t.advance()
            operand = self._parse_term()
            return UnaryOpNode(tok.value, operand)

        # Identifier → could be a variable, array access, or function call
        if tok.type == TokenType.IDENTIFIER:
            name = self._t.advance().value

            # Array access:  name[expr]
            if self._t.match(TokenType.SYMBOL, '['):
                self._t.advance()
                index = self._parse_expression()
                self._t.expect(TokenType.SYMBOL, ']')
                return ArrayAccessNode(name, index)

            # Method call with dot:  name.method(args)
            if self._t.match(TokenType.SYMBOL, '.'):
                self._t.advance()
                method = self._t.expect(TokenType.IDENTIFIER).value
                self._t.expect(TokenType.SYMBOL, '(')
                args = self._parse_arg_list()
                self._t.expect(TokenType.SYMBOL, ')')
                return CallNode(name, method, args)

            # Function call without dot:  name(args)
            if self._t.match(TokenType.SYMBOL, '('):
                self._t.advance()
                args = self._parse_arg_list()
                self._t.expect(TokenType.SYMBOL, ')')
                return CallNode(None, name, args)

            # Just a plain variable reference
            return VarNode(name)

        raise ParseError(
            f"Unexpected token in expression: {tok!r} at line {tok.line}"
        )

    def _parse_call(self) -> CallNode:
        """Parse a standalone subroutine call (used by DoNode)."""
        name = self._t.expect(TokenType.IDENTIFIER).value
        obj, method = None, name

        if self._t.match(TokenType.SYMBOL, '.'):
            self._t.advance()
            obj    = name
            method = self._t.expect(TokenType.IDENTIFIER).value

        self._t.expect(TokenType.SYMBOL, '(')
        args = self._parse_arg_list()
        self._t.expect(TokenType.SYMBOL, ')')
        return CallNode(obj, method, args)

    def _parse_arg_list(self) -> list:
        """Parse a comma-separated list of expressions inside a call."""
        args = []
        if self._t.match(TokenType.SYMBOL, ')'):   # empty argument list
            return args
        args.append(self._parse_expression())
        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            args.append(self._parse_expression())
        return args
