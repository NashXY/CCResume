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
    # 去掉常见的导出/黏贴残留的长混合字母数字ID，例如 "XV639S5FVpSwJG7U_yfRearmg"
    # 匹配长度较长(12+) 的字母数字下划线或连字符序列
    s = re.sub(r"\b[A-Za-z0-9_\-]{12,}\b", '', s)
    # 去掉 JS 对象被字符串化后的占位文本
    s = re.sub(r'\[object Object\]', '', s, flags=re.I)

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

    # 在分块前，先从清洗后的前几行中尝试提取姓名（以保留原始header信息用于姓名提取）
    header_candidate = '\n'.join([ln for ln in clean_lines if ln.strip()][:6])

    # 提取中文或英文姓名（优先尝试中文）
    result = ResumeParseResult()
    zh_name = re.search(r'([\u4e00-\u9fa5]{2,4})', header_candidate)
    if zh_name:
        result.name = zh_name.group(1)
    else:
        en_name = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', header_candidate)
        if en_name:
            result.name = en_name.group(1)

    # 现在从清洗后的行里剥离明显的个人信息行，避免它们被当作工作/项目块
    personal_line_re_list = [
        re.compile(r'年龄[:：]?\s*\d{1,3}\b', re.I),
        re.compile(r'^\s*(男|女)\s*$', re.I),
        re.compile(r'性别[:：]', re.I),
        re.compile(r'手机[:：]?|电话[:：]?|微信[:：]?', re.I),
        re.compile(r'邮箱|@', re.I),
        re.compile(r'户籍|居住地|婚姻|基本资料', re.I),
        re.compile(r'目前公司|现公司|现任|目前职位|职位[:：]', re.I),
    ]

    filtered_lines = []
    for ln in clean_lines:
        t = ln.strip()
        if not t:
            filtered_lines.append('')
            continue
        # 如果这一行明显是个人信息且长度较短（通常是 header 行），则剥离掉
        is_personal = False
        for cre in personal_line_re_list:
            if cre.search(t) and len(t) < 120:
                is_personal = True
                break
        if is_personal:
            # 跳过这类行，不加入用于块分割的文本
            continue
        filtered_lines.append(t)

    s_clean = '\n'.join(filtered_lines)

    # 优先按常见章节标题划分块，避免教育/项目/工作混在一块
    header_patterns = [
        r'^\s*教育经历\s*$', r'^\s*教育背景\s*$', r'^\s*教育\s*$',
        r'^\s*项目经验\s*$', r'^\s*项目经历\s*$', r'^\s*项目\s*$',
        r'^\s*工作经历\s*$', r'^\s*工作经验\s*$', r'^\s*职业经历\s*$',
        r'^\s*实习经历\s*$', r'^\s*自我评价\s*$', r'^\s*主要技能\s*$',
    ]
    header_re = re.compile('|'.join('(?:%s)' % p for p in header_patterns), re.I)

    lines_for_blocks = [ln for ln in s_clean.splitlines()]
    blocks = []
    current = []
    current_header = None
    for ln in lines_for_blocks:
        if header_re.match(ln.strip()):
            # 开始新的块：先把现有块推入
            if current:
                blocks.append('\n'.join(current).strip())
                current = []
            # 把标题也作为块的首行
            current.append(ln.strip())
            current_header = ln.strip()
            continue
        # 普通行追加到当前块
        current.append(ln)
    if current:
        blocks.append('\n'.join(current).strip())

    # 最后再把相邻空行产生的多段合并或清理空白块
    blocks = [b for b in (b.strip() for b in blocks) if b]



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
    def strip_leading_meta_lines(block: str) -> str:
        """去掉块开头的短个人/公司/职位元信息行，例如：姓名+性别、公司名、职位行、工作地点等。"""
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            return ''
        # 模式：姓名+性别（如 蒋大伟男）
        name_gender_re = re.compile(r'^[\u4e00-\u9fa5]{2,4}\s*(男|女)$')
        # 公司行模式（含 公司 有限公司 科技 集团 等）
        company_re = re.compile(r'(公司|有限公司|科技|集团|股份|有限|Inc|LLC)', re.I)
        # 职位/职称/工作地点/时间段 行
        title_re = re.compile(r'(职位|软件|工程师|主管|责任|工作地点|至今|\d{4}[-年])', re.I)

        # 连续剥离前几行，只要它们匹配元信息模式且较短
        i = 0
        while i < len(lines) and i < 4:
            ln = lines[i].strip()
            if len(ln) < 120 and (name_gender_re.search(ln) or company_re.search(ln) or title_re.search(ln)):
                i += 1
                continue
            break
        if i > 0:
            return '\n'.join(lines[i:]).strip()
        return block

    # 预编译标题匹配用于直接归类
    project_header_re = re.compile(r'^(项目经验|项目经历|项目)\b', re.I)
    education_header_re = re.compile(r'^(教育经历|教育背景|教育)\b', re.I)

    for block in blocks:
        # 如果块以项目/教育标题开头，直接归类，避免关键字稀释或误判
        first_line = block.splitlines()[0].strip() if block.splitlines() else ''
        if project_header_re.match(first_line):
            # 去掉标题行后保存作为一个 project 条目
            body = '\n'.join(block.splitlines()[1:]).strip()
            if body:
                result.projects.append(body)
            continue
        if education_header_re.match(first_line):
            body = '\n'.join(block.splitlines()[1:]).strip()
            if body:
                result.education.append(body)
            continue
        # 先剥离块前面的元信息行
        block = strip_leading_meta_lines(block)
        if not block:
            continue
        # 如果块明显包含个人信息关键词且内容较短，跳过（避免被误判为工作经历）
        personal_block_re = re.compile(r'(姓名|性别|手机|电话|微信|邮箱|年龄|婚姻|户籍|居住地|基本资料|目前公司|目前职位)', re.I)
        if personal_block_re.search(block) and len(block) < 200:
            continue

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
