// ============================================================
//  example.ss  —  Sample SimpleScript Program
//
//  This program demonstrates the language syntax:
//    - local and static variables
//    - while loop
//    - if / else condition
//    - function calls with arguments
//    - return values
// ============================================================

class Calculator {

    // Static variable shared across all functions in this class
    static int counter;

    // ── Compute the sum  1 + 2 + ... + n ─────────────────────
    function int sum(int n) {
        var int total;
        var int i;

        let total = 0;
        let i = 1;

        while (i < n) {
            let total = total + i;
            let i = i + 1;
        }
        let total = total + n;   // include n itself
        return total;
    }

    // ── Return the larger of two integers ────────────────────
    function int maximum(int a, int b) {
        if (a > b) {
            return a;
        } else {
            return b;
        }
    }

    // ── Compute n! (factorial) recursively ───────────────────
    function int factorial(int n) {
        if (n < 2) {
            return 1;
        }
        return n * Calculator.factorial(n - 1);
    }

    // ── Main entry point ──────────────────────────────────────
    function void main() {
        var int s;
        var int m;
        var int f;

        // Sum of 1..10 = 55
        let s = Calculator.sum(10);

        // Maximum of 42 and 17 = 42
        let m = Calculator.maximum(42, 17);

        // 5! = 120
        let f = Calculator.factorial(5);

        // Increment the static counter
        let counter = counter + 1;

        // Print results (assumes a standard Output library)
        do Output.printInt(s);
        do Output.printInt(m);
        do Output.printInt(f);

        return;
    }
}
