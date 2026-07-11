#!/usr/bin/env python3
"""L2 出图：读 financials.json + findings.json，渲染图表 → build/figures/。

用法：
    python scripts/make_figures.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.viz.charts import render_all


def main():
    chosen, manifest = render_all()
    print(f"✓ 出图完成，字体 {chosen}，生成 {len(manifest)} 张图：")
    for m in manifest:
        print(f"  {m['id']:24s} → build/{m['path']}")
    print(f"  manifest → build/figures/manifest.json")


if __name__ == "__main__":
    main()
