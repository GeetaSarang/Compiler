"""
assembler.py  —  Hack Assembly → 16-bit Binary Machine Code (Stage 6)
======================================================================
Converts Hack Assembly (.asm) into binary machine code (.hack).

Two-pass algorithm:
  Pass 1 — scan for label declarations like (LOOP) and record their ROM address.
  Pass 2 — convert each instruction to a 16-bit binary string.

Instruction formats (Hack architecture):
  A-instruction:  @value         →  0vvvvvvvvvvvvvvv
                                    (bit 15 = 0, bits 0-14 = address/constant)

  C-instruction:  [dest=]comp[;jump]  →  111accccccdddjjj
                                          (bits 15-13 = 111)

Predefined symbols:
  SP=0, LCL=1, ARG=2, THIS=3, THAT=4
  R0-R15 (RAM registers 0-15)
  SCREEN=16384, KBD=24576

Variable allocation:
  Any symbol in an @instruction that isn't predefined or a label
  gets assigned to the next available RAM address starting at 16.

Usage:
    asm = Assembler()
    binary_code = asm.assemble(assembly_source_string)
"""


class AssemblerError(Exception):
    """Raised when the assembler encounters bad input."""
    pass


class Assembler:
    """
    Two-pass Hack assembler.

    Pass 1 builds the symbol table (labels → ROM addresses).
    Pass 2 translates each instruction to 16-bit binary.
    """

    # Predefined symbols from the Hack specification
    _PREDEFINED: dict = {
        'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
        **{f'R{i}': i for i in range(16)},   # R0 through R15
        'SCREEN': 16384,
        'KBD':    24576,
    }

    # dest field: 3 bits  (which register(s) to write the result into)
    _DEST: dict = {
        '':    '000',   # don't store
        'M':   '001',   # store in RAM[A]
        'D':   '010',   # store in D register
        'MD':  '011',   # store in RAM[A] and D
        'A':   '100',   # store in A register
        'AM':  '101',   # store in A and RAM[A]
        'AD':  '110',   # store in A and D
        'AMD': '111',   # store in A, RAM[A], and D
    }

    # jump field: 3 bits  (condition for jumping to ROM[A])
    _JUMP: dict = {
        '':    '000',   # never jump
        'JGT': '001',   # jump if result > 0
        'JEQ': '010',   # jump if result = 0
        'JGE': '011',   # jump if result >= 0
        'JLT': '100',   # jump if result < 0
        'JNE': '101',   # jump if result ≠ 0
        'JLE': '110',   # jump if result <= 0
        'JMP': '111',   # always jump
    }

    # comp field: 7 bits  (what the ALU computes: 'a' bit + 6 control bits)
    _COMP: dict = {
        '0':   '0101010',
        '1':   '0111111',
        '-1':  '0111010',
        'D':   '0001100',
        'A':   '0110000',
        '!D':  '0001101',
        '!A':  '0110001',
        '-D':  '0001111',
        '-A':  '0110011',
        'D+1': '0011111',
        'A+1': '0110111',
        'D-1': '0001110',
        'A-1': '0110010',
        'D+A': '0000010',
        'D-A': '0010011',
        'A-D': '0000111',
        'D&A': '0000000',
        'D|A': '0010101',
        # 'a' bit = 1 → use M (RAM[A]) instead of A register
        'M':   '1110000',
        '!M':  '1110001',
        '-M':  '1110011',
        'M+1': '1110111',
        'M-1': '1110010',
        'D+M': '1000010',
        'D-M': '1010011',
        'M-D': '1000111',
        'D&M': '1000000',
        'D|M': '1010101',
    }

    # ── Public interface ──────────────────────────────────────────────────────

    def assemble(self, asm_source: str) -> str:
        """
        Assemble Hack Assembly source into binary machine code.
        Returns a string of 16-character binary lines (one per instruction).
        """
        clean_lines = self._clean(asm_source)
        symbols     = self._first_pass(clean_lines)
        binary      = self._second_pass(clean_lines, symbols)
        return '\n'.join(binary)

    # ── Pass 1: build symbol table ────────────────────────────────────────────

    def _clean(self, source: str) -> list[str]:
        """Remove comments and blank lines from the assembly source."""
        result = []
        for line in source.splitlines():
            line = line.split('//')[0].strip()
            if line:
                result.append(line)
        return result

    def _first_pass(self, lines: list[str]) -> dict:
        """
        Scan for label declarations of the form  (LABEL_NAME)
        and record their ROM address (the line number of the NEXT instruction).
        Returns the full symbol table.
        """
        symbols  = dict(self._PREDEFINED)
        rom_addr = 0   # labels get the address of the instruction that follows them

        for line in lines:
            if line.startswith('(') and line.endswith(')'):
                label = line[1:-1]
                if label in symbols:
                    raise AssemblerError(f"Duplicate label definition: '{label}'")
                symbols[label] = rom_addr
                # Labels are not instructions, so don't increment rom_addr
            else:
                rom_addr += 1

        return symbols

    # ── Pass 2: translate instructions ───────────────────────────────────────

    def _second_pass(self, lines: list[str], symbols: dict) -> list[str]:
        """
        Translate each instruction to 16-bit binary.
        New variable symbols are assigned RAM addresses starting at 16.
        """
        binary   = []
        var_addr = 16   # next free RAM slot for variables

        for line in lines:

            # Skip label declarations — they produce no instructions
            if line.startswith('('):
                continue

            if line.startswith('@'):
                # ── A-instruction:  @value ──────────────────────────────────
                sym = line[1:]

                if sym.isdigit():
                    # Numeric literal  e.g.  @42
                    addr = int(sym)
                elif sym in symbols:
                    # Known symbol (predefined or declared label)
                    addr = symbols[sym]
                else:
                    # New variable — allocate the next RAM slot
                    symbols[sym] = var_addr
                    addr = var_addr
                    var_addr += 1

                if addr > 32767:
                    raise AssemblerError(
                        f"Address {addr} exceeds the 15-bit limit (max 32767)"
                    )
                # Format as 16-bit binary with leading zeros
                binary.append(f'{addr:016b}')

            else:
                # ── C-instruction:  [dest=]comp[;jump] ──────────────────────
                dest, comp, jump = '', line, ''

                if '=' in line:
                    dest, comp = line.split('=', 1)
                if ';' in comp:
                    comp, jump = comp.split(';', 1)

                comp = comp.strip()
                dest = dest.strip()
                jump = jump.strip()

                if comp not in self._COMP:
                    raise AssemblerError(f"Unknown comp mnemonic: '{comp}'")
                if dest not in self._DEST:
                    raise AssemblerError(f"Unknown dest mnemonic: '{dest}'")
                if jump not in self._JUMP:
                    raise AssemblerError(f"Unknown jump mnemonic: '{jump}'")

                # Encode: 111 + 7-bit comp + 3-bit dest + 3-bit jump
                bits = '111' + self._COMP[comp] + self._DEST[dest] + self._JUMP[jump]
                binary.append(bits)

        return binary

    # ── Utility: decode a binary word (for debugging) ─────────────────────────

    @staticmethod
    def decode(word: str) -> str:
        """
        Decode a 16-bit binary string back into a human-readable instruction.
        Useful for inspecting compiler output.

        Example:
            Assembler.decode('0000000000000101')  →  'A-instruction: @5'
            Assembler.decode('1110110000010000')  →  'C-instruction: D=A'
        """
        if len(word) != 16 or not all(c in '01' for c in word):
            return f'INVALID word: {word!r}'

        val = int(word, 2)

        if word[0] == '0':
            return f'A-instruction: @{val}'

        # C-instruction — reverse-lookup comp, dest, jump
        _DEST_REV = {v: k for k, v in Assembler._DEST.items()}
        _JUMP_REV = {v: k for k, v in Assembler._JUMP.items()}
        _COMP_REV = {v: k for k, v in Assembler._COMP.items()}

        comp = _COMP_REV.get(word[3:10], '???')
        dest = _DEST_REV.get(word[10:13], '???')
        jump = _JUMP_REV.get(word[13:16], '???')

        expr = f'{dest}={comp}' if dest else comp
        if jump:
            expr += f';{jump}'
        return f'C-instruction: {expr}'
