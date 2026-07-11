"""L1 自检：会计恒等式验证。"""

from __future__ import annotations


def _find_item(table, candidates, period):
    """在 table (dict of {科目: {current, prior}}) 中按候选名列表查找。"""
    for k, v in table.items():
        for cand in candidates:
            if cand in k:
                val = v.get(period)
                if val is not None:
                    return val
    return None


def balance_identity_check(balance_sheet: dict) -> dict:
    """会计恒等式：资产总计 == 负债和所有者权益总计 == 负债合计 + 所有者权益合计。

    容差 1e-6 相对误差（允许四舍五入残差）。
    返回 {ok, current: {lhs, rhs, diff}, prior: {lhs, rhs, diff}}。
    """
    ta_candidates = ["资产总计"]
    le_candidates = [
        "负债和所有者权益总计", "负债与所有者权益总计", "负债及所有者权益总计",
        "负债和股东权益总计",   # 美的等公司用语
    ]
    liab_candidates = ["负债合计"]
    eq_candidates = ["所有者权益合计", "股东权益合计"]

    results = {}
    all_ok = True

    for period in ("current", "prior"):
        ta = _find_item(balance_sheet, ta_candidates, period)
        le = _find_item(balance_sheet, le_candidates, period)
        liab = _find_item(balance_sheet, liab_candidates, period)
        eq = _find_item(balance_sheet, eq_candidates, period)

        if ta is not None and le is not None:
            lhs, rhs = ta, le
        elif ta is not None and liab is not None and eq is not None:
            lhs, rhs = ta, liab + eq
        else:
            results[period] = {"lhs": ta, "rhs": None, "diff": None}
            all_ok = False
            continue

        diff = abs(lhs - rhs)
        rel_tol = 1e-6 * max(abs(lhs), abs(rhs), 1)
        ok = diff <= rel_tol
        if not ok:
            all_ok = False
        results[period] = {"lhs": lhs, "rhs": rhs, "diff": diff, "ok": ok}

    return {"ok": all_ok, **results}
