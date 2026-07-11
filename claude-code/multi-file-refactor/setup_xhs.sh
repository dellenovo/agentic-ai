#!/usr/bin/env bash
# setup.sh — 一键搭好「多文件协同与终端代码级重构」实验工作区
#
# 用途：把 xhs-auto-publisher 快照进本目录，建好各自的 venv，
#       跑通「重构前」绿色基线。
#
# 运行：在仓库根执行 bash claude-code/multi-file-refactor/setup.sh

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

DST="claude-code/multi-file-refactor"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

# 检查是否已存在
if [ -e "$DST/xhs-auto-publisher" ]; then
    echo "⚠ $DST 下已有快照，为避免覆盖已有改动，脚本退出。"
    echo "  如需从头重建：rm -rf $DST/xhs-auto-publisher $DST/common  然后重跑。"
    exit 1
fi

echo "==> 1/4 快照 xhs-auto-publisher 到 $DST/"
mkdir -p "$DST/common"

# 正确复制两个子目录（注意末尾没有/，这样复制的是目录本身）
for app in xhs-auto-publisher; do
    echo "  复制 $app..."
    rsync -a --exclude '.venv' --exclude 'runtime' --exclude '__pycache__' \
            --exclude '*.pyc' --exclude '.tmp_tests' \
            "$app/" "$DST/$app/"
done

echo "==> 2/4 xhs-auto-publisher：建 venv + 装依赖（国内镜像）"
( cd "$DST/xhs-auto-publisher"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -i "$MIRROR" -r requirements.txt )

echo ""
echo "✅ 工作区就绪：$DST"
echo "   - xhs-auto-publisher 准备就绪"
