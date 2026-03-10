"""Recommendation service (simple rule-based)."""


def get_recommendations(gap: str):
    base = [
        {"type": "course", "title": "岗位技能实战课", "url": "https://www.icourse163.org"},
        {"type": "practice", "title": "开源项目实践", "url": "https://github.com"},
    ]
    if not gap:
        return base

    g = gap.lower()
    if "spring" in g:
        return base + [{"type": "course", "title": "Spring Boot 实战", "url": "https://spring.io/guides"}]
    if "python" in g:
        return base + [{"type": "course", "title": "Python 工程化进阶", "url": "https://docs.python.org"}]
    if "sql" in g or "mysql" in g:
        return base + [{"type": "course", "title": "SQL 与数据库优化", "url": "https://www.postgresql.org/docs/"}]
    return base
