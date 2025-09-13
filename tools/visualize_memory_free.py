"""
Render a simple visual map of free memory blocks using 32bit/memory_map.txt.

Outputs an SVG file (32bit/free_blocks.svg) and an ASCII bar (32bit/free_blocks_ascii.txt)
that mark free regions across the address space covered by the current memory map.

Usage:
  python tools/visualize_memory_free.py [--map 32bit/memory_map.txt] [--out 32bit/free_blocks.svg]
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List, Tuple
import argparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = ROOT / "32bit" / "memory_map.txt"
DEFAULT_SVG = ROOT / "32bit" / "free_blocks.svg"
DEFAULT_ASCII = ROOT / "32bit" / "free_blocks_ascii.txt"


def parse_memory_map(text: str) -> Tuple[List[Tuple[int,int]], int, int]:
    """Parse memory_map.txt, returning list of (start,end) free gaps, min addr, max addr."""
    gaps: List[Tuple[int, int]] = []
    seg_bounds: List[Tuple[int, int]] = []

    seg_re = re.compile(r"\[(\d+),(\d+)\)")
    in_segs = False
    in_gaps = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Segments:"):
            in_segs = True
            in_gaps = False
            continue
        if line.startswith("Free gaps"):
            in_segs = False
            in_gaps = True
            continue
        m = seg_re.search(line)
        if not m:
            continue
        s = int(m.group(1)); e = int(m.group(2))
        if in_segs:
            seg_bounds.append((s, e))
        elif in_gaps:
            gaps.append((s, e))

    if seg_bounds:
        min_addr = min(s for s, _ in seg_bounds)
        max_addr = max(e for _, e in seg_bounds)
    elif gaps:
        min_addr = min(s for s, _ in gaps)
        max_addr = max(e for _, e in gaps)
    else:
        min_addr = 0; max_addr = 0
    return gaps, min_addr, max_addr


def render_svg(gaps: List[Tuple[int,int]], min_addr: int, max_addr: int, out_path: Path):
    # Basic layout: vertical ruler
    height = 1200
    width = 600
    left = 90
    right = width - 40
    bar_w = right - left
    top = 40
    bottom = height - 40
    if max_addr <= min_addr:
        scale = 1.0
    else:
        scale = (bottom - top) / float(max_addr - min_addr)

    def y_of(addr: int) -> float:
        return top + (addr - min_addr) * scale

    # SVG header
    parts: List[str] = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>")
    parts.append("<style> .lbl { font: 12px monospace; fill: #ddd } .t { font: 16px sans-serif; fill: #fff } </style>")
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#111' />")
    parts.append("<text class='t' x='20' y='24'>Free Memory Blocks</text>")
    # Address ruler
    parts.append(f"<rect x='{left}' y='{top}' width='{bar_w}' height='{bottom-top}' fill='#2a2a2a' stroke='#444' />")
    # ticks (10 steps)
    steps = 10
    for i in range(steps + 1):
        addr = int(min_addr + (max_addr - min_addr) * i / steps)
        y = y_of(addr)
        parts.append(f"<line x1='{left-8}' y1='{y:.2f}' x2='{right}' y2='{y:.2f}' stroke='#222' />")
        parts.append(f"<text class='lbl' x='10' y='{y+4:.2f}'>addr {addr}</text>")

    # Draw free gaps
    for s, e in gaps:
        y1 = y_of(s)
        y2 = y_of(e)
        h = max(1.5, y2 - y1)
        parts.append(f"<rect x='{left+2}' y='{y1:.2f}' width='{bar_w-4}' height='{h:.2f}' fill='#2e7d32' />")
        parts.append(f"<text class='lbl' x='{left+8}' y='{(y1+y2)/2:.2f}'>[{s},{e}) len={e-s}</text>")

    parts.append("</svg>")
    out_path.write_text("\n".join(parts))


def render_ascii(gaps: List[Tuple[int,int]], min_addr: int, max_addr: int, out_path: Path, cols: int = 120):
    if max_addr <= min_addr:
        out_path.write_text("(no data)\n")
        return
    scale = (max_addr - min_addr) / float(cols)
    buf = ["#"] * cols  # assume used
    for s, e in gaps:
        i1 = max(0, int((s - min_addr) / scale))
        i2 = min(cols, int((e - min_addr) / scale))
        for i in range(i1, max(i1+1, i2)):
            buf[i] = "."
    line = "".join(buf)
    legend = (
        "Legend: '.' = free, '#' = used\n"
        f"Range: [{min_addr},{max_addr}) words={max_addr - min_addr}\n"
    )
    out_path.write_text(legend + line + "\n")


def main():
    ap = argparse.ArgumentParser(description="Visualize free memory blocks using memory_map.txt")
    ap.add_argument("--map", default=str(DEFAULT_MAP), help="Path to memory_map.txt")
    ap.add_argument("--out", default=str(DEFAULT_SVG), help="Path to output SVG")
    ap.add_argument("--ascii", default=str(DEFAULT_ASCII), help="Path to output ASCII bar txt")
    args = ap.parse_args()

    mapp = Path(args.map)
    if not mapp.exists():
        raise SystemExit(f"Memory map not found: {mapp}")
    text = mapp.read_text()
    gaps, min_addr, max_addr = parse_memory_map(text)
    if not gaps:
        print("No gaps found in memory map; nothing to visualize.")
    svgp = Path(args.out)
    render_svg(gaps, min_addr, max_addr, svgp)
    print(f"Wrote {svgp}")
    ascp = Path(args.ascii)
    render_ascii(gaps, min_addr, max_addr, ascp)
    print(f"Wrote {ascp}")


if __name__ == "__main__":
    main()

