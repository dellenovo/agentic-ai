#!/usr/bin/env python3
"""L4 编排：一键重跑 解析 → 出图 → 闸门 → 报告。

用法：
    python scripts/run_pipeline.py [data/<年报>.pdf] [--skip-figures] [--code 股票代码]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.pipeline.run import run_pipeline, PipelineError


def main():
    parser = argparse.ArgumentParser(description="一键重跑量化投研 pipeline")
    parser.add_argument("pdf", nargs="?", default="", help="年报 PDF 路径（默认自动找 data/*.pdf）")
    parser.add_argument("--skip-figures", action="store_true", help="跳过出图")
    parser.add_argument("--code", default="", help="股票代码（可选）")
    args = parser.parse_args()

    pdf_path = args.pdf
    if not pdf_path:
        # 自动找 data/ 下第一个 PDF
        candidates = sorted((ROOT / "data").glob("*.pdf"))
        if not candidates:
            print("✗ 未找到年报 PDF。请在 data/ 下放入 PDF 或显式指定路径。")
            sys.exit(1)
        pdf_path = str(candidates[0])
        print(f"自动选择年报：{pdf_path}")

    try:
        run_pipeline(pdf_path, skip_figures=args.skip_figures, stock_code=args.code)
    except PipelineError as e:
        print(f"\n✗ Pipeline 中止：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
