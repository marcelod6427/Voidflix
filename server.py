from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def hello_world():
    return render_template('base.html')

@app.route("/add", methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        return "<h1>Cadastro recebido</h1>"
    else:
        return render_template('add.html')

@app.route("/about")
def sobre():
    return render_template('about.html')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(405)
def page_not_found(error):
    return render_template('405.html'), 405
