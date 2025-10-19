import os
from Source.Utils.ResumeParseUtils import ResumeParse, ResumeParseResult

class ResumeInputHandler:
    # 处理拖拽上传的简历
    def PerformDragResume(self, file_path):
        """尝试从 file_path 中提取文本（支持 .pdf 和 .docx），返回提取的字符串。
        若无法提取则返回文件名或错误信息。"""
        print(f"Processing dragged resume: {file_path}")
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        text = ''
        extraction_error = None
        try:
            if ext == '.docx':
                try:
                    import docx
                except Exception:
                    extraction_error = f"missing_python_docx: {os.path.basename(file_path)}"
                else:
                    doc = docx.Document(file_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text]
                    text = '\n'.join(paragraphs)
            elif ext == '.pdf':
                try:
                    import PyPDF2
                except Exception:
                    extraction_error = f"missing_pypdf2: {os.path.basename(file_path)}"
                else:
                    with open(file_path, 'rb') as fh:
                        reader = PyPDF2.PdfReader(fh)
                        parts = []
                        for page in reader.pages:
                            parts.append(page.extract_text() or '')
                        text = '\n'.join(parts)
            else:
                extraction_error = f"unsupported_type: {os.path.basename(file_path)}"
        except Exception as e:
            extraction_error = f"parse_exception: {str(e)}"

        print(f"[ResumeInput]执行简历拖拽，text: {text[:30]}... error={extraction_error}")
        # 始终返回 ResumeParse 的结构化结果；若提取出错，在返回值中附加 error 字段
        try:
            parsed = ResumeParse(text)
        except Exception as e:
            parsed = {"name": None, "age": None, "phone": None, "projects": [], "education": [], "error": f"parse_failed: {str(e)}"}

        if extraction_error:
            parsed['error'] = extraction_error

        return parsed

    # 处理表单提交
    def PerformSubmit(self, file_path):
        print(f"Processing submission with file: {file_path}")
        