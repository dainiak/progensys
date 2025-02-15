from os import environ

from flask import Flask
from flask import render_template, request, redirect, url_for

from flask_mail import Mail, Message
from hashlib import md5 as md5hasher

from blueprints.models import db, User

from blueprints.problems import problems_blueprint
from blueprints.problem_set import problem_set_blueprint
from blueprints.courses import courses_blueprint
from blueprints.users import users_blueprint
from blueprints.exposures import exposures_blueprint
from blueprints.grading import grading_blueprint
from blueprints.trajectory import trajectory_blueprint
from blueprints.learner_dashboard import learner_dashboard_blueprint
from blueprints.solution_reviews import solution_reviews_blueprint
from blueprints.topics import topics_blueprint
from blueprints.finals import finals_blueprint

from blueprints.autocompletion import autocompletion_blueprint

from blueprints.admin_tools import admin_tools_blueprint

import flask_login
from os import environ

app_secret_key = environ.get('APP_SECRET_KEY')
debug_mode = environ.get('DEBUG_MODE')
sqlalchemy_db_uri = environ.get('SQLALCHEMY_DATABASE_URI')
mail_server = environ.get('MAIL_SERVER')
mail_port = environ.get('MAIL_PORT')
mail_username = environ.get('MAIL_USERNAME')
mail_password = environ.get('MAIL_PASSWORD')
mail_default_sender = environ.get('MAIL_DEFAULT_SENDER')


def parse_person_name(name):
    tokens = name.strip().split()
    if len(tokens) == 2:
        return tokens[0], tokens[1], None
    if len(tokens) == 1:
        return tokens[0], None, None
    if tokens[1][-3:] in ["вна", "вич"]:
        return tokens[0], tokens[2], tokens[1]
    return tokens[1], tokens[0], tokens[2]


app = Flask(__name__)
app.register_blueprint(autocompletion_blueprint)
app.register_blueprint(problems_blueprint)
app.register_blueprint(problem_set_blueprint)
app.register_blueprint(courses_blueprint)
app.register_blueprint(users_blueprint)
app.register_blueprint(exposures_blueprint)
app.register_blueprint(grading_blueprint)
app.register_blueprint(trajectory_blueprint)
app.register_blueprint(learner_dashboard_blueprint)
app.register_blueprint(solution_reviews_blueprint)
app.register_blueprint(topics_blueprint)
app.register_blueprint(finals_blueprint)

app.register_blueprint(admin_tools_blueprint)

app.secret_key = app_secret_key

app.config["SQLALCHEMY_DATABASE_URI"] = sqlalchemy_db_uri
app.config["SQLALCHEMY_POOL_RECYCLE"] = 280
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["MAIL_SERVER"] = mail_server
app.config["MAIL_PORT"] = mail_port
app.config["MAIL_USERNAME"] = mail_username
app.config["MAIL_PASSWORD"] = mail_password
app.config["MAIL_DEFAULT_SENDER"] = mail_default_sender
app.config["MAIL_USE_SSL"] = True

app.debug = debug_mode
db.init_app(app)


mail = Mail(app)
app.config["MAILER"] = mail

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


def md5(s):
    m = md5hasher()
    m.update(s.encode())
    return m.hexdigest()


@login_manager.user_loader
def user_loader(user_id):
    return User.query.filter_by(id=user_id).first()


@login_manager.request_loader
def request_loader(req):
    user = User.query.filter_by(username=req.form.get("username")).first()
    if user is None:
        return

    if "pw" in request.form and hasattr(user, "password_hash") and md5(request.form["pw"]) == user.password_hash:
        user.is_authenticated = True
    else:
        user.is_authenticated = False

    return user


def notify_user(user_id, subject, body):
    user = User.query.filter_by(id=user_id).first()
    if not user.email:
        return
    msg = Message(
        subject="Курс «Дискретные структуры»: {}".format(subject),
        body="Здравствуйте, {}!\n{}".format(user.firstname, body),
        recipients=[user.email],
    )
    mail.send(msg)


# ------------------------------------------
# Authorization and landing
# ------------------------------------------
@app.route("/")
def root():
    if not flask_login.current_user or not hasattr(flask_login.current_user, "username"):
        return redirect("/login")
    elif flask_login.current_user.current_course_id:
        return redirect("/course-{}".format(flask_login.current_user.current_course_id))
    else:
        return redirect("/courses")


@app.route("/login", methods=["GET"])
def login():
    already_logged = False
    login_successful = False
    bad_login = False
    username = False
    if request.method == "GET":
        if flask_login.current_user is not None and hasattr(flask_login.current_user, "username"):
            already_logged = True
            username = flask_login.current_user.username
        return render_template(
            "login.html",
            already_logged=already_logged,
            login_successful=login_successful,
            bad_login=bad_login,
            username=username,
        )


@app.route("/logout")
def logout():
    flask_login.logout_user()
    return redirect(url_for("login"))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run()
