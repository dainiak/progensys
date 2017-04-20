# coding=utf8
# TODO: rights checking

from flask import Flask, abort
from flask_api import status as http_status_codes
from flask import render_template, request, redirect, url_for, jsonify

from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
from collections import defaultdict
import random
import flask_login
from pulp import LpProblem, LpVariable, LpAffineExpression, LpMinimize, LpStatus
from operator import attrgetter
from operator import or_ as operator_or
from itertools import combinations
from functools import reduce
from hashlib import md5 as md5hasher

from json import dumps as to_json_string
# from json import loads as from_json_string


# Security sensitive constants are imported from a file not being synced with github
from tpbeta_security import *

from text_tools import *


def md5(s):
    m = md5hasher()
    m.update(s.encode())
    return m.hexdigest()


ignored_topics = ['STEPIC_REVISION_SUMPROD', 'STEPIC_REVISION_ROUNDING', 'PIGEONHOLE', 'INDUCTION', 'ENUMERATION',
                  'SUMS_OF_BINOMIALS', 'DOUBLE_COUNT', 'GRAPHS_ISOMORPHIC', 'GRAPHS_COUNTING_ISOMORPHIC',
                  'GRAPHS_TREES_AND_FORESTS', 'GRAPHS_PRUFER', 'GRAPHS_METRICS', 'GRAPHS_PLANARITY',
                  'GRAPHS_GREEDY_ALGORITHM', 'GRAPHS_PIGEONHOLE', 'GRAPHS_ADVANCED',
                  'GRAPHS_COLORINGS_ADVANCED', 'GRAPHS_EULERIAN', 'GRAPHS_DEBRUIJN',
                  'GRAPHS_HAMILTONIAN', 'NUMBER_THEORY_LINEAR_EQUATIONS', 'NUMBER_THEORY_LINEAR_EQUATIONS_ADVANCED',
                  'NUMBER_THEORY_CHINESE_REMAINDER_THEOREM', 'INCLEXCL', 'POTENTIALS', 'ENUMERATION_ADVANCED',
                  'SUM_OF_BINOMALS_ADVANCED', 'NUMBER_THEORY_EULER_FERMAT_THEOREM', 'GRAPHS_MATCHINGS',
                  'NUMBER_THEORY_PRIMITIVE_ROOTS', 'GRAPHS_HAMILTONIAN_ADVANCED', 'GRAPHS_MATCHINGS_ADVANCED',
                  'NUMBER_THEORY_PRIMITIVE_ROOTS_ADVANCED', 'NUMBER_THEORY_INDEXES']


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
db = SQLAlchemy(app)
mail = Mail(app)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


class User(db.Model, flask_login.UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password_hash = db.Column(db.String(32))
    name_first = db.Column(db.Unicode(80))
    name_last = db.Column(db.Unicode(80))
    name_middle = db.Column(db.Unicode(80))
    email = db.Column(db.Unicode(80))
    current_course_id = 0

    def __repr__(self):
        return '<User {0}>'.format(self.username)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText, nullable=False)
    description = db.Column(db.UnicodeText)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True)
    title = db.Column(db.UnicodeText)
    description = db.Column(db.UnicodeText)

    def __init__(self, code):
        self.code = code


class Participant(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)

    def __init__(self, user_id, course_id, role_id):
        self.user_id = user_id
        self.course_id = course_id
        self.role_id = role_id


class ParticipantExtraInfo(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    json = db.Column(db.UnicodeText)

    def __init__(self, user_id, course_id, json):
        self.user_id = user_id
        self.course_id = course_id
        self.json = json


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100))
    title = db.Column(db.UnicodeText)
    suggested_role = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)
    suggested_course = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)


class GroupMembership(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), primary_key=True)
    suggested_course = db.Column(db.Integer, db.ForeignKey('course.id'))

    def __init__(self, user_id, group_id):
        self.user_id = user_id
        self.group_id = group_id


class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    statement = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp_created = db.Column(db.DateTime)
    timestamp_last_modified = db.Column(db.DateTime)


class ProblemRelation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    to_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('problem_relation_type.id'), nullable=False)
    weight = db.Column(db.Float)

    def __init__(self, from_id, to_id, relation_type_id, weight=1.0):
        self.from_id = from_id
        self.to_id = to_id
        self.type_id = relation_type_id
        self.weight = weight


class ProblemRelationType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True)
    description = db.Column(db.UnicodeText)


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100))
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)


class TopicLevelAssignment(db.Model):
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    level = db.Column(db.Integer, nullable=False)

    def __init__(self, course_id, topic_id, level):
        self.course_id = course_id
        self.topic_id = topic_id
        self.level = level


class ProblemTopicAssignment(db.Model):
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    weight = db.Column(db.Float)

    def __init__(self, problem_id, topic_id, weight=1.0):
        self.problem_id = problem_id
        self.topic_id = topic_id
        self.weight = weight


class Concept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    description = db.Column(db.UnicodeText)


class ProblemConceptAssignment(db.Model):
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    concept_id = db.Column(db.Integer, db.ForeignKey('concept.id'), primary_key=True)
    weight = db.Column(db.Float)

    def __init__(self, problem_id, concept_id, weight=1):
        self.problem_id = problem_id
        self.concept_id = concept_id
        self.weight = weight


class ProblemSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_adhoc = db.Column(db.Boolean)
    timestamp_created = db.Column(db.DateTime)
    timestamp_last_modified = db.Column(db.DateTime)


class ProblemSetContent(db.Model):
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'), primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    sort_key = db.Column(db.Integer)

    def __init__(self, problem_set_id, problem_id, sort_key=0):
        self.problem_id = problem_id
        self.problem_set_id = problem_set_id
        self.sort_key = sort_key


class ProblemSetExtra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'))
    content = db.Column(db.UnicodeText)
    sort_key = db.Column(db.Integer)


class Exposure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)


class ExposureContent(db.Model):
    exposure_id = db.Column(db.Integer, db.ForeignKey('exposure.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'), primary_key=True)
    sort_key = db.Column(db.Integer)

    def __init__(self, exposure_id, user_id, problem_set_id, sort_key=0):
        self.exposure_id = exposure_id
        self.user_id = user_id
        self.problem_set_id = problem_set_id
        self.sort_key = sort_key


class ExposureGrading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exposure_id = db.Column(db.Integer, db.ForeignKey('exposure.id'), nullable=False)
    grader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime)
    comment = db.Column(db.UnicodeText)
    feedback = db.Column(db.UnicodeText)

    def __init__(self, exposure_id, grader_id):
        self.exposure_id = exposure_id
        self.grader_id = grader_id


