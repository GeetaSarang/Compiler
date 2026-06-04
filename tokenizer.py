"""
tokenizer.py  —  SimpleScript Lexer (Stage 1)
==============================================
Converts raw SimpleScript source code into a flat list of Tokens.

SimpleScript keyword list:
  class, function, method, constructor,
  if, else, while, return,
  int, boolean, char, void,
  var, let, do,
  true, false, null, this, static

Usage:
    t = Tokenizer(source_code)
    while not t.is_eof():
        print(t.advance())
"""

from enum import Enum, auto


# ── Token Types ──────────────────────────────────────────────────────────────

class TokenType(Enum):
    KEYWORD    = auto()   # reserved words like 'if', 'while', 'int'
    SYMBOL     = auto()   # punctuation like '{', '(', '+'
    INTEGER    = auto()   # whole numbers 0-32767
    STRING     = auto()   # text in double quotes "hello"
    IDENTIFIER = auto()   # variable / class names
    EOF        = auto()   # end of file marker


# All reserved keywords in SimpleScript
KEYWORDS = {
    'class', 'function', 'method', 'constructor',
    'if', 'else', 'while', 'return',
    'int', 'boolean', 'char', 'void',
    'var', 'let', 'do',
    'true', 'false', 'null', 'this', 'static',
}

# All valid single-character symbols
SYMBOLS = set('{}()[].,;+-*/&|<>=~')


# ── Token class ──────────────────────────────────────────────────────────────

class Token:
    """Represents a single unit of source code (e.g. the word 'if', or '(')."""

    def __init__(self, type_: TokenType, value, line: int = 0):
        self.type  = type_
        self.value = value
        self.line  = line   # line number in source (helps with error messages)

    def __repr__(self):
        return f'Token({self.type.name}, {self.value!r}, line={self.line})'


class TokenizerError(Exception):
    """Raised when the tokenizer finds something it cannot understand."""
    pass


# ── Tokenizer class ──────────────────────────────────────────────────────────

class Tokenizer:
    """
    Scans SimpleScript source text and produces a list of Token objects.

    The constructor does all the scanning immediately. Afterwards you use
    peek() / advance() / expect() to walk through the token stream.
    """

    def __init__(self, source: str):
        self._tokens: list[Token] = []
        self._pos = 0           # current read position in _tokens list
        self._scan(source)      # fill _tokens during construction

    # ── Private: scan the whole source string ────────────────────────────────

    def _scan(self, src: str):
        """Walk character-by-character through 'src' and build self._tokens."""
        i, line = 0, 1          # i = character index, line = current line number
        n = len(src)

        while i < n:
            c = src[i]

            # --- Skip whitespace ---
            if c in ' \t\r':
                i += 1
                continue
            if c == '\n':
                line += 1
                i += 1
                continue

            # --- Skip single-line comments  // ... ---
            if src[i:i+2] == '//':
                while i < n and src[i] != '\n':
                    i += 1
                continue

            # --- Skip multi-line comments  /* ... */ ---
            if src[i:i+2] == '/*':
                i += 2
                while i < n - 1 and src[i:i+2] != '*/':
                    if src[i] == '\n':
                        line += 1
                    i += 1
                i += 2          # skip the closing '*/'
                continue

            # --- String literal  "..." ---
            if c == '"':
                j = i + 1
                while j < n and src[j] != '"':
                    if src[j] == '\n':
                        raise TokenizerError(
                            f"Unterminated string literal at line {line}"
                        )
                    j += 1
                self._tokens.append(Token(TokenType.STRING, src[i+1:j], line))
                i = j + 1
                continue

            # --- Symbol  ( ) { } [ ] . , ; + - * / & | < > = ~ ---
            if c in SYMBOLS:
                self._tokens.append(Token(TokenType.SYMBOL, c, line))
                i += 1
                continue

            # --- Integer constant  0 .. 32767 ---
            if c.isdigit():
                j = i
                while j < n and src[j].isdigit():
                    j += 1
                val = int(src[i:j])
                if val > 32767:
                    raise TokenizerError(
                        f"Integer {val} exceeds maximum value 32767 at line {line}"
                    )
                self._tokens.append(Token(TokenType.INTEGER, val, line))
                i = j
                continue

            # --- Keyword or identifier  [a-zA-Z_][a-zA-Z0-9_]* ---
            if c.isalpha() or c == '_':
                j = i
                while j < n and (src[j].isalnum() or src[j] == '_'):
                    j += 1
                word = src[i:j]
                tok_type = TokenType.KEYWORD if word in KEYWORDS else TokenType.IDENTIFIER
                self._tokens.append(Token(tok_type, word, line))
                i = j
                continue

            # --- Nothing matched — unknown character ---
            raise TokenizerError(
                f"Unknown character {c!r} at line {line}"
            )

        # Always end with an EOF marker
        self._tokens.append(Token(TokenType.EOF, None, line))

    # ── Public stream interface ───────────────────────────────────────────────

    def peek(self) -> Token:
        """Look at the current token without moving forward."""
        return self._tokens[self._pos]

    def advance(self) -> Token:
        """Return the current token and move to the next one."""
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def expect(self, type_: TokenType = None, value=None) -> Token:
        """
        Consume and return the current token.
        Raises SyntaxError if it doesn't match the expected type/value.
        """
        tok = self.advance()
        if type_ is not None and tok.type != type_:
            raise SyntaxError(
                f"Expected {type_.name} but got {tok.type.name} "
                f"({tok.value!r}) at line {tok.line}"
            )
        if value is not None and tok.value != value:
            raise SyntaxError(
                f"Expected '{value}' but got '{tok.value}' at line {tok.line}"
            )
        return tok

    def match(self, type_: TokenType = None, value=None) -> bool:
        """Return True if the current token matches type and/or value (does NOT consume it)."""
        tok = self.peek()
        if type_ is not None and tok.type != type_:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def is_eof(self) -> bool:
        """Return True when all tokens have been consumed."""
        return self.peek().type == TokenType.EOF

    def all_tokens(self) -> list[Token]:
        """Return a copy of every token (useful for debugging)."""
        return list(self._tokens)
