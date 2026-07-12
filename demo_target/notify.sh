#!/usr/bin/env bash
# 从环境变量读取飞书 webhook，未设置时跳过发送
FEISHU_WEBHOOK="${FEISHU_WEBHOOK:-}"
if [ -n "$FEISHU_WEBHOOK" ]; then
  curl -s -X POST "$FEISHU_WEBHOOK" -d '{"msg":"demo"}'
else
  echo "FEISHU_WEBHOOK not set, skipping notification" >&2
fi