#!/usr/bin/env python3
"""Portable behavior checks (no Cursor install required)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apply_patch import (  # noqa: E402
    FORBIDDEN_MARKERS,
    ITERATOR_UPGRADES,
    LR_NEW,
    REPLACEMENTS,
    WORD_NEW,
    WORD_NEW_658,
    WORD_OLD,
    WORD_OLD_658,
    patch_input_bundle,
)


def run_node(script: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.check_output(["node", path], text=True)
    finally:
        Path(path).unlink(missing_ok=True)
    return out.strip()


def test_word_boundaries() -> None:
    out = run_node(
        WORD_NEW
        + r"""
const s = "hello 안녕하세요 world";
const path = [];
let p = s.length;
for (let i = 0; i < 3 && p > 0; i++) {
  p = l(s, p);
  path.push(s.slice(0, p) + "|" + s.slice(p));
}
console.log(JSON.stringify(path));
"""
    )
    expected = [
        "hello 안녕하세요 |world",
        "hello |안녕하세요 world",
        "|hello 안녕하세요 world",
    ]
    got = json.loads(out)
    assert got == expected, got


def test_word_boundaries_658_variant() -> None:
    out = run_node(
        WORD_NEW_658
        + r"""
const s = "hello 안녕하세요 world";
const path = [];
let p = s.length;
for (let i = 0; i < 3 && p > 0; i++) {
  p = l(s, p);
  path.push(s.slice(0, p) + "|" + s.slice(p));
}
console.log(JSON.stringify(path));
"""
    )
    expected = [
        "hello 안녕하세요 |world",
        "hello |안녕하세요 world",
        "|hello 안녕하세요 world",
    ]
    got = json.loads(out)
    assert got == expected, got


def test_stock_word_motion_skips_hangul_658_variant() -> None:
    out = run_node(
        WORD_OLD_658
        + r"""
const s = "hello 안녕하세요 world";
const path = [];
let p = s.length;
for (let i = 0; i < 2 && p > 0; i++) {
  p = l(s, p);
  path.push(s.slice(0, p) + "|" + s.slice(p));
}
console.log(JSON.stringify(path));
"""
    )
    got = json.loads(out)
    assert got == [
        "hello 안녕하세요 |world",
        "|hello 안녕하세요 world",
    ], got


def test_stock_word_motion_skips_hangul() -> None:
    """Unpatched Option+Left treats Hangul as filler and jumps to the previous ASCII word."""
    out = run_node(
        WORD_OLD
        + r"""
const s = "hello 안녕하세요 world";
const path = [];
let p = s.length;
for (let i = 0; i < 2 && p > 0; i++) {
  p = l(s, p);
  path.push(s.slice(0, p) + "|" + s.slice(p));
}
console.log(JSON.stringify(path));
"""
    )
    got = json.loads(out)
    assert got == [
        "hello 안녕하세요 |world",
        "|hello 안녕하세요 world",
    ], got


def test_plain_left_hangul_is_one_syllable() -> None:
    """Stock Left/Right is UTF-16 --, which for NFC Hangul is one syllable. Do not patch this."""
    out = run_node(
        r"""
const s = "hello 안녕하세요";
let p = s.length;
const path = [];
for (let i = 0; i < 6; i++) {
  p -= 1;
  path.push(s.slice(0, p) + "|" + s.slice(p));
}
const g = new Intl.Segmenter(void 0, { granularity: "grapheme" });
let gp = s.length;
const gpath = [];
for (let i = 0; i < 6; i++) {
  let prev = 0;
  for (const seg of g.segment(s.slice(0, gp))) prev = seg.index;
  gp = prev;
  gpath.push(s.slice(0, gp) + "|" + s.slice(gp));
}
console.log(JSON.stringify({ path, gpath }));
"""
    )
    got = json.loads(out)
    assert got["path"] == [
        "hello 안녕하세|요",
        "hello 안녕하|세요",
        "hello 안녕|하세요",
        "hello 안|녕하세요",
        "hello |안녕하세요",
        "hello| 안녕하세요",
    ], got
    assert got["gpath"] == got["path"], got


def test_width2_up_lands_on_wrong_glyph() -> None:
    """Why visual Up/Down is not applied: Hangul width 2 vs caret o++."""
    out = run_node(
        r"""
