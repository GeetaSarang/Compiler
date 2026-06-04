"""
vm_translator.py  —  VM Code → Hack Assembly (Stage 5)
=======================================================
Translates stack-based VM instructions into Hack Assembly language.

How each VM command maps to assembly:
  push constant N  →  load N into D, push D onto stack
  pop local N      →  compute address, store value there
  add              →  pop two values, push their sum
  sub              →  pop two values, push their difference
  neg              →  negate the top of the stack
  eq / lt / gt     →  comparison using conditional jumps
  label L          →  define a jump target (FUNCTION$L)
  goto L           →  unconditional jump
  if-goto L        →  pop top of stack, jump if non-zero
  function f n     →  define function f with n local variables
  call f n         →  save caller frame, jump to function f
  return           →  restore caller frame, return to caller

Hack register conventions:
  R13  — scratch register (used for target address in pop)
  R14  — stores FRAME during return
  R15  — stores return address during return

Usage:
    translator = VMTranslator()
    asm_code = translator.translate(vm_code_string)
"""


_SEG_BASE = {
    'local':    'LCL',
    'argument': 'ARG',
    'this':     'THIS',
    'that':     'THAT',
}


class VMTranslator:
    """
    Converts VM source code (one instruction per line) into Hack Assembly.

    Bootstrap code (SP=256, call Sys.init) is added at the top automatically.
    """

    def __init__(self):
        self._out:      list = []
        self._lbl_cnt:  int  = 0
        self._cur_func: str  = 'GLOBAL'   # current function name (for label scoping)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _emit(self, *lines: str):
        self._out.extend(lines)

    def _new_label(self) -> str:
        """Make a unique label that won't clash with user labels."""
        lbl = f'VM_L{self._lbl_cnt}'
        self._lbl_cnt += 1
        return lbl

    # ── Public interface ──────────────────────────────────────────────────────

    def translate(self, vm_code: str) -> str:
        """
        Translate a string of VM instructions into Hack Assembly.
        Returns the assembly source as a string.
        """
        self._emit_bootstrap()

        for raw_line in vm_code.splitlines():
            # Strip inline comments and whitespace
            line = raw_line.split('//')[0].strip()
            if not line:
                continue
            self._emit(f'// {line}')   # echo VM instruction as comment (helps debugging)
            self._translate_line(line)

        return '\n'.join(self._out)

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    def _emit_bootstrap(self):
        """
        The Hack computer starts execution at ROM address 0.
        Bootstrap code sets up the stack pointer and calls Sys.init.
        """
        self._emit(
            '// === Bootstrap: SP = 256, call Sys.init ===',
            '@256', 'D=A', '@SP', 'M=D',
        )
        self._emit(*self._call_asm('Sys.init', 0, ret_label='BOOTSTRAP_RET'))

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _translate_line(self, line: str):
        """Parse one VM instruction and emit the corresponding assembly."""
        parts = line.split()
        cmd   = parts[0]

        if cmd == 'push':
            self._gen_push(parts[1], int(parts[2]))
        elif cmd == 'pop':
            self._gen_pop(parts[1], int(parts[2]))
        elif cmd in ('add', 'sub', 'and', 'or'):
            self._gen_binary(cmd)
        elif cmd in ('neg', 'not'):
            self._gen_unary(cmd)
        elif cmd in ('lt', 'gt', 'eq'):
            self._gen_compare(cmd)
        elif cmd == 'label':
            # Labels are scoped to the current function:  function$label
            self._emit(f'({self._cur_func}${parts[1]})')
        elif cmd == 'goto':
            self._emit(f'@{self._cur_func}${parts[1]}', '0;JMP')
        elif cmd == 'if-goto':
            # Pop top of stack; jump if it's non-zero (true)
            self._emit(
                '@SP', 'AM=M-1', 'D=M',
                f'@{self._cur_func}${parts[1]}', 'D;JNE',
            )
        elif cmd == 'function':
            self._gen_function(parts[1], int(parts[2]))
        elif cmd == 'call':
            self._emit(*self._call_asm(parts[1], int(parts[2])))
        elif cmd == 'return':
            self._gen_return()
        else:
            raise ValueError(f"Unknown VM command: {line!r}")

    # ── Push / Pop ────────────────────────────────────────────────────────────

    def _gen_push(self, segment: str, index: int):
        """
        Load the value from segment[index] into D,
        then push D onto the stack.
        """
        if segment == 'constant':
            # 'constant' is not a real memory segment — just the literal value
            self._emit(f'@{index}', 'D=A')

        elif segment in _SEG_BASE:
            # local, argument, this, that:  D = *(base + index)
            base = _SEG_BASE[segment]
            self._emit(f'@{base}', 'D=M', f'@{index}', 'A=D+A', 'D=M')

        elif segment == 'temp':
            # temp N → RAM[5 + N]
            self._emit(f'@{5 + index}', 'D=M')

        elif segment == 'pointer':
            # pointer 0 = THIS,  pointer 1 = THAT
            reg = 'THIS' if index == 0 else 'THAT'
            self._emit(f'@{reg}', 'D=M')

        elif segment == 'static':
            # static N → a symbol  FunctionName.N  (linker assigns the address)
            self._emit(f'@{self._cur_func}.{index}', 'D=M')

        else:
            raise ValueError(f"Unknown push segment: '{segment}'")

        # Push D onto the stack
        self._emit('@SP', 'A=M', 'M=D', '@SP', 'M=M+1')

    def _gen_pop(self, segment: str, index: int):
        """
        Compute the target address, save it in R13,
        then pop the stack value and store it there.
        """
        if segment in _SEG_BASE:
            base = _SEG_BASE[segment]
            self._emit(f'@{base}', 'D=M', f'@{index}', 'D=D+A', '@R13', 'M=D')

        elif segment == 'temp':
            self._emit(f'@{5 + index}', 'D=A', '@R13', 'M=D')

        elif segment == 'pointer':
            reg = 'THIS' if index == 0 else 'THAT'
            self._emit(f'@{reg}', 'D=A', '@R13', 'M=D')

        elif segment == 'static':
            self._emit(f'@{self._cur_func}.{index}', 'D=A', '@R13', 'M=D')

        else:
            raise ValueError(f"Unknown pop segment: '{segment}'")

        # Pop stack top into address stored in R13
        self._emit('@SP', 'AM=M-1', 'D=M', '@R13', 'A=M', 'M=D')

    # ── Arithmetic / Logic ────────────────────────────────────────────────────

    def _gen_binary(self, op: str):
        """
        Binary operations: pop y, peek x, replace x with (x op y).
        This avoids a second pop+push by operating in-place on the stack.
        """
        compute = {'add': 'D+M', 'sub': 'M-D', 'and': 'D&M', 'or': 'D|M'}[op]
        self._emit(
            '@SP', 'AM=M-1', 'D=M',   # pop y → D;  SP now points to x
            'A=A-1',                   # point to x (one below current top)
            f'M={compute}',            # overwrite x with x op y
        )

    def _gen_unary(self, op: str):
        """Unary operations: negate or bitwise-NOT the top of the stack."""
        expr = '-M' if op == 'neg' else '!M'
        self._emit('@SP', 'A=M-1', f'M={expr}')

    def _gen_compare(self, op: str):
        """
        Comparison operations: pop two, push -1 (true) or 0 (false).
        Uses conditional jumps with unique labels.
        """
        true_lbl = self._new_label()
        end_lbl  = self._new_label()
        jump     = {'lt': 'JLT', 'gt': 'JGT', 'eq': 'JEQ'}[op]

        self._emit(
            '@SP', 'AM=M-1', 'D=M',        # pop y
            'A=A-1', 'D=M-D',              # D = x - y
            f'@{true_lbl}', f'D;{jump}',   # jump to true_lbl if condition holds
            '@SP', 'A=M-1', 'M=0',         # false → push 0
            f'@{end_lbl}', '0;JMP',
            f'({true_lbl})',
            '@SP', 'A=M-1', 'M=-1',        # true → push -1
            f'({end_lbl})',
        )

    # ── Function / Call / Return ──────────────────────────────────────────────

    def _gen_function(self, name: str, n_locals: int):
        """
        function f n  —  define function f with n local variables.
        Locals are initialised to 0.
        """
        self._cur_func = name
        self._emit(f'// function {name} {n_locals}', f'({name})')
        for _ in range(n_locals):
            # Push 0 onto stack n times (fills the local segment with zeros)
            self._emit('@SP', 'A=M', 'M=0', '@SP', 'M=M+1')

    def _call_asm(self, func: str, n_args: int, ret_label: str = None) -> list:
        """
        Return a list of assembly lines implementing a VM call.

        What happens:
          1. Push return address (label after the call)
          2. Push caller's LCL, ARG, THIS, THAT (save frame)
          3. Reposition ARG to point at the first argument
          4. Set LCL = SP (new local frame)
          5. Jump to the function
          6. Place the return address label here
        """
        if ret_label is None:
            ret_label = f'{self._cur_func}$ret.{self._new_label()}'

        return [
            # Push return address
            f'@{ret_label}', 'D=A', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Save caller's LCL
            '@LCL',  'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Save caller's ARG
            '@ARG',  'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Save caller's THIS
            '@THIS', 'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Save caller's THAT
            '@THAT', 'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # ARG = SP - 5 - n_args  (point ARG at the first argument)
            f'@{n_args + 5}', 'D=A', '@SP', 'D=M-D', '@ARG', 'M=D',
            # LCL = SP  (start of new local frame)
            '@SP', 'D=M', '@LCL', 'M=D',
            # Jump to the function body
            f'@{func}', '0;JMP',
            # Return address label (execution resumes here after the call)
            f'({ret_label})',
        ]

    def _gen_return(self):
        """
        Return from the current function to the caller.

        Steps:
          1. FRAME = LCL  (save local frame base in R14)
          2. RET = *(FRAME - 5)  (retrieve the return address into R15)
          3. *ARG = pop()  (place return value where caller expects it)
          4. SP = ARG + 1  (shrink stack back to caller's top)
          5. Restore THAT, THIS, ARG, LCL from saved frame
          6. Jump to RET
        """
        self._emit(
            # FRAME → R14
            '@LCL', 'D=M', '@R14', 'M=D',
            # RET = *(FRAME - 5) → R15
            '@5', 'A=D-A', 'D=M', '@R15', 'M=D',
            # *ARG = return value
            '@SP', 'AM=M-1', 'D=M', '@ARG', 'A=M', 'M=D',
            # SP = ARG + 1
            '@ARG', 'D=M+1', '@SP', 'M=D',
            # Restore THAT = *(FRAME-1)
            '@R14', 'AM=M-1', 'D=M', '@THAT', 'M=D',
            # Restore THIS = *(FRAME-2)
            '@R14', 'AM=M-1', 'D=M', '@THIS', 'M=D',
            # Restore ARG = *(FRAME-3)
            '@R14', 'AM=M-1', 'D=M', '@ARG',  'M=D',
            # Restore LCL = *(FRAME-4)
            '@R14', 'AM=M-1', 'D=M', '@LCL',  'M=D',
            # Jump to return address
            '@R15', 'A=M', '0;JMP',
        )
