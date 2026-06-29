# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这个项目是什么

从零搭建的本地量化投研系统：把 `data/` 里的年报 PDF，自动解析三张合并报表 → **由 Claude Code 亲自做财务风险研判** → 出图 → 生成带图表的 HTML 投研报告。

## 铁律（不可违背）

1. **分析判断由 Claude Code 亲自做，代码不碰判断。** 财务风险研判、三表勾稽结论由我直接产出成数据文件；Python 脚本只做确定性工作（解析 PDF、出图、汇编 HTML）。
2. **任何脚本里都不调用大模型 API**，不引入 LLM SDK / 在线服务。
3. **报告输出到 `reports/`**（文件名 `report_<股票代码>_<期>_<时间戳>.html`，每次运行独立、不覆盖历史）；结构化产物到 `data/parsed/`；图片到 `build/figures/`；研判产物到 `analysis/`。
4. 调试时**遇报错自己修到跑通**（缺包、表格定位、数字格式、中文字体等），调试过程留在终端、不清屏。
5. 年报 PDF 默认不入库；`data/parsed/`、`build/`、`reports/` 视为生成产物不入库（从 PDF 重跑即可得到）。

## 架构（DAG，不是直线流水线）

```
            ┌──→ L2 出图 (viz) ──── build/figures/*.png ──┐
L1 解析 ──→ ┤                                            ├──→ L5 报告 → reports/*.html
(parsing)   └──→ L3 研判 (我·人工) ─ analysis/findings.json┘
            financials.json 扇出                          扇入
```

- **唯一硬约束**：`L1 最先、L5 最后`。中间 **L2 出图** 与 **L3 研判** 互不依赖、**可并行**。
- **L3 是人工闸门**：不是脚本，是我读 `financials.json` 后亲自产出 `analysis/findings.json`。确定性 pipeline 不能自动跑 L3——进 L5 前要**检查 findings.json 是否就位，缺则明确提示并停下**。
- 每层只依赖上游落盘的文件，不互相 import 业务逻辑。

| 层 | 包 | 职责 | 产出 |
|---|---|---|---|
| L1 解析 | `src/ai_quant/parsing/` | PDF 定位**合并**三表，抽期末+期初，会计恒等式自检 | `data/parsed/financials.json` |
| L2 出图 | `src/ai_quant/viz/` | 读结构化数据渲染图，处理中文字体 | `build/figures/*.png` + `manifest.json` |
| L3 研判 | 我（非代码） | 隐性风险研判 + 三表勾稽，每条挂数据依据 | `analysis/findings_<代码>.json` |
| L4 编排 | `src/ai_quant/pipeline/` | 一键重跑，含 L3 闸门检查 | 终端日志 |
| L5 报告 | `src/ai_quant/report/` | fan-in 汇编单页 HTML | `reports/report_<period>.html` |

CLI 入口在 `scripts/`：`parse_report.py` / `make_figures.py` / `build_report.py` / `run_pipeline.py`，各自薄封装对应层。

## 数据契约

**`data/parsed/financials.json`**（L1 产出，L2/L3/L5 都读）：
```jsonc
{
  "meta": {"company","stock_code","period","currency","unit","source_pdf","parsed_at"},
  "statements": {
    "balance_sheet": {"<科目>": {"current": 数, "prior": 数}},
    "income":        {"<科目>": {"current": 数, "prior": 数}},
    "cash_flow":     {"<科目>": {"current": 数, "prior": 数}}
  },
  "checks": {"balance_identity": {"ok", "lhs", "rhs", "diff"}}
}
```
约定：金额一律 `float`（元、去千分位、负数转负值）；期末=`current`、期初=`prior`；科目用规范中文名。

**`analysis/findings_<代码>.json`**（我产出，L2/L5 读）：
```jsonc
{
  "meta": {"summary": "..."},
  "risk_findings": [{"id","topic","severity","conclusion",
                     "evidence":[{"statement","item","value","period"}]}],
  "cross_checks":  [{"id","title","conclusion","evidence":[...]}],
  "cross_checks_round2": [],
  "indirect_method_bridge": {"waterfall": [{"label","value","type"}]},
  "inventory_composition": [{"name","current","prior"}]
}
```
**每条结论必须挂 `evidence`**（指向具体报表+科目+期间），保证可追溯。

