# Fuzzing parsers and input handlers

Read this when code takes bytes or text from outside the program (files, network messages, uploads, configuration, query strings, clipboard, other services) and must never crash, hang or misbehave on them, or when the project contains C, C++, unsafe Rust, cgo or other native code. Property-based testing, which shares many ideas, is in `advanced-testing.md`. Deciding whether a crash is exploitable belongs to `../../code-security-review/GUIDE.md`.

## When it pays off

- **Strong targets:** parsers and decoders (file formats, protocols, configuration, Markdown, CSV, query languages), deserializers, decompressors, image and media handling, URL and path normalization, HTML sanitizers, anything written in a memory-unsafe language or crossing an FFI boundary, and validators built on complex regular expressions.
- **Weak targets:** business logic with structured inputs (property tests fit better), code dominated by network or database calls, user interface code.
- **Fuzzing and property tests differ in mechanics.** A property test draws structured values from a generator, runs a fixed number of cases and belongs in the normal suite. A coverage-guided fuzzer mutates raw inputs, keeps the ones that reach new code, and runs for minutes to days. Some setups serve both: Go's native fuzz targets run their seed inputs as ordinary tests, Rust targets can take `arbitrary`-derived structs, and HypoFuzz runs existing Hypothesis tests as long-running fuzz targets.

## Harness rules

The harness is the function the fuzzer calls with each input. Most failed fuzzing efforts are harness problems.

1. **One target, one input format.** Separate harnesses for the header parser and the body decoder; a shared harness for formats that share a corpus only when they really share structure. For an object whose operations interact (a cache, a buffer, a container), one harness can read an operation code and arguments from the input in a loop: the fuzzing counterpart of a model-based test.
2. **Accept every input.** Empty, huge and malformed inputs must reach the code under test or be skipped deliberately (`if len(data) > 1<<16 { return }`). The harness itself must never crash.
3. **Stay deterministic.** No real clock, randomness, network, shared temporary files or global state that survives between calls. Derive any seed from the input and reset globals at the start of each call, or crashes will not reproduce.
4. **Stay fast.** No logging, sleeping or large setup per call; build fixtures once outside the per-input function. In-process fuzzers should reach hundreds to thousands of executions per second.
5. **Let real failures surface.** Catch only the documented error type (`ParseError`, `io.EOF`, an `Err` result). Never swallow all exceptions and never call `exit`.
6. **Check more than survival.** After a successful parse, assert something: the value renders and re-parses to itself, a canonical form is stable, sizes stay within limits, or a second parser agrees (a differential harness).
7. **Bound resources** so hangs and memory blowups are reported instead of stalling the run: input length (`-max_len`), per-input timeout (`-timeout`), memory (`-rss_limit_mb`).
8. **Keep bypasses out of production.** If a checksum or signature check blocks all progress, skip it only in fuzzing builds: `cfg(fuzzing)` (set by cargo-fuzz) in Rust, or the conventional `FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION` macro in C and C++ (defined in OSS-Fuzz builds; define it yourself locally). Test the real check separately.

## Per language

### Go (built in since Go 1.18)

```go
// header/fuzz_test.go
func FuzzParseHeader(f *testing.F) {
	f.Add("Content-Type: text/plain")          // seeds; also files in testdata/fuzz/FuzzParseHeader/
	f.Fuzz(func(t *testing.T, line string) {
		h, err := Parse(line)
		if err != nil {
			return // documented rejection
		}
		again, err := Parse(h.String())
		if err != nil || again != h {
			t.Fatalf("round trip changed %q into %q (err %v)", line, h.String(), err)
		}
	})
}
```

```bash
go test -run='^$' -fuzz='^FuzzParseHeader$' -fuzztime=120s ./header   # one target per run
go test ./header        # replays the seeds and every saved failure as ordinary tests
```

A failing input is minimized and written to `testdata/fuzz/FuzzParseHeader/`; commit it, and it becomes a permanent regression case. The generated corpus lives in the build cache (`go env GOCACHE`); `go clean -fuzzcache` clears it. Run concurrent code under `go test -race` as well.

