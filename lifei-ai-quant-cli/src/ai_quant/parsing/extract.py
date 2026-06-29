"""L1 解析层：从年报 PDF 定位合并三表，抽期末/期初数，落盘结构化数据。

定位策略（兼容两种年报格式）：
  格式 A（宁德/比亚迪）：``1、合并资产负债表`` / ``3、合并利润表`` /
    ``5、合并现金流量表``，每行 [科目名, 期末, 期初] 或 [科目名, 附注号, 期末, 期初]。
  格式 B（美的等）：``合并及公司资产负债表`` / ``2025 年度合并及公司利润表`` /
    ``2025 年度合并及公司现金流量表``，每行 [科目名, 附注, 合并期, 合并上期, 公司期, 公司上期]，
    此时取前两个数字列（合并列）作为 current/prior。
- 单位为年报原文标注（元/千元/万元），数值按原文存为 float，meta.unit 标明。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pdfplumber

# 格式 A：编号小节标题锚点（1/3/5 = 合并，2/4/6 = 母公司）
_SECTION_RE_A = re.compile(r"^\s*(\d+)\s*、\s*(合并|母公司)\s*(资产负债表|利润表|现金流量表)")

# 格式 B：无编号、合并及公司并列格式，如 "合并及公司资产负债表" / "2025 年度合并及公司利润表"
_SECTION_RE_B = re.compile(
    r"(?:\d{4}\s*年(?:度)?\s*)?合并及公司\s*(资产负债表|利润表|现金流量表)"
)
# 匹配合并利润表/现金流量表的 (续) 页，不发起新小节
_SECTION_RE_B_CONT = re.compile(
    r"(?:\d{4}\s*年(?:度)?\s*)?合并及公司\s*(利润表|现金流量表)\(续\)"
)

# 跨页运行页眉 / 编制说明 / 单位 / 日期 / 纯页码 等噪声行
_NOISE_RE = re.compile(
    r"(年年度报告全文|^编制单位|^单位：|^财务附注|^二、财务报表|^\d{4}年12月31日"
    r"|后附财务报表附注|^资产 附注|^附注七|^[0-9]{2,4}$)"
)

# 数字 token：可带千分位、可负、可被中/英文括号包裹表示负数；
# 也接受单独的 "-" / "—" 作为空值占位列（格式 B 中公司列为空时常见）。
_NUM_TOKEN_RE = re.compile(r"^[（(]?[-－—]?[\d,]+(?:\.\d+)?[)）]?$")
_EMPTY_NUM_RE = re.compile(r"^[-－—]$")

# 合并三表分别需要的「当前列」表头语义（仅用于 meta 记录，不影响解析）
_PERIOD_LABELS = {
    "balance_sheet": ("期末余额", "期初余额"),
    "income": ("本期", "上期"),
    "cash_flow": ("本期", "上期"),
}


def parse_num(token: str):
    """把一个数字 token 解析成 float；括号代表负数；无效返回 None。"""
    t = token.strip().replace(",", "")
    neg = False
    if (t.startswith("(") and t.endswith(")")) or (t.startswith("（") and t.endswith("）")):
        neg = True
        t = t[1:-1]
    t = t.replace("－", "-").replace("—", "-")
    if t in ("", "-"):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _normalize_parens(line: str) -> str:
    """规整括号内紧贴的空格：``(649,350 )`` → ``(649,350)``，让负数 token 可被识别。"""
    line = re.sub(r"([(（])\s+", r"\1", line)
    line = re.sub(r"\s+([)）])", r"\1", line)
    return line


def split_name_and_numbers(line: str):
    """把一行拆成 (科目名, [数值...])；只取行尾连续的数字/空值 token。

    返回的数值列表保留出现顺序。注意：部分年报在科目名与金额之间
    多一列『附注编号』，因此行尾可能出现 3 个数字 [附注号, 期末, 期初]——取值时
    由 _pick_periods 取最后两个，自动丢掉附注号。
    格式 B（美的等）的“-”为空值占位列，也当作数值 token 处理（parse 为 None）。

    若行尾没有数字 token，数值列表为空。
    """
    tokens = _normalize_parens(line).split()
    nums = []

    def _is_numlike(t):
        return (_NUM_TOKEN_RE.match(t) and any(c.isdigit() for c in t)) or _EMPTY_NUM_RE.match(t)

    while tokens and _is_numlike(tokens[-1]):
        nums.insert(0, tokens.pop())
    name = "".join(tokens).strip()  # 中文科目名内部无空格，直接拼回
    values = [parse_num(t) for t in nums]
    return name, values


def _pick_periods(values):
    """从数值列表取 (合并期末/本期, 合并期初/上期)。

    格式 A（2-3 列）：[附注号?, 期末, 期初] → 取最后两个。
    格式 B（4 列）：[合并期末, 合并期初, 公司期末, 公司期初] → 取前两个。
    """
    vals = [v for v in values if v is not None]
    n = len(vals)
    if n >= 4:
        return vals[0], vals[1]   # 格式 B：合并列在前
    if n >= 2:
        return vals[-2], vals[-1]  # 格式 A：取最后两列
    if n == 1:
        return vals[0], None
    return None, None


def _collect_lines(pdf, page_start: int, page_end: int):
    """收集 [page_start, page_end] 页（1-based，含端点）的所有非噪声文本行。"""
    lines = []
    for pno in range(page_start, page_end + 1):
        text = pdf.pages[pno - 1].extract_text() or ""
        for raw in text.splitlines():
            s = raw.strip()
            if not s or _NOISE_RE.search(s):
                continue
            lines.append(s)
    return lines


def _find_sections(lines):
    """返回所有报表小节标题的位置：[{idx, num, format, type}]。

    格式 A（宁德/比亚迪）：带编号，kind='合并'|'母公司'，num=1-6。
    格式 B（美的等）：无编号，合并+公司并列，format='B'，num=0。
    不依赖编号顺序。
    """
    secs = []
    for i, s in enumerate(lines):
        ma = _SECTION_RE_A.match(s)
        if ma:
            secs.append({"idx": i, "num": int(ma.group(1)), "format": "A",
                         "kind": ma.group(2), "type": ma.group(3)})
            continue
        # 格式 B 续页不算新小节标题（用 idx 中断上一节即可；但 slice 只看 start/end，
        # 我们只需为非续页的每张表各自记一次起始）
        mb = _SECTION_RE_B.match(s)
        if mb and not _SECTION_RE_B_CONT.match(s):
            secs.append({"idx": i, "num": 0, "format": "B",
                         "kind": "合并", "type": mb.group(1)})
    return secs


def _slice_consolidated(lines, secs, stype):
    """切出某张『合并』报表的行：从它的标题切到下一张报表标题为止。

    格式 A：匹配 kind='合并' & type==stype。
    格式 B：匹配 kind='合并' & type==stype（format=='B'），
            同时把唯一同名 (续) 行之后的内容也并入（避免被中途截断）。
    """
    # 找到该表的主节标题索引与下一节标题索引
    target_idx = None
    next_idx = None
    for j, sec in enumerate(secs):
        if sec["kind"] == "合并" and sec["type"] == stype:
            if target_idx is None:
                target_idx = sec["idx"]
        elif target_idx is not None and sec["type"] != stype:
            next_idx = sec["idx"]
            break
    if target_idx is None:
        return []
    end = next_idx if next_idx is not None else len(lines)
    return lines[target_idx:end]


def _is_category_header(line: str) -> bool:
    """形如 "流动资产：" 的分类小标题（无数值，不应并入下一个科目名）。"""
    return line.endswith("：") or line.endswith(":")


def _parse_statement(section_lines, statement_key):
    """把一个小节的行解析成 {科目名: {current, prior}}。

    单行 ``科目名 期末数 期初数`` 直接成条目。另用一个小状态机回收「夹心折行」：
        '四、利润总额（亏损总额以"－"号填'   ← 名字上半（无数）
        '89,526,545 63,182,039'              ← 纯数字行
        '列）'                                ← 名字下半（无数）
    把上下半拼成完整名、中间数字行作其值。无值科目自然被丢弃。
    """
    items = {}
    pending_name = ""   # 已累积、尚无数值的名字片段
    held_values = None  # 已出现、但名字还没拼全的数值

    def commit_pending():
        nonlocal pending_name, held_values
        name = pending_name.strip()
        if held_values is not None and name and name not in items:
            cur, pri = _pick_periods(held_values)
            items[name] = {"current": cur, "prior": pri}
        pending_name = ""
        held_values = None

    for s in section_lines:
        if _SECTION_RE_A.match(s) or _SECTION_RE_B.match(s):
            continue  # 跳过小节标题行本身
        name, values = split_name_and_numbers(s)

        if name and values:
            # 完整单行科目：先结清可能挂起的夹心项，再登记自己
            commit_pending()
            current, prior = _pick_periods(values)
            if name not in items:
                items[name] = {"current": current, "prior": prior}
        elif values and not name:
            # 纯数字行：属于正在拼接的夹心科目
            held_values = values
        elif name and not values:
            # 纯名字行：分类小标题则重置，否则作为名字片段累积
            if _is_category_header(s):
                commit_pending()
            else:
                pending_name += name
        # 空行已在 _collect_lines 过滤

    commit_pending()
    return items


_UNIT_RE = re.compile(r"单位[:：]\s*(千元|万元|元)")
_COMPANY_RE = re.compile(r"编制单位[:：]\s*([一-龥A-Za-z（）()]+(?:公司|集团|股份))")
# 封面直接取公司名：匹配前几页中独占一行的 "...股份有限公司" 或 "...公司"
_COMPANY_COVER_RE = re.compile(r"^([一-龥A-Za-z（）()]+(?:股份有限公司|有限责任公司|有限公司|集团))$")
_PERIOD_RE = re.compile(r"(\d{4})\s*年年度报告")


def _detect_meta(pdf, page_start, lines, pdf_path, stock_code):
    """从 PDF 文本动态识别公司名/单位/报告期，不写死任何公司。"""
    head_text = "\n".join(lines[:60])
    first_text = pdf.pages[0].extract_text() or ""

    unit_m = _UNIT_RE.search("\n".join(lines[:30]))
    unit = unit_m.group(1) if unit_m else "千元"

    company = None
    comp_m = _COMPANY_RE.search(head_text)
    if comp_m:
        company = comp_m.group(1)
    if not company:
        # 用封面正则匹配独占一行的公司名
        for ln in first_text.splitlines():
            s = ln.strip()
            cm2 = _COMPANY_COVER_RE.match(s)
            if cm2:
                company = cm2.group(1)
                break
    if not company:
        for ln in first_text.splitlines():
            s = ln.strip()
            if (s.endswith("公司") or s.endswith("有限公司")) and 4 <= len(s) <= 30:
                company = s
                break

    period_m = _PERIOD_RE.search(first_text)
    period = f"{period_m.group(1)}FY" if period_m else "FY"

    code = stock_code
    if not code:
        cover = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(3, len(pdf.pages))))
        cm = re.search(r"(?:股票|证券)代码[:：\s]*([0-9]{6})", cover)
        if cm:
            code = cm.group(1)
    return {"company": company or "（未识别）", "unit": unit, "period": period, "stock_code": code}


def extract_financials(pdf_path: str, stock_code: str = "") -> dict:
    """主入口：解析年报 PDF，返回符合数据契约的结构化 dict。

    公司名 / 单位 / 报告期从 PDF 文本动态识别；stock_code 可选传入。
    """
    with pdfplumber.open(pdf_path) as pdf:
        # 三张合并报表都落在「二、财务报表」区，先粗定位含关键字的页范围再精切。
        # 兼容格式 A（"合并资产负债表"）和格式 B（"合并及公司资产负债表"）。
        kw_pages = []
        kw_patterns = [
            "合并资产负债表", "合并现金流量表",
            "合并及公司资产负债表", "合并及公司现金流量表",
        ]
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            if any(kw in t for kw in kw_patterns):
                kw_pages.append(i + 1)
        if not kw_pages:
            # 最后兜底：扫描全文档找带"合并"和"报表"关键词的页
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                if "合并" in t and ("资产负债表" in t or "利润表" in t or "现金流量表" in t):
                    kw_pages.append(i + 1)
                    break
        if not kw_pages:
            raise RuntimeError("未找到合并财报页。请检查 PDF 是否为 A 股年报标准格式。")
        page_start = min(kw_pages)
        page_end = min(max(kw_pages) + 5, len(pdf.pages))  # 格式 B 表后有续页和股东权益变动表
        lines = _collect_lines(pdf, page_start, page_end)
        secs = _find_sections(lines)

        statements = {
            "balance_sheet": _parse_statement(_slice_consolidated(lines, secs, "资产负债表"), "balance_sheet"),
            "income": _parse_statement(_slice_consolidated(lines, secs, "利润表"), "income"),
            "cash_flow": _parse_statement(_slice_consolidated(lines, secs, "现金流量表"), "cash_flow"),
        }

        detected = _detect_meta(pdf, page_start, lines, pdf_path, stock_code)
        meta = {
            "company": detected["company"],
            "stock_code": detected.get("stock_code") or stock_code,
            "period": detected["period"],
            "currency": "CNY",
            "unit": detected["unit"],
            "source_pdf": pdf_path,
            "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "period_labels": _PERIOD_LABELS,
            "consolidated_pages": {"scan_from": page_start, "scan_to": page_end},
        }

    from .checks import balance_identity_check

    checks = {"balance_identity": balance_identity_check(statements["balance_sheet"])}
    return {"meta": meta, "statements": statements, "checks": checks}
