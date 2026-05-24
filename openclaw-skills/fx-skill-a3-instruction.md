---
name: fx-pair-conversion-query
description: |
    使用ExchangeRate-API Pair Conversion Requests查询一对币种的汇率
    支持/fx-pair-conversion-query斜杠命令触发
    支持自然语言触发，分为 2 种情况：
    1. 查汇率，如“查一下美元和人民币的汇率”。此时前者为base currency, 后者为target currency
    2. 查询指定金额base currency可以转换成多少金额的target currency，如“1 美元可以换多少人民币”、“我需要 100 美元，需要多少人民币”.这种情况下需要传具体的金额给到 API endpoint
metadata:
  openclaw:
    requires:
      env:
        - EXCHANGE_RATE_API_KEY
      bins:
        - curl
        - jq
---
