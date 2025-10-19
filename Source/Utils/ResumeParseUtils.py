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
    # 先清洗常见噪声：页眉/页脚（第1页共7页 等）、长的十六进制或重复编码串、纯符号行等
    # 删除典型的页码标记
    s = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', s)
    s = re.sub(r'第\s*\d+\s*页', '', s)
    s = re.sub(r'共\s*\d+\s*页', '', s)
    s = re.sub(r'Page\s*\d+', '', s, flags=re.I)
    # 去掉长的十六进制/随机串（例如 OCR/导出残留）
    s = re.sub(r'[A-Fa-f0-9]{16,}', '', s)
    # 去掉连续的 ~ 或特殊分隔符
    s = re.sub(r'~{2,}', '', s)

    # 按行过滤明显噪声行
    lines = [ln for ln in s.splitlines()]
    clean_lines = []
    long_hex_re = re.compile(r'[A-Fa-f0-9]{12,}')
    page_re = re.compile(r'第\s*\d+\s*页|共\s*\d+\s*页|Page\s*\d+', re.I)
    punct_re = re.compile(r'^[\W_~]+$')
    for ln in lines:
        t = ln.strip()
        if not t:
            clean_lines.append('')
            continue
        # 如果包含页码、长十六进制串或是纯符号行，则跳过
        if page_re.search(t):
            continue
        if long_hex_re.search(t):
            # 这一类通常是导出残留或加密串，丢弃
            continue
        if punct_re.match(t) and len(t) > 4:
            continue
        # 如果行过短且不包含中文/字母数字，跳过
        if len(t) < 4 and not re.search(r'[\u4e00-\u9fffA-Za-z0-9]', t):
            continue
        clean_lines.append(t)

    s_clean = '\n'.join(clean_lines)

    # 以空行为块分割（用清洗后的文本）
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", s_clean) if b.strip()]

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

    # 只把满足一定条件的块归为 projects/education，过滤残余噪声块
    for block in blocks:
        sc = score_block(block)
        # 要判为 education，需要 education 特征明显
        if sc['education'] >= 3:
            result.education.append(block)
            continue

        # 判为 project 的额外要求：要么有项目关键词/职责/业绩等，要么包含技术关键词
        has_project_keywords = any(re.search(kw, block, re.I) for kw in [r'项目', r'项目经验', r'职责', r'业绩', r'完成', r'负责'])
        tech_count = len(tech_regex.findall(block))
        if (sc['project'] >= 2 and (has_project_keywords or tech_count > 0)) or (sc['work'] >= 2 and sc['project'] >= 1 and tech_count > 0):
            result.projects.append(block)
            continue

        # 其余视为非目标块，忽略
        continue

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
    
    print(f"[ResumeParseUtils]ResumeParse结果: {result}")

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
