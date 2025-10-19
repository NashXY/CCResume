import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# 可选的中文分词/词性标注增强（jieba）
try:
    import jieba
    import jieba.posseg as pseg
    _HAS_JIEBA = True
except Exception:
    _HAS_JIEBA = False

# 可选的 transformers-based NER（懒加载）
_NER_PIPELINE = None
_USE_TRANSFORMERS_NER = True
def _get_ner_pipeline():
    global _NER_PIPELINE
    if _NER_PIPELINE is not None:
        return _NER_PIPELINE
    try:
        from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
        # 使用一个通用的中文 NER 模型（可替换为你偏好的模型）
        model_name = 'ckiplab/bert-base-chinese-ner'
        _NER_PIPELINE = pipeline('ner', model=model_name, tokenizer=model_name, aggregation_strategy='simple')
    except Exception:
        _NER_PIPELINE = None
    return _NER_PIPELINE


def _normalize(text: str) -> str:
    return re.sub(r"\r", "\n", text or "").strip()


def normalize_cjk_spacing(text: str) -> str:
    """去除中文字符之间不必要的空白（把 '工 作 经 历' -> '工作经历'），并删除零宽字符。"""
    if not text:
        return text
    # 删除零宽空格等
    text = text.replace('\u200b', '')
    # 把中文字符之间的空白去除，多次替换以覆盖连续拆分的情况
    # 匹配: 中文字符 + 空白 + 中文字符
    text = re.sub(r'([\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', r"\1", text)
    return text


@dataclass
class ResumeParseResult:
    name: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    careers: List[str] = field(default_factory=list)
    education: List[str] = field(default_factory=list)
    # 结构化输出
    careers_struct: List[Dict[str, Any]] = field(default_factory=list)
    education_struct: List[Dict[str, Any]] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'age': self.age,
            'sex': self.sex,
            'phone': self.phone,
            'email': self.email,
            'careers': self.careers,
            'careers_struct': self.careers_struct,
            'education': self.education,
            'education_struct': self.education_struct,
        }


