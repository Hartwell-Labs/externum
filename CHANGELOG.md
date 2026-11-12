# Changelog

All notable changes to Externum will be documented in this file.

## [4.4.0] - 2026-11-12 — "Titan"

Language and VM parity release: the bytecode VM (the default `externum run`
backend) now implements the features that previously only worked through the
Python transpiler, and a batch of long-standing defects is fixed in both.
The same program now prints byte-identical output on `--backend vm` and
`--backend python`.

### Added
- **Comprehensions on the VM** — list, set and dict comprehensions with
  filters, nested `for` clauses and tuple targets; the old
  "the bytecode VM does not support comprehensions yet" error is gone.
- **Class inheritance + `super()` on the VM** — base classes are linked at
  `MAKE_CLASS`, method lookup walks the MRO depth-first, and `super()`
  resolves through a new `ExternumSuper` proxy.
- **`with ... as` on the VM** — binds each context and closes it on exit.
- **Enums as values and constructors** — `Color.RED` is a value, `Color.RED(x)`
  constructs a payload variant; equality, hashing and `repr` are defined.
  The Python backend generates the same shape.
- **Generators on the VM** — `yield`, `yield from` and `for` over generator
  functions work; `yield from` is desugared by the parser for both backends.
- **Walrus operator `:=`** — lexer, parser and both backends.
- **Star unpacking everywhere** — `f(*args)`, `f(**kwargs)`, `[*xs]`, `(*xs,)`
  via new `CALL_EX`, `LIST_APPEND/EXTEND`, `SET_ADD`, `DICT_SET/UPDATE` and
  `LIST_TO_TUPLE` opcodes.
- **Function-level `defer`** — real `try/finally` in the Python backend and
  deferred execution on every `return`/`break`/`continue` in the VM.
- **`comptime` declarations** — accepted by the transpiler (evaluated at load).
- **`Ok`/`Err`/`Some` and type names** (`Int`, `Str`, `List`, `Dict`,
  `Optional`, `Union`, ...) in the runtime globals, plus union and generic
  annotations (`Int | None`, `def f[T](x: T)`).
- **f-string format specs and conversions** on the VM (`f"{x:.2f}"`, `{x!r}`),
  triple-quoted strings, and `print(sep=..., end=...)` keyword arguments.
- **`except ... as e` binding, exception-type filters and `finally`** on the
  VM (exceptions are now passed as objects, not strings).
- **`del obj[i]`, `del obj.attr`, `del name`** on the VM.
- 33 new regression tests in `tests/test_v440_features.py` (452 total).

### Fixed
- **Index assignment on the VM** wrote into the wrong slot (`d["k"] = 1`
  produced `{1: "k"}`); `SET_INDEX` now receives `(obj, index, value)`.
- **`d[k] += v`** on the VM (double `SWAP` left the stack in the wrong order).
- **Tuple assignment `a, b = 1, 2`** on the VM (RHS was compiled as a name).
- **`match` with alternation** (`case "a" | "b"`) on the VM.
- **`not in` / `is not`** were split into unary `not` + unknown token; both
  backends emit the correct operator now.
- **Method calls on a list literal** (`[].count(1)`) — the parser dropped the
  postfix chain after a list literal.
- **Struct fields** — the VM used synthetic `field0..fieldN` names instead of
  the declared ones; structs also accept keyword arguments and pre-fill
  missing fields with `None`.
- **`try/finally` with `return` on the VM** — the `finally` block now runs on
  early exits.
- **`print("a", end="")`** printed an extra space/newline on the VM.
- **Macros were not expanded on the VM** (`VM.run_source` skipped
  `preprocess`), so `macro SQUARE(x)` failed with `undefined global SQUARE`.
- **String escapes** (`"\n"`) stayed literal on the VM; literals are now
  decoded with `ast.literal_eval` (also covers raw/triple-quoted strings).
- **Index/call receivers** (`c.most_common()[0]`, `[].count(1)`) compiled the
  whole receiver text as a name; receivers now go through the expression
  compiler.
- **`@p = value` deref stores** had the pointer and value swapped on the VM.
- **`match` binding patterns and guards** (`case n if n > 1:`) on the VM —
  only literals were matched before. Destructuring (`case [a, b]:`) works too.
