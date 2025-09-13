import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

ROOT = Path(__file__).resolve().parent.parent
OS_PATH = ROOT / "32bit" / "emulator_os.txt"
JSON_PATH = ROOT / "32bit" / "compiled_routines.json"
OUT_PATH = ROOT / "32bit" / "memory_map.txt"


class Segment:
    __slots__ = ("start", "end", "kind", "name", "notes")

    def __init__(self, start: int, end: int, kind: str, name: str, notes: str = ""):
        self.start = int(start)
        self.end = int(end)
        self.kind = str(kind)
        self.name = str(name)
        self.notes = str(notes)

    @property
    def length(self) -> int:
        return max(0, self.end - self.start)

    def as_line(self) -> str:
        return f"[{self.start},{self.end})  {self.kind:12}  {self.name:20} len={self.length}  {self.notes}"


def _parse_int(s: str) -> Optional[int]:
    try:
        return int(s.strip())
    except Exception:
        return None


def parse_os_fixed_regions(os_text: str) -> Tuple[List[Segment], Dict[str, int]]:
    segs: List[Segment] = []
    symbols: Dict[str, int] = {}

    call_stub_base: Optional[int] = None
    prog_table_base: Optional[int] = None

    # regex for lines like: name = 2000  ; comment may contain "N bytes"
    assign_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*(?:;\s*(.*))?$")
    # digits before the token 'bytes' in the trailing comment
    bytes_re = re.compile(r"(\d+)\s*bytes", re.IGNORECASE)

    for raw in os_text.splitlines():
        line = raw.split(';', 1)[0].rstrip('\n')
        s = raw.strip()
        if not s:
            continue
        # CALL_STUB base
        if s.upper().startswith("CALL_STUB ="):
            val = _parse_int(s.split('=', 1)[1])
            if val is not None:
                call_stub_base = val
            continue
        # Program table base
        if s.lower().startswith("prog_table ="):
            val = _parse_int(s.split('=', 1)[1])
            if val is not None:
                prog_table_base = val
            continue
        # Generic pointer assignment
        m = assign_re.match(line.strip())
        if m:
            name = m.group(1)
            addr = int(m.group(2))
            symbols[name] = addr
            # Attempt to infer a length from comment (e.g. "; 16 bytes" or "80 bytes reserved")
            comment = m.group(3) or ""
            blen = None
            bmatch = bytes_re.search(raw)
            if bmatch:
                try:
                    blen = int(bmatch.group(1))
                except Exception:
                    blen = None
            # input buffers sometimes say "(80 bytes reserved)" in comment
            if blen:
                segs.append(Segment(addr, addr + blen, "os-data", name, "from comment"))
            else:
                # Single pointer
                segs.append(Segment(addr, addr + 1, "os-var", name))

    # Represent call stub as 3-word trampoline if present
    if call_stub_base is not None:
        segs.append(Segment(call_stub_base, call_stub_base + 3, "os-code", "CALL_STUB", "JSR,<op>,RET"))

    # prog_table base returned; length will be filled from JSON if available
    if prog_table_base is not None:
        segs.append(Segment(prog_table_base, prog_table_base, "os-table", "prog_table", "length from JSON"))

    return segs, symbols


def parse_compiled_json(json_text: str, existing: List[Segment]) -> List[Segment]:
    data = json.loads(json_text)
    segs = list(existing)

    # Map modules and their bss/data
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        if "base" in v and "length" in v and "words" in v:
            base = int(v["base"])
            length = int(v["length"])
            name = str(k)
            kind = "code"
            if name.lower() == "program_table":
                kind = "prog_table"
            elif name.lower().endswith("_data"):
                kind = "data"
            segs.append(Segment(base, base + length, kind, name))
            # add BSS if present
            bss = v.get("bss")
            if isinstance(bss, dict) and "base" in bss and "size" in bss:
                bbase = int(bss["base"])
                bsize = int(bss["size"])
                segs.append(Segment(bbase, bbase + bsize, "bss", name))

    return segs


def summarize(segs: List[Segment]) -> str:
    # Consolidate prog_table segment if OS placeholder had zero length
    # Sort by start
    segs = sorted(segs, key=lambda s: (s.start, s.end))

    # Fix OS prog_table length if we have a compiled one
    pt_os_idx = None
    pt_img_idx = None
    for i, s in enumerate(segs):
        if s.kind == "os-table" and s.name == "prog_table":
            pt_os_idx = i
        if s.kind == "prog_table":
            pt_img_idx = i
    if pt_os_idx is not None and pt_img_idx is not None:
        segs[pt_os_idx].end = segs[pt_img_idx].end

    # Build gaps
    gaps: List[str] = []
    for i in range(len(segs) - 1):
        a = segs[i]
        b = segs[i + 1]
        if b.start > a.end:
            gaps.append(f"[{a.end},{b.start})  words={b.start - a.end}  (free)")

    # Compose output
    lines: List[str] = []
    lines.append("Memory Map Overview (sorted by start address)")
    lines.append("")
    lines.append("Segments:")
    for s in segs:
        lines.append("  " + s.as_line())
    lines.append("")
    if gaps:
        lines.append("Free gaps between segments:")
        for g in gaps:
            lines.append("  " + g)
    return "\n".join(lines) + "\n"


def main():
    if not OS_PATH.exists():
        raise SystemExit(f"OS file not found: {OS_PATH}")
    os_text = OS_PATH.read_text()
    segs, _ = parse_os_fixed_regions(os_text)

    if JSON_PATH.exists():
        segs = parse_compiled_json(JSON_PATH.read_text(), segs)
    else:
        # Still write an OS-only map
        pass

    OUT_PATH.write_text(summarize(segs))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