### Rust (cargo-fuzz, nightly toolchain)

```bash
cargo install cargo-fuzz
cargo fuzz init && cargo fuzz add parse_header        # creates fuzz/fuzz_targets/parse_header.rs
cargo +nightly fuzz run parse_header -- -max_total_time=300
cargo +nightly fuzz run parse_header fuzz/artifacts/parse_header/crash-<hash>   # reproduce
cargo +nightly fuzz tmin parse_header fuzz/artifacts/parse_header/crash-<hash>  # minimize
cargo +nightly fuzz cmin parse_header                  # shrink the corpus in fuzz/corpus/parse_header/
cargo +nightly fuzz coverage parse_header              # coverage data for llvm-cov
```

```rust
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    if let Ok(text) = std::str::from_utf8(data) {
        if let Ok(h) = mycrate::Header::parse(text) {
            assert_eq!(mycrate::Header::parse(&h.to_string()).ok(), Some(h));
        }
    }
});
```

For structured input, derive `arbitrary::Arbitrary` on an input struct and take it as the closure argument. cargo-fuzz builds with AddressSanitizer by default; for crates with no `unsafe` code, `--sanitizer none` runs faster. Check `unsafe` code in the normal tests with Miri as well: `cargo +nightly miri test`.

### Python (Atheris)

```python
# fuzz/fuzz_config.py
import sys
import atheris

with atheris.instrument_imports():
    from myproject.config import ConfigError, parse_config

def test_one_input(data: bytes) -> None:
    text = atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(4096)
    try:
        cfg = parse_config(text)
    except ConfigError:
        return
    assert parse_config(cfg.render()) == cfg

atheris.Setup(sys.argv, test_one_input)
atheris.Fuzz()
```

```bash
python fuzz/fuzz_config.py -max_total_time=300 fuzz/corpus/   # libFuzzer flags
python fuzz/fuzz_config.py crash-<sha1>                       # reproduce one input
```

In pure Python, fuzzing finds uncaught exceptions, hangs, recursion limits and broken invariants. Memory errors in C extensions need the extension built with AddressSanitizer. Check that an Atheris release supports the project's Python version before adopting it; Hypothesis-based tests are the lighter alternative.

### JavaScript and TypeScript

Property tests with fast-check and a high `numRuns` cover most needs, including error-contract properties over `fc.string()` and `fc.uint8Array()`. Coverage-guided fuzzers for Node.js exist (Jazzer.js); check their maintenance status and license before adopting one. For regular expressions applied to user input, test for catastrophic backtracking: run long adversarial strings with a timeout, or use a checker such as the `regexp/no-super-linear-backtracking` rule of eslint-plugin-regexp.

### C and C++ (libFuzzer, AFL++)

```c
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    struct header h;
    if (parse_header((const char *)data, size, &h) == 0)
        check_header_invariants(&h);   /* abort() on violation */
    return 0;
}
```

```bash
clang -g -O1 -fno-omit-frame-pointer -fsanitize=fuzzer,address,undefined \
  fuzz_header.c header.c -o fuzz_header
./fuzz_header -max_total_time=600 -max_len=4096 -timeout=5 corpus/ seeds/   # new inputs go to corpus/
./fuzz_header crash-<sha1>                                   # reproduce
./fuzz_header -minimize_crash=1 -runs=100000 crash-<sha1>    # minimize
./fuzz_header -merge=1 corpus-min/ corpus/                   # minimize the corpus
```

libFuzzer is still supported but no longer actively developed; AFL++ (`afl-clang-fast`, `afl-fuzz -i seeds -o findings -- ./target @@`) is the usual choice for long multi-core campaigns and can build the same `LLVMFuzzerTestOneInput` harness. On the JVM, Jazzer adds `@FuzzTest` to JUnit 5.

## Seeds, dictionaries and coverage

