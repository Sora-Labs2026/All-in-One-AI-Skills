# Content-hash caching for expensive processing

Read this when the same files or records are processed again and again (parsing PDFs, OCR, extracting text, computing embeddings, transcoding, feature extraction, model scoring) and you want to skip work whose inputs have not changed. Caching in request paths (Redis, HTTP, CDN) is in `../../engineering-practices/references/performance.md` and `redis.md`.

## The idea

Key each result by a hash of everything that determines it, not by a file name or path. Then:

- a renamed or moved file is still a hit;
- a changed file, a new tool version or a different setting is automatically a miss;
- identical inputs from different places share one entry.

It fits work that is deterministic (same inputs, same output), expensive compared with hashing, and repeated across runs or users. It does not fit results that depend on time, live data or randomness you do not control.

## What goes into the key

The most common bug is a key that omits an input. Include:

1. **The content:** a hash of the input bytes (or, for many inputs, of a sorted manifest of their names and hashes).
2. **The processor identity:** a version string you bump whenever the code's output changes, plus the versions of libraries or models that affect the output (parser version, OCR engine, embedding model and revision).
3. **The configuration:** every option that changes the output (language, page range, resolution, chunk size), serialized canonically.
4. **The output format version,** so a change to how results are stored invalidates old entries.

Serialize these as one canonical structure before hashing, so that two different inputs can never produce the same byte string.

## A small, safe implementation

```python
import hashlib, json, os, tempfile
from pathlib import Path

PROCESSOR = {"name": "pdf-text", "version": "3", "parser": "pdfminer.six 20240706"}
FORMAT_VERSION = 2

def content_digest(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()   # Python 3.11+; read in chunks on older versions

def cache_key(path: Path, config: dict) -> str:
    material = {"content": content_digest(path), "processor": PROCESSOR,
                "config": config, "format": FORMAT_VERSION}
    blob = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()

def cached_run(path: Path, config: dict, compute, root: Path = Path(".cache/pdf-text")):
    key = cache_key(path, config)
    entry = root / key[:2] / f"{key}.json"          # fan out to keep directories small
    try:
        stored = json.loads(entry.read_text(encoding="utf-8"))
        if stored.get("key") == key:
            return stored["result"]                   # hit
    except (FileNotFoundError, ValueError):
        pass                                          # missing or corrupt: treat as a miss
    result = compute(path, **config)                  # the processing function knows nothing about caching
    entry.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=entry.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"key": key, "result": result}, f)
    os.replace(tmp, entry)                            # atomic rename: readers never see half a file
    return result
```

- **Atomic writes:** write to a temporary file in the same directory, then rename. A crash leaves a stray temporary file, never a truncated entry. Concurrent writers of the same key write the same content, so the last rename winning is harmless.
- **Corruption is a miss:** unreadable or mismatched entries are recomputed (and may be deleted), never fatal.
- **Keep the processing pure:** a wrapper adds caching; the function itself stays testable without a cache. Offer `--no-cache` and `--refresh` switches for debugging.
- **Do not cache failures** as if they were results. Cache "this input is unparseable" only deliberately, with the processor version in the key so a fixed parser retries.
- Log hits and misses with a shortened key, and report the hit rate at the end of a run.

## Speed of the key itself

- Hashing reads every byte. For large files that rarely change, keep a small index of `path -> (size, mtime_ns, inode, digest)` and reuse the digest when the first three match. Timestamps can mislead (coarse resolution, tools that preserve times, edits within the same tick), so treat this as a hint: rehash when a file's recorded modification time was very close to when you recorded it, and offer a full-verify mode.
- `hashlib.sha256` and `hashlib.blake2b` are both fine; BLAKE2 is often faster in the standard library. Faster non-cryptographic hashes (xxHash family) are acceptable only when nobody can craft inputs to collide with someone else's entry, which rules them out for caches shared across users or trust boundaries. Never use MD5 or SHA-1 where inputs may be adversarial.

## Size, eviction and cleanup

- Give the cache a size cap and an eviction rule (least recently used by a recorded last-access time; file access times are unreliable on many mounts).
- Provide a `cache clean` command and document where the cache lives. Never place it inside the source tree without a `.gitignore` entry.
- Results that are large (images, embeddings for whole corpora) belong in an object store or a columnar file keyed the same way, with the index in a small database.

## Security and privacy

- A cache holds copies of the processed data. If the inputs are personal or confidential, the cache inherits their sensitivity, retention and deletion duties; deleting a source document must also delete its cached outputs.
- Never deserialize formats that execute code (Python `pickle`, `joblib` files built on it) from a cache another user or job can write to. Prefer JSON, Parquet, Arrow or `safetensors`.
- CI caches: an entry restored in a privileged job must have been written by a trusted job. Do not let untrusted pull-request jobs write caches that release jobs read (`../../code-security-review/GUIDE.md`).

## Where this already exists

Use the tool's own mechanism before writing one: build systems and package managers with content-addressed caches, CI caches keyed on the lockfile hash (`hashFiles('**/package-lock.json')` in GitHub Actions), pipeline orchestrators with cache keys on task inputs, data versioning tools with run caches, and `joblib.Memory` for local Python experiments (pickle caveat above). The rules about complete keys and versions apply to all of them.

## Checks (done when)

- [ ] The key covers content, processor and library versions, configuration and output format; a test proves that changing each one causes a miss.
- [ ] A test proves that renaming or moving an input is a hit.
- [ ] Writes are atomic; a corrupt entry is recomputed; failures are not cached by accident.
- [ ] The cache has a location, a size cap, a clean command and a stated retention; sensitive inputs make it sensitive.
- [ ] The run reports hit and miss counts, and timings with and without the cache were measured.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Key by path or name | Hash the content |
| New parser version returns old results | Processor and library versions in the key |
| Same file, different settings, same result | Configuration in the key |
| Half-written entries after a crash | Temporary file plus atomic rename |
| `pickle` loaded from a shared cache | Data-only formats |
| Cache grows until the disk fills | Size cap, eviction, clean command |
