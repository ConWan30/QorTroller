"""Build paste-ready Cowork bundle: base64 file bodies for exact sha256 recovery."""
from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "docs/a2a/poep/poep-gameplay-live-design.md",
    "docs/a2a/poep/round-live-01-grok-open.md",
    "docs/a2a/poep/poep-gameplay-live-loop.md",
    "docs/a2a/pkg/mailbox/outbox/7096757871bd5c06.json",
    "docs/a2a/poep/COWORK-HANDOFF-live-dual-connect.md",
]
# honesty model for live build
OPTIONAL = [
    "l9_presence/poep_gameplay_session.py",
]
OUT_MD = ROOT / "docs/a2a/poep/COWORK-PASTE-BUNDLE-live-dual-connect.md"
OUT_ZIP = ROOT / "docs/a2a/poep/cowork-poep-live-sealed.zip"
DESKTOP_DIR = Path.home() / "Desktop" / "cowork-poep-live"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    all_rels = FILES + OPTIONAL
    items: list[tuple[str, str, str]] = []  # path, sha, b64
    for rel in all_rels:
        raw = (ROOT / rel).read_bytes()
        items.append((rel, sha256(raw), base64.standard_b64encode(raw).decode("ascii")))

    # zip for drag-drop attach
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, h, _ in items:
            zf.write(ROOT / rel, arcname=rel.replace("\\", "/"))
        # flat copies also at zip root for easy open
        for rel, h, _ in items:
            zf.write(ROOT / rel, arcname=Path(rel).name)

    for rel, h, _ in items:
        (DESKTOP_DIR / Path(rel).name).write_bytes((ROOT / rel).read_bytes())
    (DESKTOP_DIR / "cowork-poep-live-sealed.zip").write_bytes(OUT_ZIP.read_bytes())

    lines: list[str] = []
    lines.append("# COWORK PASTE BUNDLE — poep-gameplay-live (base64, exact pins)")
    lines.append("")
    lines.append("Attachments may fail. **Paste this whole file** into Cowork and run §0.")
    lines.append("Alternatively attach **`cowork-poep-live-sealed.zip`** from operator Desktop folder")
    lines.append("`%USERPROFILE%\\Desktop\\cowork-poep-live\\`.")
    lines.append("")
    lines.append("## 0. Extract + verify (Cowork)")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 <<'PY'")
    lines.append("from pathlib import Path")
    lines.append("import base64, hashlib, re, sys")
    lines.append("bundle = Path('COWORK-PASTE-BUNDLE-live-dual-connect.md')")
    lines.append("for cand in [bundle, Path('docs/a2a/poep')/bundle.name]:")
    lines.append("    if cand.is_file():")
    lines.append("        bundle = cand; break")
    lines.append("text = bundle.read_text(encoding='utf-8')")
    lines.append("blocks = re.split(r'(?m)^### FILE: ', text)")
    lines.append("n = 0")
    lines.append("for b in blocks[1:]:")
    lines.append("    header, _, rest = b.partition(chr(10))")
    lines.append("    path_s, _, meta = header.partition('|')")
    lines.append("    path = path_s.strip()")
    lines.append("    m = re.search(r'sha256=([0-9a-f]{64})', meta)")
    lines.append("    expect = m.group(1)")
    lines.append("    m2 = re.search(r'```(?:b64|base64)?\\n(.*?)\\n```', rest, re.S)")
    lines.append("    if not m2:")
    lines.append("        print('NO_B64', path); sys.exit(2)")
    lines.append("    raw = base64.standard_b64decode(''.join(m2.group(1).split()))")
    lines.append("    got = hashlib.sha256(raw).hexdigest()")
    lines.append("    Path(path).parent.mkdir(parents=True, exist_ok=True)")
    lines.append("    Path(path).write_bytes(raw)")
    lines.append("    ok = got == expect")
    lines.append("    print(('OK' if ok else 'MISMATCH'), got, path)")
    lines.append("    if not ok: sys.exit(2)")
    lines.append("    n += 1")
    lines.append("print('ALL_PINS_OK', n)")
    lines.append("PY")
    lines.append("```")
    lines.append("")
    lines.append("## 1. Pin table")
    lines.append("")
    lines.append("| path | sha256 |")
    lines.append("|------|--------|")
    for rel, h, _ in items:
        lines.append(f"| `{rel}` | `{h}` |")
    lines.append("")
    lines.append("- envelope_id: `7096757871bd5c06`")
    lines.append("- design (prior): first row above")
    lines.append("- body (LIVE-01): second row")
    lines.append("")
    lines.append("## 2. Mandate after ALL_PINS_OK")
    lines.append("")
    lines.append("```text")
    lines.append("Ground against design + LIVE-01. BUILD L1+L2 only.")
    lines.append("Dry non-candidate. MIN_GO_*=2. amplitude 60/80. poep_enabled False.")
    lines.append("No desk campaigns. No commit. Write round-live-02-claude-build.md")
    lines.append("If MISMATCH: re-HOLD.")
    lines.append("```")
    lines.append("")
    lines.append("## 3. Base64 file bodies")
    lines.append("")
    for rel, h, b64 in items:
        # wrap b64 at 76 cols
        wrapped = "\n".join(b64[i : i + 76] for i in range(0, len(b64), 76))
        lines.append(f"### FILE: {rel} | sha256={h}")
        lines.append("")
        lines.append("```b64")
        lines.append(wrapped)
        lines.append("```")
        lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (DESKTOP_DIR / OUT_MD.name).write_text(OUT_MD.read_text(encoding="utf-8"), encoding="utf-8")

    # self-test extract
    text = OUT_MD.read_text(encoding="utf-8")
    import re
    blocks = re.split(r"(?m)^### FILE: ", text)
    for b in blocks[1:]:
        header, _, rest = b.partition("\n")
        path_s, _, meta = header.partition("|")
        path = path_s.strip()
        expect = re.search(r"sha256=([0-9a-f]{64})", meta).group(1)
        m2 = re.search(r"```(?:b64|base64)?\n(.*?)\n```", rest, re.S)
        raw = base64.standard_b64decode("".join(m2.group(1).split()))
        got = sha256(raw)
        assert got == expect, (path, got, expect)
        assert raw == (ROOT / path).read_bytes()
    print("BUNDLE_OK", OUT_MD)
    print("ZIP_OK", OUT_ZIP)
    print("DESKTOP", DESKTOP_DIR)
    for rel, h, _ in items:
        print(h, rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