- **`sorted`/`min`/`max` `key=`** were dropped on the VM; lambdas are now
  callable from host code (`EXTERNUMClosure.__call__`).
- **Class attribute access** (`Pokemon.__init__`) returned Python's
  `ExternumClass.__init__` instead of the Externum method.
- **Type names in the VM globals** (`Int`, `Str`, `List`, ...) so
  `alloc(Int)` and annotations resolve.
- **`examples/hardcore.ext` and `examples/pokedex.ext` now produce identical
  output on both backends** (regression tests added). `examples/hello.ext`
  still differs by design: the VM does not execute inline Bash blocks.

## [4.3.1] - 2026-09-25

### Changed
- packaging: full PyPI `project_urls` (Repository, Issues, Changelog,
  Documentation, Organization) so registry pages link to the live docs site
  and the Hartwell Labs org; no code changes

## [4.3.0] - 2026-09-23

### Added
- **`externum translate`** — source-to-source translation into Externum:
  - `externum translate file.py` (py2ext): AST-based Python→Externum with type
    inference for the strict declaration syntax (`x: Int = ...`), f-strings →
    `"$"..."`, `if __name__ == "__main__"` hoisted into `main()` (auto-run),
    stdlib import warnings, `--report` for a warning/coverage summary
  - `externum translate file.rs` (rs2ext): heuristic Rust→Externum — `fn`/`let`,
    `struct`, `impl` → class, `match` arms → `case`, `println!`/`format!` →
    `print`/`$"..."`, `vec!`, type mapping (`Vec<f64>` → `List[Float]`, ...)
  - both are best-effort: anything unmapped is reported as a warning, never
    silently mangled; 28 new tests round-trip output through the real compiler

### Fixed
- **bare generator expressions in call arguments** — `sum(x for x in xs)` used
  to compile to invalid Python (`sum(x, for, x in xs)`); the parser now
  recognises the `FOR` clause in call args and emits a proper comprehension
- **classes used inside functions on the VM** — a module-level class was stored
  with `STORE_VAR`, which lands in the frame locals and is invisible to function
  bodies (`undefined global `X``); module-level classes now store via
  `STORE_GLOBAL`, matching the function path and the Python backend
