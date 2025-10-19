import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


def _normalize(text: str) -> str:
    return re.sub(r"\r", "\n", text or "").strip()


@dataclass
class ResumeParseResult:
    name: Optional[str] = None
    age: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    projects: List[str] = field(default_factory=list)
    education: List[str] = field(default_factory=list)


def ResumeParse(text: str) -> ResumeParseResult:
    """根据块分类启发式从简历文本中提取 name, age, phone, projects, education。

    返回 ResumeParseResult 实例。
    """
    if not text or not text.strip():
        return ResumeParseResult()

    s = _normalize(text)
    # 以空行为块分割
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", s) if b.strip()]

    result = ResumeParseResult()

    # header 探测
    header = "\n".join(blocks[:2]) if blocks else ""
    zh_name = re.search(r'([\u4e00-\u9fa5]{2,4})', header)
    if zh_name:
        result.name = zh_name.group(1)
    else:
        en_name = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', header)
        if en_name:
            result.name = en_name.group(1)

    # phone 和 age
    # email
    email_m = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', s)
    if email_m:
        result.email = email_m.group(0)

    phone_m = re.search(r'(?:\+?\d{1,3}[\s-])?(?:\(?0?\d{2,4}\)?[\s-])?[\d\s-]{6,15}', s)
    if phone_m:
        result.phone = re.sub(r'[^0-9+]', '', phone_m.group(0))

    age_m = re.search(r'(?:(?:Age|年龄)[:：]?\s*(\d{2})\b)', s, re.I)
    if age_m:
        result.age = age_m.group(1)
    else:
        birth_m = re.search(r'出生[:：]?\s*(\d{4})', s)
        if birth_m:
            try:
                birth = int(birth_m.group(1))
                import datetime

                result.age = str(datetime.datetime.now().year - birth)
            except Exception:
                pass

    # 关键词
    project_kw = [r'项目', r'项目经验', r'project', r'实现', r'功能', r'优化', r'技术栈', r'GitHub', r'仓库', r'负责', r'实现了', r'解决']
    education_kw = [r'学校', r'学位', r'毕业', r'本科', r'硕士', r'博士', r'专业']
    work_kw = [r'公司', r'任职', r'职位', r'职责', r'负责', r'工作内容']
    tech_regex = re.compile(r'\b(Python|Java|C\+\+|C#|React|Django|Flask|Docker|Kubernetes|MySQL|PostgreSQL|SQL)\b', re.I)

    def score_block(block: str) -> Dict[str, int]:
        p = e = w = 0
        for kw in project_kw:
            if re.search(kw, block, re.I):
                p += 2
        for kw in education_kw:
            if re.search(kw, block, re.I):
                e += 3
        for kw in work_kw:
            if re.search(kw, block, re.I):
                w += 2
        tech_count = len(tech_regex.findall(block))
        p += tech_count
        return {"project": p, "education": e, "work": w}

    for block in blocks:
        sc = score_block(block)
        if sc['education'] >= 3:
            result.education.append(block)
        elif sc['project'] >= 2:
            result.projects.append(block)
        elif sc['work'] >= 2 and sc['project'] >= 1:
            result.projects.append(block)
        else:
            # fallback: 忽略
            pass

    # 去重
    def clean_list(lst: List[str]) -> List[str]:
        out = []
        seen = set()
        for x in lst:
            t = x.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    result.projects = clean_list(result.projects)
    result.education = clean_list(result.education)

    return result


if __name__ == '__main__':
    sample = """
    张三

    教育背景
    本科：计算机科学，某某大学

    项目经验
    2020-2021 项目A: 使用 Python 和 Flask 实现 X 功能
    """
    print(ResumeParse(sample))
