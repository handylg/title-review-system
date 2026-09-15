"""ORM 对象到响应结构的序列化辅助。"""

from __future__ import annotations

from typing import Iterable

from backend import scoring
from backend.models import Achievement, AchievementStatus, ContributionRule, Person


def person_out(person: Person) -> dict:
    return {
        "id": person.id,
        "name": person.name,
        "employee_no": person.employee_no,
        "department_id": person.department_id,
        "department_name": person.department.name if person.department else None,
        "current_title": person.current_title,
        "apply_title": person.apply_title,
        "is_active": person.is_active,
    }


def achievement_out(
    achievement: Achievement,
    rules: Iterable[ContributionRule],
) -> dict:
    calculated = scoring.calculate_achievement(achievement, rules)
    authors = []
    total = 0.0
    for item in calculated:
        author = item["author"]
        person = author.person
        total += item["score"]
        authors.append(
            {
                "person_id": author.person_id,
                "person_name": person.name if person else f"#{author.person_id}",
                "employee_no": person.employee_no if person else "",
                "department_name": person.department.name if person and person.department else None,
                "rank": author.rank,
                "is_corresponding": author.is_corresponding,
                "custom_ratio": author.custom_ratio,
                "ratio": item["ratio"],
                "score": item["score"],
            }
        )

    return {
        "id": achievement.id,
        "title": achievement.title,
        "category_id": achievement.category_id,
        "category_name": achievement.category.name if achievement.category else "",
        "level_id": achievement.level_id,
        "level_name": achievement.level.name if achievement.level else "",
        "base_score": achievement.level.base_score if achievement.level else 0.0,
        "owner_id": achievement.owner_id,
        "owner_name": achievement.owner.name if achievement.owner else None,
        "year": achievement.year,
        "achievement_date": achievement.achievement_date,
        "external_no": achievement.external_no,
        "publisher": achievement.publisher,
        "remark": achievement.remark,
        "evidence_url": achievement.evidence_url,
        "status": achievement.status,
        "status_label": AchievementStatus.LABELS.get(achievement.status, achievement.status),
        "reject_reason": achievement.reject_reason,
        "total_score": round(total, 2),
        "authors": authors,
    }
