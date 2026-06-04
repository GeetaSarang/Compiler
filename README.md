# SimpleScript Compiler
### A College-Level Compiler Project in Python

---

## What is this?

A **complete compiler** written in Python that translates SimpleScript (`.ss`) source code
all the way down to 16-bit binary machine code.

```
Source Code (.ss)
      ↓  Tokenizer       — splits source into words/symbols (tokens)
      ↓  Parser          — builds a tree structure from tokens (AST)
      ↓  Code Generator  — converts tree into stack-machine VM code
      ↓  VM Translator   — converts VM code into Hack Assembly
      ↓  Assembler       — converts Assembly into binary machine code (.hack)
Binary Machine Code (.hack)
```

---

## Files

| File | Stage | What it does |
|------|-------|--------------|
| `tokenizer.py` | Stage 1 | Breaks source code into Tokens |
| `syntax_tree.py` | Stage 2 | Defines all AST node classes |
| `parser.py` | Stage 3 | Builds the AST from tokens |
| `code_generator.py` | Stage 4 | Walks the AST and emits VM code |
| `vm_translator.py` | Stage 5 | Translates VM code → Hack Assembly |
| `assembler.py` | Stage 6 | Translates Assembly → 16-bit binary |
| `compiler.py` | Main | Wires all stages together + CLI |
| `example.ss` | Example | Sample SimpleScript source program |

---

## Quick Start

No installation needed — just Python 3.10+.

```bash
# Compile the example program (all 5 stages)
python compiler.py example.ss

# See what each stage produces
python compiler.py example.ss --verbose

# Stop after a specific stage
python compiler.py example.ss --stage tokenize
python compiler.py example.ss --stage parse
python compiler.py example.ss --stage codegen
python compiler.py example.ss --stage vmtranslate
python compiler.py example.ss --stage assemble
```

---

## SimpleScript Language

SimpleScript is a small class-based language. Here is the syntax:

### Class structure
```
class ClassName {
    static int count;                  // class-level variable

    function int add(int a, int b) {   // static function
        var int result;                // local variable
        let result = a + b;
        return result;
    }

    method void reset() {              // instance method
        let count = 0;
        return;
    }
}
```

### Statements
| Statement | Example |
|-----------|---------|
| Assignment | `let x = 5;` |
| Array write | `let arr[i] = 10;` |
| If/else | `if (x > 0) { ... } else { ... }` |
| While loop | `while (x < 10) { ... }` |
| Call (discard result) | `do Output.printInt(x);` |
| Return | `return x;`  or  `return;` |

### Types
`int`, `boolean`, `char`, `void`, and any class name.

### Operators
`+` `-` `*` `/` `&` `|` `<` `>` `=` `~` (bitwise NOT) `-` (negate)

### Constants
`true`, `false`, `null`, `this`, integer literals, string literals

---

## How each stage works

### Stage 1 — Tokenizer (`tokenizer.py`)
Reads the source character by character and groups characters into meaningful
units called **tokens**. For example:

```
let x = 42;
→  Token(KEYWORD, 'let')
   Token(IDENTIFIER, 'x')
   Token(SYMBOL, '=')
   Token(INTEGER, 42)
   Token(SYMBOL, ';')
```

### Stage 2 — Syntax Tree (`syntax_tree.py`)
Defines Python classes for every kind of node in the **Abstract Syntax Tree (AST)**.
The AST is a tree that represents the program structure. For example:

```
let x = a + 1;
→  LetNode(name='x', expr=BinaryOpNode('+', VarNode('a'), IntegerNode(1)))
```

### Stage 3 — Parser (`parser.py`)
A **recursive-descent parser** that reads the token stream and builds an AST.
Each grammar rule becomes one Python method.

### Stage 4 — Code Generator (`code_generator.py`)
Walks the AST and emits **VM (stack machine) instructions**. Contains a
symbol table to track where each variable lives in memory.

```
let x = a + 1;
→  push local 0    (push 'a')
   push constant 1
   add
   pop local 1     (store into 'x')
```

### Stage 5 — VM Translator (`vm_translator.py`)
Translates VM instructions into **Hack Assembly language**:

```
push constant 42  →  @42
                     D=A
                     @SP
                     A=M
                     M=D
                     @SP
                     M=M+1
```

### Stage 6 — Assembler (`assembler.py`)
Two-pass assembler. Pass 1 finds all label declarations and their addresses.
Pass 2 encodes each instruction as a **16-bit binary string**:

```
@42      →  0000000000101010
D=A      →  1110110000010000
```

---

## Writing your own SimpleScript program

1. Create a file called `MyProgram.ss`
2. Write a class with the same name as the file:

```
class MyProgram {
    function int double(int n) {
        return n * 2;
    }

    function void main() {
        var int result;
        let result = MyProgram.double(21);
        do Output.printInt(result);
        return;
    }
}
```

3. Compile it:
```bash
python compiler.py MyProgram.ss --verbose
```

---

## Requirements

- Python 3.10 or newer
- No external libraries needed (standard library only)