**`build/figures/manifest.json`**：`[{"id","path","title","caption"}]`，报告层按 `id` 内嵌。

## 技术选型

- **PDF 解析**：`pdfplumber` 优先（对带框线表格的 `extract_tables` 友好、纯 Python 无系统依赖）；抽不干净再退到 `PyMuPDF(fitz)` 按文本块+坐标定位。避开需要 JVM 的 tabula/Camelot。
- **出图**：`matplotlib`，`Agg` 后端离线静态 PNG 直接内嵌 HTML。
- **报告**：`Jinja2` 模板渲染单页 HTML，图片 base64 内嵌。
- **数据交换**：全用 JSON 落盘，层间解耦、可单独重跑。

## 解析层约定

- **定位用编号锚点**，不靠页码：财报正文里 `1、合并资产负债表` / `3、合并利润表` / `5、合并现金流量表`（母公司是 2/4/6）。
- **单位按原文存**（元/千元/万元），meta.unit 标明，不擅自换算。
- **列序**：行尾第一数=期末/本期(current)，第二数=期初/上期(prior)。部分年报多一列附注编号——取最后两个数字。
- **夹心折行**：长科目名被劈成「名上半 / 纯数字行 / 名下半」三行，用状态机拼回。
- **自检**：`资产总计 == 负债和所有者权益总计 == 负债合计+所有者权益合计`，期末/期初各一组，相对容差 1e-6。

## 出图层渲染约定

- **后端**：`matplotlib.use("Agg")`（无界面，直接出 PNG）。
- **中文字体**：用回退链挑第一个本机可用 CJK 字体，写进 `rcParams["font.sans-serif"]`；macOS 可用：`PingFang SC` → `Hiragino Sans GB` → `Arial Unicode MS` → `Heiti SC` → `Songti SC`。
- **负号**：必须 `rcParams["axes.unicode_minus"] = False`。
- **金额展示**：源数据按 meta.unit 存，出图统一换算成「亿元」展示。
- **配色**：深蓝主色 `#1f4e79`、警示红 `#c00000`、正向绿 `#2e7d32`、上期浅蓝 `#a6c8e0`、中性灰 `#7f7f7f`。
- **产出**：`build/figures/*.png` + `manifest.json`。

## 多公司支持

- 解析层动态识别公司名/单位/期；股票代码封面可识别则自动取，否则用 `--code` 显式指定。
- 研判按 `findings_<代码>.json` 归档、报告按 `report_<代码>_<期>_<时间戳>.html` 命名，多家公司及多次运行互不覆盖。
- 科目命名差异由 `src/ai_quant/common.py` 的别名表统一解析。

## 已知风险点

1. **别抓错报表**：年报同时含「母公司」与「合并」三表，必须锁定**合并**报表标题。
2. **数字格式**：千分位逗号、负数括号 `(1,234)`、单位（元/万元）、跨页续表、空单元格。
3. **科目定位**：用「科目名 + 所在表」双重定位，避开同名/合计行/缩进子科目。
4. **趋势图数据有限**：单份年报通常只给期末/期初两期，趋势图可能退化为两期对比。
5. **matplotlib 中文乱码**：必踩，配好中文字体后把渲染配置写回本文件。
6. **恒等式容差**：四舍五入/单位换算有残差，自检设合理容差而非严格相等。

## 常用命令

```bash
cd lifei-ai-quant-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/parse_report.py   data/<年报>.pdf      # L1 解析 → financials.json + 恒等式自检
python scripts/make_figures.py                        # L2 出图 → build/figures/*.png + manifest.json
python scripts/build_report.py                        # L5 报告 → reports/report_<period>.html
python scripts/run_pipeline.py  [data/<年报>.pdf]      # L4 一键：解析→出图→L3闸门→报告
```
