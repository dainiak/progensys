# coding=utf8

from flask import Flask
from flask import render_template, request, redirect, url_for, jsonify

from flask_mail import Mail, Message

from blueprints.models import db, Problem, Topic, User, Trajectory, History

from blueprints.problems import problems_blueprint
from blueprints.courses import courses_blueprint
from blueprints.users import users_blueprint
from blueprints.exposures import exposures_blueprint
from blueprints.grading import grading_blueprint
from blueprints.trajectory import trajectory_blueprint
from blueprints.autocompletion import autocompletion_blueprint

from collections import defaultdict

import flask_login
from pulp import LpProblem, LpVariable, LpAffineExpression, LpMinimize, LpStatus
from operator import attrgetter
from operator import or_ as operator_or
from itertools import combinations
from functools import reduce

# Security sensitive constants are imported from a file not being synced with github
from tpbeta_security import *

from text_tools import *


def parse_person_name(name):
    tokens = name.strip().split()
    if len(tokens) == 2:
        return tokens[0], tokens[1], None
    if len(tokens) == 1:
        return tokens[0], None, None
    if tokens[1][-3:] in ['вна', 'вич']:
        return tokens[0], tokens[2], tokens[1]
    return tokens[1], tokens[0], tokens[2]


app = Flask(__name__)
app.register_blueprint(autocompletion_blueprint)
app.register_blueprint(problems_blueprint)
app.register_blueprint(courses_blueprint)
app.register_blueprint(users_blueprint)
app.register_blueprint(exposures_blueprint)
app.register_blueprint(grading_blueprint)
app.register_blueprint(trajectory_blueprint)

app.secret_key = tpbeta_app_secret_key

app.config['SQLALCHEMY_DATABASE_URI'] = tpbeta_sqlalchemy_db_uri
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = tpbeta_mail_server
app.config['MAIL_PORT'] = tpbeta_mail_port
app.config['MAIL_USERNAME'] = tpbeta_mail_username
app.config['MAIL_PASSWORD'] = tpbeta_mail_password
app.config['MAIL_DEFAULT_SENDER'] = tpbeta_mail_default_sender
app.config['MAIL_USE_SSL'] = True

app.debug = True
db.init_app(app)


mail = Mail(app)
app.config['MAILER'] = mail

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def user_loader(user_id):
    return User.query.filter_by(id=user_id).first()

#
# @login_manager.request_loader
# def request_loader(req):
#     user = User.query.filter_by(username=req.form.get('username')).first()
#     if user is None:
#         return
#
#     if 'pw' in request.form and hasattr(user, 'password_hash') and md5(request.form['pw']) == user.password_hash:
#         user.is_authenticated = True
#     else:
#         user.is_authenticated = False
#
#     return user


def notify_user(user_id, subject, body):
    user_data = User.query.filter_by(id=user_id).first()
    if not user_data.email:
        return
    msg = Message(subject='Курс ДС: {}'.format(subject),
                  body='Здравствуйте, {}!\n{}'.format(user_data.firstname, body),
                  recipients=[user_data.email])
    mail.send(msg)


# ------------------------------------------
# Authorization and landing
# ------------------------------------------
@app.route('/')
def root():
    if not flask_login.current_user or not hasattr(flask_login.current_user, 'username'):
        return redirect('/login')
    elif flask_login.current_user.current_course_id:
        return redirect('/course-{}'.format(flask_login.current_user.current_course_id))
    else:
        return redirect('/courses')


@app.route('/login', methods=['GET'])
def login():
    already_logged = False
    login_successful = False
    bad_login = False
    username = False
    if request.method == 'GET':
        if flask_login.current_user is not None and hasattr(flask_login.current_user, 'username'):
            already_logged = True
            username = flask_login.current_user.username
        return render_template(
            'login.html',
            already_logged=already_logged,
            login_successful=login_successful,
            bad_login=bad_login,
            username=username)


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run()