- the VM raises a clear "the bytecode VM does not support comprehensions yet"
  error instead of a confusing `undefined global `(p`` for textual comprehensions

## [4.2.2] - 2026-09-22

### Changed
- Packaging: the PyPI long description now reflects the current README
  (includes the "Support the project" section with the Externum Pro Pack
  and launch-week pricing). No code changes.

## [4.2.1] - 2026-09-19

### Added
- **Functions in the bash target** (`--target bash`): `def`/`fn` compile to real bash
  functions — positional params bound with `local`, default params via
  `local p="${N:-default}"`, `return <expr>` emitted as `printf '%s\n'` + `return 0`
  and captured through command substitution `$( f args )`. **Recursion works**
  (every local is dynamic per invocation). String concatenation (`s + "!"`, including
  in `return`/`print`) renders as a single double-quoted word. Bare calls to
  value-returning functions discard the result (`> /dev/null`), matching the Python
  target's semantics. A compile-time warning fires when a function both prints and
  returns a value (the two streams share stdout in bash).
- 3 new end-to-end tests that execute the generated bash (recursion → 720, defaults +
  string concat, statement-call discards value). Suite: 379.

### Fixed
- f-string gotcha in codegen: `${i:-default}` inside an f-string was parsed as a
  format spec (`Unknown format code '!'`) — escaped braces now.

## [4.2.0] - 2026-09-19

### Added
- **`|>` pipeline operator**: `x |> f(a, b)` desugars to `f(x, a, b)`. Works in the
  Python target (transpiler desugar) and on the VM (`PIPE_CALL` now dispatches
  user functions and closures, not just callables). Left-associative, so
  `x |> f |> g` chains correctly.
- **`fn` keyword**: `fn name(args) -> T:` is an alias for `def` (lexer keyword +
  parser dispatch). Rust-flavored spelling of the same construct.
- **Real bash backend** (`externum/bash_backend.py`): `--target bash` now
  translates module-level Externum logic — integer/float-free arithmetic via
  `$(( ))`, `while`, `for`/`for range`, `if`/`elif`/`else` (including `[[ str == str ]]`),
  `break`/`continue`, `print`, and embedded `bash { ... }` blocks verbatim — into a
  standalone `set -euo pipefail` script. Unsupported statements emit warnings on
  stderr instead of silently vanishing (the old behavior produced empty scripts).
- 8 new tests (VM aug-assign at module level and inside functions, operator
  semantics for `-=`/`*=`/`%=`, parenthesized RHS, pipe in both backends,
  `fn` alias, bash backend loop + warning behavior). Suite: 376.

### Fixed
- **Issue #21** — augmented assignment at module top level stored into a local
  frame nothing ever read: loop counters never advanced and `externum vm` hung
  silently (the original benchmark hang). Store path now mirrors `_stmt_ASSIGN`
  (`STORE_GLOBAL` when not inside a function).
- **Issue #21 (related)** — the parser reports `"*="`-style operators with the
  `=` suffix, but the bytecode `op_map` was keyed on bare operators: every
  augmented op except `+=` silently degraded to addition. Also: `obj.attr += v`,
  `x[i] += v` and `*p += v` emitted no store at all — now desugared through the
  normal ASSIGN paths.
- **Issue #22** — parenthesized right-hand sides (`total + ((i*3+7) % 1000)`)
  reached the bytecode compiler as raw text and fell through to `_compile_name`
  (`undefined global (((...)))`). `_compile_simple_expr` now strips redundant
  outer parentheses before the literal/name dispatch.
- Lexer was missing `%=`, so `x %= 5` tokenized as `x % = 5` (parsed as a
  comparison against an unknown token); `%=` added to the lexer and to the
  parser's aug-assign dispatch.
- Issues #19 and #20 (empty bash/bytecode output for logic programs) are fully
  closed by the bash backend and the 4.1.0 artifact work respectively.

## [4.1.0] - 2026-09-19

### Added
- **Real bytecode artifacts**: `externum app.ext --target bytecode -o app.exbc`
  emits a self-contained `.exbc` file (magic header `EXBC` + version + payload).
  Run it with `externum run app.exbc` — the VM loads and executes it directly,
  skipping lexer/parser/compiler entirely. The source file never needs to ship.
- `module_to_bytes` / `module_from_bytes` / `save_module` / `load_module` in
  `externum.bytecode`, with magic/version/length validation.
- 2 new tests (artifact roundtrip executes identically; garbage rejection).

### Fixed
- (4.0.0) `--target bash` never worked; single-target `compile()` API now
  returns a dict — see 4.0.0 notes.

## [4.0.0] - 2026-09-19

### Fixed
- `externum file.ext --target bash` crashed with "list indices must be integers
  or slices, not str" — `Compiler.compile()` now returns a dict for single
  targets, matching what the CLI always expected. The bash target has never
  worked through the CLI before this release.
- Unknown `--target` values now raise a clear `ValueError` instead of
  returning an empty string.

### Changed
- Docs: test counts unified to the actual suite size (366), Why? section and a
  real end-to-end ASCII demo moved to the top of the README.

## [0.3.0] - 2026-09-15

### Added
- Native string interpolation: `$"Hello {name}, {a+b}!"` — lexer, parser, and both compilers (Python transpiler + bytecode VM)
- f-string-compatible escape semantics: `{{` and `}}` render as literal braces
- 8 new tests covering interpolation through both execution targets

## [0.2.0] - 2025-08-01

### Added
- Architecture documentation
- TUI IDE (terminal-based editor)
- Post-quantum crypto builtins
- Enhanced bytecode compiler
- 30+ instruction set
- Module system with imports
- Class/trait/impl system
- Pattern matching
- Generators and channels
- Macros
- Memory management (alloc/free)
- Full CI/CD pipeline

### Fixed
- Module import resolution
- Class instantiation
- Pattern matching with guards

## [0.1.0] - 2025-01-01

### Added
- Initial language design
- Lexer, parser, compiler
- VM execution engine
- Basic type system
