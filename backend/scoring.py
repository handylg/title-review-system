"""积分计算引擎。

计算流程：
1. 取成果级别（Level）的基础分 base_score；
2. 依据「作者人数 + 类别」匹配作者贡献系数规则 ContributionRule，
   得到每个排名的分成系数；
3. 若作者设置了 custom_ratio（人工核定），优先使用人工系数；
4. 若成果指定了通讯作者且规则配置了 corresponding_ratio，
   则以该系数作为通讯作者分成，其余作者按原比例等比例缩放；
5. 个人得分 = 基础分 × 分成系数。
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from backend.models import Achievement, ContributionRule

# 未配置规则时的默认分成方案（按作者人数）
DEFAULT_RATIO_TABLE: dict[int, list[float]] = {
    1: [1.0],
    2: [0.6, 0.4],
    3: [0.5, 0.3, 0.2],
    4: [0.4, 0.3, 0.2, 0.1],
}


def default_ratios(author_count: int) -> list[float]:
    """生成默认分成系数。5 人及以上：前两位固定，其余均分剩余份额。"""
    if author_count <= 0:
        return []
    if author_count in DEFAULT_RATIO_TABLE:
        return list(DEFAULT_RATIO_TABLE[author_count])
    first_two = [0.35, 0.25]
    rest = round(1.0 - sum(first_two), 6)
    each = round(rest / (author_count - 2), 6)
    return first_two + [each] * (author_count - 2)


def find_rule(
    rules: Iterable[ContributionRule],
    category_id: Optional[int],
    author_count: int,
) -> Optional[ContributionRule]:
    """优先匹配类别专属规则，其次匹配通用规则。"""
    fallback: Optional[ContributionRule] = None
    for rule in rules:
        if rule.author_count != author_count:
            continue
        if category_id is not None and rule.category_id == category_id:
            return rule
        if rule.category_id is None:
            fallback = rule
    return fallback


def resolve_ratios(
    authors: Sequence,
    category_id: Optional[int],
    rules: Iterable[ContributionRule],
) -> list[float]:
    """返回与 authors 顺序一致的最终分成系数。"""
    ordered = list(authors)
    count = len(ordered)
    if count == 0:
        return []

    rule = find_rule(rules, category_id, count)
    if rule and len(rule.ratios) == count:
        ratios = [float(x) for x in rule.ratios]
    else:
        ratios = default_ratios(count)

    # 人工核定系数优先
    for idx, author in enumerate(ordered):
        if getattr(author, "custom_ratio", None) is not None:
            ratios[idx] = float(author.custom_ratio)

    # 通讯作者分成调整
    if rule is not None and rule.corresponding_ratio is not None:
        corresponding = [i for i, a in enumerate(ordered) if a.is_corresponding]
        if corresponding:
            ci = corresponding[0]
            target = float(rule.corresponding_ratio)
            others_total = sum(r for i, r in enumerate(ratios) if i != ci)
            if others_total > 0:
                remaining = max(1.0 - target, 0.0)
                factor = remaining / others_total
                for i in range(count):
                    if i != ci:
                        ratios[i] = ratios[i] * factor
            ratios[ci] = target

    return [round(r, 6) for r in ratios]


def calculate_achievement(
    achievement: Achievement,
    rules: Iterable[ContributionRule],
) -> list[dict]:
    """计算成果中每位作者的系数与得分。

    返回列表元素：{author, ratio, score}
    """
    authors = sorted(achievement.authors, key=lambda a: a.rank)
    base_score = float(achievement.level.base_score) if achievement.level else 0.0
    ratios = resolve_ratios(authors, achievement.category_id, rules)

    result: list[dict] = []
    for author, ratio in zip(authors, ratios):
        result.append(
            {
                "author": author,
                "ratio": round(ratio, 6),
                "score": round(base_score * ratio, 2),
            }
        )
    return result


def author_score_map(
    achievement: Achievement,
    rules: Iterable[ContributionRule],
) -> dict[int, float]:
    """返回 {person_id: 得分} 映射（仅统计 person_id）。"""
    return {item["author"].person_id: item["score"] for item in calculate_achievement(achievement, rules)}
