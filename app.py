from flask import Flask, render_template
from Source.ProgramInstance import ProgramInstance

app = Flask(__name__)


@app.route("/")
def home():
    # 每次访问主页时，创建 ProgramInstance 并执行 BeginPlay
    instance = ProgramInstance()
    instance.BeginPlay()
    return render_template("Home.html")  # 假设你的 Home.html 在 templates 目录下


if __name__ == "__main__":
    app.run(debug=True)