class ExposureGradingResult(db.Model):
    exposure_grading_id = db.Column(db.Integer, db.ForeignKey('exposure_grading.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'), primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    problem_status_id = db.Column(db.Integer, db.ForeignKey('problem_status_info.id'), nullable=False)
    comment = db.Column(db.UnicodeText)
    feedback = db.Column(db.UnicodeText)

    def __init__(self, exposure_grading_id, user_id, problem_set_id, problem_id, problem_status_id):
        self.exposure_grading_id = exposure_grading_id
        self.user_id = user_id
        self.problem_set_id = problem_set_id
        self.problem_id = problem_id
        self.problem_status_id = problem_status_id


class Trajectory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    suggested_course_id = db.Column(db.Integer, db.ForeignKey('course.id'))


class TrajectoryContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trajectory_id = db.Column(db.Integer, db.ForeignKey('trajectory.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    sort_key = db.Column(db.Integer)

    def __init__(self, trajectory_id, topic_id, sort_key=None):
        self.trajectory_id = trajectory_id
        self.topic_id = topic_id
        if sort_key is not None:
            self.sort_key = sort_key


class ProblemStatus(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    status_id = db.Column(db.Integer, db.ForeignKey('problem_status_info.id'), nullable=False)
    timestamp_last_changed = db.Column(db.DateTime)

    def __init__(self, user_id, problem_id, status_id):
        self.user_id = user_id
        self.problem_id = problem_id
        self.status_id = status_id


class ProblemStatusInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True)
    title = db.Column(db.UnicodeText)
    icon = db.Column(db.Unicode(100), unique=True)
    description = db.Column(db.UnicodeText)

    def __init__(self, code, title, icon, description=''):
        self.code = code
        self.title = title
        self.icon = icon
        self.description = description


class ProblemSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    statement = db.Column(db.UnicodeText, nullable=False)
    comment = db.Column(db.UnicodeText)


class ProblemComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    content = db.Column(db.UnicodeText)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    in_reply_to = db.Column(db.Integer, db.ForeignKey('problem_comment.id'))


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'))
    event = db.Column(db.Text)
    comment = db.Column(db.UnicodeText)


@login_manager.user_loader
def user_loader(user_id):
    return User.query.filter_by(id=user_id).first()


@login_manager.request_loader
def request_loader(req):
    user = User.query.filter_by(username=req.form.get('username')).first()
    if user is None:
        return

    if 'pw' in request.form and hasattr(user, 'password_hash') and md5(request.form['pw']) == user.password_hash:
        user.is_authenticated = True
    else:
        user.is_authenticated = False

    return user


@app.route('/users', methods=['GET'])
@flask_login.login_required
def user_management_view():
    if flask_login.current_user.username == tpbeta_superuser_username:
        return render_template('view_users.html')


@app.route('/api/user', methods=['POST'])
@flask_login.login_required
def api_user_management():
    if flask_login.current_user.username != tpbeta_superuser_username:
        return None

    json = request.get_json()
    if json and 'action' in json:
        if json['action'] == 'load':
            query = User.query

            if json.get('filter'):
                frontend_filter = json['filter']
                if frontend_filter.get('username'):
                    query = query.filter(User.username.like('%' + frontend_filter['username'] + '%'))
                if frontend_filter.get('name_last'):
                    query = query.filter(User.name_last.like('%' + frontend_filter['name_last'] + '%'))
                if frontend_filter.get('name_first'):
                    query = query.filter(User.name_first.like('%' + frontend_filter['name_first'] + '%'))
                if frontend_filter.get('name_middle'):
                    query = query.filter(User.name_middle.like('%' + frontend_filter['name_middle'] + '%'))
                if frontend_filter.get('email'):
                    query = query.filter(User.email.like('%' + frontend_filter['email'] + '%'))

            users = query.limit(100).all()

            return jsonify(list({
                'id': u.id,
                'username': u.username,
                'name_first': u.name_first,
                'name_last': u.name_last,
                'name_middle': u.name_middle,
                'email': u.email
            } for u in users))
        elif json['action'] == 'update':
            changed = False
            if not json.get('item'):
                return jsonify(error='No item specified')
            item = json['item']
            if not item.get('id'):
                return jsonify(error='No ID specified')
            user = User.query.filter_by(id=item['id']).first()
            if not user:
                return jsonify(error='User with this id not found')
            if 'name_first' in item and item['name_first'] != user.name_first:
                changed = True
                user.name_first = item['name_first']
            if 'name_last' in item and item['name_last'] != user.name_middle:
                changed = True
                user.name_last = item['name_last']
            if 'name_middle' in item and item['name_middle'] != user.name_middle:
                changed = True
                user.name_middle = item['name_middle']
            if 'username' in item and item['username'] and item['username'] != user.username:
                if db.session.query(db.exists().where(User.username == item['username'])).scalar():
                    if changed:
                        db.session.commit()
                    return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                                    'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
                changed = True
                user.username = item['username']

            if 'email' in item and item['email'] and item['email'] != user.email:
                if db.session.query(db.exists().where(User.email == item['email'])).scalar():
                    if changed:
                        db.session.commit()
                    return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                                    'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
                changed = True
                user.email = item['email']

            if changed:
                db.session.commit()
            return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                            'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
        elif json['action'] == 'insert':
            if not json.get('item'):
                return jsonify(error='No item specified')

            item = json['item']
            user = User()
            user.name_first = item.get('name_first', '')
            user.name_last = item.get('name_last', '')
            user.name_middle = item.get('name_middle', '')

            if not item.get('username'):
                return jsonify(error="Username not specified")
            if db.session.query(db.exists().where(User.username == item['username'])).scalar():
                return jsonify(error="Username already exists")
            user.username = item['username']

            if not item.get('email'):
                return jsonify(error="Email not specified")
            if db.session.query(db.exists().where(User.username == item['email'])).scalar():
                return jsonify(error="Email already exists")
            user.email = item['email']

            db.session.commit()
            return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                            'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
        elif json['action'] == 'delete':
            if not json.get('item'):
                return jsonify(error='No item specified')
            item = json['item']
            if not item.get('id'):
                return jsonify(error='No ID specified')
            user = User.query.filter_by(id=item['id']).first()
            if not user:
                return jsonify(error='User with this id not found')

            db.session.query(
                ExposureContent
            ).filter(
                ExposureContent.user_id == user.id
            ).delete()

            db.session.query(
                Participant
            ).filter(
                Participant.user_id == user.id
            ).delete()

            db.session.query(
                GroupMembership
            ).filter(
                GroupMembership.user_id == user.id
            ).delete()

            db.session.query(
                ProblemStatus
            ).filter(
                ProblemStatus.user_id == user.id
            ).delete()

            db.session.delete(user)
            db.session.commit()
            return jsonify(result='Success')

    abort(400, 'Action not supported')


# ------------------------------------------
# Exposure view and API
# ------------------------------------------
@app.route('/api/exposure', methods=['POST'])
@flask_login.login_required
def api_exposure():
    if flask_login.current_user.username not in tpbeta_teacher_usernames:
        return "Login required for this URL"

    json = request.get_json()
    if not json or 'action' not in json:
        return jsonify(error='Expected JSON format and action')

    if json['action'] == 'load':
        if not json.get('user_ids'):
            return jsonify(error='User IDs not specified')
        if not json.get('exposure_ids'):
            return jsonify(error='Exposure IDs not specified')

        exposure_ids = json.get('exposure_ids')
        user_ids = json.get('user_ids')
        db_data = db.session.query(
            User.name_last,
            User.name_first,
            User.id,
            Exposure.timestamp,
            Exposure.id,
            ExposureContent.problem_set_id
        ).filter(
            User.id.in_(user_ids),
            Exposure.id.in_(exposure_ids),
            ExposureContent.user_id == User.id,
            ExposureContent.exposure_id == Exposure.id
        ).all()
        data_for_frontend = []

        for user_name_last, \
            user_name_first, \
            user_id, \
            exposure_timestamp, \
            exposure_id, \
            problem_set_id \
                in db_data:
            data_for_frontend.append(dict())
            data_for_frontend[-1]['user_id'] = user_id
            data_for_frontend[-1]['exposure_id'] = exposure_id
            data_for_frontend[-1]['problem_set_id'] = problem_set_id
            data_for_frontend[-1]['exposure_date'] = exposure_timestamp.isoformat()[:10]
            data_for_frontend[-1]['learner_name'] = '{} {}'.format(user_name_last, user_name_first)
            problem_ids = list(map(
                lambda x: x[0],
                db.session.query(
                    ProblemSetContent.problem_id
                ).filter(
                    ProblemSetContent.problem_set_id == problem_set_id
                ).order_by(
                    ProblemSetContent.sort_key
                ).all()))
            graded_problems = db.session.query(
                ExposureGradingResult.problem_id,
                ExposureGradingResult.problem_status_id
            ).filter(
                ExposureGrading.exposure_id == exposure_id,
                ExposureGradingResult.exposure_grading_id == ExposureGrading.id,
                ExposureGradingResult.user_id == user_id,
                ExposureGradingResult.problem_set_id == problem_set_id
            ).all()
            graded_problems = {p[0]: p[1] for p in graded_problems}

            for problem_position, problem_id in enumerate(problem_ids):
                problem_position += 1
                data_for_frontend[-1]['p{}'.format(problem_position)] = graded_problems.get(
                    problem_id,
                    -problem_id
                )
                data_for_frontend[-1]['pid{}'.format(problem_position)] = problem_id

        return jsonify(data_for_frontend)

    elif json['action'] == 'delete':
        item = json.get('item')
        if not item:
            return jsonify(error='No data provided for storing the grading results')
        user_id = item.get('user_id')
        exposure_id = item.get('exposure_id')
        problem_set_id = item.get('problem_set_id')
        if None in [user_id, exposure_id, problem_set_id]:
            return jsonify(error='Data required for deleting exposure record was not provided')
        exposure_record = ExposureContent.query.filter_by(
            exposure_id=exposure_id,
            user_id=user_id,
            problem_set_id=problem_set_id
        ).first()
        if not exposure_record:
            return jsonify(error='The specified exposure record was not found')
        db.session.delete(exposure_record)
        db.session.commit()
        result_report = 'Deleted the exposure record.'
        problem_set = ProblemSet.query.filter_by(id=problem_set_id).first()
        if (problem_set.is_adhoc and not db.session.query(
                    ExposureContent.id
                ).filter(
                    ExposureContent.problem_set_id == problem_set_id
                ).first()):
            db.session.delete(problem_set)
            db.session.commit()
            result_report += ' The problem set was ad hoc and not used elsewhere, so deleted it too.'
        return jsonify(result=result_report)

    elif json['action'] == 'update':
        item = json.get('item')
        if not item:
            return jsonify(error='No data provided for storing the grading results')
        grader_id = flask_login.current_user.id
        user_id = item.get('user_id')
        exposure_id = item.get('exposure_id')
        problem_set_id = item.get('problem_set_id')
        if None in [grader_id, user_id, exposure_id, problem_set_id]:
            return jsonify(error='Data required for storing the grading result was not provided')

        grading = ExposureGrading.query.filter_by(grader_id=grader_id, exposure_id=exposure_id).first()
        if not grading:
            grading = ExposureGrading(exposure_id, grader_id)
            grading.timestamp = datetime.now()
            db.session.add(grading)
            db.session.commit()
            grading = ExposureGrading.query.filter_by(grader_id=grader_id, exposure_id=exposure_id).first()

        existing_grading_results = ExposureGradingResult.query.filter_by(
            exposure_grading_id=grading.id,
            user_id=user_id,
            problem_set_id=problem_set_id
        ).all()
        existing_grading_results = {egc.problem_id: egc for egc in existing_grading_results}

        for field_name in item:
            if field_name.startswith('pid'):
                problem_no = field_name[len('pid'):]
                problem_id = int(item[field_name])
                problem_status_id = item.get('p{}'.format(problem_no))
                if problem_status_id >= 0:
                    if problem_id in existing_grading_results:
                        existing_grading_results[problem_id].problem_status_id = problem_status_id
                    else:
                        grading_result = ExposureGradingResult(
                            grading.id,
                            user_id,
                            problem_set_id,
                            problem_id,
                            problem_status_id
                        )
                        db.session.add(grading_result)
                else:
                    item['p{}'.format(problem_no)] = -problem_id

        db.session.commit()
        return jsonify(item)


@app.route('/exposure/date-<exposure_date>', methods=['GET'])
@flask_login.login_required
def view_exposure_table(exposure_date):
    if flask_login.current_user.username not in tpbeta_teacher_usernames:
        return "Login required for this URL"

    exposures = Exposure.query.all()
    exposure_ids = list(map(
        attrgetter('id'),
        filter(lambda x: x.timestamp.isoformat()[:10] == exposure_date, exposures)
    ))
    if len(exposure_ids) == 0:
        return jsonify(error='No exposures with specified date were found')

    user_ids = list(map(lambda x: x[0], db.session.query(User.id).all()))

    all_problems = list(map(
        lambda x: x[0],
        db.session.query(
            Problem.id
        ).filter(
            ExposureContent.problem_set_id == ProblemSetContent.problem_set_id,
            Problem.id == ProblemSetContent.problem_id,
            ExposureContent.exposure_id.in_(exposure_ids),
            ExposureContent.user_id.in_(user_ids)
        ).all()))
    problem_statuses = [{'name': ps.icon, 'id': ps.id} for ps in ProblemStatusInfo.query.all()]

    return render_template(
        'view_exposures.html',
        all_problems=to_json_string(all_problems),
        exposure_ids=to_json_string(exposure_ids),
        user_ids=to_json_string(user_ids),
        problem_statuses=to_json_string(problem_statuses)
    )


# ------------------------------------------
# Grading view and API
# ------------------------------------------
@app.route('/api/grading', methods=['POST'])
@flask_login.login_required
def api_grading():
    if flask_login.current_user.username not in tpbeta_teacher_usernames:
        return "Login required for this URL"

    json = request.get_json()
    if not json or 'action' not in json:
        return jsonify(error='Expected JSON format and action')

    if json['action'] == 'load':
        if not json.get('user_ids'):
            return jsonify(error='User IDs not specified')
        if not json.get('exposure_ids'):
            return jsonify(error='Exposure IDs not specified')

        exposure_ids = json.get('exposure_ids')
        user_ids = json.get('user_ids')
        db_data = db.session.query(
            User.name_last,
            User.name_first,
            User.id,
            Exposure.timestamp,
            Exposure.id,
            ExposureContent.problem_set_id
        ).filter(
            User.id.in_(user_ids),
            Exposure.id.in_(exposure_ids),
            ExposureContent.user_id == User.id,
            ExposureContent.exposure_id == Exposure.id
        ).all()
        data_for_frontend = []

        for user_name_last, \
            user_name_first, \
            user_id, \
            exposure_timestamp, \
            exposure_id, \
            problem_set_id \
                in db_data:
            data_for_frontend.append(dict())
            data_for_frontend[-1]['user_id'] = user_id
            data_for_frontend[-1]['exposure_id'] = exposure_id
            data_for_frontend[-1]['problem_set_id'] = problem_set_id
            data_for_frontend[-1]['exposure_date'] = exposure_timestamp.isoformat()[:10]
            data_for_frontend[-1]['learner_name'] = '{} {}'.format(user_name_last, user_name_first)
            problem_ids = list(map(
                lambda x: x[0],
                db.session.query(
                    ProblemSetContent.problem_id
                ).filter(
                    ProblemSetContent.problem_set_id == problem_set_id
                ).order_by(
                    ProblemSetContent.sort_key
                ).all()))
            graded_problems = db.session.query(
                ExposureGradingResult.problem_id,
                ExposureGradingResult.problem_status_id
            ).filter(
                ExposureGrading.exposure_id == exposure_id,
                ExposureGradingResult.exposure_grading_id == ExposureGrading.id,
                ExposureGradingResult.user_id == user_id,
                ExposureGradingResult.problem_set_id == problem_set_id
            ).all()
            graded_problems = {p[0]: p[1] for p in graded_problems}

            for problem_position, problem_id in enumerate(problem_ids):
                problem_position += 1
                data_for_frontend[-1]['p{}'.format(problem_position)] = graded_problems.get(
                    problem_id,
                    -problem_id
                )
                data_for_frontend[-1]['pid{}'.format(problem_position)] = problem_id

        return jsonify(data_for_frontend)

    elif json['action'] == 'update':
        item = json.get('item')
        if not item:
            return jsonify(error='No data provided for storing the grading results')
        grader_id = flask_login.current_user.id
        user_id = item.get('user_id')
        exposure_id = item.get('exposure_id')
        problem_set_id = item.get('problem_set_id')
        if None in [grader_id, user_id, exposure_id, problem_set_id]:
            return jsonify(error='Data required for storing the grading result was not provided')

        grading = ExposureGrading.query.filter_by(grader_id=grader_id, exposure_id=exposure_id).first()
        if not grading:
            grading = ExposureGrading(exposure_id, grader_id)
            grading.timestamp = datetime.now()
            db.session.add(grading)
            db.session.commit()
            grading = ExposureGrading.query.filter_by(grader_id=grader_id, exposure_id=exposure_id).first()

        existing_grading_results = ExposureGradingResult.query.filter_by(
            exposure_grading_id=grading.id,
            user_id=user_id,
            problem_set_id=problem_set_id
        ).all()
        existing_grading_results = {egc.problem_id: egc for egc in existing_grading_results}

        for field_name in item:
            if field_name.startswith('pid'):
                problem_no = field_name[len('pid'):]
                problem_id = int(item[field_name])
                problem_status_id = item.get('p{}'.format(problem_no))
                if problem_status_id >= 0:
                    if problem_id in existing_grading_results:
                        existing_grading_results[problem_id].problem_status_id = problem_status_id
                    else:
                        grading_result = ExposureGradingResult(
                            grading.id,
                            user_id,
                            problem_set_id,
                            problem_id,
                            problem_status_id
                        )
                        db.session.add(grading_result)
                else:
                    item['p{}'.format(problem_no)] = -problem_id

        db.session.commit()
        return jsonify(item)


@app.route('/grading/date-<exposure_date>/group-<group>', methods=['GET'])
@app.route('/grading/date-<exposure_date>', methods=['GET'])
@flask_login.login_required
def view_grading_table(exposure_date, group=None):
    if flask_login.current_user.username not in tpbeta_teacher_usernames:
        return "Login required for this URL"

    if group is not None and not db.session.query(db.exists().where(Group.code == group)).scalar():
        return jsonify(error='Group not found')

    exposures = Exposure.query.all()
    exposure_ids = list(map(
        attrgetter('id'),
        filter(lambda x: x.timestamp.isoformat()[:10] == exposure_date, exposures)
    ))
    if len(exposure_ids) == 0:
        return jsonify(error='No exposures with specified date were found')

    if group is not None:
        group_id = Group.query.filter_by(code=group).first().id

        user_ids = list(map(
            lambda x: x[0],
            db.session.query(User.id).filter(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id == User.id,
                ExposureContent.exposure_id.in_(exposure_ids),
                ExposureContent.user_id == User.id)
            .all()))
    else:
        user_ids = list(map(lambda x: x[0], db.session.query(User.id).all()))

    all_problems = list(map(
        lambda x: x[0],
        db.session.query(
            Problem.id
        ).filter(
            Problem.id == ProblemSetContent.problem_id,
            ExposureContent.problem_set_id == ProblemSetContent.problem_set_id,
            ExposureContent.exposure_id.in_(exposure_ids),
            ExposureContent.user_id.in_(user_ids))
        .all()))
    problem_statuses = [{'name': ps.icon, 'id': ps.id} for ps in ProblemStatusInfo.query.all()]

    return render_template(
        'view_grading_results.html',
        all_problems=to_json_string(all_problems),
        exposure_ids=to_json_string(exposure_ids),
        user_ids=to_json_string(user_ids),
        problem_statuses=to_json_string(problem_statuses)
    )


# ------------------------------------------
# Trajectory view and API
# ------------------------------------------
@app.route('/api/trajectory', methods=['POST'])
@flask_login.login_required
def api_trajectory():
    if flask_login.current_user.username not in tpbeta_teacher_usernames:
        return "Login required for this URL"

    json = request.get_json()
    if not json or 'action' not in json:
        return jsonify(error='Expected JSON format and action')

    if json['action'] == 'load':
        if not json.get('trajectory_id'):
            return jsonify(error='Trajectory ID not specified')

        trajectory_id = json['trajectory_id']

        data = sorted(db.session.query(
            TrajectoryContent.sort_key,
            TrajectoryContent.id,
            TrajectoryContent.topic_id,
            Topic.code
        ).filter(
            TrajectoryContent.trajectory_id == trajectory_id,
            Topic.id == TrajectoryContent.topic_id
        ).all())
        result = []
        for sort_key, item_id, topic_id, topic_code in data:
            result.append({
                'sort_key': sort_key,
                'id': item_id,
                'topic_id': topic_id,
                'topic_code': topic_code
            })

        return jsonify(result)

    elif json['action'] == 'reorder':
        if not json.get('trajectory_id') or not json.get('ids'):
            return jsonify(error='Trajectory ID or reordering not specified')

        trajectory_id = json['trajectory_id']
        new_order = json['ids']
        items = {tc.id: tc for tc in db.session.query(
            TrajectoryContent
        ).filter(
            TrajectoryContent.trajectory_id == trajectory_id,
            TrajectoryContent.id.in_(new_order)
        ).all()}

        for i, item_id in enumerate(new_order):
            items[item_id].sort_key = 10 * (i + 1)

        db.session.commit()
        return jsonify(result='Successfully reordered items')

    elif json['action'] == 'insert':
        if not json.get('trajectory_id'):
            return jsonify(error='Trajectory ID not specified')
        if not json.get('topic_id') and not json.get('topic_code'):
            return jsonify(error='Neither topic ID not code is specified')
        trajectory_id = json['trajectory_id']
        sort_key = json.get('sort_key')
        topic_id = json.get('topic_id')
        topic_code = json.get('topic_code')
        if not topic_code:
            topic_code = Topic.query.filter_by(id=topic_id).first().code
        elif not topic_id:
            topic_id = Topic.query.filter_by(code=topic_code).first().id
        tc = TrajectoryContent(trajectory_id, topic_id, sort_key)
        db.session.add(tc)
        db.session.commit()

        return jsonify(id=tc.id, topic_id=tc.topic_id, topic_code=topic_code, sort_key=tc.sort_key)

    elif json['action'] == 'update':
        if not json.get('trajectory_id'):
            return jsonify(error='Trajectory ID not specified')
        if not json.get('id'):
            return jsonify(error='Item ID not specified')
        if not json.get('topic_id') and not json.get('topic_code'):
            return jsonify(error='Neither topic ID not code is specified')

        sort_key = json.get('sort_key')
        topic_id = json.get('topic_id')
        topic_code = json.get('topic_code')
        if not topic_code:
            topic_code = Topic.query.filter_by(id=topic_id).first().code
        elif not topic_id:
            topic_id = Topic.query.filter_by(code=topic_code).first().id
        tc = TrajectoryContent.query.filter_by(trajectory_id=json['trajectory_id'], id=json['id']).first()
        if not tc:
            abort(400, 'Specified item not found or does not belong to the trajectory')
        tc.topic_id = topic_id
        tc.sort_key = sort_key
        db.session.commit()

        return jsonify(id=tc.id, topic_id=tc.topic_id, topic_code=topic_code, sort_key=tc.sort_key)

    elif json['action'] == 'delete':
        if not json.get('id'):
            return jsonify(error='ID not specified')
        tc = TrajectoryContent.query.filter_by(id=json['id']).first()
        if not tc:
            return jsonify(error='Item with specified ID not found')
        db.session.delete(tc)
        db.session.commit()
        return jsonify(result='Item successfuly deleted')

    abort(400, 'Your request should be insert/delete/reorder')


@app.route('/trajectory/trajectory-<int:trajectory_id>', methods=['GET'])
@flask_login.login_required
def view_trajectory(trajectory_id):
    if flask_login.current_user.username not in tpbeta_teacher_usernames:
        return "Login required for this URL"
    return render_template('view_trajectory.html', trajectory_id=trajectory_id)


@app.route('/api/autocomplete/topic_code', methods=['POST'])
def autocomplete_topic_code():
    query = request.get_json('query')
    topic_codes = db.session.query(Topic.code).filter(Topic.code.like('%' + str(query) + '%')).all()
    return jsonify(matches=[item[0] for item in topic_codes])


# ------------------------------------------
# Courses view and API
# ------------------------------------------
@app.route('/api/courses', methods=['POST'])
def api_courses():
    if not request.get_json() or not request.get_json().get('action'):
        abort(400)

    if not flask_login.current_user or not flask_login.current_user.username:
        abort(400)

    user_username = flask_login.current_user.username
    user_id = flask_login.current_user.id
    json = request.get_json()
    action = json.get('action')

    if action == 'get_available_courses':
        data = db.session.query(
            Course.id,
            Course.title,
            Course.description,
            Role.title,
            Role.description
        ).filter(
            User.username == user_username,
            Participant.user_id == User.id,
            Participant.course_id == Course.id,
            Role.id == Participant.role_id
        ).all()

        return jsonify(list(
            {
                'course_id': course_id,
                'course_title': course_title,
                'course_description': course_description,
                'role_title': role_title,
                'role_description': role_description
            }
            for course_id, course_title, course_description, role_title, role_description in data
        ))
    elif action == 'get_available_actions' and json.get('course_id'):
        course_id = json.get('course_id')
        role_code = db.session.query(Role.code).filter(
            Participant.user_id == user_id,
            Participant.course_id == course_id,
            Participant.role_id == Role.id
        ).scalar()
        if not role_code:
            abort(403)
        action_list = []
        if role_code == 'ADMIN':
            action_list.append({
                'title': 'Управление пользователями',
                'url': url_for('user_management_view')
            })
        if role_code in ['ADMIN', 'INSTRUCTOR']:
            action_list.append({
                'title': 'Редактирование задач',
                'url': url_for('view_problems')
            })


        return jsonify(action_list)



@app.route('/courses', methods=['GET'])
def view_courses():
    return render_template('view_available_courses.html')


@app.route('/course-<int:course_id>')
def view_course(course_id):
    if not flask_login.current_user or not flask_login.current_user.username:
        abort(403)
    role_code = db.session.query(Role.code).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == course_id,
        Participant.role_id == Role.id
    ).scalar()
    if not role_code:
        abort(403)

    return render_template(
        'view_course.html',
        course_id=course_id
    )


@app.route('/problems', methods=['GET'])
def view_problems():
    return render_template('view_problems.html')


@app.route('/api/problems', methods=['POST'])
def api_problems():
    if not request.get_json() or not request.get_json().get('action'):
        abort(400)

    if not flask_login.current_user or not flask_login.current_user.username:
        abort(400)

    user_id = flask_login.current_user.id
    course_id = flask_login.current_user.current_course_id or Course.query.first().id
    json = request.get_json()
    action = json.get('action')

    role_code = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == user_id,
        Participant.course_id == course_id,
        Role.id == Participant.role_id
    ).scalar()

    if role_code not in ['INSTRUCTOR', 'ADMIN']:
        abort(403)

    if action == 'load':
        query = db.session.query(
            Problem.id,
            Problem.statement,
            Topic.code,
        ).filter(
            Topic.id == ProblemTopicAssignment.topic_id,
            Problem.id == ProblemTopicAssignment.problem_id
        )

        if json.get('filter'):
            filter = json.get('filter')
            if filter.get('problem_id'):
                query = query.filter(Problem.id == filter.get('problem_id'))
            if filter.get('topic_codes'):
                topic_codes = filter.get('topic_codes').strip().split()
                query = query.filter(
                    ProblemTopicAssignment.problem_id == Problem.id,
                    ProblemTopicAssignment.topic_id == Topic.id,
                    Topic.code.in_(topic_codes)
                )
            if filter.get('problem_statement'):
                statement_filter = filter.get('problem_statement')
                query = query.filter(Problem.statement.like('%{}%'.format(statement_filter)))

            if filter.get('page_index') is not None and filter.get('page_size'):
                count = query.count()
                page_index = filter['page_index'] - 1
                page_size = filter['page_size']
                query = query.slice(page_index * page_size, page_index * page_size + page_size)

        data = query.all()
        return jsonify({
            'itemsCount': count,
            'data': list(
                {
                    'problem_id': problem_id,
                    'problem_statement_raw': problem_statement,
                    'problem_statement': process_problem_statement(problem_statement),
                    'topic_codes': topic_codes
                }
                for problem_id,
                    problem_statement,
                    topic_codes
                in data
            )
        })

    elif action == 'delete':
        if not json.get('problem_id'):
            abort(400)
        problem = db.session.query(Problem).filter(Problem.id == json.get('problem_id')).first()
        if not problem:
            abort(404)

        db.session.query(
            ProblemTopicAssignment
        ).filter(
            ProblemTopicAssignment.problem_id == problem.id
        ).delete()

        db.session.delete(problem)
        db.session.commit()
        return jsonify(result='Successfully deleted a problem')

    elif action == 'update':
        if not json.get('item'):
            abort(400)
        item = json.get('item')
        problem_id = item.get('problem_id')
        problem = Problem.query.filter_by(id=problem_id).first()
        if not problem:
            abort(404)
        if item.get('problem_statement_raw') is not None:
            problem.statement = item.get('problem_statement_raw')
        if item.get('topic_codes') is not None:
            topic_codes = [s.strip() for s in item.get('topic_codes').strip().split()]
            topic_ids = list(map(
                lambda x: x[0],
                db.session.query(Topic.id).filter(Topic.code.in_(topic_codes)).all()
            ))
            db.session.query(ProblemTopicAssignment).filter(
                ProblemTopicAssignment.problem_id == problem_id
            ).delete()
            for topic_id in topic_ids:
                db.session.add(ProblemTopicAssignment(problem_id, topic_id))
            db.session.commit()

        db.session.commit()
        return jsonify({
            'problem_id': problem_id,
            'problem_statement_raw': problem.statement,
            'problem_statement': process_problem_statement(problem.statement),
            'topic_codes': '\n'.join(
                r[0] for r in db.session.query(
                    Topic.code
                ).filter(
                    Topic.id == ProblemTopicAssignment.topic_id,
                    ProblemTopicAssignment.problem_id == problem_id
                ))
        })

    elif action == 'insert':
        if not json.get('item'):
            abort(400)
        item = json.get('item')

        if item.get('problem_statement_raw') is None:
            abort(400)

        problem = Problem()
        problem.statement = item.get('problem_statement_raw')
        db.session.add(problem)

        if item.get('topic_codes') is not None:
            topic_codes = [s.strip() for s in item.get('topic_codes').strip().split()]
            topic_ids = list(map(
                lambda x: x[0],
                db.session.query(Topic.id).filter(Topic.code.in_(topic_codes)).all()
            ))
            for topic_id in topic_ids:
                db.session.add(ProblemTopicAssignment(problem.id, topic_id))

        db.session.commit()
        return jsonify({
            'problem_id': problem.id,
            'problem_statement_raw': problem.statement,
            'problem_statement': process_problem_statement(problem.statement),
            'topic_codes': '\n'.join(
                r[0] for r in db.session.query(
                    Topic.code
                ).filter(
                    Topic.id == ProblemTopicAssignment.topic_id,
                    ProblemTopicAssignment.problem_id == problem.id
                ))
        })


@app.route('/latex_to_html', methods=['POST'])
@flask_login.login_required
def preprocess_latex_text():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher"
    if request.json and 'text' in request.json and request.json['text']:
        return jsonify(result=latex_to_html(request.json['text']))
    return jsonify(result='')


@app.route('/group/<int:group_number>/test/<int:test_number>/view', methods=['GET', 'POST'])
@flask_login.login_required
def view_test(group_number, test_number):
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to view tests"

    users = db.session.query(User.id, User.firstname, User.lastname) \
        .join(Learner, Learner.user_id == User.id) \
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id) \
        .filter(AcademicGroup.number == group_number) \
        .all()
    if len(users) == 0:
        return 'Нет данных о студентах из группы {0}'.format(group_number)

    users = {u[0]: '{0} {1}'.format(u[1], u[2]) for u in users}

    testlog_items = TestLog.query.filter(TestLog.test_number == test_number, TestLog.user.in_(list(users))).all()
    if len(testlog_items) == 0:
        return 'Нет данных о тесте номер {0} группы {1}'.format(test_number, group_number)

    test_date = testlog_items[0].datetime

    log_info = ''
    # if flask_login.current_user.username == tpbeta_superuser_username:
    #     log_info = '; '.join(str(cid) + ' : ' +  ','.join(str(t) for t in clones[cid]) for cid in clones)

    problem_sets = dict()

    for item in testlog_items:
        user_id = item.user
        user_problem_ids = list(map(int, item.problems.split(',')))
        user_problems = {p.id: p.statement for p in Problem.query.filter(Problem.id.in_(user_problem_ids)).all()}
        problem_sets[user_id] = [{'id': id, 'text': latex_to_html(user_problems[id])} for id in user_problem_ids]

    return render_template(
        'test_printout.html',
        problems=problem_sets,
        users=users,
        group=group_number,
        suggested_test_number=test_number,
        date=test_date.isoformat()[:10],
        log_info=log_info,
        view_only=True)


