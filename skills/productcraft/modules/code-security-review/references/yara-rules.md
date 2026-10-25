# YARA rules for detecting malicious files

Reference for the `code-security-review` module. Read it when the user wants detection rules for suspicious files: samples from an incident, malicious packages or extensions found during a supply-chain review, webshells on a server, booby-trapped documents. YARA matches byte and string patterns in files or memory. It does not watch behavior or network traffic, and a plain hash list is simpler when only exact files matter.

**Detection only.** Write rules that recognize malicious files. Never write, modify, build, unpack-and-run or "improve" malware, and never produce a working malicious sample to test a rule; test against real samples the user already holds and against clean files. Describe indicators, not how to build or evade them. Decline requests for evasion.

**Contents:** [Handling samples](#handling-samples) · [Rule anatomy](#rule-anatomy) · [Choosing strings](#choosing-strings) · [Conditions](#conditions) · [Testing](#testing) · [Supply-chain scanning](#supply-chain-scanning) · [Reporting hits](#reporting-hits)

## Handling samples

- Never execute a sample or open it in the application it targets. Analyze on a dedicated virtual machine or analysis host with no credentials, no shared folders and no access to production networks; a container is not enough for live malware (`../../agent-safety/references/isolation.md`).
- Keep samples in password-protected archives (the common convention is the password `infected`) so they are not opened or quarantined by accident, and record each sample's SHA-256.
- Do not upload samples or the user's private files to public scanning services without the owner's agreement; uploads are shared with other subscribers and can alert the attacker.
- Commit rules and the hashes of their test samples, not the samples themselves, unless the repository is a restricted sample store.

## Rule anatomy

```yara
rule MAL_Lnx_ExampleLoader_Config_2026_10
{
    meta:
        description = "Detects the config block of the (fictional) ExampleLoader family by its marker plus one family-specific artifact"
        author = "Security team"
        date = "2026-10-25"
        reference = "Internal case 2026-117"
        hash1 = "<sha256 of sample 1>"
        hash2 = "<sha256 of sample 2>"
        score = 80

    strings:
        $cfg_marker = "EXLCFG-v2|" ascii
        $lock_file  = "/tmp/.exl-lock-7f3a" ascii
        $key_sched  = { 9E 37 79 B9 ?? ?? 7F 4A 7C 15 }
        $user_agent = "Mozilla/5.0 (X11; ExampleUpdater/2.3)" ascii

    condition:
        uint32(0) == 0x464C457F            // "\x7fELF", read as a little-endian integer
        and filesize < 5MB
        and $cfg_marker
        and 1 of ($lock_file, $key_sched, $user_agent)
}
```

- **Name:** follow the team's convention. If there is none, use a prefix for confidence (`MAL_` for a known family, `SUSP_` for suspicious traits used in hunting, `HKTL_` for dual-use tools, `WEBSHELL_`), then platform, family, what is matched, and a date.
- **Meta:** what the rule matches and how, author, date, reference, the hashes it was built from, and a score or severity if the consuming system uses one. Update a `modified` date on every change.
- **Strings:** named by role (`$cfg_`, `$ua_`, `$code_`) so conditions can use groups.
- **Condition:** cheap checks first, then strings.

## Choosing strings

**Strong** (the author chose them, and changing them means rebuilding): configuration markers and keys, mutex or lock-file names, custom protocol headers and user agents, build and debug paths left in binaries, embedded constants used by the family's own code, distinctive typos in messages, specific command-and-control URL paths.

**Supporting:** code sequences specific to the family, written as hex with wildcards for addresses and registers (`{ 8B 45 ?? 33 C9 [2-6] E8 }`); resource names; section names.

**Weak, never alone:** API and function names (`VirtualAlloc`, `CreateRemoteThread`, `fetch`, `eval`), strings from libraries, runtimes and compilers, common commands and paths (`cmd.exe`, `/bin/sh`, `powershell`), anything belonging to a packer rather than the payload.

- YARA selects short fixed substrings ("atoms", about four bytes) from each string to prefilter files quickly. Strings shorter than four bytes, or made of repeated bytes (`00 00 00 00`, `90 90 90 90`), make almost every file a candidate and slow the whole rule set.
- **Modifiers cost work; add them only on evidence.** `wide` when the sample stores UTF-16 text, `nocase` when case really varies between samples, `fullword` to stop substring matches, `xor` or `base64` when the sample stores the string encoded (bound the key range, for example `xor(0x01-0xff)`).
- **Packed samples** (high entropy, few readable strings) need a rule on the unpacked payload or a separate `SUSP_` rule for the packer. A family rule built on a packer stub matches every program packed the same way.
- **String extraction tools** (`strings -a -n 8`, `strings -a -e l` for UTF-16LE, FLOSS for obfuscated strings) and automatic rule generators produce candidates. Expect to discard most of them after checking each against clean files.

## Conditions

Check the file type and size first. `uint16`, `uint32` and friends read little-endian; `uint16be` and `uint32be` read big-endian. Write the bytes reversed for the little-endian forms:

| File type | Bytes on disk | Condition |
|---|---|---|
| Windows PE | `4D 5A` ... `50 45 00 00` at the offset stored at `0x3C` | `uint16(0) == 0x5A4D and uint32(uint32(0x3C)) == 0x00004550` |
| ELF | `7F 45 4C 46` | `uint32(0) == 0x464C457F` |
| Mach-O, 64-bit little-endian | `CF FA ED FE` | `uint32(0) == 0xFEEDFACF` |
| Mach-O universal | `CA FE BA BE` | `uint32be(0) == 0xCAFEBABE` (Java class files share this magic; add a Mach-O check such as a small architecture count, `uint32be(4) < 20`) |
| ZIP, and formats built on it (OOXML, JAR, APK) | `50 4B 03 04` | `uint32(0) == 0x04034B50` |
| PDF | `25 50 44 46` (`%PDF`) | `uint32(0) == 0x46445025` |
| Legacy Office (OLE2) | `D0 CF 11 E0 A1 B1 1A E1` | `uint32(0) == 0xE011CFD0 and uint32(4) == 0xE11AB1A1` |
| Android DEX | `64 65 78 0A` (`dex\n`) | `uint32(0) == 0x0A786564` |

A byte-swapped constant raises no error; the rule just never fires. Scan one known file of each type before trusting a magic check.

- **Combine by confidence:** `any of ($strong_*)` only when each strong string is unique on its own; otherwise require combinations such as `$cfg_marker and 2 of ($support_*)`. Generic strings must never be able to fire the rule alone.
- **Position and counts:** `$hdr at 0`, `$cfg in (0..4096)`, `#beacon >= 3`, `@cfg[1] < 1024`.
- **Shared prefilters:** a `private rule` (for example `private rule IsELF { condition: uint32(0) == 0x464C457F }`) keeps file-type logic in one place; other rules use `IsELF and ...`.
- **Regular expressions:** start with a literal of at least four bytes, bound every repetition (`[a-z0-9]{8,16}`, `.{0,40}`), never `.*` or `.+`. Prefer hex strings with jumps (`[0-16]`) when the bytes are fixed.
- **Loops:** guard with `filesize` and bound the range (`for any i in (1..#cfg) : ( ... )`).
- **Modules** (`pe`, `elf`, `math`, `hash`, `dotnet` and others) answer structural questions such as imports, sections, signatures and entropy. Load one only when bytes cannot express the check, and confirm the module and its fields exist in the engine the user deploys: classic YARA (4.x) and YARA-X differ in available modules and in some regular-expression details.

## Testing

A rule is ready when:

1. it compiles without warnings in the engine and version that will run it;
2. it matches every sample in the positive set (several samples, not one; matching only the samples it was written from means it is over-fitted);
3. it matches nothing in a clean set of the same file types: operating-system binaries and libraries, the organization's own software and its dependencies, popular installers and packages from official sources, ordinary documents of the targeted format. Thousands of files of the target type is a reasonable floor;
4. its scan time over a realistic corpus is measured and acceptable;
5. the positive and negative results are stored next to the rule and rerun on every change.

```sh
# Classic YARA (4.x)
yarac rules/example_loader.yar /tmp/example_loader.yarc   # compile; prints slow-pattern warnings
yara -s -r rules/example_loader.yar samples/              # every sample listed, with the matching strings
yara -r rules/example_loader.yar clean/ | wc -l           # expect 0
time yara -r rules/ corpus/ > /dev/null                   # cost of the whole set

# YARA-X
yr check rules/
yr scan rules/example_loader.yar samples/
```

Flags differ between versions, including how directories are walked; check `yara --help` or `yr help scan` for the installed one.

**False positives:** find which string matched (`yara -s`). If it belongs to a common library or framework, replace it with something more specific or require it together with a strong string. Add `not $fp_*` exclusions sparingly; they are brittle. An isolated clean-file hit can often be fixed by tightening the condition; hits on many unrelated files mean the strings are not specific to the family, so choose new ones.

## Supply-chain scanning

YARA works well as a second check after `../../agent-safety/scripts/scan_skill.py` and the dependency review in `secrets-and-dependencies.md`: scan `node_modules/`, a virtualenv's `site-packages/`, a vendored folder or an extension before trusting it (`yara -r rules/ node_modules/`). Single indicators such as `eval`, `fetch`, `child_process` or `process.env` appear in countless legitimate packages; rules need combinations, such as an install hook that downloads and runs code, or credential-file paths together with an outbound request.

```yara
rule SUSP_JS_InstallHook_PipesDownloadToShell
{
    meta:
        description = "Detects package manifests whose install hook downloads a script and pipes it to a shell"
        author = "Security team"
        date = "2026-10-25"
        score = 60

    strings:
        $name = "\"name\"" ascii
        $version = "\"version\"" ascii
        $hook = /"(pre|post)?install"\s*:\s*"[^"]{0,200}(curl|wget)[^"]{0,200}\|\s*(ba)?sh/

    condition:
        filesize < 64KB and $name and $version and $hook
}
```

## Reporting hits

A match means the bytes are present, not that the file is malicious or that it ever ran. Report each hit as a lead with the rule name, file path, SHA-256 and the identifiers of the matched strings, never a dump of malicious content, and say which rule set version and engine produced it. No matches proves little: packing, new variants and encodings the rule does not cover all stay invisible. Confirmed malicious code in a dependency is a supply-chain finding (`secrets-and-dependencies.md`): stop installing it, tell the user which machines and CI runs installed it, and treat credentials those environments held as exposed. For an extension, it means a `REJECT` verdict (`../../agent-safety/references/vetting-extensions.md`).
