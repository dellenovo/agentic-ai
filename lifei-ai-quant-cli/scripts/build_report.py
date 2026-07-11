#!/usr/bin/env python3
"""L5 报告：fan-in 汇编 HTML 投研报告。

输入：data/parsed/financials.json + analysis/findings.json + build/figures/manifest.json
产出：reports/report_<代码>_<期>_<时间戳>.html

用法：
    python scripts/build_report.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.report.build import build_report


def main():
    out = build_report()
    print(f"✓ 报告生成：{out.name}（{out.stat().st_size / 1024:.0f} KB，图表内嵌）")
    print(f"  打开：open '{out}'")


if __name__ == "__main__":
    main()
