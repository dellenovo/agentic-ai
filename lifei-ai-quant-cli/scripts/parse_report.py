#!/usr/bin/env python3
"""L1 解析：从年报 PDF 定位合并三表，抽期末/期初数，落盘 financials.json + 恒等式自检。

用法：
    python scripts/parse_report.py data/<年报>.pdf [--code 股票代码]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.parsing.extract import extract_financials


def main():
    parser = argparse.ArgumentParser(description="解析年报 PDF → financials.json")
    parser.add_argument("pdf", help="年报 PDF 路径")
    parser.add_argument("--code", default="", help="股票代码（可选，PDF 封面可自动识别）")
    args = parser.parse_args()

    data = extract_financials(args.pdf, stock_code=args.code)
    out = ROOT / "data" / "parsed" / "financials.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    m = data["meta"]
    st = data["statements"]
    ck = data["checks"]
    print(f"✓ 解析完成：{m['company']}（{m['stock_code']}）{m['period']}")
    print(f"  单位：{m['unit']}")
    print(f"  资产负债表 {len(st['balance_sheet'])} 科目 / 利润表 {len(st['income'])} 科目 / 现金流量表 {len(st['cash_flow'])} 科目")
    ok = ck["balance_identity"]["ok"]
    print(f"  会计恒等式自检：{'✓ 通过' if ok else '✗ 不平'}")
    if not ok:
        sys.exit(1)
    print(f"  产物：{out}")


if __name__ == "__main__":
    main()
