# C and C++ memory-safety review

Reference for the `code-security-review` module. Read it when the scope contains C or C++: native services and daemons, parsers and codecs, language extensions, libraries shipped to others, command-line tools that read untrusted files. It adds memory corruption and undefined behavior, which the general classes in `vulnerability-classes.md` do not cover. Kernel code, drivers and bare-metal firmware need a specialist; say so in the scope and treat anything found there as a lead.

Tools named here are optional. Build instrumented binaries only from the local checkout, in a scratch build directory, after reading the build scripts. Record anything that could not be built or run as `NOT_VERIFIED`.

**Contents:** [Attacker and sources](#attacker-and-sources) · [Function-by-function questions](#function-by-function-questions) · [Bug classes](#bug-classes) · [C++ lifetimes and classes](#c-lifetimes-and-classes) · [Windows targets](#windows-targets) · [Sanitizers and fuzzing](#sanitizers-and-fuzzing) · [Static analysis and searches](#static-analysis-and-searches) · [Hardened builds](#hardened-builds) · [Confirm, rate, fix](#confirm-rate-fix)

## Attacker and sources

Write down which attacker the review assumes before reading code, because it decides what is reachable:

- **Remote:** bytes from the network, uploaded files, messages from other services, data from less-trusted processes over IPC.
- **Local, unprivileged:** another user on the same machine attacking a setuid or setgid program, a root daemon's socket, files in shared or world-writable directories, environment variables and arguments of privileged programs.

Then list every place untrusted bytes enter: `recv`, `read`, `fread`, `getline`, `mmap` of user files, parser entry points, IPC handlers, `getenv` in privileged code. Length and count fields inside formats are the usual starting point: most memory bugs are a length the code believed.

## Function-by-function questions

The same author tends to repeat the same wrong assumption, so memory bugs come in groups. Follow the data through each function that handles untrusted input and answer the questions below for every relevant spot, noting the lines you looked at in the coverage record. A function with many copies or index operations gets an answer for each of them, and a confirmed bug is a reason to reread the rest of that function, and the code written alongside it, more carefully.

1. **What arrives:** which arguments and fields come from the attacker, and what does the function assume about them (non-NULL, `len <= cap`, already validated, lock held)? Find every caller and check that each one guarantees it.
2. **Arithmetic on sizes:** for each length, count, offset and allocation size, note its type and signedness, and whether it can overflow, wrap or be truncated before it is used.
3. **Writes:** what bounds each array index, pointer store, `memcpy`, `memmove`, `strcpy`-family call and storing loop? The bound must be the destination's capacity, not the source's length.
4. **Reads:** the same question for reads. Out-of-bounds reads leak memory even when no write goes wrong.
5. **Strings:** who guarantees the terminating NUL, and does every size include it?
6. **Lifetime:** is each allocation freed exactly once on every path? After `free`, are all aliases (struct fields, caches, lists, callbacks) cleared or provably unused?
7. **Error paths:** is every call that can fail checked (`malloc`, `read`, `write`, `snprintf`, `setuid`, `pthread_*`, parser functions), and does the cleanup after a failure leave no half-built state behind?
8. **Initialization:** is every variable and struct field written before it is read? Is a struct with padding copied out to a socket, file or caller?
9. **Hidden types:** `sizeof` applied to a pointer instead of the object (`sizeof(p)` versus `sizeof(*p)`; array parameters are pointers), macros that evaluate an argument twice (`MAX(i++, n)`) or lack parentheses, and implicit signed-to-unsigned conversions in comparisons.

## Bug classes

| Class (CWE) | What it looks like | Notes |
|---|---|---|
| Buffer overflow, stack or heap (787, 121, 122) | `memcpy(dst, src, hdr->len)` with `len` from input; `strcpy`, `strcat`, `sprintf`, `gets`; loops ending at `<= n` | Check the bound against the destination, at the point of the write |
| Out-of-bounds read (125) | Reply length taken from the request; parser reads `p[i+3]` after checking only `i < len` | Leaks memory contents, often secrets |
| Integer overflow into a small allocation (190, 680) | `malloc(count * size)`, `len + 1` where `len` can be `SIZE_MAX`, 32-bit `width * height * 4` | Use `calloc`, `reallocarray`, `__builtin_mul_overflow` or C23 `ckd_mul` |
| Signedness and truncation (195, 197, 681) | `int len` checked with `len < max` then passed to `memcpy` as `size_t`; `size_t` stored in `int` or `uint16_t` | A negative length passes the check and becomes huge |
| Off-by-one (193) | `buf[sizeof buf] = 0`; `strncat(dst, src, sizeof dst)` (the limit must be the space left minus one, not the buffer size) | |
| Use after free, double free (416, 415) | Free on an error path then reuse on the shared cleanup path; pointer kept in a list after `free`; aliases left pointing at the old block after `realloc` moves it | |
| NULL dereference (476) | Unchecked `malloc` or lookup result | Usually a crash in user space; still a denial of service |
| Uninitialized memory (457, 908) | Stack struct sent whole; partially filled output buffer | Information leak or wrong control flow |
| Format string (134) | `printf(msg)`, `fprintf(fp, msg)`, `syslog(prio, msg)` with input in `msg` | `-Wformat -Wformat-security` flags most |
| `snprintf` return misuse | `p += snprintf(p, end - p, ...)` | Returns the length that would have been written; on truncation `p` passes `end` |
| Unterminated or silently truncated strings | `strncpy` leaves no NUL when the source fills the buffer; `strlcpy` truncates without error unless the return value is checked against the size; `readlink` never terminates | |
| Unbounded input functions | `scanf("%s")`, `gets` | Use a width (`%63s` for a 64-byte buffer) or `fgets` plus parsing |
| Overlapping copy | `memcpy` with overlapping regions is undefined | `memmove` |
| Type confusion (843) | Tagged unions read without checking the tag; wrong struct cast from a `void *` context | |
| Undefined behavior the optimizer uses | Signed overflow (`if (x + 100 < x)` is deleted), shifts by the type width or more, dereference before a NULL check (the check is deleted), strict-aliasing violations | Find with UBSan; see [hardened builds](#hardened-builds) for compiler flags that keep checks |
| Precedence slips | `if (flags & MASK == 0)`, `*p++` versus `(*p)++`, `sizeof x + 1` | |
| Ignored errors (252, 253) | `read` returning `-1` used as a length; `setuid` failure ignored, so the program continues as root (273) | |
| Filesystem races (367, 59) | `access()` or `stat()` then `open()`; predictable names in `/tmp`; following symlinks in shared directories | `open` with `O_CREAT \| O_EXCL \| O_NOFOLLOW`, `mkstemp`, `openat` relative to a directory descriptor, `openat2` with `RESOLVE_BENEATH` (Linux 5.6+), `fstat` the open descriptor |
| Descriptor leaks | Missing `O_CLOEXEC`, so children inherit secrets or sockets | |
| Concurrency (362) | Shared state without a lock, unprotected reference counts, double-checked initialization | Find with TSan |
| Signal handlers (479, 828) | Handlers calling `malloc`, `printf`, `free` or touching shared state | Only async-signal-safe functions; set a `volatile sig_atomic_t` flag instead |
| Privileged programs | Dropping privileges in the wrong order or without checking; trusting `PATH`, `IFS` or other environment | Order: `setgroups`, `setgid`, `setuid`, each checked; `secure_getenv`; `system` and `popen` with input are command injection (class 1.3) |
| Resource exhaustion (400, 770) | Allocation sized by an input length with no cap; recursion depth controlled by nesting; `alloca` or VLAs sized by input | Cap sizes and depth before allocating |
| Library contract misuse | `qsort` comparators that overflow (`return a - b;`) or are inconsistent; `va_start` without `va_end`; `strtok` in threads; `getenv` pointers used after `setenv`; `realloc(p, 0)` | |

Cryptographic code (comparisons, key wiping, randomness) is covered in `crypto-implementation.md`.

## C++ lifetimes and classes

- **Dangling views:** `const char *p = make_name().c_str();` or a `std::string_view` or `std::span` over a temporary or over a container that later grows. The pointer outlives the buffer.
- **References and captures:** returning a reference to a local; a lambda capturing by reference (`[&]`) stored in a callback, thread or task that outlives the scope.
- **Iterator invalidation:** `push_back`, `insert` or `erase` while iterating; holding references into a `std::vector` across growth; `unordered_map` rehash.
- **Use after move:** reading a moved-from object as if it still held its value.
- **Smart pointers:** two `shared_ptr` objects created from the same raw pointer (double delete; use `make_shared` and `enable_shared_from_this`); keeping `unique_ptr::get()` after the owner dies; cycles of `shared_ptr` (leaks); `delete` on memory from `new[]`.
- **Unchecked access:** `operator[]` does not bounds-check; `.at()` does. Turn on the standard library's hardening in release builds: `-D_GLIBCXX_ASSERTIONS` for libstdc++, `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST` for libc++ 18 and later.
- **Exceptions:** resources acquired outside RAII leak when a constructor throws; a destructor that throws during unwinding, or an exception escaping a `noexcept` function, calls `std::terminate` (denial of service).
- **Initialization order:** static objects in different translation units initialize in an unspecified order; virtual calls in constructors and destructors do not dispatch to the derived class.
- **Integer traps:** `v.size() - 1` on an empty container wraps to a huge value; loops mixing `int` and `size_t`.

## Windows targets

- **Process creation:** `CreateProcess` with a NULL application name and an unquoted path containing spaces runs `C:\Program.exe` if it exists (CWE-428).
- **DLL loading:** `LoadLibrary("name.dll")` searches the application and working directories, which may be writable (CWE-427). Call `SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32)` early, or use `LoadLibraryExW` with `LOAD_LIBRARY_SEARCH_SYSTEM32` and full paths.
- **Objects and IPC:** named pipes, shared memory and events created by a service with a NULL DACL or default security; the return value of `ImpersonateNamedPipeClient` ignored, so the code continues with the service's own rights.
- **Services and installers:** privileged code writing to or loading from user-writable paths; installers unpacking into `%TEMP%` and then running what they unpacked (race).
- **Build flags:** `/GS`, `/guard:cf`, `/DYNAMICBASE`, `/HIGHENTROPYVA`, `/NXCOMPAT`, `/CETCOMPAT`, `/sdl`. `dumpbin /headers` lists the DLL characteristics a binary was linked with.

## Sanitizers and fuzzing

Run the project's own tests in a sanitizer build first. Each report names the bad access, where the memory was allocated and where it was freed, which turns silent corruption into evidence.

- **AddressSanitizer plus UndefinedBehaviorSanitizer, in one build:** add `-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -g -O1` to the compile and link flags (`CFLAGS`, `CXXFLAGS`, `LDFLAGS`) and run the test suite. This finds out-of-bounds accesses, use after free, double free, leaks (on Linux), signed overflow, invalid shifts and bad casts. `ASAN_OPTIONS=detect_stack_use_after_return=1` adds stack-lifetime checks.
- **Separate builds** for MemorySanitizer (`-fsanitize=memory`, Clang on Linux; every linked library, including the C++ standard library, must be instrumented or its reports are false) and ThreadSanitizer (`-fsanitize=thread`) for threaded code. Neither combines with AddressSanitizer.
- **Fuzz every parser and decoder an attacker can reach,** with one harness per entry point. Harness rules, libFuzzer and AFL++ commands, seeds, coverage and crash triage are in `../../engineering-practices/references/fuzzing.md`. For the audit, record the harness, run time, executions and coverage reached: a short run without crashes is weak evidence, not a `PASS`. Every crash becomes a regression input that runs under AddressSanitizer.

## Static analysis and searches

- **Compiler warnings first:** `-Wall -Wextra -Wformat=2 -Werror=format-security -Wconversion -Wsign-conversion -Wimplicit-fallthrough -Wshadow`. Many projects never enabled them; the first build is a cheap lead list.
- **Analyzers, if installed:** GCC `-fanalyzer` (best for C), the Clang static analyzer (`scan-build make`), `clang-tidy` with `bugprone-*`, `cert-*` and `clang-analyzer-*` checks, `cppcheck`, and CodeQL or Semgrep if the project already configures them. Most need a compilation database: `cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, or `bear -- make` for Make projects.
- **Starter searches** (leads, not findings):

```sh
rg -n -t c -t cpp \
  -e '\b(gets|strcpy|strcat|sprintf|vsprintf|stpcpy|wcscpy|wcscat)\s*\(' \
  -e '\bv?printf\s*\(\s*[^"\s)]' \
  -e '\b(v?fprintf|v?dprintf|syslog)\s*\(\s*[^,]+,\s*[^"\s]' \
  -e '\bv?snprintf\s*\(\s*[^,]+,[^,]+,\s*[^"\s]' \
  -e '\bscanf\s*\(\s*"[^"]*%s' \
  -e '\b(alloca|tmpnam|tempnam|mktemp)\s*\(' \
  -e '\b(malloc|realloc)\s*\([^;]*\*' .
```

The format-string patterns match any call whose format argument is not a string literal; most hits pass a constant through a variable, so check where the format comes from.

## Hardened builds

These GCC and Clang options for Linux follow the OpenSSF Compiler Options Hardening Guide for C and C++. Missing hardening is a `LOW` or `INFO` hardening note on its own; it raises the severity of real memory bugs because it decides how hard they are to exploit.

| Option | What it adds | How to see it in the binary |
|---|---|---|
| `-O2 -D_FORTIFY_SOURCE=3` (`=2` on older compilers or C libraries) | Size-checked versions of `memcpy`, `strcpy`, `sprintf` and others; needs optimization to work | `readelf --dyn-syms -W BIN \| grep '_chk@'` lists `__strcpy_chk` and similar |
| `-fstack-protector-strong` | Stack canaries | `__stack_chk_fail` in the dynamic symbols |
| `-fstack-clash-protection` | Probes large stack allocations so they cannot jump the guard page | Not easily visible |
| `-fcf-protection=full` (x86-64), `-mbranch-protection=standard` (AArch64) | Control-flow protection (CET, or BTI and PAC) | `readelf -n BIN` shows `x86 feature: IBT, SHSTK` or `AArch64 feature: BTI, PAC`; the note only counts if every linked object was built with it |
| `-fPIE -pie` | Position-independent executable, so ASLR covers the main binary | `readelf -h BIN` shows `DYN (Position-Independent Executable file)` |
| `-Wl,-z,relro -Wl,-z,now` | Full RELRO: relocations read-only after start-up | `readelf -l` has `GNU_RELRO` and `readelf -d` shows `BIND_NOW` |
| `-Wl,-z,noexecstack` | Non-executable stack | `readelf -lW BIN \| grep GNU_STACK` shows `RW`, not `RWE` |
| `-ftrivial-auto-var-init=zero` (GCC 12+, Clang 16+) | Zero-fills uninitialized locals, closing many information leaks | |
| `-fstrict-flex-arrays=3` (GCC 13+, Clang 16+) | Only `[]` counts as a flexible array member, so bounds checks see real sizes | |
| `-fno-strict-overflow`, `-fno-delete-null-pointer-checks`, `-fno-strict-aliasing` | Stops the optimizer deleting overflow and NULL checks that rely on undefined behavior | |
| `-D_GLIBCXX_ASSERTIONS` or libc++ hardening (C++) | Bounds-checked `operator[]` and other precondition checks | |

How to check what a release really used:

- Read the build log (`make VERBOSE=1`, `cmake --build . -v`) or `compile_commands.json`. Distribution compilers (Ubuntu, Fedora, Debian) turn several of these on by default, so a flag missing from the build files may still be on; check the binary.
- For a GCC binary with debug information, the compiler records its options in the DWARF producer string: `readelf --debug-dump=info BIN | grep -m1 DW_AT_producer`. Clang does not record them unless built with `-grecord-command-line`, and preprocessor definitions such as `_FORTIFY_SOURCE` never appear there; use the `_chk` symbols instead. `checksec`, if installed, summarizes the same checks.
- Debug information in a shipped binary discloses source paths, types and internal names. Ship stripped binaries and keep the debug data separately (`objcopy --only-keep-debug BIN BIN.debug`, then `strip --strip-debug BIN`).

## Confirm, rate, fix

- **Confirm** by reproducing through the real entry point, or a harness calling the vulnerable function, in an ASan and UBSan build. The sanitizer report with the input that triggers it is `TESTED_LOCAL` evidence. Without a reproducer, a `CONFIRMED` finding needs a complete trace with concrete values, for example: `count = 0x40000001` from the header, `count * 4` wraps to `4` in 32-bit arithmetic, `malloc(4)`, then a loop writes `count` elements.
- **Rate** from what is demonstrated: which memory can be written or read, how much, whether the attacker controls content and length, and which mitigations are on. Say "attacker-controlled heap write of up to 64 KiB past a 256-byte buffer", not "remote code execution", unless execution was shown. Writing a working exploit is out of scope; the sanitizer report is the proof.
- **Fix** at the write: check the length against the destination's capacity, do size arithmetic in `size_t` with overflow checks, replace unbounded string functions, free and clear pointers in one place, and set ownership rules for each allocation. Add the crashing input to the test suite, run it under ASan and see it fail before the fix. Then search for the same pattern elsewhere (variant hunting in `audit-phases.md`).