function upChar(t,e){if(-1===t.indexOf("\n"))return null;const n=Math.min(Math.max(0,e),t.length),r=n<=0?-1:t.lastIndexOf("\n",n-1);if(-1===r)return null;const o=t.lastIndexOf("\n",Math.max(0,r-1)),s=-1===o?0:o+1,c=n-(r+1),i=r-s;return s+Math.min(c,i)}
function cw(t){const e=t.codePointAt(0);if(e>=44032&&e<=55215)return 2;return 1}
function col(t,e,n){let r=0;for(let o=e;o<n;o++)r+=cw(t[o]);return r}
function atCol(t,e,n,r){let o=0,s=e;for(;s<n;s++){const w=cw(t[s]);if(o+w>r)break;o+=w}return s}
function upWidth2(t,e){if(-1===t.indexOf("\n"))return null;const n=Math.min(Math.max(0,e),t.length),r=n<=0?-1:t.lastIndexOf("\n",n-1);if(-1===r)return null;const s=t.lastIndexOf("\n",Math.max(0,r-1)),c=-1===s?0:s+1,i=col(t,r+1,n);return atCol(t,c,r,i)}
function mark(t,i){return t.slice(0,i)+"|"+t.slice(i)}
const s = "안녕하세요\nhello";
console.log(JSON.stringify({
  stock: mark(s, upChar(s, s.length)),
  width2: mark(s, upWidth2(s, s.length)),
}));
"""
    )
    got = json.loads(out)
    assert got["stock"] == "안녕하세요|\nhello", got
    assert got["width2"] == "안녕|하세요\nhello", got


def test_up_down_uses_character_columns() -> None:
    """CLI caret is 1 column per code point; CJK width-2 columns miss the glyph."""
    out = run_node(
        r"""
function up(t,e){if(-1===t.indexOf("\n"))return null;const n=Math.min(Math.max(0,e),t.length),r=n<=0?-1:t.lastIndexOf("\n",n-1);if(-1===r)return null;const o=t.lastIndexOf("\n",Math.max(0,r-1)),s=-1===o?0:o+1,c=n-(r+1),i=r-s;return s+Math.min(c,i)}
function down(t,e){if(-1===t.indexOf("\n"))return null;const n=Math.min(Math.max(0,e),t.length),r=t.indexOf("\n",n);if(-1===r)return null;const o=n<=0?-1:t.lastIndexOf("\n",n-1),s=n-(-1===o?0:o+1),c=r+1,i=t.indexOf("\n",c),u=(-1===i?t.length:i)-c;return c+Math.min(s,u)}
function mark(t,i){return t.slice(0,i)+"|"+t.slice(i)}
const s = "안녕하세요\nhello";
const end = s.length;
const fromH = s.indexOf("\n")+2;
console.log(JSON.stringify({
  upFromEnd: mark(s, up(s, end)),
  upFromE: mark(s, up(s, fromH)),
  downFromAn: mark(s, down(s, 1)),
}));
"""
    )
    got = json.loads(out)
    assert got["upFromEnd"] == "안녕하세요|\nhello", got
    assert got["upFromE"] == "안|녕하세요\nhello", got
    assert got["downFromAn"] == "안녕하세요\nh|ello", got


def test_thai_width() -> None:
    out = run_node(
        r"""
function cw(t) {
  const e = t.codePointAt(0);
  if (e == null) return 1;
  if (/\p{Mn}|\p{Me}|\p{Cf}/u.test(t)) return 0;
  return 1;
}
const thai = "ที่นี่จ้า";
let w = 0;
for (const ch of thai) w += cw(ch);
console.log(String(w));
"""
    )
    assert int(out) == 4, out


def test_hangul_display_width() -> None:
    out = run_node(
        r"""
