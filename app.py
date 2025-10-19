from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
from werkzeug.utils import secure_filename
from Source.ProgramInstance import ProgramInstance
from Source.System.ResumeInput.ResumeInputHandler import ResumeInputHandler

app = Flask(__name__)

# upload folder
UPLOAD_DIR = os.path.join("Saved", "Uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.route("/")
def home():
    # 每次访问主页时，创建 ProgramInstance 并执行 BeginPlay
    instance = ProgramInstance()
    instance.BeginPlay()
    return render_template("Home.html")  # 假设你的 Home.html 在 templates 目录下


@app.route("/ResumeInput", methods=["GET", "POST"])
def resume_input():
    allowed_ext = {".pdf", ".doc", ".docx"}

    if request.method == "POST":
        # 保存上传的单个文件（仅允许特定扩展）
        f = request.files.get("file")
        saved_paths = []
        if f and f.filename:
            _, ext = os.path.splitext(f.filename)
            if ext.lower() not in allowed_ext:
                return redirect(url_for("resume_input", error=1))
            filename = secure_filename(f.filename)
            dest = os.path.join(UPLOAD_DIR, filename)
            f.save(dest)
            saved_paths.append(dest)

        # 处理表单数据（示例）
        form = request.form.to_dict()

        handler = ResumeInputHandler()
        # 调用后端系统处理
        handler.PerformSubmit(saved_paths)

        # 重定向回 GET 并显示成功
        return redirect(url_for("resume_input", success=1))

    # GET 请求：渲染表单
    success = request.args.get("success")
    error = request.args.get("error")
    return render_template("ResumeInput/ResumeInput.html", success=success, error=error)


@app.route('/ResumeInput/ajax', methods=['POST'])
def resume_input_ajax():
    """AJAX 端点：接收文件和表单字段，保存文件并调用 PerformSubmit，返回 JSON。"""
    try:
        allowed_ext = {'.pdf', '.doc', '.docx'}
        files = request.files.getlist('file')
        saved_paths = []
        saved_names = []
        import uuid
        for f in files:
            if not f or not f.filename:
                continue
            _, ext = os.path.splitext(f.filename)
            if ext.lower() not in allowed_ext:
                return jsonify(ok=False, error='bad_extension'), 400
            short_name = secure_filename(f.filename)
            saved_name = f"{uuid.uuid4().hex}_{short_name}"
            dest = os.path.join(UPLOAD_DIR, saved_name)
            try:
                f.save(dest)
            except Exception:
                app.logger.exception('Failed to save ajax-uploaded file')
                return jsonify(ok=False, error='save_failed'), 500
            saved_paths.append(dest)
            saved_names.append(short_name)

        form = request.form.to_dict()
        handler = ResumeInputHandler()
        texts = []
        print(f"[ResumeInput]拖拽简历 saved_paths: {saved_paths}")
        try:
            if hasattr(handler, 'PerformDragResume'):
                txt = handler.PerformDragResume(saved_paths[0])
                texts.append(txt)
        except Exception:
            app.logger.exception('Error while performing drag resume')
            texts.append(None)

        return jsonify(ok=True, filenames=saved_names, texts=texts)
    except Exception:
        app.logger.exception('Unhandled exception in resume_input_ajax')
        return jsonify(ok=False, error='internal_error'), 500


if __name__ == "__main__":
    app.run(debug=True)
