# C++

Read this before writing or changing C++: libraries, services, tools, performance-critical components, native extensions. It covers building and writing C++ well. Memory-safety review (overflows, lifetimes as vulnerabilities, hardened builds, fuzzing harnesses) is `../../code-security-review/references/c-and-cpp.md`; firmware is `embedded.md`.

## Orient first

- **Build system:** CMake (`CMakeLists.txt`, often with `CMakePresets.json`), Meson, Bazel (`MODULE.bazel`), or Make. Build only through it; never compile files by hand with flags you guessed.
- **Standard level:** `CMAKE_CXX_STANDARD` or `target_compile_features(<t> PUBLIC cxx_std_20)`. Write for that level and for the oldest compiler in the CI matrix; library support for newer features lags the language (for example `std::format` and modules arrived late in some standard libraries).
- **Dependencies:** vcpkg (`vcpkg.json`), Conan (`conanfile.*`), CMake `FetchContent`, git submodules or a system package manager. Add a dependency through the same mechanism, with a pinned version, and ask first.
- **Compiler database:** `CMAKE_EXPORT_COMPILE_COMMANDS=ON` produces `compile_commands.json`, which clang-tidy and editors need.
- Style and analysis config: `.clang-format`, `.clang-tidy`, cppcheck settings. Format only the lines or files you change if the project is not fully formatted.

```bash
cmake --list-presets                          # if presets exist, use them
cmake --preset dev && cmake --build --preset dev
ctest --preset dev --output-on-failure        # or: ctest --test-dir build --output-on-failure
clang-format --dry-run -Werror <changed files>
clang-tidy -p build <changed .cpp files>
```

## Language level cheat sheet

| Feature | Standard |
|---|---|
| `std::optional`, `std::variant`, `std::string_view`, structured bindings, `if constexpr`, `std::filesystem` | C++17 |
| Concepts, ranges, `std::span`, `std::format`, `<=>`, designated initializers, coroutines (language only), `std::jthread` and stop tokens, modules | C++20 |
| `std::expected`, `std::print`, `std::mdspan`, deducing `this`, `std::flat_map`, `import std;` | C++23 |
| Static reflection, contracts, `std::execution`, a hardened standard library mode | C++26 (being finalized in 2026; check compiler support before use) |

## Ownership and lifetimes

- **Rule of zero:** let members (`std::vector`, `std::string`, `std::unique_ptr`) manage resources so the class needs no destructor, copy or move operations. When a class owns a raw resource (file descriptor, handle), wrap it in a small RAII type with deleted copies and `noexcept` moves, and nothing else.
- `std::unique_ptr` is the default owner; `std::make_unique` to create. `std::shared_ptr` only for genuinely shared ownership; it costs atomic reference counting and hides lifetimes. Raw pointers and references are non-owning observers.
- **Views do not own.** `std::string_view` and `std::span` dangle when the data they point to dies:

```cpp
std::string_view name() { return std::string("tmp"); }   // dangling: the string dies at return
auto parts = split(read_file(path));                      // views into a temporary that is already gone
```

  Return owning types from functions that create data; store owning types in members; use views for parameters.
- **Iterator and reference invalidation:** `push_back`, `insert` and `erase` on a `std::vector` may invalidate every iterator, pointer and reference into it. Do not hold them across mutation; use indices, or reserve capacity first when the bound is known.
- `std::move` only casts; the moved-from object is valid but unspecified. Do not read it again except to assign or destroy it. Mark move constructors and move assignment `noexcept`, or `std::vector` copies instead of moving on reallocation.
- Capturing by reference in a lambda that outlives the scope (stored callbacks, threads, coroutines) dangles. Capture by value or by `shared_ptr`, and think about coroutine frames that outlive their arguments.
- Static initialization order across translation units is unspecified; use function-local statics or `constinit`.

## Interfaces and style

- `const` by default: parameters by `const&` for large types, by value for small or sink parameters that are moved into place; `const` member functions where nothing changes.
- `explicit` on single-argument constructors; `[[nodiscard]]` on functions whose result must be checked (error codes, `expected`).
- Constrain templates with concepts (C++20) or `static_assert` on traits, so errors appear at the call site, not deep inside instantiations.
- Prefer `enum class`, `std::array`, `std::optional` and `std::variant` to plain enums, C arrays, sentinel values and unions.
- No `using namespace std;` in headers; headers include what they use and nothing more.
- Error handling follows the project: exceptions, error codes, or `std::expected` (C++23, or a compatible library on older standards). Never let an exception cross a C ABI boundary, a thread entry point or a destructor (destructors are implicitly `noexcept`).

