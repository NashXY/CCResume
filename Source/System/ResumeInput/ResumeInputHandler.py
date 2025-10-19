import os

class ResumeInputHandler:
    # 处理拖拽上传的简历
    def PerformDragResume(self, file_path):
        """尝试从 file_path 中提取文本（支持 .pdf 和 .docx），返回提取的字符串。
        若无法提取则返回文件名或错误信息。"""
        print(f"Processing dragged resume: {file_path}")
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        text = ''
        try:
            if ext == '.docx':
                try:
                    import docx
                except Exception:
                    return f"(无法解析 .docx：缺少 python-docx 库) {os.path.basename(file_path)}"
                doc = docx.Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text]
                text = '\n'.join(paragraphs)
            elif ext == '.pdf':
                try:
                    import PyPDF2
                except Exception:
                    return f"(无法解析 .pdf：缺少 PyPDF2 库) {os.path.basename(file_path)}"
                with open(file_path, 'rb') as fh:
                    reader = PyPDF2.PdfReader(fh)
                    parts = []
                    for page in reader.pages:
                        parts.append(page.extract_text() or '')
                    text = '\n'.join(parts)
            else:
                return f"(不支持的文件类型) {os.path.basename(file_path)}"
        except Exception as e:
            return f"(解析出错) {str(e)}"
        print(f"[ResumeInput]执行简历拖拽，text: {text[:30]}...")
        return text or f"(未能提取文本) {os.path.basename(file_path)}"

    # 处理表单提交
    def PerformSubmit(self, file_path):
        print(f"Processing submission with file: {file_path}")
