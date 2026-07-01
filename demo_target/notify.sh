#!/usr/bin/env bash
# ⚠️ 演示用假 webhook（非真实）—— 从环境变量读取
FEISHU_WEBHOOK="${FEISHU_WEBHOOK:-}"
curl -s -X POST "$FEISHU_WEBHOOK" -d '{"msg":"demo"}'