def ResumeParse(text: str, debug: bool = False) -> ResumeParseResult:
    """根据块分类启发式从简历文本中提取 name, age, phone, education，以及工作/项目类信息合并在 careers 中。
        it2_clean = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]', '', it2)
    返回 ResumeParseResult 实例。
    """
    if not text or not text.strip():
        return ResumeParseResult()

    s = _normalize(text)
    # 先规范中文间的空格（把 '工 作 经 历' 之类的拆分恢复为连写）
    s = normalize_cjk_spacing(s)
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

    # 有时 header 是多项由 | 或 / 分隔的短项（例如: "男 | 年龄：28岁 | 13558910629 | 期望薪资"）
    # 把这些行拆分并把能识别的个人信息剥离
    header_items = []
    for ln in header_candidate.splitlines():
        if '|' in ln or '/' in ln or ';' in ln:
            parts = re.split(r'[|/;，,]+', ln)
            header_items.extend([p.strip() for p in parts if p.strip()])
        else:
            header_items.append(ln.strip())

    # 初始化结果对象（确保 header 处理可以直接写入字段）
    result = ResumeParseResult()

    # 把 header_items 里的个人域识别出来并从 clean_lines 中移除相应短行
    personal_short_re = re.compile(r'^(男|女|\d{1,3}岁|\+?\d{6,15}|\d{6,}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$', re.I)
    # 先从 header_items 中直接识别联系方式/年龄/性别等，并优先设置 result 的字段
    for it in header_items:
        if not it:
            continue
        it_strip = it.strip()
        # 手机（优先严格的中国手机号格式）
        m_mobile = re.search(r'(?<!\d)(?:\+?86[-\s]?)?(1[3-9]\d{9})(?!\d)', it_strip)
        if m_mobile:
            result.phone = m_mobile.group(1)
            # 从 clean_lines 中移除
            clean_lines = [ln for ln in clean_lines if ln.strip() != it_strip]
            continue
        # email
        if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', it_strip):
            result.email = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', it_strip).group(0)
            clean_lines = [ln for ln in clean_lines if ln.strip() != it_strip]
            continue
        # 年龄
        age_m_h = re.search(r'(\d{2})岁|年龄[:：]?\s*(\d{1,3})', it_strip)
        if age_m_h:
            age_val = age_m_h.group(1) or age_m_h.group(2)
            result.age = age_val
            clean_lines = [ln for ln in clean_lines if ln.strip() != it_strip]
            continue
        # 性别
        if re.match(r'^(男|女)$', it_strip):
            result.sex = it_strip
            clean_lines = [ln for ln in clean_lines if ln.strip() != it_strip]
            continue
    # 如果 header_items 没设置 name，在 header_candidate 中寻找候选姓名（排除诸如'年龄'等词）
    result = ResumeParseResult() if 'result' not in locals() else result
    stop_words_for_name = set(['年龄', '性别', '个人优势', '求职意向', '期望薪资', '期望城市', '工作经验'])
    candidate_name = None
    # 优先从 header_items 中找纯中文 2-4 字项（可能含性别尾缀）
    for it in header_items:
        if not it:
            continue
        it2 = it.strip()
        if any(sw in it2 for sw in stop_words_for_name):
            continue
        # 清理常见噪声
        it2_clean = re.sub(r'[^-\u4e00-\u9fa5]', '', it2)
        # 优先选择纯中文且长度为2-4的项
        if re.fullmatch(r'[\u4e00-\u9fa5]{2,4}', it2_clean):
            candidate_name = it2_clean
            break
    # 如果未找到且可用 jieba，尝试 posseg 在 header_candidate 上找 nr
    if not candidate_name and _HAS_JIEBA and re.search(r'[\u4e00-\u9fff]', header_candidate):
        try:
            for w, flag in pseg.cut(header_candidate):
                if flag == 'nr' and 2 <= len(w) <= 4 and w not in stop_words_for_name:
                    candidate_name = w
                    break
        except Exception:
            pass

    # 如果找到候选姓名，写入 result
    if candidate_name:
        result.name = candidate_name

    # 最后的回退：如果仍未识别到姓名，从 header_candidate 或全文抓取第一个符合姓名模式的中文词
    if not result.name:
        m = re.search(r'([\u4e00-\u9fa5]{2,4})\s*(?:男|女)?', header_candidate)
        if m:
            result.name = m.group(1)
        else:
            m2 = re.search(r'([\u4e00-\u9fa5]{2,4})\s*(?:男|女)?', s)
            if m2:
                result.name = m2.group(1)

    # 如果之前未通过 header_items 设置到 phone/email/age/sex，则后面再做更严格的提取

    # 识别性别（中文/英文），优先在 header_candidate 中查找
    sex = None
    sex_m = re.search(r'性别[:：]?\s*(男|女)', header_candidate)
    if not sex_m:
        sex_m = re.search(r'性别[:：]?\s*(男|女)', s, re.I)
    if not sex_m:
        # 有时姓名后直接跟性别，如 "蒋大伟男" 或正文中出现姓名+性别
        tail_sex = re.search(r'^[\u4e00-\u9fa5]{2,4}(男|女)$', header_candidate)
        if not tail_sex:
            tail_sex = re.search(r'([\u4e00-\u9fa5]{2,4})(男|女)', s)
        sex_m = tail_sex
    if sex_m:
        # 如果捕获了多组（例如名+性别），取最后一组作为性别
        try:
            if sex_m.lastindex and sex_m.lastindex >= 2:
                sex = sex_m.group(sex_m.lastindex)
            else:
                sex = sex_m.group(1)
        except Exception:
            sex = sex_m.group(1)
    else:
        # 英文 male/female
        eng = re.search(r'\b(male|female)\b', header_candidate, re.I) or re.search(r'\b(male|female)\b', s, re.I)
        if eng:
            sex = eng.group(1).lower()

    # 归一化：如果是英文 male/female，转换为中文 '男'/'女'，否则保留中文标记
    if sex:
        if sex.lower() == 'male':
            result.sex = '男'
        elif sex.lower() == 'female':
            result.sex = '女'
        else:
            result.sex = sex

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
        r'^\s*实习经历\s*$', r'^\s*自我评价\s*$', r'^\s*主要技能\s*$', r'^\s*培训经历\s*$',
    ]
    header_re = re.compile('|'.join('(?:%s)' % p for p in header_patterns), re.I)

    # 更稳健的块拆分：基于章节 header 关键词把文本拆分为多个块（保留 header 行）
    split_headers = r'教育经历|教育背景|教育|项目经验|项目经历|项目|工作经历|工作经验|职业经历|实习经历|自我评价|主要技能|培训经历|培训'
    # 使用多行模式，在 header 前进行拆分（保留 header 行作为新块首行）
    blocks = [b.strip() for b in re.split(r'(?m)(?=^\s*(?:' + split_headers + r')\b)', s_clean) if b.strip()]
    # 进一步，如果某个块本身为空，删除
    blocks = [b for b in blocks if b]

    # 如果某些块中间仍包含公司行或 '公司名 职位' 形式，把这些块按行拆分为更小块，
    # 以便公司行能作为独立块被识别为 career 的起始
    company_line_re = re.compile(r'^[\s\S]*?(公司|有限公司|科技|集团|股份)[\s\S]*$', re.I)
    refined_blocks = []
    for b in blocks:
        lines = [ln for ln in b.splitlines()]
        # 如果某行匹配公司行且不是块首行，则切分
        split_indices = []
        for idx, ln in enumerate(lines):
            if idx > 0 and company_line_re.match(ln.strip()):
                split_indices.append(idx)
        if not split_indices:
            refined_blocks.append(b)
            continue
        prev = 0
        for si in split_indices:
            part = '\n'.join(lines[prev:si]).strip()
            if part:
                refined_blocks.append(part)
            prev = si
        last = '\n'.join(lines[prev:]).strip()
        if last:
            refined_blocks.append(last)
    blocks = refined_blocks



    # phone 和 age
    # email
    email_m = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', s)
    if email_m:
        result.email = email_m.group(0)

    # phone: 优先严格的中国手机号匹配，回退到较宽松的匹配但排除年份范围等
    phone_m = re.search(r'(?<!\d)(?:\+?86[-\s]?)?(1[3-9]\d{9})(?!\d)', s)
    if phone_m:
        result.phone = phone_m.group(1)
    else:
        phone_m2 = re.search(r'(?:\+?\d{1,3}[\s-])?(?:\(?0?\d{2,4}\)?[\s-])?[\d\s-]{6,15}', s)
        if phone_m2:
            raw = phone_m2.group(0)
            # 如果是年份区间（例如 2018-2021），不要当作电话
            if re.search(r'\d{4}\s*[-–—]\s*\d{4}', raw):
                pass
            else:
                result.phone = re.sub(r'[^0-9+]', '', raw)

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
    project_kw = [r'项目', r'项目经验', r'project', r'实现', r'功能', r'优化', r'技术栈', r'GitHub', r'仓库', r'负责', r'实现了', r'解决', r'业绩', r'项目描述', r'项目名称', r'成果', r'完成']
    education_kw = [r'学校', r'学位', r'毕业', r'本科', r'硕士', r'博士', r'专业']
    work_kw = [r'公司', r'任职', r'职位', r'职责', r'负责', r'工作内容']
    tech_regex = re.compile(r'\b(Python|Java|C\+\+|C#|React|Django|Flask|Docker|Kubernetes|MySQL|PostgreSQL|SQL|FPGA|WiFi|BT|5G|4G|SMF|Golang|Go|OpenWrt|openwrt|FPGA|Ethernet)\b', re.I)

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
        # 如果可用 jieba，对于中文文本，检测组织名 (nt) 增强工作得分
        if _HAS_JIEBA and re.search(r'[\u4e00-\u9fff]', block):
            try:
                for word, flag in pseg.cut(block):
                    if flag == 'nt':
                        w += 2
                    # 人名在某些情况下提示该块可能为职责或项目的一部分
                    if flag == 'nr':
                        p += 0
            except Exception:
                pass
        p += tech_count
        # 如果块中包含明显的个人信息（电话/邮箱/年龄/性别），对其进行惩罚，避免误判为工作/项目
        if re.search(r'(姓名|性别|手机|电话|微信|邮箱|年龄|婚姻|户籍|居住地|基本资料)', block, re.I):
            w = max(0, w - 2)
            p = max(0, p - 2)
        # 如果块包含 '业绩' 或 '项目描述' 等明显的项目指示词，提高 project 得分
        if re.search(r'(业绩|项目描述|项目名称|成果)', block, re.I):
            p += 3
        # 如果块含有编号列表且出现技术关键词，则很可能是项目经历/项目说明
        if re.search(r'(?m)^\s*\d+[\.|\)|、]\s+', block) and tech_count > 0:
            p += 3
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
            # 对于非常短的 header-like 行（例如 '男 | 28岁' 或 '公司名'），也应剥离
            if len(ln) < 120 and (name_gender_re.search(ln) or company_re.search(ln) or title_re.search(ln) or re.search(r'^[\|/;\-\w\s]{1,40}$', ln)):
                i += 1
                continue
            break
        if i > 0:
            return '\n'.join(lines[i:]).strip()
        return block

    # 预编译标题匹配用于直接归类
    project_header_re = re.compile(r'^(项目经验|项目经历|项目)\b', re.I)
    education_header_re = re.compile(r'^(教育经历|教育背景|教育)\b', re.I)
    career_header_re = re.compile(r'^(工作经历|工作经验|职业经历|任职|公司)\b', re.I)

    if debug:
        print('\n[DEBUG] Found blocks:')
        for i, b in enumerate(blocks):
            snippet = b.replace('\n', ' || ')[:200]
            sc_tmp = score_block(b)
            print(f'  [{i}] len={len(b)} score={sc_tmp} header={b.splitlines()[0] if b.splitlines() else ""}')
            print('    ', snippet)

    for block in blocks:
        # 如果块以项目/教育标题开头，直接归类，避免关键字稀释或误判
        first_line = block.splitlines()[0].strip() if block.splitlines() else ''
        # 如果首行看起来像公司名（例如包含 公司/有限公司/科技/集团/股份），直接归类为 career
        if re.search(r'(公司|有限公司|科技|集团|股份)', first_line, re.I):
            body = '\n'.join(block.splitlines()[1:]).strip()
            # 把公司行与后续正文合并，便于后续的结构化解析识别 company/title/period
            if body:
                career_text = first_line + '\n' + body
            else:
                career_text = first_line
            if career_text:
                result.careers.append(career_text)
            continue
        if project_header_re.match(first_line):
            # 去掉标题行后保存作为一个 careers 条目（把项目经验并入 careers）
            body = '\n'.join(block.splitlines()[1:]).strip()
            if body:
                result.careers.append(body)
            continue
        if education_header_re.match(first_line):
            body = '\n'.join(block.splitlines()[1:]).strip()
            if body:
                result.education.append(body)
            continue
        if career_header_re.match(first_line):
            # 去掉标题行，整块作为 career 条目（职业/公司经历）
            body = '\n'.join(block.splitlines()[1:]).strip()
            if body:
                result.careers.append(body)
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
        # 如果块中包含学校/学院/大学/本科/硕士/学位/培训等关键词，优先判为 education
        education_indicators = re.compile(r'(大学|学院|学校|本科|硕士|博士|学位|毕业|培训经历|培训机构|培训)', re.I)
        if education_indicators.search(block):
            result.education.append(block)
            continue
        # 判为 career（职业/公司经历）：包含公司/任职/职位/工作地点等关键词且篇幅较长
        if (sc['work'] >= 2 or re.search(r'公司|任职|职位|工作地点|职责|业绩', block, re.I)):
            result.careers.append(block)
            continue
        # 要判为 education，需要 education 特征明显（放在 career 检测之后，避免混淆）
        if sc['education'] >= 3:
            result.education.append(block)
            continue

        # 判为 project 的额外要求：要么有项目关键词/职责/业绩等，要么包含技术关键词
        has_project_keywords = any(re.search(kw, block, re.I) for kw in [r'项目', r'项目经验', r'职责', r'业绩', r'完成', r'负责'])
        tech_count = len(tech_regex.findall(block))
        if (sc['project'] >= 2 and (has_project_keywords or tech_count > 0)):
            # 明确为项目段，把项目并入 careers 列表
            result.careers.append(block)
            continue

        # 其余视为非目标块，忽略
        continue

        # 启发式结构化拆分（尽量提取 company/title/period/responsibilities/technologies）
    def split_career_block(block: str) -> Dict[str, Any]:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        item: Dict[str, Any] = { 'company': None, 'title': None, 'period': None, 'responsibilities': [], 'technologies': [] }
        if not lines:
            return item
        # 第一行若包含公司关键词，则作为 company 或 title
        first = lines[0]
        # 清理 company 字段：去掉页码/长随机串/重复标记等噪声
        def clean_company_name(name: str) -> str:
            if not name:
                return None
            n = name.strip()
            # 删除明显的页码/页眉标记
            n = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', n)
            n = re.sub(r'第\s*\d+\s*页', '', n)
            # 删除长混合 ID
            n = re.sub(r'[A-Za-z0-9_\-]{12,}', '', n)
            # 删除重复的分隔符和不可见字符
            n = re.sub(r'[~]{2,}', '', n)
            n = n.replace('\u200b', '')
            n = n.strip()
            return n or None

        if re.search(r'公司|有限公司|科技|集团|股份', first):
            item['company'] = clean_company_name(first)
            rest = lines[1:]
        else:
            # 尝试用行内模式提取 title 与 company
            # 例如: "哲库（ZEKU）科技上海有限公司\n软件开发（高级主管工程师） 2022.12-至今"
            if len(lines) > 1 and re.search(r'\d{4}', lines[1]):
                item['company'] = first
                rest = lines[1:]
            else:
                rest = lines

        # 查找 period（形如 2022.12-至今 或 2018.09-2021.09）
        period_re = re.compile(r'(\d{4}[\.\-年]?\d{0,2})\s*[-—–到至]\s*(\d{4}[\.\-年]?\d{0,2}|至今)', re.I)
        title_re = re.compile(r'(职位|职务|软件|工程师|主管|经理|技术|开发|负责人|专家)', re.I)
        tech_regex_local = re.compile(r'\b(Python|Java|C\+\+|C#|Go|Golang|Django|Flask|Docker|Kubernetes|FPGA|WiFi|BT|5G|4G|SMF)\b', re.I)
        # 先把整个块传给 NER（若可用），以获取 ORG/DATE/PER 提示，然后优先使用 NER 结果
        ner_entities = []
        if _USE_TRANSFORMERS_NER:
            ner_pipe = _get_ner_pipeline()
            if ner_pipe:
                try:
                    ner_entities = ner_pipe(block)
                except Exception:
                    ner_entities = []

        # 解析 NER 输出，尽可能保留 offset(start/end)以便合并相邻实体
        ner_orgs: List[Dict[str, Any]] = []
        ner_pers: List[Dict[str, Any]] = []
        ner_dates: List[Dict[str, Any]] = []
        if ner_entities:
            for ent in ner_entities:
                g = (ent.get('entity_group') or ent.get('entity') or '').upper()
                w = (ent.get('word') or ent.get('entity') or '').strip()
                if not w:
                    continue
                start = ent.get('start')
                end = ent.get('end')
                rec = {'word': w, 'start': start, 'end': end}
                if g in ('ORG', 'ORGANIZATION'):
                    ner_orgs.append(rec)
                elif g in ('PER', 'PERSON'):
                    ner_pers.append(rec)
                elif g in ('DATE', 'TIME'):
                    ner_dates.append(rec)

        # helper to sort by start if available else keep original order
        def _sort_by_start(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not lst:
                return lst
            if all(x.get('start') is not None for x in lst):
                return sorted(lst, key=lambda x: x['start'])
            return lst

        ner_orgs = _sort_by_start(ner_orgs)
        ner_pers = _sort_by_start(ner_pers)
        ner_dates = _sort_by_start(ner_dates)

        # company: 选择最长的 ORG（排除过短的噪声）
        if ner_orgs:
            cand = [o['word'] for o in ner_orgs if len(re.sub(r'\s+', '', o['word'])) > 1]
            if cand:
                cand = sorted(cand, key=lambda x: len(x), reverse=True)
                item['company'] = clean_company_name(cand[0])

        # name: 首个 PER
        if ner_pers and not result.name:
            result.name = ner_pers[0]['word']

        # period: 合并相邻的 DATE 实体为一个 period 字符串
        if ner_dates:
            merged_dates: List[str] = []
            if all(d.get('start') is not None for d in ner_dates):
                # 使用 start/end 进行合并：当相邻实体间距很小（例如 <=2）视为同一日期片段
                cur = ner_dates[0].copy()
                for nxt in ner_dates[1:]:
                    if cur.get('end') is not None and nxt.get('start') is not None and (nxt['start'] - cur['end'] <= 2):
                        # 合并
                        cur['word'] = cur['word'] + nxt['word']
                        cur['end'] = nxt.get('end')
                    else:
                        merged_dates.append(cur['word'])
                        cur = nxt.copy()
                merged_dates.append(cur['word'])
            else:
                # 没有偏移信息，按顺序合并连续的数字/年/月/token序列
                buf = ner_dates[0]['word']
                for rec in ner_dates[1:]:
                    w = rec['word']
                    # 如果当前 buf 或 w 包含中文年/月或 '.' 或 '-'，把它们合并
                    if re.search(r'[年月/\.-]', buf) or re.search(r'[年月/\.-]', w) or (len(w) <= 4 and w.isdigit() and len(buf) <= 6):
                        buf = buf + w
                    else:
                        merged_dates.append(buf)
                        buf = w
                merged_dates.append(buf)

            # 过滤掉明显是年龄（例如单个数字 28 且与 result.age 相等）的候选
            cleaned_md = []
            for md in merged_dates:
                md_clean = re.sub(r'[^0-9年月日/\.-]', '', md)
                if result.age and re.fullmatch(r'\d{1,3}', md_clean) and md_clean == str(result.age):
                    continue
                cleaned_md.append(md)
            if cleaned_md:
                if len(cleaned_md) == 1:
                    item['period'] = cleaned_md[0]
                else:
                    item['period'] = ' - '.join(cleaned_md)

        for ln in rest:
            # period
            pm = period_re.search(ln)
            if pm and not item['period']:
                item['period'] = pm.group(0)
                continue
            # title
            if not item['title'] and title_re.search(ln):
                item['title'] = ln
                continue
            # techs
            techs = tech_regex_local.findall(ln)
            if techs:
                item['technologies'].extend([t for t in techs if t])
            # responsibilities（非标题/时间行则归为职责）
            if not title_re.search(ln) and not period_re.search(ln):
                item['responsibilities'].append(ln)

        # 简单去重
        item['technologies'] = list(dict.fromkeys(item['technologies']))
        # 进一步标准化 company 名称
        if item.get('company'):
            item['company'] = clean_company_name(item['company'])
        return item

    # 构建结构化列表（对所有 careers 进行结构化拆分）
    # 去重/清理列表的辅助函数
    def clean_list(lst: List[str]) -> List[str]:
        out = []
        seen = set()
        for x in lst:
            t = x.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    # 先对碎片做一次预处理：把短段/编号段合并到其上一条 career（如果合适），以减少断裂
    merged_careers = []
    numbered_prefix_re = re.compile(r'^\s*(?:\d+[\.、\)\-]|\d+\.?\d+\s*\.|\(\d+\)|（\d+）)')
    for c in result.careers:
        c_strip = c.strip()
        # 短片段判断：长度较短或首行为编号或只有一行且以小写词/数字开头
        lines_c = [l for l in c_strip.splitlines() if l.strip()]
        is_short = len(c_strip) < 120 or len(lines_c) == 1 and len(lines_c[0]) < 80
        starts_numbered = bool(lines_c and numbered_prefix_re.match(lines_c[0]))
        if (is_short or starts_numbered) and merged_careers:
            # 如果上一条很长或上一条包含公司信息，合并到上一条
            prev = merged_careers[-1]
            # 规则：如果 prev 包含 '公司' 等关键词或长度较长，则把当前碎片附加为职责/子项目
            if re.search(r'公司|有限公司|科技|集团|股份|任职|职位', prev, re.I) or len(prev) > 200:
                merged_careers[-1] = prev.rstrip() + '\n' + c_strip
                continue
        merged_careers.append(c_strip)

    # 用合并后的列表替代
    result.careers = merged_careers

    for c in result.careers:
        item = split_career_block(c)
        if item.get('company') is None and result.careers_struct:
            prev = result.careers_struct[-1]
            # 如果当前片段有 title 且前一条没有 title，则填充为 title；否则把 title 当作一条职责插入
            if item.get('title'):
                if not prev.get('title'):
                    prev['title'] = item['title']
                else:
                    prev.setdefault('responsibilities', []).append(item['title'])
            # 合并职责
            if item.get('responsibilities'):
                prev.setdefault('responsibilities', []).extend(item.get('responsibilities'))
            # 合并 period（只有当 prev 没有 period 时才填充）
            if item.get('period') and not prev.get('period'):
                prev['period'] = item.get('period')
            # 合并技术栈并去重
            prev['technologies'] = list(dict.fromkeys((prev.get('technologies') or []) + (item.get('technologies') or [])))
        else:
            result.careers_struct.append(item)
    for e in result.education:
        result.education_struct.append({'raw': e})

    # 回退扫描：如果未识别到教育经历，从全文中查找包含学校/学院/本科/学位/培训等关键词的行
    if not result.education:
        edu_candidates = []
        lines = [ln.strip() for ln in s_clean.splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            if re.search(r'(大学|学院|学校|本科|硕士|博士|学位)', ln, re.I):
                # 合并相邻的时间/学位行
                group = ln
                if i+1 < len(lines) and re.search(r'\d{4}[\.\-年]', lines[i+1]):
                    group = group + ' ' + lines[i+1]
                edu_candidates.append(group)
        if edu_candidates:
            result.education = clean_list(edu_candidates)
            result.education_struct = [{'raw': e} for e in result.education]

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
