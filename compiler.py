"""
compiler.py  —  SimpleScript Compiler  (main entry point)
==========================================================
Runs the full compilation pipeline:

  .ss  ─[Tokenizer]──►  Tokens
       ─[Parser]─────►  AST (Abstract Syntax Tree)
       ─[CodeGen]────►  VM Code        (.vm)
       ─[VMTranslator]► Hack Assembly  (.asm)
       ─[Assembler]──►  Machine Code   (.hack)

Usage:
  python compiler.py <source.ss>                      # full pipeline
  python compiler.py <source.ss> --stage tokenize     # stop after tokenizing
  python compiler.py <source.ss> --stage parse        # stop after parsing
  python compiler.py <source.ss> --stage codegen      # stop after code generation
  python compiler.py <source.ss> --stage vmtranslate  # stop after VM→ASM
  python compiler.py <source.ss> --stage assemble     # full (default)
  python compiler.py <source.ss> --verbose            # print detailed output

Example:
  python compiler.py example.ss --verbose
"""

import sys
import os
import argparse
import time

from tokenizer      import Tokenizer
from parser         import Parser
from code_generator import CodeGenerator
from vm_translator  import VMTranslator
from assembler      import Assembler


# ── Color helpers (ANSI escape codes, degrade gracefully on Windows) ──────────

_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f'\033[{code}m{text}\033[0m' if _USE_COLOR else text

def ok(msg):   print(_c('32', '  ✓ ') + msg)
def info(msg): print(_c('36', '  » ') + msg)
def err(msg):  print(_c('31', '  ✗ ') + msg, file=sys.stderr)
def hdr(msg):  print('\n' + _c('1;34', msg))


# ── Pipeline stages ───────────────────────────────────────────────────────────

def stage_tokenize(source: str, verbose: bool):
    hdr('[1/5]  Tokenizer  —  source code → token stream')
    t0 = time.perf_counter()
    tokenizer = Tokenizer(source)
    elapsed   = time.perf_counter() - t0
    tokens    = tokenizer.all_tokens()
    ok(f'{len(tokens) - 1} tokens produced  ({elapsed*1000:.1f} ms)')
    if verbose:
        for tok in tokens[:-1]:    # skip the EOF token
            info(str(tok))
    return tokenizer


def stage_parse(tokenizer: Tokenizer, verbose: bool):
    hdr('[2/5]  Parser  —  tokens → Abstract Syntax Tree (AST)')
    t0  = time.perf_counter()
    ast = Parser(tokenizer).parse()
    elapsed = time.perf_counter() - t0
    ok(f'Class "{ast.name}" parsed  ({elapsed*1000:.1f} ms)')
    ok(f'{len(ast.subroutines)} subroutine(s),  {len(ast.static_vars)} static variable(s)')
    if verbose:
        for sub in ast.subroutines:
            info(f'  {sub.kind}  {sub.return_type}  {sub.name}()'
                 f'  [{len(sub.params)} param(s), {len(sub.local_vars)} local(s)]')
    return ast


def stage_codegen(ast, base_path: str, verbose: bool) -> str:
    hdr('[3/5]  Code Generator  —  AST → VM Code')
    t0      = time.perf_counter()
    vm_code = CodeGenerator().generate(ast)
    elapsed = time.perf_counter() - t0

    vm_path = base_path + '.vm'
    with open(vm_path, 'w', encoding='utf-8') as f:
        f.write(vm_code)

    lines = [l for l in vm_code.splitlines() if l.strip()]
    ok(f'{len(lines)} VM instructions  →  {vm_path}  ({elapsed*1000:.1f} ms)')
    if verbose:
        for line in lines:
            info(f'  {line}')
    return vm_code


