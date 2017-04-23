# coding=utf8

from flask import Flask, abort
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


from datetime import datetime, date, timedelta
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
app.config['EXPLAIN_TEMPLATE_LOADING'] = True

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


@app.route('/latex_to_html', methods=['POST'])
@flask_login.login_required
def preprocess_latex_text():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher"
    if request.json and 'text' in request.json and request.json['text']:
        return jsonify(result=latex_to_html(request.json['text']))
    return jsonify(result='')


@app.route('/test/create/<int:group_number>/lp', methods=['GET', 'POST'])
@flask_login.login_required
def create_test_lp(group_number):
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to create tests"

    if request.method == 'POST':
        return

    max_problems_per_user = int(request.args.get('max', 5))
    current_variation = defaultdict(int)

    users = db.session.query(User.id) \
        .join(Learner, Learner.user_id == User.id) \
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id) \
        .filter(AcademicGroup.number == group_number) \
        .all()

    suggested_test_number = max((x[0] for x in db.session.query(TestLog.test_number).filter(TestLog.user.in_(map(attrgetter('id'), users))).all()), default=0) + 1

    users = {u.id: '{0} {1}'.format(u.firstname, u.lastname) for u in users}

    ignored_topic_ids = [x[0] for x in db.session.query(Topic.id).filter(Topic.topic.in_(ignored_topics)).all()]

    event_to_number = {'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3}
    trajectory_list = Trajectory.query.first().topics.split('|')
    trajectory_topics = list(set(trajectory_list))
    trajectory_list = [i for i in map(int, trajectory_list) if i not in ignored_topic_ids]
    problems_for_trajectory = Problem.query.filter(Problem.topics.in_(trajectory_topics)).all()
    problems_for_trajectory = {problem.id: problem for problem in problems_for_trajectory}
    topic_levels = {t.id: t.level for t in Topic.query.filter(Problem.id.in_(trajectory_topics)).all()}
    problem_ids = list(problems_for_trajectory.keys())

    clones = defaultdict(set)
    problems_by_topic = defaultdict(set)
    for problem_id, problem in problems_for_trajectory.items():
        problems_by_topic[int(problem.topics)].add(problem_id)
        if problem.clones and len(problem.clones) > 0:
            clones[problem_id].update(int(i) for i in problem.clones.split(','))
            for cid in clones[problem_id]:
                clones[cid].add(problem_id)

    log_info = ''

    problems_available_for_user = defaultdict(set)
    user_history = defaultdict(lambda: {i: -1 for i in problem_ids})
    num_appearances = defaultdict(int)
    exposed_problems = defaultdict(set)
    remaining_trajectory_items = dict()

    for user_id in users:
        counted_problems = set()
        problems_available_for_user[user_id] = set(problem_ids)
        user_history_items = History.query.filter(History.user == user_id, History.problem.in_(problem_ids))
        for h in user_history_items:
            if h.event in event_to_number:
                user_history[user_id][h.problem] = max(user_history[user_id][h.problem], event_to_number[h.event])
                num_appearances[h.problem] += 1
                exposed_problems[user_id].add(h.problem)
        user_remaining_trajectory_items = trajectory_list[:]
        for i, t in enumerate(user_remaining_trajectory_items):
            for problem_id in problems_by_topic[t]:
                if user_history[user_id][problem_id] >= 2 and problem_id not in counted_problems:
                    user_remaining_trajectory_items[i] = 0
                    problems_available_for_user[user_id].remove(problem_id)
                    if problem_id in clones:
                        problems_available_for_user[user_id] -= clones[problem_id]
                    break
        problems_for_user_uncovered_topics = set()
        user_remaining_trajectory_items = list(filter(None, user_remaining_trajectory_items))
        for topic_id in user_remaining_trajectory_items:
            problems_for_user_uncovered_topics.update(problems_by_topic[topic_id])
        problems_available_for_user[user_id].intersection_update(problems_for_user_uncovered_topics)
        remaining_trajectory_items[user_id] = user_remaining_trajectory_items

    penalty_for_having_same_problem_on_next_quiz = 1
    penalty_for_not_giving_a_brand_new_problem = 1
    penalty_for_giving_clone_of_exposed_problem = 1
    penalty_for_having_underflow = 1000

    lp = LpProblem(name='Test Generation', sense=LpMinimize)
    lp_objective = LpAffineExpression()

    lp_vars_user_problem = dict()
    for user_id in users:
        for problem_id in problems_available_for_user[user_id]:
            lp_vars_user_problem[(user_id, problem_id)] = LpVariable(
                name='user_problem_{}_{}'.format(user_id, problem_id), cat='Binary')

    for user_id in users:
        # Number of problems for user should definitely not exceed the maximum
        lp += (sum(lp_vars_user_problem[(user_id, problem_id)] for problem_id in
                   problems_available_for_user[user_id]) <= max_problems_per_user)
        # Number of problems for user should preferably be no less than minimum
        min_problems = min(max_problems_per_user, len(problems_available_for_user[user_id]), len(remaining_trajectory_items))
        lp_underflow_variable = LpVariable('underflow_{}'.format(user_id), lowBound=0)
        lp += (sum(lp_vars_user_problem[(user_id, problem_id)] for problem_id in
                   problems_available_for_user[user_id]) + lp_underflow_variable >= min_problems)
        lp_objective += penalty_for_having_underflow * lp_underflow_variable

    for user_id in users:
        for level in set(topic_levels.values()):
            lp_vars_levels = {level: LpVariable(name='user_level_{}_{}'.format(user_id, level), cat='Binary')}
        for level_lower, level_upper in combinations(set(topic_levels.values()), 2):
            if level_lower > level_upper:
                level_lower, level_upper = level_upper, level_lower

        for topic_id in remaining_trajectory_items[user_id]:
            problems_for_user_and_topic = problems_by_topic[topic_id] & problems_available_for_user[user_id]
            if len(problems_for_user_and_topic) >= 2:
                # The number of problems for any topic should not exceed the number
                # of times this topic appears in a trajectory
                # TODO: make it work when the number of times exceeds 2
                lp += (
                sum(lp_vars_user_problem[(user_id, problem_id)] for problem_id in problems_for_user_and_topic) <= 1)
            lp_var = LpVariable(name='gets_topic_{}_{}'.format(user_id, topic_id), cat='Binary')
            lp += (lp_var >= topic_levels[topic_id])

    for user_id in users:
        for problem_id in problems_available_for_user[user_id]:
            if problem_id in exposed_problems[user_id]:
                lp_objective += penalty_for_having_same_problem_on_next_quiz * lp_vars_user_problem[
                    (user_id, problem_id)]
            if num_appearances[problem_id] > 0:
                lp_objective += penalty_for_not_giving_a_brand_new_problem * lp_vars_user_problem[(user_id, problem_id)]
        clones_of_exposed_problems = reduce(operator_or,
                                                      (clones[problem_id] for problem_id in exposed_problems[user_id]),
                                                      set()) - exposed_problems[user_id]
        for problem_id in problems_available_for_user[user_id] & clones_of_exposed_problems:
            lp_objective += penalty_for_giving_clone_of_exposed_problem * lp_vars_user_problem[(user_id, problem_id)]

    lp.setObjective(lp_objective)

    try:
        lp.solve()
        log_info = 'Problem status is “{}” with objective function value “{}”'.format(LpStatus[lp.status],
                                                                                      lp.objective.value())
    except:
        log_info = 'Failed to solve the linear program'

    problem_sets = defaultdict(list)
    for user_id, problem_id in lp_vars_user_problem:
        if lp_vars_user_problem[(user_id, problem_id)].value() > 0:
            problem = problems_for_trajectory[problem_id]
            problem_sets[user_id].append({
                'id': problem_id,
                'text': latex_to_html(problem.statement, variation=current_variation[problem_id]),
                'level': topic_levels[int(problem.topics)]
            })

            current_variation[problem_id] += 1

    return render_template(
        'test_printout.html',
        problems=problem_sets,
        users=users,
        group=group_number,
        suggested_test_number=suggested_test_number,
        date=date.today().isoformat(),
        max_problems=max_problems_per_user,
        log_info=log_info)


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