function cw(t) {
  const e = t.codePointAt(0);
  if (e == null) return 1;
  if (/\p{Mn}|\p{Me}|\p{Cf}/u.test(t)) return 0;
  if (e >= 8203 && e <= 8205 || e === 65279) return 0;
  return e >= 4352 && e <= 4447 || e >= 11904 && e <= 40959 || e >= 44032 && e <= 55215 ||
    e >= 63744 && e <= 64255 || e >= 65072 && e <= 65103 || e >= 65280 && e <= 65376 ||
    e >= 65504 && e <= 65510 || e >= 127744 && e <= 129535 ? 2 : 1;
}
let w = 0;
for (const ch of "안녕") w += cw(ch);
console.log(String(w));
"""
    )
    assert int(out) == 4, out


def test_patcher_has_no_ime_cursor_hack() -> None:
    text = (ROOT / "apply_patch.py").read_text()
    for marker in FORBIDDEN_MARKERS:
        assert marker not in text, f"apply_patch.py still contains {marker!r}"
    assert "def patch_6260" not in text
    assert "log-update.js" not in text
    assert "e.write(" not in text
    assert "upFromBottom" not in text
    assert "[Symbol.iterator]().next()" in LR_NEW
    assert all(old in text for old, _new in ((u[1], u[2]) for u in ITERATOR_UPGRADES))
    assert [label for label, *_ in REPLACEMENTS] == ["empty-line findLine"]


def test_empty_line_findline_maps_blank_not_url() -> None:
    """Stock findLine misses empty lines (start===end); scroll then jumps to the URL."""
    from apply_patch import FIND_LINE_NEW, FIND_LINE_OLD

    out = run_node(
        r"""
function findLineStock(lines, e, textLength) {
  if (e >= textLength) {
    if (0 === lines.length) return {line:0,column:0};
    const last = lines[lines.length-1];
    return {line: lines.length-1, column: last.visualWidth};
  }
  let n=0, r=lines.length-1;
  for (;n<=r;) {
    const o=Math.floor((n+r)/2), s=lines[o];
    if (e>=s.startIndex&&e<s.endIndex) {
      const t=e-s.startIndex;
      return {line:o, column:s.charToColumn[t]||0};
    }
    e<s.startIndex?r=o-1:n=o+1;
  }
  return {line:0, column:0};
}
function findLineFixed(lines, e, textLength) {
  if (e >= textLength) {
    if (0 === lines.length) return {line:0,column:0};
    const last = lines[lines.length-1];
    return {line: lines.length-1, column: last.visualWidth};
  }
  let n=0, r=lines.length-1;
  const t={lines};
  for (;n<=r;) {
    const o=Math.floor((n+r)/2), s=lines[o];
"""
        + FIND_LINE_NEW
        + r"""
  }
  return {line:0, column:0};
}
const lines = [
  {startIndex:0,endIndex:80,visualWidth:80,charToColumn:Object.fromEntries([...Array(81)].map((_,i)=>[i,i]))},
  {startIndex:80,endIndex:120,visualWidth:40,charToColumn:Object.fromEntries([...Array(41)].map((_,i)=>[i,i]))},
  {startIndex:121,endIndex:121,visualWidth:0,charToColumn:{0:0}},
  {startIndex:122,endIndex:127,visualWidth:5,charToColumn:Object.fromEntries([...Array(6)].map((_,i)=>[i,i]))},
  {startIndex:128,endIndex:128,visualWidth:0,charToColumn:{0:0}},
  {startIndex:129,endIndex:129,visualWidth:0,charToColumn:{0:0}},
  {startIndex:130,endIndex:184,visualWidth:54,charToColumn:Object.fromEntries([...Array(55)].map((_,i)=>[i,i]))},
];
const textLength = 184;
console.log(JSON.stringify({
  stockBlank: findLineStock(lines, 129, textLength),
  fixedBlank: findLineFixed(lines, 129, textLength),
  stockEol: findLineStock(lines, 120, textLength),
  fixedEol: findLineFixed(lines, 120, textLength),
  stockKorean: findLineStock(lines, 130, textLength),
  fixedKorean: findLineFixed(lines, 130, textLength),
}));
"""
    )
    got = json.loads(out)
    assert got["stockBlank"] == {"line": 0, "column": 0}, got
    assert got["fixedBlank"] == {"line": 5, "column": 0}, got
    assert got["stockEol"] == {"line": 0, "column": 0}, got
    assert got["fixedEol"]["line"] == 1 and got["fixedEol"]["column"] == 40, got
    assert got["stockKorean"]["line"] == 6, got
    assert got["fixedKorean"]["line"] == 6, got
    assert FIND_LINE_OLD not in FIND_LINE_NEW


def test_empty_line_scroll_keeps_korean_visible() -> None:
    """Wrapped URL + blank above Korean: stock scroll jumps to 0; fixed keeps scroll."""
    from apply_patch import FIND_LINE_NEW

    out = run_node(
        r"""
