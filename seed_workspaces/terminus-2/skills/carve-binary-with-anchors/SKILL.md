---
name: carve-binary-with-anchors
description: Recover strings or structured records from a corrupted / truncated / deleted file when you know some substring of the target. Covers disk-image carving (e.g. "deleted launchcode.txt"), truncated SQLite DBs, binary blobs of unknown format, WAL/journal remnants, and any task where `sqlite3`/`cat`/`strings` alone won't work. Use when a task says "recover", "corrupted", "deleted", "truncated", or the data lives in `.dat`, `.img`, `.raw`, `.bin`, `.db` with a header mismatch.
---

# Carve Binary Data with Anchors

When the data you want is embedded in a larger binary (disk image, damaged DB, memory dump), don't guess — anchor on what you know and widen outward.

## Step 0 — Find the real data source

Tasks often give you a container, not the file. `ls -la /app/` and check for:

- `.dat`, `.img`, `.raw`, `.bin`, `.dd`, `.iso` — raw disk or filesystem images
- `.db`, `.sqlite`, `.db-wal`, `.db-journal` — database + journal
- Large opaque files under a nested dir (`/app/varsea/disks/*.dat` style)

Confirm with:

```bash
file /app/<candidate>
stat /app/<candidate>          # size sanity
xxd /app/<candidate> | head     # first 256 bytes — filesystem or app signature?
```

Do NOT try ext-level undelete (`extundelete`, `debugfs`) on `/` inside the container — the deletion happened in an *image* that ships with the task, not on your running FS. The recovery target is almost always the `.dat`/`.img` file itself.

## Step 1 — Anchor with known substrings

The task almost always tells you something: "starts with `8XD`", "format `PASSWORD=…`", a magic number, a schema string like `testword`. Use `grep -aob` to get every byte offset where the anchor appears:

```bash
grep -aob '8XD'      /app/disk.dat     # occurrences of prefix
grep -aob 'testword' /app/trunc.db     # occurrences of schema literal
grep -aob -P '\x00PNG'  /app/image.raw # bytes via regex
```

`-a` treats the file as text; `-o` prints only the match; `-b` prepends the byte offset. This is your coordinate system.

## Step 2 — Window around each offset

For each offset, pull a small context window with `dd` (byte-precise):

```bash
OFF=12345
dd if=/app/disk.dat bs=1 skip=$((OFF-20)) count=60 status=none \
  | xxd                                        # look at raw bytes
dd if=/app/disk.dat bs=1 skip=$((OFF-20)) count=60 status=none \
  | tr -c 'A-Z0-9' ' ' | tr -s ' ' '\n' | grep .  # filter to expected charset
```

If the target is printable with a known alphabet (uppercase+digits, hex, base64), the `tr -c '<class>' ' '` trick collapses noise into candidate tokens; `sort -u | awk 'length==23'` filters by expected length.

## Step 3 — Enumerate when you can't uniquely identify

If the carve leaves ambiguity (e.g. two plausible 23-char strings matching prefix+suffix), the task often lets you submit multiple guesses — check the verifier. For password-style tasks:

```bash
# Concatenate all windows that contain both anchors, then enumerate
# prefix/suffix splits that add up to the required length.
```

Writing *all* candidates to the answer file (one per line) is usually accepted — a list of 10–1000 guesses is fine.

## Step 4 — For truncated SQLite specifically

- `sqlite3 /app/trunc.db ".schema"` may still work if the header survives. Try it first.
- If `sqlite3` errors with "database disk image is malformed", you can still scan for table-literal strings (`grep -aob 'testword' /app/trunc.db`) and decode cell records byte-by-byte.
- SQLite stores records as `(header-size varint) (type-codes varint*) (payload)`. `testwordXY` (10 bytes) is type `23` or `25` (text length*2+13); the integer that follows is usually type `1..6` (1..6 byte big-endian signed int) or `8`/`9` (literal 0/1). Read one byte of type-code after the string to learn the integer width.
- Python `struct.unpack('>q', b'\x00'*pad + raw)` beats reinventing varint parsing.

## Step 5 — When nothing matches

If `grep -aob anchor file` returns nothing, your anchor is wrong or the data is compressed/encoded:

- Try a fuzzier anchor (first 2 chars).
- Check for compression: `xxd | head` shows `1f 8b` (gzip), `78 9c` (zlib), `fd 37 7a` (xz), `50 4b` (zip), `42 5a 68` (bzip2).
- Check for base64/hex encoding: `head -c 512 file | tr -cd 'A-Za-z0-9+/=' | wc -c` — if near 512, probably base64.

## Anti-patterns

- Running `extundelete` / `testdisk` / `photorec` on `/dev/*` inside a Docker container.
- Assuming `strings file | grep …` is enough — it drops offset info, can't window, and misses non-ASCII.
- Brute-forcing the full keyspace (`8XD…W54` = 17 chars × 36^17) — always carve first, enumerate after.
- Running `sqlite3` once, seeing "malformed", and giving up. You can read the raw bytes.