- **Seed corpus:** a handful of small, valid and varied inputs from the tests, the specification's examples and real files with personal data removed. Commit small seeds (`testdata/fuzz/<Target>/`, `fuzz/corpus/<target>/`, `seeds/`); keep large generated corpora in CI caches or artifacts.
- **Dictionaries** help a fuzzer get past keywords and magic values: one token per line, for example `kw_select="SELECT"` and `magic="\x89PNG"`, passed with `-dict=format.dict`. Extract tokens from the grammar, the specification and constants in the parser.
- **Check what the harness reaches** before running for hours: collect coverage on the corpus (`cargo fuzz coverage`, `go test -coverprofile=c.out` over the seeds, `-print_final_stats=1` in libFuzzer). Coverage that stops at a checksum calls for a fuzzing-build bypass; coverage that stops at structure calls for a dictionary or structure-aware input.

## Sanitizers

| Tool | Finds | Notes |
|---|---|---|
| AddressSanitizer (`-fsanitize=address`) | Out-of-bounds access, use after free, double free, leaks (LeakSanitizer on Linux) | Roughly doubles run time; the default partner for fuzzing |
| UndefinedBehaviorSanitizer (`-fsanitize=undefined`) | Signed overflow, invalid shifts, misaligned access, null dereference | Combine with ASan in the same build |
| MemorySanitizer (`-fsanitize=memory`, Clang) | Reads of uninitialized memory | Every linked library must be instrumented too |
| ThreadSanitizer (`-fsanitize=thread`) | Data races | Separate build; cannot be combined with ASan |
| Go race detector (`-race`), Miri for Rust | Data races in Go; undefined behavior in `unsafe` Rust | Run in the normal test job |

Run the regular test suite of native code under ASan and UBSan in CI too; sanitizers find bugs in tests that pass.

## When the fuzzer finds something

1. **Reproduce** from the saved input with the commands above. If it does not reproduce, the harness or the code has nondeterminism; fix that first.
2. **Minimize** the input (Go does this automatically; `tmin`, `-minimize_crash=1`).
3. **Deduplicate** by the top frames of the stack trace; many crash files are one bug.
4. **Classify:** a harness bug (fix the harness); a resource limit (decide the limit the code should enforce, since unbounded memory or time on untrusted input is itself a bug); or a real defect (crash, panic, hang, sanitizer report, broken invariant).
5. **Treat as potentially security-relevant** any sanitizer report, any hang or blowup reachable from untrusted input, and parser disagreements in security checks. Rate them with `../../code-security-review/GUIDE.md`. In a public project, do not publish crashing inputs before the fix ships.
6. **Fix at the source** and keep the input as a regression test: commit it under `testdata/fuzz/` in Go; in Rust, keep it in the corpus and add a unit test with `include_bytes!`; elsewhere, a unit test that feeds the bytes.
7. Rerun the fuzzer for a while after the fix.

## Budgets and CI

| When | What |
|---|---|
| After changing a parser locally | One to five minutes per affected target |
| Every pull request | Replay the corpus and saved failures; optionally a short run (a few minutes) with a cached corpus, for example with ClusterFuzzLite on GitHub Actions or GitLab |
| Scheduled | Hours per target, corpus kept between runs |
| Open-source projects that are widely used or critical | Apply to OSS-Fuzz for continuous fuzzing |

Report executions, duration, coverage reached and findings. "No crashes in ten minutes" is weak evidence; write it exactly like that rather than "fuzzed, no issues".

## Checks (done when)

- [ ] Each harness is deterministic, accepts any input, catches only documented errors and asserts at least one invariant beyond not crashing.
- [ ] Coverage over the corpus reaches the code the change touched.
- [ ] Native code ran under ASan and UBSan; Go concurrency under `-race`; unsafe Rust under Miri where possible.
- [ ] Every finding was reproduced, minimized, classified and, if real, fixed with its input kept as a regression test.
- [ ] Fuzzing bypasses compile only in fuzzing builds.
- [ ] The report states run time and executions, not just "no crashes".

## Anti-patterns

- A harness that wraps everything in `try: ... except Exception: pass`.
- Logging, network calls or real time inside the per-input function.
- Fuzzing for hours with a harness that never gets past the first validation check.
- Deleting crash files instead of turning them into regression tests.
- Shipping a checksum bypass in a release build.
- Treating a fuzzing run as a security sign-off.