function findLineStock(lines, e, textLength) {
  if (e >= textLength) {
    const last = lines[lines.length-1];
    return {line: lines.length-1, column: last.visualWidth};
  }
  let n=0, r=lines.length-1;
  for (;n<=r;) {
    const o=Math.floor((n+r)/2), s=lines[o];
    if (e>=s.startIndex&&e<s.endIndex) return {line:o, column:0};
    e<s.startIndex?r=o-1:n=o+1;
  }
  return {line:0, column:0};
}
function findLineFixed(lines, e, textLength) {
  if (e >= textLength) {
    const last = lines[lines.length-1];
    return {line: lines.length-1, column: last.visualWidth};
  }
  let n=0, r=lines.length-1;
  const t={lines};
  for (;n<=r;) {
    const o=Math.floor((n+r)/2), s=lines[o];
"""
        + FIND_LINE_NEW
        + r"""
  }
  return {line:0, column:0};
}
function scrollTo(findLine, lines, e, V1, prev, textLength) {
  const s = lines.length, c = Math.max(0, s - V1);
  let i = Math.min(Math.max(0, prev), c);
  const r = findLine(lines, e, textLength).line;
  r < i ? (i = r) : r >= i + V1 && (i = r - V1 + 1);
  return Math.min(Math.max(0, i), c);
}
const lines = [
  {startIndex:0,endIndex:80,visualWidth:80,charToColumn:{0:0}},
  {startIndex:80,endIndex:120,visualWidth:40,charToColumn:{0:0}},
  {startIndex:121,endIndex:121,visualWidth:0,charToColumn:{0:0}},
  {startIndex:122,endIndex:127,visualWidth:5,charToColumn:{0:0}},
  {startIndex:128,endIndex:128,visualWidth:0,charToColumn:{0:0}},
  {startIndex:129,endIndex:129,visualWidth:0,charToColumn:{0:0}},
  {startIndex:130,endIndex:184,visualWidth:54,charToColumn:{0:0}},
];
const textLength = 184, V1 = 6;
const onKorean = scrollTo(findLineFixed, lines, 130, V1, 0, textLength);
const stockBlank = scrollTo(findLineStock, lines, 129, V1, onKorean, textLength);
const fixedBlank = scrollTo(findLineFixed, lines, 129, V1, onKorean, textLength);
// Soft-wrap shared boundary must stay on the next visual line (not EOL of prev).
const soft = findLineFixed(lines, 80, textLength);
console.log(JSON.stringify({onKorean, stockBlank, fixedBlank, soft}));
"""
    )
    got = json.loads(out)
    assert got["onKorean"] == 1, got
    assert got["stockBlank"] == 0, got
    assert got["fixedBlank"] == 1, got
    assert got["soft"] == {"line": 1, "column": 0}, got


def test_grapheme_steps() -> None:
    out = run_node(
        r"""
