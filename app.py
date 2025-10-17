from flask import Flask, render_template
from Source.ProgramInstance import ProgramInstance
from Source.System.ResumeInput.ResumeInputSystem import ResumeInputSystem

app = Flask(__name__)


@app.route("/")
def home():
    # 每次访问主页时，创建 ProgramInstance 并执行 BeginPlay
    instance = ProgramInstance()
    instance.BeginPlay()
    return render_template("Home.html")  # 假设你的 Home.html 在 templates 目录下

@app.route("/ResumeInput")
def resume_input():
    # 每次访问简历录入页面时，创建 ResumeInputSystem 并执行 BeginPlay
    resumeInputSystem = ResumeInputSystem()
    resumeInputSystem.BeginPlay()
    return render_template("ResumeInput/ResumeInput.html")  # 使用 templates/ResumeInput/ResumeInput.html


if __name__ == "__main__":
    app.run(debug=True)