## Concurrency

- A data race is undefined behavior, not just a wrong value. Every piece of shared mutable state has one mutex that guards it, documented next to it.
- `std::scoped_lock` (locks several mutexes without deadlock), `std::unique_lock` with `std::condition_variable::wait(lock, predicate)` (always with a predicate, because wakeups can be spurious).
- `std::jthread` joins on destruction and carries a `stop_token` for cooperative cancellation; a plain `std::thread` that is neither joined nor detached terminates the program.
- Atomics: default sequentially consistent ordering. Weaker orderings (`acquire`/`release`, `relaxed`) only with a written argument and ThreadSanitizer runs; lock-free structures only with a measured need.
- Run the tests under ThreadSanitizer for any change to concurrent code.

## Sanitizers in the development loop

| Build | Finds | Notes |
|---|---|---|
| `-fsanitize=address,undefined -fno-omit-frame-pointer -g` | Buffer overflows, use after free, leaks, signed overflow, misaligned access, invalid shifts | Run the whole test suite this way regularly; about 2x slowdown |
| `-fsanitize=thread` | Data races, lock-order inversions | Cannot be combined with AddressSanitizer; separate build |
| `-fsanitize=memory` (Clang only) | Reads of uninitialized memory | Needs every library built with it; usually only in dedicated setups |

Add a sanitizer preset or build type if the project has none, with the user's agreement. A finding is a bug until proven otherwise; fix the cause, not the report. Hardened release flags and fuzzing harnesses are covered in the security reference and `../../engineering-practices/references/fuzzing.md`.

## Warnings and static analysis

- GCC and Clang: at least `-Wall -Wextra -Wpedantic`, and `-Wconversion -Wsign-conversion -Wshadow` where the project tolerates them; MSVC: `/W4 /permissive-`. Treat new warnings in changed code as errors even if the build does not.
- clang-tidy checks worth having on new code: `bugprone-*`, `performance-*`, `modernize-*` (with care in old code), `cppcoreguidelines-*` selectively. Do not enable a new check across the codebase as part of a feature.
- Apply suppressions on a single line with a reason (`// NOLINT(bugprone-xyz): reason`).

## Testing

- Use the framework present (GoogleTest, Catch2, doctest, Boost.Test), registered with CTest so `ctest` runs everything.
- Test through the public interface; inject time, randomness and I/O through small interfaces or template parameters.
- Death tests or exit-code checks for code that must abort on invariant violations.
- Benchmarks with Google Benchmark or nanobench, in release builds, compared over repeated runs; check the optimizer did not delete the measured work (`benchmark::DoNotOptimize`).

## Performance

- Measure first: `perf record`/`perf report` on Linux, Instruments on macOS, VTune or the Visual Studio profiler on Windows, or an instrumenting profiler such as Tracy for frame-based apps.
- Typical wins: contiguous containers (`std::vector`, flat maps) over node-based ones; `reserve`; avoiding copies in loops (`const auto&`); data layouts that keep hot fields together; moving allocation out of hot loops. Virtual calls and exceptions are rarely the bottleneck; confirm with a profile before restructuring.
- Release builds: `-O2` is the usual baseline; `-O3`, link-time optimization and profile-guided optimization are measured one at a time.

## Build hygiene and ABI

- Modern CMake is target-based: `target_include_directories`, `target_link_libraries` with `PRIVATE`/`PUBLIC`/`INTERFACE`, `target_compile_options`. Avoid global `include_directories` and `add_definitions`.
- Compile times: forward declarations in headers, include-what-you-use, precompiled headers for stable heavy headers, `ccache` or `sccache`, and keeping template-heavy code out of widely included headers.
- A shared library's ABI changes when a public class's layout, a virtual function list or an inline function changes. For libraries with binary consumers, hide implementation behind a pointer to implementation (pimpl) and version the soname; ask before breaking ABI.
- Do not mix runtimes or standard-library ABIs (for example MSVC debug and release runtimes, or libstdc++ and libc++) across library boundaries.

## Done when

- [ ] The project's build, tests (through CTest or its runner) and format check pass on the configured presets.
- [ ] Changed code compiles without new warnings at the project's warning level, at the declared standard.
- [ ] Tests ran under AddressSanitizer and UndefinedBehaviorSanitizer, and under ThreadSanitizer for concurrent changes, or the report says why not.
- [ ] No owning raw pointers, no stored views into temporaries, no references held across container mutation in new code.
- [ ] Public headers and ABI of shipped libraries are unchanged, or the break was agreed.
