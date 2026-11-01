# Perl

Read this before writing or changing Perl: scripts, modules, web applications (Mojolicious, Dancer2, Catalyst, CGI), text-processing tools and the tests around them. It covers modern idioms by version, the toolchain, security traps and testing. Recovering what an old, undocumented Perl system does before changing it is `legacy-modernization.md`; command-line design is `cli-tools.md`.

## Orient first

- **Perl version:** `perl -v`, the `use v5.xx;` line at the top of files, `requires 'perl'` in `cpanfile`, `MIN_PERL_VERSION` in `Makefile.PL`, or the system the code is deployed on. Long-lived systems often run whatever the operating system ships, which can be several releases old. Write for the oldest version the code must run on.
- **Dependencies:** `cpanfile` with `cpanfile.snapshot` (Carton) is the lockfile pattern; `Makefile.PL`, `Build.PL` or `dist.ini` (Dist::Zilla) for distributions. Install into the project, never into the system Perl: `carton install` then `carton exec -- prove -lr t`, or `cpanm --local-lib=local --installdeps .` with `local::lib`.
- **Tools the project may configure:** Perl::Tidy (`.perltidyrc`) for formatting, Perl::Critic (`.perlcriticrc`) for linting, `prove` for tests, Devel::Cover for coverage. Run what is configured; add new tools only with agreement.

```bash
perl -c lib/App/Orders.pm                  # syntax check (compiles; runs BEGIN blocks)
prove -lr t                                # run the test suite with lib/ on @INC
perlcritic --profile .perlcriticrc lib     # if configured
perltidy -b -bext='/' lib/App/Orders.pm    # if configured; or check-only per the project
```

`perl -c` executes `BEGIN` blocks and `use` statements, so it runs code from the modules it loads; do not run it on untrusted code.

## Modern Perl by version

| Feature | Available from |
|---|---|
| `say`, `state`, `//` (defined-or) | 5.10 |
| Postfix dereference (`$aref->@*`, `$href->%*`) | 5.24 (stable) |
| `isa` operator (`$obj isa My::Class`) | 5.32 (experimental), 5.36 (stable) |
| Subroutine signatures stable; `use v5.36` enables `strict`, `warnings`, `say` and signatures, and disables indirect-object syntax | 5.36 (May 2022) |
| `builtin::` functions (`true`, `false`, `trim`, `blessed`, `weaken`, `ceil`, `floor`) | 5.36 (experimental), most stable in 5.40 |
| `class`, `field`, `method` (core object system) | 5.38 (experimental; still experimental in 5.42, July 2025) |
| `try`/`catch`/`finally` stable; `for my ($k, $v) (%h)` stable | 5.40 (June 2024) |

- Start modules and scripts with the version bundle the project's minimum allows (`use v5.36;`). On older Perls, `use strict; use warnings;` at the top of every file, always.
- Signatures replace `my ($self, %args) = @_;` unpacking and check argument counts:

```perl
use v5.36;

sub order_total ($lines, $discount = 0) {
    my $sum = 0;
    $sum += $_->{qty} * $_->{unit_cents} for $lines->@*;
    return $sum - $discount;
}
```

- Experimental features print warnings and can change between releases. Do not adopt `class` or other experimental syntax in production code unless the project already uses it and pins the Perl version.

## Idioms that prevent bugs

- **Context:** the same expression returns different things in list and scalar context (`my $count = @items;` versus `my ($first) = @items;`; `localtime` returns a string in scalar context). `return;` (not `return undef;`) returns an empty list in list context, so `if (my @r = f())` behaves.
- **References and nesting:** autovivification creates intermediate hashes on read (`exists $h{a}{b}` creates `$h{a}`). Check each level, or use `no autovivification` if the project uses that module.
- **Errors:** `die` with an object or a message ending in `\n` (no line number) for user-facing errors. With `eval { }`, `$@` can be clobbered by destructors and nested evals; the safe pattern is `eval { ...; 1 } or do { my $err = $@ || 'unknown error'; ... }`. On 5.40 and later, `try`/`catch` is cleaner; on older Perls, Try::Tiny.
- **Strings and encodings:** decode input at the boundary (`Encode::decode('UTF-8', $bytes)` or an `:encoding(UTF-8)` layer on file handles), work with characters inside, encode on output. `use utf8;` only declares that the source file contains UTF-8 literals. Mixing bytes and characters produces "Wide character" warnings and double-encoded text.
- **Files:** three-argument `open` with lexical handles and checked results (or `use autodie;`): `open(my $fh, '<:encoding(UTF-8)', $path) or die "open $path: $!";`. Path::Tiny if the project uses it.
- **Regular expressions:** `/x` with comments for anything non-trivial, named captures (`(?<year>\d{4})` read through `%+`), `\A` and `\z` anchors for whole-string validation (`$` also matches before a trailing newline), and `qr//` for patterns reused in loops.
- **Objects:** Moo for lightweight classes with typed attributes (with Type::Tiny constraints); Moose where its meta-object protocol is already used. Plain `bless`ed hashes in existing code are fine to keep; do not rewrite an object system as part of a feature.
- **Modules:** one package per file, `package App::Orders;` matching `lib/App/Orders.pm`, `use Exporter 'import'` with `our @EXPORT_OK` (export nothing by default), and a true final value (`1;`) unless the version bundle makes it implicit (5.38 and later).

