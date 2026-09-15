"""初始化默认数据（类别、级别、作者贡献系数规则）与演示数据。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    Achievement,
    AchievementAuthor,
    AchievementStatus,
    Category,
    ContributionRule,
    Department,
    Level,
    Person,
)
from backend.scoring import DEFAULT_RATIO_TABLE

DEFAULT_CATEGORIES: list[dict] = [
    {
        "name": "论文",
        "code": "paper",
        "sort_order": 1,
        "description": "期刊论文、会议论文等",
        "levels": [
            ("SCI 一区", 100.0),
            ("SCI 二区", 80.0),
            ("SCI 三区", 60.0),
            ("SCI 四区", 40.0),
            ("EI 期刊论文", 35.0),
            ("中文核心（北大核心/CSSCI）", 30.0),
            ("普通期刊", 10.0),
        ],
    },
    {
        "name": "专利",
        "code": "patent",
        "sort_order": 2,
        "description": "发明、实用新型、外观设计等",
        "levels": [
            ("国际专利（PCT）", 80.0),
            ("发明专利", 60.0),
            ("实用新型专利", 20.0),
            ("外观设计专利", 10.0),
            ("软件著作权", 15.0),
        ],
    },
    {
        "name": "课题",
        "code": "project",
        "sort_order": 3,
        "description": "纵向、横向科研项目",
        "levels": [
            ("国家级重大/重点项目", 200.0),
            ("国家级一般项目", 150.0),
            ("省部级重点项目", 100.0),
            ("省部级一般项目", 60.0),
            ("市厅级项目", 30.0),
            ("校级项目", 10.0),
        ],
    },
    {
        "name": "著作",
        "code": "book",
        "sort_order": 4,
        "description": "专著、编著、译著、教材",
        "levels": [
            ("学术专著", 100.0),
            ("编著", 60.0),
            ("译著", 50.0),
            ("规划教材", 40.0),
        ],
    },
    {
        "name": "获奖",
        "code": "award",
        "sort_order": 5,
        "description": "科研与教学成果奖励",
        "levels": [
            ("国家级一等奖", 300.0),
            ("国家级二等奖", 200.0),
            ("国家级三等奖", 150.0),
            ("省部级一等奖", 150.0),
            ("省部级二等奖", 100.0),
            ("省部级三等奖", 60.0),
            ("市厅级一等奖", 60.0),
            ("市厅级二等奖", 40.0),
            ("市厅级三等奖", 20.0),
        ],
    },
]

# 通用作者贡献系数（category_id 为空）
DEFAULT_RULES: list[dict] = [
    {"author_count": 1, "ratios": [1.0], "corresponding_ratio": None},
    {"author_count": 2, "ratios": [0.6, 0.4], "corresponding_ratio": None},
    {"author_count": 3, "ratios": [0.5, 0.3, 0.2], "corresponding_ratio": None},
    {"author_count": 4, "ratios": [0.4, 0.3, 0.2, 0.1], "corresponding_ratio": None},
    {"author_count": 5, "ratios": [0.35, 0.25, 0.15, 0.15, 0.10], "corresponding_ratio": None},
    {"author_count": 6, "ratios": [0.30, 0.20, 0.15, 0.15, 0.10, 0.10], "corresponding_ratio": None},
]

SAMPLE_DEPARTMENTS = [
    {"name": "计算机科学与技术学院", "code": "CS"},
    {"name": "机械工程学院", "code": "ME"},
    {"name": "经济管理学院", "code": "EM"},
    {"name": "外国语学院", "code": "FL"},
]

SAMPLE_PERSONS = [
    {"name": "张伟", "employee_no": "1001", "dept": "CS", "current_title": "副教授", "apply_title": "教授"},
    {"name": "李娜", "employee_no": "1002", "dept": "CS", "current_title": "讲师", "apply_title": "副教授"},
    {"name": "王强", "employee_no": "1003", "dept": "ME", "current_title": "讲师", "apply_title": "副教授"},
    {"name": "赵敏", "employee_no": "1004", "dept": "EM", "current_title": "副教授", "apply_title": "教授"},
    {"name": "陈晨", "employee_no": "1005", "dept": "FL", "current_title": "助教", "apply_title": "讲师"},
    {"name": "刘洋", "employee_no": "1006", "dept": "CS", "current_title": "教授", "apply_title": "教授"},
]


def _seed_base(db: Session) -> dict:
    """写入类别、级别、默认作者贡献系数规则，返回 code -> Category 映射。"""
    categories: dict[str, Category] = {}
    for item in DEFAULT_CATEGORIES:
        category = Category(
            name=item["name"],
            code=item["code"],
            sort_order=item["sort_order"],
            description=item["description"],
        )
        db.add(category)
        db.flush()
        categories[category.code] = category
        for order, (level_name, score) in enumerate(item["levels"], start=1):
            db.add(
                Level(
                    category_id=category.id,
                    name=level_name,
                    base_score=score,
                    sort_order=order,
                )
            )

    for rule in DEFAULT_RULES:
        db.add(
            ContributionRule(
                category_id=None,
                author_count=rule["author_count"],
                ratios=rule["ratios"],
                corresponding_ratio=rule["corresponding_ratio"],
                remark="系统默认规则",
            )
        )
    db.flush()
    return categories


def _seed_demo(db: Session, categories: dict[str, Category]) -> None:
    """写入演示用部门、人员与成果。"""
    dept_map: dict[str, Department] = {}
    for item in SAMPLE_DEPARTMENTS:
        dept = Department(name=item["name"], code=item["code"])
        db.add(dept)
        db.flush()
        dept_map[item["code"]] = dept

    person_map: dict[str, Person] = {}
    for item in SAMPLE_PERSONS:
        person = Person(
            name=item["name"],
            employee_no=item["employee_no"],
            department_id=dept_map[item["dept"]].id,
            current_title=item["current_title"],
            apply_title=item["apply_title"],
        )
        db.add(person)
        db.flush()
        person_map[item["employee_no"]] = person

    def level_id(code: str, name: str) -> int:
        for level in categories[code].levels:
            if level.name == name:
                return level.id
        raise KeyError(f"未找到级别 {code}/{name}")

    samples = [
        {
            "title": "面向复杂场景的多模态目标检测方法研究",
            "category": "paper",
            "level": "SCI 一区",
            "owner": "1001",
            "year": 2025,
            "publisher": "IEEE TPAMI",
            "external_no": "10.1109/TPAMI.2025.0001",
            "status": AchievementStatus.APPROVED,
            "authors": [("1001", 1, True), ("1002", 2, False), ("1006", 3, False)],
        },
        {
            "title": "一种基于深度学习的缺陷检测装置",
            "category": "patent",
            "level": "发明专利",
            "owner": "1002",
            "year": 2025,
            "external_no": "ZL2025 1 0123456.7",
            "status": AchievementStatus.APPROVED,
            "authors": [("1002", 1, False), ("1001", 2, False)],
        },
        {
            "title": "智能制造关键共性技术研究与应用",
            "category": "project",
            "level": "国家级一般项目",
            "owner": "1003",
            "year": 2026,
            "external_no": "国科金 62XXXXXX",
            "status": AchievementStatus.PENDING,
            "authors": [("1003", 1, False), ("1001", 2, False), ("1006", 3, False), ("1002", 4, False)],
        },
        {
            "title": "区域经济高质量发展评价体系研究",
            "category": "award",
            "level": "省部级二等奖",
            "owner": "1004",
            "year": 2025,
            "status": AchievementStatus.APPROVED,
            "authors": [("1004", 1, False), ("1003", 2, False)],
        },
        {
            "title": "大学英语混合式教学模式改革",
            "category": "book",
            "level": "规划教材",
            "owner": "1005",
            "year": 2026,
            "status": AchievementStatus.REJECTED,
            "reject_reason": "佐证材料不完整，请补充出版社出版证明",
            "authors": [("1005", 1, False), ("1004", 2, False)],
        },
    ]

    for item in samples:
        achievement = Achievement(
            title=item["title"],
            category_id=categories[item["category"]].id,
            level_id=level_id(item["category"], item["level"]),
            owner_id=person_map[item["owner"]].id,
            year=item["year"],
            achievement_date=f"{item['year']}-06-01",
            external_no=item.get("external_no", ""),
            publisher=item.get("publisher", ""),
            status=item["status"],
            reject_reason=item.get("reject_reason", ""),
            remark="演示数据",
        )
        db.add(achievement)
        db.flush()
        for employee_no, rank, is_corresponding in item["authors"]:
            db.add(
                AchievementAuthor(
                    achievement_id=achievement.id,
                    person_id=person_map[employee_no].id,
                    rank=rank,
                    is_corresponding=is_corresponding,
                )
            )


def seed_all(db: Session, with_demo: bool = True) -> None:
    """首次运行写入默认数据；已有数据则跳过。"""
    has_category = db.scalar(select(Category.id).limit(1)) is not None
    if has_category:
        return
    categories = _seed_base(db)
    if with_demo:
        _seed_demo(db, categories)
    db.commit()