function next(t, e) {
  const g = new Intl.Segmenter(void 0, { granularity: "grapheme" });
  const s = g.segment(t.slice(e))[Symbol.iterator]().next().value;
  return e + (s ? s.segment.length : 1);
}
function prev(t, e) {
  if (e <= 0) return 0;
  const g = new Intl.Segmenter(void 0, { granularity: "grapheme" });
  let p = 0;
  for (const s of g.segment(t.slice(0, e))) p = s.index;
  return p;
}
const t = "a👍한";
console.log(JSON.stringify({
  next0: next(t, 0),
  nextA: next(t, 1),
  prevEnd: prev(t, t.length),
  prevHan: prev(t, prev(t, t.length)),
}));
"""
    )
    got = json.loads(out)
    assert got["next0"] == 1, got
    assert got["nextA"] == 3, got  # thumbs-up is two UTF-16 units
    assert got["prevEnd"] == 3, got
    assert got["prevHan"] == 1, got


def test_iterator_upgrade_on_old_patch() -> None:
    from apply_patch import FIND_LINE_OLD

    stub = (
        "__wordSeg granularity:\"grapheme\" n.backspace&&B>0){const __g= function __cw( \\p{Mn}|\\p{Me}|\\p{Cf}"
        "__g.segment(__rest).next().value"
        "__g.segment(J.slice(B)).next().value"
        + FIND_LINE_OLD
    )
    updated, applied = patch_input_bundle(stub)
    assert "grapheme iterator (right)" in applied
    assert "grapheme iterator (delete)" in applied
    assert "empty-line findLine" in applied
    assert ".segment(__rest).next()" not in updated
    assert "[Symbol.iterator]().next()" in updated
    assert FIND_LINE_OLD not in updated


def test_apply_does_not_touch_arrows_or_width() -> None:
    from apply_patch import BS_OLD, FIND_LINE_OLD, LR_OLD, NAV_OLD, TL_OLD

    fixture = "HEAD" + WORD_OLD + LR_OLD + BS_OLD + NAV_OLD + TL_OLD + FIND_LINE_OLD + "TAIL"
    updated, applied = patch_input_bundle(fixture)
    assert applied == ["word helpers", "empty-line findLine"], applied
    assert LR_OLD in updated
    assert BS_OLD in updated
    assert NAV_OLD in updated
    assert TL_OLD in updated
    assert FIND_LINE_OLD not in updated
    assert "e===s.endIndex&&(s.startIndex===s.endIndex" in updated
    assert "__cw" not in updated
    assert 'granularity:"grapheme"' not in updated
    assert "\\p{Mn}|\\p{Me}|\\p{Cf}" not in updated


def test_apply_on_fixture_is_unique_and_valid_js() -> None:
    for old in (WORD_OLD, WORD_OLD_658):
        pieces = ["exports.id=658;exports.modules={};", old]
        for _label, repl_old, _new, _already in REPLACEMENTS:
            pieces.append(repl_old)
        fixture = "".join(pieces)
        updated, applied = patch_input_bundle(fixture)
        assert applied == ["word helpers", "empty-line findLine"], applied
        for marker in FORBIDDEN_MARKERS:
            assert marker not in updated
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(updated)
            path = f.name
        try:
            subprocess.check_call(["node", "--check", path])
        finally:
            Path(path).unlink(missing_ok=True)


def test_one_orig_backup_never_overwritten() -> None:
    import apply_patch as ap

    tmp = Path(tempfile.mkdtemp())
    backup_dir = tmp / "backups"
    backup_dir.mkdir()
    target = tmp / "versions" / "2026.08.11-e8db854" / "4794.index.js"
    target.parent.mkdir(parents=True)
    target.write_text("vanilla")
    previous = ap.BACKUP_DIR
    ap.BACKUP_DIR = backup_dir
    try:
        first = ap.ensure_original_backup(target, "vanilla")
        assert first is not None
        first.write_text("VANILLA-KEEP")
        target.write_text("changed")
        second = ap.ensure_original_backup(target, "vanilla")
        assert second == first
        assert first.read_text() == "VANILLA-KEEP"
        target.write_text("__wordSeg patched")
        assert ap.ensure_original_backup(target, "__wordSeg patched") == first
        assert first.read_text() == "VANILLA-KEEP"
        assert ap.original_backup_for(target) == first
    finally:
        ap.BACKUP_DIR = previous
        shutil.rmtree(tmp, ignore_errors=True)


def test_restore_rejects_dry_run_combo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "apply_patch.py"), "--restore", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "use --restore or --dry-run" in result.stderr + result.stdout


def test_bin_wrapper_body_is_safe_shell() -> None:
    from apply_patch import WRAPPER_MARKER, bin_wrapper_body, is_our_bin_wrapper

    body = bin_wrapper_body(ROOT / "apply_patch.py")
    assert body.startswith("#!/bin/sh\n")
    assert WRAPPER_MARKER in body
    assert "--ensure" in body
    assert "cursor-agent/versions" in body.replace("\\", "/")
    tmp = Path(tempfile.mkdtemp())
    try:
        wrapper = tmp / "agent"
        wrapper.write_text(body)
        assert is_our_bin_wrapper(wrapper)
        other = tmp / "symlink-agent"
        other.symlink_to(wrapper)
        assert not is_our_bin_wrapper(other)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_install_bin_wrappers_replaces_symlink() -> None:
    import apply_patch as ap

    tmp = Path(tempfile.mkdtemp())
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    versions = tmp / "versions" / "2026.09.08-test"
    versions.mkdir(parents=True)
    fake = versions / "cursor-agent"
    fake.write_text("#!/bin/sh\necho real\n")
    fake.chmod(0o755)
    stolen = bin_dir / "agent"
    stolen.symlink_to(fake)
    (bin_dir / "cursor-agent").symlink_to(fake)

    prev_bin, prev_versions = ap.BIN_DIR, ap.DEFAULT_VERSIONS
    ap.BIN_DIR = bin_dir
    ap.DEFAULT_VERSIONS = versions.parent
    try:
        written = ap.install_bin_wrappers()
        assert {p.name for p in written} == {"agent", "cursor-agent"}
        assert ap.is_our_bin_wrapper(bin_dir / "agent")
        assert not (bin_dir / "agent").is_symlink()
        again = ap.install_bin_wrappers()
        assert again == []
    finally:
        ap.BIN_DIR = prev_bin
        ap.DEFAULT_VERSIONS = prev_versions
        shutil.rmtree(tmp, ignore_errors=True)


def test_latest_version_skips_tmp_extract_dirs() -> None:
    import apply_patch as ap

    tmp = Path(tempfile.mkdtemp())
    versions = tmp / "versions"
    versions.mkdir()
    old = versions / "2026.09.01-aaaaaaa"
    new = versions / "2026.09.08-bbbbbbb"
    staging = versions / ".tmp-2026.09.09-ccccccc"
    for d in (old, new, staging):
        d.mkdir()
        (d / "cursor-agent").write_text("#!/bin/sh\n")
    # Make staging newest so a naive mtime sort would pick it.
    import os
    import time

    now = time.time()
    os.utime(old, (now - 30, now - 30))
    os.utime(new, (now - 10, now - 10))
    os.utime(staging, (now, now))
    assert ap.latest_version(versions) == new
    shutil.rmtree(tmp, ignore_errors=True)


def test_repo_privacy() -> None:
    # Concatenate so this file does not embed full forbidden tokens as literals.
    forbidden = (
        "crsr" + "_",
        "Bear" + "er ",
        "sk-" + "ant-",
        "sk-" + "proj-",
        "test1234" + "!",
        "/Users/" + "yoyo/",
    )
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".bak":
            raise AssertionError(f"do not ship backups: {path}")
        if path.name == Path(__file__).name:
            continue
        if path.suffix not in {".py", ".md", ".txt", ".gitignore"} and path.name != "LICENSE":
            continue
        text = path.read_text(errors="ignore")
        for needle in forbidden:
            assert needle not in text, f"{path.name} contains sensitive marker"


if __name__ == "__main__":
    test_word_boundaries()
    test_word_boundaries_658_variant()
    test_stock_word_motion_skips_hangul()
    test_stock_word_motion_skips_hangul_658_variant()
    test_plain_left_hangul_is_one_syllable()
    test_width2_up_lands_on_wrong_glyph()
    test_up_down_uses_character_columns()
    test_thai_width()
    test_hangul_display_width()
    test_patcher_has_no_ime_cursor_hack()
    test_empty_line_findline_maps_blank_not_url()
    test_empty_line_scroll_keeps_korean_visible()
    test_grapheme_steps()
    test_iterator_upgrade_on_old_patch()
    test_apply_does_not_touch_arrows_or_width()
    test_apply_on_fixture_is_unique_and_valid_js()
    test_one_orig_backup_never_overwritten()
    test_restore_rejects_dry_run_combo()
    test_bin_wrapper_body_is_safe_shell()
    test_install_bin_wrappers_replaces_symlink()
    test_latest_version_skips_tmp_extract_dirs()
    test_repo_privacy()
    print("ok")
    sys.exit(0)