## Security

Most Perl vulnerabilities come from the shell, `open`, string `eval` and SQL. Review every place where outside data reaches them.

- **Commands:** `system('convert', $in, $out)` with a list of two or more arguments runs without a shell. A single string (`system("convert $in $out")`), backticks and `qx//` with interpolated data go through `/bin/sh` and are command injection. To capture output safely, use `open(my $fh, '-|', 'git', 'log', '--format=%H', $ref)` or IPC::Run3 / IPC::Open3 with argument lists. Put `--` before user-supplied arguments when the program supports it.
- **Two-argument `open`** interprets leading or trailing characters in the file name (`|cmd`, `>file`, `<`). Always use three-argument `open`.
- **SQL:** DBI placeholders for every value (`$dbh->prepare('SELECT ... WHERE id = ?')` then `execute($id)`); identifiers chosen from an allowlist or quoted with `$dbh->quote_identifier`. Never interpolate into SQL strings. DBIx::Class builds parameterized queries but accepts literal SQL through `\` references, which need the same care.
- **Taint mode** (`#!perl -T`) marks outside data (environment, arguments, input) as tainted and refuses to use it in shell, file and `eval` operations until it passes through a regex capture. Untaint with a strict pattern for the expected shape (`/\A([\w.-]{1,64})\z/`), never with `/(.*)/`. Under taint mode, set `$ENV{PATH}` to a fixed value and delete `IFS`, `CDPATH`, `ENV` and `BASH_ENV`.
- **Code execution:** no string `eval` on data; no `require` or `do` on paths built from input. `Storable::thaw`, `retrieve` and YAML loaders that create blessed objects can run code through destructors on untrusted input; use JSON for data from outside, and turn off object loading in YAML modules (`$YAML::XS::LoadBlessed = 0`).
- **Regex denial of service:** nested quantifiers such as `(a+)+` on untrusted input backtrack exponentially. Rewrite them, use possessive quantifiers or atomic groups (`(?>...)`), bound input length, and never compile user input as a pattern without `quotemeta` (`\Q...\E`).
- **Web output:** use the template engine's escaping (Mojolicious `<%= %>` escapes, `<%== %>` does not; Template Toolkit needs the `html` filter unless configured to escape by default). Encode for the context: HTML, URL, JavaScript, JSON.
- **Files and paths:** resolve user-supplied paths with `Cwd::realpath` or Path::Tiny's `realpath` and check they stay under an allowed root; create temporary files with File::Temp, not predictable names.
- **Randomness:** `rand` is not for tokens or passwords; use Crypt::URandom, or Crypt::PRNG from CryptX if the project has it.

## Testing

- `t/*.t` files run under `prove`; each prints TAP. Test::More is everywhere; Test2::V0 (the modern suite) gives better deep comparisons and diagnostics and coexists with Test::More tests.

```perl
use v5.36;
use Test2::V0;
use App::Orders qw(order_total parse_order);

is order_total([{ qty => 2, unit_cents => 500 }]), 1000, 'sums quantity times price';
like dies { order_total(undef) }, qr/lines required/, 'rejects missing lines';
is parse_order('{"id":7,"lines":[]}'), hash { field id => 7; field lines => []; end; }, 'parses the shape';
done_testing;
```

- `subtest` groups related checks; `done_testing` instead of a fixed plan unless the project uses plans.
- **Isolation:** each test file runs in its own process; within a file, do not share mutable globals between subtests. Use File::Temp for files and an in-memory or containerized database for data access.
- **Mocking:** Test::MockModule (restores the original when the mock object goes out of scope) or Test2::Mock; never assign to a glob (`*Pkg::fetch = sub {...}`) without restoring it, which leaks into later tests.
- **Time and network:** inject clocks and HTTP clients; Test::MockTime or a passed-in `now` for time-dependent code.
- `prove -lr -j4 t` runs files in parallel; tests that share a database or fixed paths must not then collide.
- **Coverage:** `cover -test` (Devel::Cover) writes an HTML report; use it to find untested branches, not as a score.

## Review checklist

- [ ] `strict` and `warnings` (or a version bundle that enables them) in every file.
- [ ] No string-form `system`, backticks or two-argument `open` with outside data; DBI placeholders everywhere.
- [ ] No string `eval`, `Storable` or blessed-object YAML loading on untrusted input.
- [ ] Encoding is decoded at input and encoded at output; no mixed byte and character strings.
- [ ] Regexes on untrusted input have no nested quantifiers and use `\A`/`\z` for validation.
- [ ] Syntax and features match the minimum Perl version; no experimental features without a pinned version.

## Done when

- [ ] `prove -lr t` passed, plus Perl::Critic and Perl::Tidy checks where configured.
- [ ] Dependencies were installed into a local library (Carton or `local::lib`), never the system Perl, and `cpanfile` and the snapshot were updated together.
- [ ] Security-relevant changes have tests with hostile input (shell metacharacters, `../` paths, quotes in SQL values).
- [ ] The report states the Perl version tested and any version the code was not tested on.