def stage_vmtranslate(vm_code: str, base_path: str, verbose: bool) -> str:
    hdr('[4/5]  VM Translator  —  VM Code → Hack Assembly')
    t0       = time.perf_counter()
    asm_code = VMTranslator().translate(vm_code)
    elapsed  = time.perf_counter() - t0

    asm_path = base_path + '.asm'
    with open(asm_path, 'w', encoding='utf-8') as f:
        f.write(asm_code)

    lines = [l for l in asm_code.splitlines() if l.strip()]
    ok(f'{len(lines)} assembly lines  →  {asm_path}  ({elapsed*1000:.1f} ms)')
    if verbose:
        for line in lines[:60]:
            info(f'  {line}')
        if len(lines) > 60:
            info(f'  … ({len(lines) - 60} more lines)')
    return asm_code


def stage_assemble(asm_code: str, base_path: str, verbose: bool) -> str:
    hdr('[5/5]  Assembler  —  Hack Assembly → Binary Machine Code')
    t0           = time.perf_counter()
    machine_code = Assembler().assemble(asm_code)
    elapsed      = time.perf_counter() - t0

    hack_path = base_path + '.hack'
    with open(hack_path, 'w', encoding='utf-8') as f:
        f.write(machine_code)

    n = len([l for l in machine_code.splitlines() if l.strip()])
    ok(f'{n} machine-code words  →  {hack_path}  ({elapsed*1000:.1f} ms)')

    if verbose:
        lines = machine_code.splitlines()[:10]
        for line in lines:
            decoded = Assembler.decode(line)
            info(f'  {line}   ← {decoded}')
        if n > 10:
            info(f'  … ({n - 10} more words)')
    return machine_code


# ── Full compile ──────────────────────────────────────────────────────────────

def compile_file(source_path: str, stop_at: str = 'assemble', verbose: bool = False):
    # Read source file
    if not os.path.isfile(source_path):
        err(f"File not found: {source_path}")
        sys.exit(1)
    if not source_path.endswith('.ss'):
        err(f"Expected a .ss (SimpleScript) file, got: {source_path}")
        sys.exit(1)

    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    base = os.path.splitext(source_path)[0]

    print(_c('1;35', '\n╔══════════════════════════════════════╗'))
    print(_c('1;35', '║     SimpleScript Compiler  v1.0      ║'))
    print(_c('1;35', '╚══════════════════════════════════════╝'))
    print(f'  Source : {source_path}')
    print(f'  Size   : {len(source)} characters')

    try:
        t_total = time.perf_counter()

        tokenizer = stage_tokenize(source, verbose)
        if stop_at == 'tokenize': return

        ast = stage_parse(tokenizer, verbose)
        if stop_at == 'parse': return

        vm_code = stage_codegen(ast, base, verbose)
        if stop_at == 'codegen': return

        asm_code = stage_vmtranslate(vm_code, base, verbose)
        if stop_at == 'vmtranslate': return

        stage_assemble(asm_code, base, verbose)

        elapsed_total = time.perf_counter() - t_total
        print(_c('1;32', f'\n  ✅  Compilation successful!  ({elapsed_total*1000:.1f} ms total)\n'))
        print('  Output files:')
        print(f'    {base}.vm    — VM (stack-machine) code')
        print(f'    {base}.asm   — Hack Assembly')
        print(f'    {base}.hack  — Binary machine code\n')

    except SyntaxError as e:
        err(f'Syntax error: {e}')
        sys.exit(2)
    except NameError as e:
        err(f'Name error: {e}')
        sys.exit(2)
    except Exception as e:
        err(f'Compilation failed: {e}')
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(3)


# ── Command-line interface ────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog='compiler',
        description='SimpleScript compiler — compile .ss source files to machine code.',
    )
    ap.add_argument('source', help='Path to the .ss source file')
    ap.add_argument(
        '--stage',
        choices=['tokenize', 'parse', 'codegen', 'vmtranslate', 'assemble'],
        default='assemble',
        help='Stop the pipeline after this stage (default: assemble = full compile)',
    )
    ap.add_argument(
        '--verbose', '-v', action='store_true',
        help='Print detailed output for each stage',
    )
    args = ap.parse_args()
    compile_file(args.source, stop_at=args.stage, verbose=args.verbose)


if __name__ == '__main__':
    main()
