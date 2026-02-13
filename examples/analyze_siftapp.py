#!/usr/bin/env python3
"""
Inspect legacy .siftapp containers to aid reverse engineering.

This performs non-destructive structural analysis:
- header fields
- size/alignment/entropy
- token/internal-id collisions
- optional crypto candidate scan (heuristic; not guaranteed)
"""

from __future__ import annotations

import argparse
import collections
import math
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = collections.Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def parse_header(data: bytes) -> dict:
    if len(data) < 16:
        return {"valid": False}
    return {
        "prefix": data[:8].hex(),
        "token_u32_le": struct.unpack_from("<I", data, 8)[0],
        "token_bytes": data[8:12].hex(),
        "suffix": data[12:16].hex(),
    }


def scan_crypto_candidates(path: Path, data: bytes) -> list[tuple]:
    """
    Try a small set of AES decrypt candidates via openssl and report
    signature hits near the start of plaintext.
    """
    if shutil.which("openssl") is None:
        return []

    words = [0x2BF0510B, 0x559C91B1, 0x9DCC27F9, 0xD727C08A]
    keys = {
        "epy_le": b"".join(struct.pack("<I", w) for w in words),
        "epy_be": b"".join(struct.pack(">I", w) for w in words),
        "header16": data[:16],
    }
    ivs = {
        "zero": b"\x00" * 16,
        "header16": data[:16],
        "epyiv_le": b"".join(
            struct.pack("<I", w) for w in [0x00010203, 0x04050607, 0x08090A0B, 0x0C0D0E0F]
        ),
        "epyiv_be": b"".join(
            struct.pack(">I", w) for w in [0x00010203, 0x04050607, 0x08090A0B, 0x0C0D0E0F]
        ),
    }
    modes = ["aes-128-cbc", "aes-128-cfb", "aes-128-ctr", "aes-128-ecb"]
    signatures = [b"\x7fELF", b"MZ", b"PK\x03\x04", b"manifest.json"]

    ct = data[16:]
    hits = []
    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / "cipher.bin"
        in_path.write_bytes(ct)
        for key_name, key in keys.items():
            for mode in modes:
                mode_ivs = {"none": b""} if mode == "aes-128-ecb" else ivs
                for iv_name, iv in mode_ivs.items():
                    cmd = [
                        "openssl",
                        "enc",
                        f"-{mode}",
                        "-d",
                        "-nopad",
                        "-K",
                        key.hex(),
                        "-in",
                        str(in_path),
                    ]
                    if mode != "aes-128-ecb":
                        cmd += ["-iv", iv.hex()]
                    try:
                        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                    except subprocess.CalledProcessError:
                        continue

                    head = out[:4096]
                    ascii_ratio = sum(1 for b in head if 32 <= b < 127) / max(1, len(head))
                    for sig in signatures:
                        pos = head.find(sig)
                        if pos != -1 and pos < 512:
                            hits.append(
                                (
                                    path.name,
                                    key_name,
                                    mode,
                                    iv_name,
                                    sig.decode("latin1", errors="ignore"),
                                    pos,
                                    round(ascii_ratio, 4),
                                )
                            )
    return hits


def analyze_file(path: Path, scan_crypto: bool) -> dict:
    data = path.read_bytes()
    hdr = parse_header(data)
    info = {
        "path": str(path),
        "name": path.name,
        "size": len(data),
        "size_mod_16": len(data) % 16,
        "entropy_full": shannon_entropy(data),
        "entropy_body": shannon_entropy(data[16:]) if len(data) > 16 else 0.0,
        "tail_u32_le": struct.unpack_from("<I", data, len(data) - 4)[0] if len(data) >= 4 else None,
        "header": hdr,
        "crypto_hits": scan_crypto_candidates(path, data) if scan_crypto else [],
    }
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze legacy .siftapp container structure.")
    parser.add_argument(
        "path",
        nargs="?",
        default="sifteo-gen1-redux/payload/Siftapps",
        help="Path to a .siftapp file or directory of .siftapp files.",
    )
    parser.add_argument(
        "--scan-crypto",
        action="store_true",
        help="Run heuristic AES candidate scans via openssl.",
    )
    args = parser.parse_args()

    base = Path(args.path)
    if not base.exists():
        raise SystemExit(f"Path not found: {base}")

    if base.is_dir():
        files = sorted(base.glob("*.siftapp"))
    else:
        files = [base]

    if not files:
        raise SystemExit(f"No .siftapp files found at: {base}")

    reports = [analyze_file(p, args.scan_crypto) for p in files]
    print(f"Analyzed {len(reports)} .siftapp file(s)\n")

    token_map: dict[int, list[str]] = collections.defaultdict(list)
    internal_map: dict[int, list[str]] = collections.defaultdict(list)

    for r in reports:
        h = r["header"]
        token = h.get("token_u32_le")
        token_bytes = h.get("token_bytes", "n/a")
        internal_id = None
        if token is not None:
            token_map[token].append(r["name"])
            # convention in preserved files: byte[10] tracks "internal id"
            internal_id = int(token_bytes[4:6], 16)
            internal_map[internal_id].append(r["name"])

        print(
            f"{r['name']}: size={r['size']} mod16={r['size_mod_16']} "
            f"H={r['entropy_full']:.4f}/{r['entropy_body']:.4f} "
            f"token={token_bytes} tail=0x{r['tail_u32_le']:08x}"
        )

    shared_tokens = {k: v for k, v in token_map.items() if len(v) > 1}
    shared_internal = {k: v for k, v in internal_map.items() if len(v) > 1}

    print("\nShared token values:")
    if shared_tokens:
        for token, names in sorted(shared_tokens.items(), key=lambda kv: kv[0]):
            print(f"  0x{token:08x}: {', '.join(names)}")
    else:
        print("  (none)")

    print("\nShared internal-id byte values:")
    if shared_internal:
        for iid, names in sorted(shared_internal.items(), key=lambda kv: kv[0]):
            print(f"  0x{iid:02x}: {', '.join(names)}")
    else:
        print("  (none)")

    if args.scan_crypto:
        print("\nCrypto candidate hits (heuristic):")
        hits = [hit for r in reports for hit in r["crypto_hits"]]
        if not hits:
            print("  none")
        else:
            for hit in hits:
                name, key_name, mode, iv_name, sig, pos, ascii_ratio = hit
                print(
                    f"  {name}: key={key_name} mode={mode} iv={iv_name} "
                    f"sig={sig!r}@{pos} ascii_ratio={ascii_ratio}"
                )


if __name__ == "__main__":
    main()