@app.route('/test/create_for_user/<int:user_id>', methods=['GET', 'POST'])
@flask_login.login_required
def create_test_for_user(user_id):
    max_problems = int(request.args.get('max', 5))
    current_variation = defaultdict(int)

    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to create tests"

    users = User.query.filter_by(id=user_id).all()
    suggested_test_number = max(
        (x[0] for x in db.session.query(TestLog.test_number).filter(TestLog.user == users[0].id).all()), default=0) + 1

    users = {u.id: '{0} {1}'.format(u.firstname, u.lastname) for u in users}

    ignored_topic_ids = [x[0] for x in db.session.query(Topic.id).filter(Topic.topic.in_(ignored_topics)).all()]

    event_to_number = {'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3}
    trajectory_list = Trajectory.query.first().topics.split('|')
    trajectory_topics = list(set(trajectory_list))
    topic_levels = {t.id: t.level for t in Topic.query.filter(Problem.id.in_(trajectory_topics)).all()}
    trajectory_list = [i for i in map(int, trajectory_list) if i not in ignored_topic_ids]
    problems_for_trajectory = Problem.query.filter(Problem.topics.in_(trajectory_topics)).all()
    problem_ids = list(p.id for p in problems_for_trajectory)
    clones = defaultdict(set)
    problems_by_topic = defaultdict(list)
    for p in problems_for_trajectory:
        problems_by_topic[int(p.topics)].append(p)
        if p.clones and len(p.clones) > 0:
            c = [int(i) for i in p.clones.split(',')]
            clones[p.id].update(c)
            for cid in clones[p.id]:
                clones[cid].add(p.id)

    log_info = ''

    problem_sets = dict()

    for user_id in users:
        user_history = {i: -1 for i in problem_ids}
        group_number = AcademicGroup.query.filter_by(
            id=Learner.query.filter_by(user_id=user_id).first().academic_group).first().number
        user_history_items = History.query.filter(History.user == user_id, History.problem.in_(problem_ids))
        for h in user_history_items:
            if h.event in event_to_number:
                user_history[h.problem] = max(user_history[h.problem], event_to_number[h.event])
        user_remaining_trajectory_items = trajectory_list[:]
        counted_problems = set()
        for i, t in enumerate(user_remaining_trajectory_items):
            for p in problems_by_topic[t]:
                if user_history[p.id] >= 2 and p.id not in counted_problems:
                    user_remaining_trajectory_items[i] = 0
                    counted_problems.add(p.id)
                    if p.id in clones:
                        counted_problems.update(clones[p.id])
                    break

        user_remaining_trajectory_items = filter(None, user_remaining_trajectory_items)
        used_problem_ids = set()
        problems_for_user = list()
        for topic_id in user_remaining_trajectory_items:
            for p in problems_by_topic[topic_id]:
                if user_history[p.id] == -1 and (p.id not in used_problem_ids):
                    problems_for_user.append(p)
                    used_problem_ids.add(p.id)
                    if p.id in clones:
                        used_problem_ids.update(clones[p.id])
                    break
            else:
                for p in problems_by_topic[topic_id]:
                    if user_history[p.id] <= 1 and (p.id not in used_problem_ids):
                        problems_for_user.append(p)
                        used_problem_ids.add(p.id)
                        if p.id in clones:
                            used_problem_ids.update(clones[p.id])
                        break
        problem_sets[user_id] = []
        for p in problems_for_user[:max_problems]:
            problem_sets[user_id].append({
                'id': p.id,
                'text': latex_to_html(p.statement, variation=current_variation[p.id]),
                'level': topic_levels[int(p.topics)]
            })
            current_variation[p.id] += 1

    return render_template(
        'test_printout.html',
        problems=problem_sets,
        users=users,
        group=group_number,
        suggested_test_number=suggested_test_number,
        date=date.today().isoformat(),
        max_problems=max_problems,
        log_info=log_info)


@app.route('/test/create/<int:group_number>', methods=['GET', 'POST'])
@flask_login.login_required
def create_test(group_number):
    max_problems = int(request.args.get('max', 5))
    current_variation = defaultdict(int)

    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to create tests"

    if request.method == 'POST':
        if not request.json or 'test_number' not in request.json:
            return jsonify(result='Ошибка сохранения.')
        test_number = int(request.json['test_number'])
        test_date = datetime(*map(int, request.json['test_date'].split('-')))
        for s in request.json['problems'].split('|'):
            s_user, s_problems = s.split(':')
            if not s_user or db.session.query(TestLog.id).filter(TestLog.test_number == int(test_number),
                                                                 TestLog.user == int(s_user)).first():
                db.session.rollback()
                return jsonify(
                    result='Ошибка: в базе данных уже есть запись о тесте {0} у пользователя #{1}'.format(test_number,
                                                                                                          s_user))
            testlog = TestLog()
            testlog.test_number = test_number
            testlog.datetime = test_date
            testlog.user = int(s_user)
            testlog.problems = s_problems
            db.session.add(testlog)
        db.session.commit()
        return jsonify(result='Информация о тесте сохранена.')

    users = db.session.query(User) \
        .join(Learner, Learner.user_id == User.id) \
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id) \
        .filter(AcademicGroup.number == group_number) \
        .all()

    suggested_test_number = max(
        (x[0] for x in db.session.query(TestLog.test_number).filter(TestLog.user == users[0].id).all()), default=0) + 1

    users = {u.id: '{0} {1}'.format(u.firstname, u.lastname) for u in users}

    ignored_topic_ids = [x[0] for x in db.session.query(Topic.id).filter(Topic.topic.in_(ignored_topics)).all()]

    event_to_number = {'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3}
    trajectory_list = Trajectory.query.first().topics.split('|')
    trajectory_topics = list(set(trajectory_list))
    trajectory_list = [i for i in map(int, trajectory_list) if i not in ignored_topic_ids]
    problems_for_trajectory = Problem.query.filter(Problem.topics.in_(trajectory_topics)).all()
    topic_levels = {t.id: t.level for t in Topic.query.filter(Problem.id.in_(trajectory_topics)).all()}
    problem_ids = list(p.id for p in problems_for_trajectory)
    clones = defaultdict(set)
    problems_by_topic = defaultdict(list)
    for p in problems_for_trajectory:
        problems_by_topic[int(p.topics)].append(p)
        if p.clones and len(p.clones) > 0:
            c = [int(i) for i in p.clones.split(',')]
            clones[p.id].update(c)
            for cid in clones[p.id]:
                clones[cid].add(p.id)

    log_info = ''

    problem_sets = dict()

    for user_id in users:
        user_history = {i: -1 for i in problem_ids}
        user_history_items = History.query.filter(History.user == user_id, History.problem.in_(problem_ids))
        for h in user_history_items:
            if h.event in event_to_number:
                user_history[h.problem] = max(user_history[h.problem], event_to_number[h.event])
        user_remaining_trajectory_items = trajectory_list[:]
        counted_problems = set()
        for i, t in enumerate(user_remaining_trajectory_items):
            for p in problems_by_topic[t]:
                if user_history[p.id] >= 2 and p.id not in counted_problems:
                    user_remaining_trajectory_items[i] = 0
                    counted_problems.add(p.id)
                    if p.id in clones:
                        counted_problems.update(clones[p.id])
                    break

        user_remaining_trajectory_items = filter(None, user_remaining_trajectory_items)
        used_problem_ids = set()
        problems_for_user = list()
        for topic_id in user_remaining_trajectory_items:
            for p in problems_by_topic[topic_id]:
                if user_history[p.id] == -1 and (p.id not in used_problem_ids):
                    problems_for_user.append(p)
                    used_problem_ids.add(p.id)
                    if p.id in clones:
                        used_problem_ids.update(clones[p.id])
                    break
            else:
                for p in problems_by_topic[topic_id]:
                    if user_history[p.id] <= 1 and (p.id not in used_problem_ids):
                        problems_for_user.append(p)
                        used_problem_ids.add(p.id)
                        if p.id in clones:
                            used_problem_ids.update(clones[p.id])
                        break
        problem_sets[user_id] = []
        for p in problems_for_user[:max_problems]:
            problem_sets[user_id].append({
                'id': p.id,
                'text': latex_to_html(p.statement, variation=current_variation[p.id]),
                'level': topic_levels[int(p.topics)]
            })
            current_variation[p.id] += 1

    return render_template(
        'test_printout.html',
        problems=problem_sets,
        users=users,
        group=group_number,
        suggested_test_number=suggested_test_number,
        date=date.today().isoformat(),
        max_problems=max_problems,
        log_info=log_info)


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


@app.route('/learnerdashboard')
@flask_login.login_required
def learner_dashboard():
    if not flask_login.current_user or not hasattr(flask_login.current_user, 'username'):
        return redirect(url_for('login'))
    username = flask_login.current_user.username
    logs = TestLog.query.filter_by(user=flask_login.current_user.id).all()
    if len(logs) == 0:
        return 'Не найдено записей о результатах контрольных работ пользователя <em>{0}</em>'.format(username)
    return 'Найдены записи о тестах, проводившихся в следующие даты:<br>' + '<br>'.join(
        '<a href="{1}">{0}</a>'.format(log.datetime.isoformat()[:10],
                                       url_for('test_results', test_number=log.test_number)) for log in logs)


@app.route('/learnerdashboard/test/<int:test_number>', methods=['GET'])
@flask_login.login_required
def test_results(test_number):
    user_id = flask_login.current_user.id
    if ('user' in request.args) and flask_login.current_user.username in teachers:
        user_id = int(request.args['user'])

    log = TestLog.query.filter_by(user=user_id, test_number=test_number).first()
    if not log:
        return "Не найдена информация о тесте"
    test_history = History.query.filter_by(user=user_id, comment='TEST{0}'.format(test_number)).all()
    result_translator = {'SEEN': '∅', 'TRIED': '□', 'ALMOST': '◩', 'SUCCESS': '■'}
    u_history = {h.problem: result_translator[h.event] for h in test_history if h.event in result_translator}
    problem_ids = list(map(int, log.problems.split(',')))
    marks = problem_ids[:]
    for i, id in enumerate(problem_ids):
        marks[i] = {
            'result': u_history.get(id, ''),
            'id': id
        }

    return render_template(
        'student_test_results.html',
        name=db.session.query(User.username).filter(User.id == user_id).first()[0],
        test=test_number,
        marks=marks
    )


def getUsersTrajectoryResults(user_ids):
    results = dict()
    event_to_number = {'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3}
    all_topics = Topic.query.all()
    trajectory_list = Trajectory.query.first().topics.split('|')
    trajectory_topics = list(set(trajectory_list))
    trajectory_list = list(map(int, trajectory_list))
    topic_levels = {t.id: t.level for t in all_topics if t.id in trajectory_list}
    problems_for_trajectory = Problem.query.filter(Problem.topics.in_(trajectory_topics)).all()
    problem_ids = list(p.id for p in problems_for_trajectory)
    clones = defaultdict(set)
    problems_by_topic = defaultdict(list)
    for p in problems_for_trajectory:
        problems_by_topic[int(p.topics)].append(p)
        if p.clones and len(p.clones) > 0:
            c = [int(i) for i in p.clones.split(',')]
            clones[p.id].update(c)
            for cid in clones[p.id]:
                clones[cid].add(p.id)

    results[0] = {level: len([1 for t in trajectory_list if topic_levels[t] == level]) for level in
                  set(topic_levels.values())}

    for user_id in user_ids:
        user_history_items = History.query.filter(History.user == user_id, History.problem.in_(problem_ids)).all()
        if len(user_history_items) == 0:
            continue

        user_history = {i: -1 for i in problem_ids}
        review_requests = dict()
        for h in user_history_items:
            if h.event == 'REVIEW_REQUEST':
                review_requests[h.problem] = h
                if h.problem not in user_history:
                    user_history[h.problem] = event_to_number['ALMOST']
                else:
                    user_history[h.problem] = max(user_history[h.problem], event_to_number['ALMOST'])
            if h.event in event_to_number:
                user_history[h.problem] = max(user_history[h.problem], event_to_number[h.event])
        user_trajectory_results = [0] * len(trajectory_list)
        counted_problems = set()
        for i, t in enumerate(trajectory_list):
            for p in problems_by_topic[t]:
                if user_history[p.id] >= 2 and p.id not in counted_problems:
                    user_trajectory_results[i] = user_history[p.id]
                    counted_problems.add(p.id)
                    if p.id in clones:
                        counted_problems.update(clones[p.id])
                    break
        results[user_id] = {key: 0 for key in results[0].keys()}

        for i in range(len(trajectory_list)):
            if user_trajectory_results[i] == event_to_number['SUCCESS']:
                results[user_id][topic_levels[trajectory_list[i]]] += 1

        results[user_id]['final_grade'] = 0

        res1, res2, res3 = (results[user_id][i] for i in [1, 2, 3])
        maxres1, maxres2, maxres3 = (results[0][i] for i in [1, 2, 3])

        if res1 < maxres1:
            res2 += res3
            res3 = 0
            while res1 < maxres1 and res2 >= 3:
                res2 -= 3
                res1 += 1
            if res2 > maxres2:
                res3 = res2 - maxres2
                maxres2 = res3

        while res2 < maxres2 and res3 >= 2:
            res3 -= 2
            res2 += 1

        if res1 == maxres1:
            results[user_id]['final_grade'] = 4
            if res2 >= 2:
                results[user_id]['final_grade'] += 1
            if res2 >= 4:
                results[user_id]['final_grade'] += 1
            if res2 >= maxres2:
                results[user_id]['final_grade'] += 1
                if res3 >= 1:
                    results[user_id]['final_grade'] += 1
                if res3 >= 2:
                    results[user_id]['final_grade'] += 1
                if res3 >= 3:
                    results[user_id]['final_grade'] += 1

    return results


@app.route('/learnerdashboard/trajectory', methods=['GET'])
@flask_login.login_required
def trajectory_progress():
    user_id = flask_login.current_user.id
    if ('user' in request.args) and flask_login.current_user.username in teachers:
        user_id = int(request.args['user'])

    final_grade = getUsersTrajectoryResults([user_id])
    if final_grade and user_id in final_grade:
        final_grade = final_grade[user_id]['final_grade']
    else:
        final_grade = '???'

    event_to_number = {'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3}
    number_to_square = {-1: '□', 0: '□', 1: '□', 2: '◩', 3: '■'}
    all_topics = Topic.query.all()
    topic_names = {t.id: t.topic for t in all_topics}
    topic_levels = {t.id: t.level for t in all_topics}
    trajectory_list = Trajectory.query.first().topics.split('|')
    trajectory_topics = list(set(trajectory_list))
    trajectory_list = list(map(int, trajectory_list))
    problems_for_trajectory = Problem.query.filter(Problem.topics.in_(trajectory_topics)).all()
    problem_ids = list(p.id for p in problems_for_trajectory)
    clones = defaultdict(set)
    problems_by_topic = defaultdict(list)
    for p in problems_for_trajectory:
        problems_by_topic[int(p.topics)].append(p)
        if p.clones and len(p.clones) > 0:
            c = [int(i) for i in p.clones.split(',')]
            clones[p.id].update(c)
            for cid in clones[p.id]:
                clones[cid].add(p.id)

    user_history_items = History.query.filter(History.user == user_id, History.problem.in_(problem_ids))
    user_history = {i: -1 for i in problem_ids}
    review_requests = dict()
    for h in user_history_items:
        if h.event == 'REVIEW_REQUEST':
            review_requests[h.problem] = h
            if h.problem not in user_history:
                user_history[h.problem] = event_to_number['ALMOST']
            else:
                user_history[h.problem] = max(user_history[h.problem], event_to_number['ALMOST'])
        if h.event in event_to_number:
            user_history[h.problem] = max(user_history[h.problem], event_to_number[h.event])
    trajectory_results = [0] * len(trajectory_list)
    result_witnesses = [0] * len(trajectory_list)
    counted_problems = set()
    for i, t in enumerate(trajectory_list):
        for p in problems_by_topic[t]:
            if user_history[p.id] >= 2 and p.id not in counted_problems:
                trajectory_results[i] = user_history[p.id]
                result_witnesses[i] = p.id
                counted_problems.add(p.id)
                if p.id in clones:
                    counted_problems.update(clones[p.id])
                break
    results = []
    for i in range(len(trajectory_list)):
        r = {
            'topic': topic_names[trajectory_list[i]],
            'level': topic_levels[trajectory_list[i]],
            'result': number_to_square[trajectory_results[i]],
            'witness': result_witnesses[i],
            'status': ''
        }
        if trajectory_results[i] == 2:
            problem_id = result_witnesses[i]
            h = db.session.query(History.datetime).filter(History.user == user_id, History.problem == problem_id,
                                                          History.event == 'ALMOST').first()
            if h and h[0]:
                delta = datetime.now() - h[0]
            if problem_id in review_requests:
                review_request = review_requests[problem_id]
                if review_request.comment and len(review_request.comment) > 0:
                    tokens = review_request.comment.split('|', maxsplit=2)
                    reviewer = tokens[0]
                    if len(tokens) == 1:
                        r['comment'] = 'Ваше решение на проверке у {0}'.format(reviewer)
                        r['status'] = 'REVIEWER_ASSIGNED'
                    else:
                        r['status'] = tokens[1]
                        if len(tokens) == 3:
                            r['comment'] = tokens[2]
                        else:
                            r['comment'] = 'Ваше решение на проверке у {0}'.format(reviewer)
                else:
                    r['comment'] = 'Запрос на проверку отправлен, но проверяющий ещё не назначен.'
            else:
                r['comment'] = 'Вы ещё не отправляли запрос на проверку этой задачи.<br>На сдачу дорешки осталось {0} дней'.format(21 - delta.days)
                r['status'] = 'REVIEW_NOT_REQUESTED'

        results.append(r)

    return render_template('student_trajectory.html',
                           results=results,
                           user=user_id,
                           final_grade=final_grade
                           )


@app.route('/grades')
@flask_login.login_required
def show_final_grades():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to view userlist"
    users = User.query.all()
    grades = getUsersTrajectoryResults({u.id for u in users})
    for u in users:
        u.name = u.lastname + ' ' + u.firstname
        if u.id in grades:
            u.grades = grades[u.id]

    return render_template(
        'final_grades.html',
        users=filter(lambda x: (hasattr(x, 'grades') and 1 in x.grades and x.grades[1] >= 0),
                     sorted(users, key=lambda u: u.name)),
        maximum_grades=grades[0])


@app.route('/users')
@flask_login.login_required
def show_user_list():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to view userlist"
    users = User.query.all()

    for u in users:
        u.name = u.lastname + ' ' + u.firstname

    return render_template(
        'user_list.html',
        users=sorted(users, key=lambda u: u.name),
        superuser=(flask_login.current_user.username == tpbeta_superuser_username))


@app.route('/recover_password', methods=['POST'])
@flask_login.login_required
def recover_password():
    if flask_login.current_user.username != tpbeta_superuser_username:
        return jsonify(result='Login error')

    if 'user_id' not in request.json:
        return jsonify(result='Error')

    user_id = int(request.json['user_id'])
    user = User.query.filter_by(id=user_id).first()

    if not user.email:
        return jsonify(result='Невозможно выслать пароль: не указан email.')

    random.seed(str(datetime.now()))
    letters = 'qwertyuiopasdfghjklzxcvbnm1029384756'
    new_password = ''.join(letters[int(random.random() * len(letters))] for _ in range(8))

    msg = Message(subject='Временный пароль к информационной системе по курсу ДС',
                  body='''Ваше имя пользователя для входа в систему: {0}\nВаш пароль для входа: {1}'''.format(
                      user.username, new_password),
                  recipients=[user.email])
    mail.send(msg)

    user.password_hash = md5(new_password)
    db.session.commit()

    return jsonify(result='Успешно выслан пароль "{0}"'.format(new_password))


def notify_user(user_id, subject, body):
    user_data = User.query.filter_by(id=user_id).first()
    if not user_data.email:
        return
    msg = Message(subject='Курс ДС: {}'.format(subject),
                  body='Здравствуйте, {}!\n{}'.format(user_data.firstname, body),
                  recipients=[user_data.email])
    mail.send(msg)


@app.route('/corrections', methods=['GET', 'POST'])
@flask_login.login_required
def corrections_interface():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to mark corrections"

    if request.method == 'POST':
        if not request.json or 'user' not in request.json or 'problem' not in request.json or 'result' not in request.json:
            return jsonify(result='Ошибка сохранения.')
        user = int(request.json['user'])
        problem = int(request.json['problem'])
        result = int(request.json['result'])
        if result == 1:
            new_item = History()
            new_item.user = user
            new_item.problem = problem
            new_item.event = 'SUCCESS'
            if 'comment' in request.json:
                new_item.comment = 'CORRECTION|' + request.json['comment']
            notify_user(
                user,
                'Ваше решение принято',
                'Ваша дорешка по задаче {} принята. Дополнительный комментарий от проверяющего: {}'.format(problem,
                                                                                                           request.json[
                                                                                                               'comment'] if 'comment' in request.json else '(отсутствует)'));
            new_item.comment = 'CORRECTION'
            new_item.datetime = datetime.now()
            db.session.add(new_item)
            db.session.commit()
            return jsonify(result='Задача {0} помечена как зачтённая'.format(problem))
        else:
            item = History.query.filter_by(user=user, problem=problem, event='SUCCESS', comment='CORRECTION').first()
            if not item:
                return jsonify(result='Задача {0} не найдена среди помеченных зачтённых задач'.format(problem))
            db.session.delete(item)
            db.session.commit()
            return jsonify(result='Задача {0} удалена из зачтённых'.format(problem))

    history_items_almost = History.query.filter_by(event='ALMOST').all()
    history_items_success = History.query.filter_by(event='SUCCESS', comment='CORRECTION').all()
    users = User.query.all()
    usernames = dict()
    for u in users:
        usernames[u.id] = u.username

    remaining_corrections = defaultdict(dict)
    for item in history_items_almost:
        remaining_corrections[item.user][item.problem] = 0
    for item in history_items_success:
        if item.user in remaining_corrections and item.problem in remaining_corrections[item.user]:
            remaining_corrections[item.user][item.problem] = 1

    data = []
    for uid in remaining_corrections:
        latex_project_url = db.session.query(Learner.latex_project_url).filter(Learner.user_id == uid).first()
        if latex_project_url:
            latex_project_url = latex_project_url[0]
        if not latex_project_url:
            latex_project_url = ''
        data.append({
            'id': uid,
            'name': usernames[uid],
            'url': latex_project_url,
            'problems': sorted(({'id': pid, 'result': res} for pid, res in remaining_corrections[uid].items()),
                               key=lambda x: x['id'])
        })
    data.sort(key=lambda x: usernames[x['id']])
    return render_template('corrections.html', data=data)


@app.route('/review', methods=['POST', 'GET'])
@flask_login.login_required
def review_interface():
    if request.method == 'POST':
        if not request.json or 'user' not in request.json or 'problem' not in request.json or 'action' not in request.json:
            return jsonify(result='Ошибка сохранения')
        user = int(request.json['user'])
        problem = int(request.json['problem'])
        action = request.json['action']
        if action == 'SEND_FOR_REVIEW':
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if h:
                return jsonify(result='Запрос на проверку уже был отправлен ранее.')
            h = History()
            h.datetime = datetime.now()
            h.user = user
            h.problem = problem
            h.event = 'REVIEW_REQUEST'
            db.session.add(h)
            db.session.commit()
            return jsonify(result='Запрос отправлен')
        elif action == 'RESEND_FOR_REVIEW':
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if not h:
                return jsonify(result='Запрос на проверку ранее не отправлялся.')
            tokens = h.comment.split('|')
            tokens[1] = 'REVIEW_REQUEST_RESENT'
            h.comment = '|'.join(tokens[:2])
            db.session.commit()
            return jsonify(result='Запрос отправлен')
        elif action == 'TAKE_FOR_REVIEW' and flask_login.current_user.username in teachers:
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if not h.comment or '|' not in h.comment:
                h.comment = flask_login.current_user.username
            else:
                pos = h.comment.find('|')
                h.comment = flask_login.current_user.username + h.comment[pos:]
            db.session.commit()
            return jsonify(result='Успешно изменён проверяющий для задачи', reviewer=flask_login.current_user.username)
        elif action == 'DELETE_REQUEST' and flask_login.current_user.username in teachers:
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            db.session.delete(h)
            db.session.commit()
            return jsonify(result='Запрос на проверку закрыт')
        elif action == 'SEND_FOR_REWORK' and flask_login.current_user.username in teachers:
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if 'comment' in request.json:
                comment = request.json['comment']
            else:
                comment = 'Проверяющий {0} затребовал доработку решения'.format(flask_login.current_user.username)
            h.comment = '{0}|{1}|{2}'.format(flask_login.current_user.username, 'REWORK_REQUIRED', comment)
            h.datetime = datetime.now()
            notify_user(
                user,
                'Ваше решение отправлено на доработку',
                'Ваша дорешка по задаче {} отправлена на доработку с комментарием: {}'.format(problem, comment));
            db.session.commit()
            return jsonify(result='Запрос на доработку отправлен')
        elif action == 'REMOVE_EXPIRED':
            if flask_login.current_user.username != tpbeta_superuser_username:
                return jsonify(result='Только суперпользователь может выполнять этот запрос')
            n_deleted = 0
            n_close_to_expiration = 0
            for i in History.query.filter_by(event='ALMOST').all():
                if db.session.query(History.id).filter(History.user == i.user, History.problem == i.problem,
                                                       History.event.in_(['SUCCESS', 'REVIEW_REQUEST'])).first():
                    continue
                if not i.datetime:
                    continue
                delta = datetime.now() - i.datetime
                if delta.days <= 21:
                    continue
                if delta.days >= 19:
                    n_close_to_expiration += 1
                db.session.delete(i)
                n_deleted += 1
            db.session.commit()
            return jsonify(
                result='Удалено {0} просроченных заданий; {1} заданий близки к просроченным'.format(n_deleted,
                                                                                                    n_close_to_expiration))

    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to mark corrections"
    history_items = History.query.filter_by(event='REVIEW_REQUEST').all()
    items = []
    for h in history_items:
        username = db.session.query(User.username).filter(User.id == h.user).first()[0]
        reviewer = ''
        state = 'Ожидает проверки с {0}'.format(h.datetime + timedelta(minutes=3 * 60))
        formal_state = 'PENDING'

        if h.comment:
            tokens = h.comment.split('|', maxsplit=2)
            reviewer = tokens[0]
            if len(tokens) > 1:
                formal_state = tokens[1]
                if formal_state == 'REWORK_REQUIRED':
                    state = 'На доработке с {0}'.format(h.datetime + timedelta(minutes=3 * 60))
                if formal_state == 'REVIEW_REQUEST_RESENT':
                    state = 'Студент доработал решение и отправил запрос на перепроверку'

        latex_project_url = db.session.query(Learner.latex_project_url).filter(Learner.user_id == h.user).first()
        if latex_project_url:
            latex_project_url = latex_project_url[0]
        if not latex_project_url:
            latex_project_url = ''

        items.append({
            'username': username,
            'url': latex_project_url,
            'user_id': h.user,
            'problem': h.problem,
            'datetime': h.datetime,
            'reviewer': reviewer,
            'state': state,
            'formal_state': formal_state
        })
    return render_template('review_requests_list.html',
                           items=sorted(items, key=lambda x: (x['state'], x['datetime'])),
                           current_logged_user=flask_login.current_user.username,
                           show_remove_expired_ui=(flask_login.current_user.username == tpbeta_superuser_username))


@app.route('/topic_stats')
def show_topic_stats():
    trajectory_topic_ids = list(map(int, Trajectory.query.first().topics.split('|')))
    topics = Topic.query.filter(Topic.id.in_(trajectory_topic_ids))

    data = []
    for topic in topics:
        topic_problem_ids = [x[0] for x in db.session.query(Problem.id).filter(Problem.topics == str(topic.id)).all()]
        history_items_users = [x[0] for x in
                               db.session.query(History.user).filter(History.problem.in_(topic_problem_ids),
                                                                     History.event.in_(['SUCCESS', 'ALMOST'])).all()]
        user_progress = defaultdict(int)
        for u in history_items_users:
            user_progress[u] += 1

        qty_in_trajectory = sum(1 for i in trajectory_topic_ids if i == topic.id)
        data.append({
            'topic': topic.topic,
            'level': topic.level,
            'qty_in_trajectory': qty_in_trajectory,
            'num_problems': len(topic_problem_ids),
            'num_tries': db.session.query(History.id).filter(History.problem.in_(topic_problem_ids)).count(),
            'num_successful_tries': len(history_items_users),
            'num_clears': sum(1 for u in user_progress if user_progress[u] == qty_in_trajectory)
        })

    return render_template('problem_stats.html', data=data)


@app.route('/comments')
@flask_login.login_required
def view_comments():
    if flask_login.current_user.username not in teachers:
        return 'Просматривать комментарии могут только преподаватели'

    comments = ProblemComment.query.all()

    comments_processed = []
    usernames = dict()

    for c in sorted(comments, key=lambda x: x.datetime, reverse=True):
        if c.author not in usernames:
            user_id, username = db.session.query(User.id, User.username).filter(User.id == c.author).first()
            usernames[user_id] = username
        comments_processed.append({
            'text': c.text if len(c.text) < 1000 else c.text[:1000] + '…',
            'author_username': usernames[c.author],
            'author_id': c.author,
            'datetime': c.datetime.isoformat().replace('T', '<br>').replace('-', '&#8209;'),
            'problem_id': c.problem_id
        })

    return render_template('view_all_comments.html', comments=comments_processed)


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


@app.route('/api/authorization', methods=['POST'])
def api_authorization():
    if request.form and request.form.get('username') and request.form.get('password'):
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user is not None and hasattr(user, 'password_hash') and md5(request.form.get('password')) == user.password_hash:
            flask_login.login_user(user)
            return redirect(url_for('view_courses'))
        else:
            abort(403)

    json = request.get_json()
    if not json:
        abort(400)
    if json.get('action') == 'login' and json.get('username'):
        user = User.query.filter_by(username=json.get('username')).first()
        if user is not None and hasattr(user, 'password_hash') and md5(json.get('password')) == user.password_hash:
            flask_login.login_user(user)
            return jsonify('Logged in'), http_status_codes.HTTP_200_OK
        else:
            abort(401)

    elif json.get('action') == 'logout':
        flask_login.logout_user()
        return jsonify('Logged out'), http_status_codes.HTTP_200_OK

    elif json.get('action') == 'get_authorized_user':
        if flask_login.current_user and hasattr(flask_login.current_user, 'username'):
            return jsonify({
                'id': flask_login.current_user.id,
                'username': flask_login.current_user.username,
                'name_first': flask_login.current_user.name_first,
                'name_last': flask_login.current_user.name_last
            }), http_status_codes.HTTP_200_OK
        return jsonify({
            'id': 0,
            'username': None
        }), http_status_codes.HTTP_200_OK

    abort(400)


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

    else:
        user = User.query.filter_by(username=request.form['username']).first()
        if user is not None and hasattr(user, 'password_hash') and md5(request.form['pw']) == user.password_hash:
            flask_login.login_user(user)
            login_successful = True
            username = request.form['username']
        else:
            bad_login = True




@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run()