# coding=utf8

def parse_person_name(name):
    tokens = name.strip().split()
    if len(tokens) == 2:
        return tokens[0],tokens[1],None
    if len(tokens) == 1:
        return tokens[0],None,None
    if tokens[1][-3:] in ['вна', 'вич']:
        return tokens[0],tokens[2],tokens[1]
    return tokens[1],tokens[0],tokens[2]

import re

def process_problem_variations_mathmode(text, variation = None):
    return re.compile(r'\{\{(.*?)\}\}', re.DOTALL).sub(lambda m:\
        ''.join(r'\class{problem-variation-' + str(i) + '}{ ' + opt + ' } ' for i, opt in enumerate(m.group(1).split('||')))\
        , text)

def process_problem_variations_textmode(text, variation = None):
    return re.compile(r'\{\{(.*?)\}\}', re.DOTALL).sub(lambda m:\
        ''.join(r'<span class="problem-variation-{0}">{1}</span>'.format(i, opt) for i, opt in enumerate(m.group(1).split('||')))\
        , text)

def gcd(x, y):
    if x % y == 0:
        return y
    if y % x == 0:
        return x
    return gcd(min(x, y), max(x, y) % min(x, y))

def lcm(seq):
    cur_lcm = 1
    for k in seq:
        cur_lcm = k * cur_lcm // gcd(k, cur_lcm)
    return cur_lcm

def process_problem_variations(text, variation = None):
    if variation is not None:
        def variation_chooser(match_object):
            options = match_object.group(1).split('||')
            return options[variation % len(options)]
        return re.compile(r'\{\{(.*?)\}\}', re.DOTALL).sub(variation_chooser, text)

    num_variations = list(set(len(s.split('||')) for s in re.compile(r'\{\{(.*?)\}\}', re.DOTALL).findall(text)))
    text = re.compile(r'\$\$(.*?)\$\$', re.DOTALL).sub(lambda m: r'$${0}$$'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = re.compile(r'\$(.*?)\$', re.DOTALL).sub(lambda m: r'${0}$'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = re.compile(r'\\\((.*?)\\\)', re.DOTALL).sub(lambda m: r'\({0}\)'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = re.compile(r'\\\[(.*?)\\\]', re.DOTALL).sub(lambda m: r'\[{0}\]'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = process_problem_variations_textmode(text, variation)

    if (variation is not None) or len(num_variations) == 0:
        return text

    max_variations = max(num_variations)
    if max_variations <= 1:
        return text

    buttons_html = '\n'.join('''
        <button
        class="problem-variation-control btn btn-default"
        data-variation="{0}"
        onclick="
            for(var i = 0; i < {1}; ++i) {{
                $(event.target).parent().parent().find('.problem-variation-' + i.toString()).hide(0);
            }}
            $(event.target).parent().parent().find('.problem-variation-' + event.target.dataset.variation).css('display','inline');
        ">{0}</button>'''.replace('\n','').\
        format(i, max_variations) for i in range(lcm(num_variations)))

    return r'<div class="dontprint">Вариация {0}</div>{1}'.format(buttons_html, text)


def process_latex_lists(text):
    def shuffler(s):
        s = s.split(r'\item')[1:]
        random.shuffle(s)
        return r'\begin{itemize} \item' + r' \item '.join(s) + r'\end{itemize}'
    text = re.compile(r'\\begin{shuffledlist}(.*?)\\end{shuffledlist}', re.DOTALL).sub(lambda m: shuffler(m.group(1)), text)

    return text\
        .replace(r'\begin{enumerate}','<ol>')\
        .replace(r'\end{enumerate}','</ol>')\
        .replace(r'\begin{itemize}','<ul>')\
        .replace(r'\end{itemize}','</ul>')\
        .replace(r'\item','<li>')

def process_xypic_macros(text):
    return re.compile(r'\\edge{(.*?)}', re.DOTALL).sub(lambda m: r'\ar@{{-}}[{0}]'.format(m.group(1)), text)\
        .replace(r'\vrtxf', r'*[o]{\bullet}')\
        .replace(r'\vrtx', r'*[o]{\circ}')

def latex_to_html(text, variation = None):
    text = re.compile(r'(?<!\\)%.*$', re.MULTILINE).sub('', text)
    text = escape(text)
    text = re.compile(r'\\emph{(.*?)}', re.DOTALL).sub(lambda m: r'<em>{0}</em>'.format(m.group(1)), text)
    text = re.compile(r'\\textit{(.*?)}', re.DOTALL).sub(lambda m: r'<em>{0}</em>'.format(m.group(1)), text)
    text = re.compile(r'\\textbf{(.*?)}', re.DOTALL).sub(lambda m: r'<strong>{0}</strong>'.format(m.group(1)), text)
    text = re.sub(r'\\,', ' ', text).replace('---','—').replace('--','–').replace('~','&nbsp;')

    text = process_latex_lists(text)
    text = process_problem_variations(text, variation)
    text = process_xypic_macros(text)

    return text

from flask import Flask
from flask import escape, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, date
from collections import defaultdict
import random
import flask.ext.login as flask_login

# Security sensitive constants are imported from a file not being synced with github
from tpbeta_security import *

app = Flask(__name__)

app.secret_key = tpbeta_app_secret_key

app.config['SQLALCHEMY_DATABASE_URI'] = tpbeta_sqlalchemy_db_uri
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280

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
teachers = tpbeta_teacher_usernames



from hashlib import md5 as md5hasher

def md5(s):
    m = md5hasher()
    m.update(s.encode())
    return m.hexdigest()

class AcademicGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer)
    year = db.Column(db.Integer)
    def __init__(self, number, year = None):
        self.number = number
        self.year = year

class User(db.Model, flask_login.UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    pwdhash = db.Column(db.String(32))
    firstname = db.Column(db.Unicode(80))
    middlename = db.Column(db.Unicode(80))
    lastname = db.Column(db.Unicode(80))
    email = db.Column(db.Unicode(80))
    def __repr__(self):
        return '<User {0}>'.format(self.username)

class Learner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique = True, nullable = False)
    academic_group = db.Column(db.Integer, db.ForeignKey('academic_group.id'))
    latex_project_url = db.Column(db.UnicodeText)

    # In case a student is visiting classes with a different group:
    academic_group_real = db.Column(db.Integer, db.ForeignKey('academic_group.id'))

    def __init__(self, username, email, names):
        self.username = username
        self.email = email

class ProblemSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable = False)
    datetime = db.Column(db.DateTime, nullable = False)
    statement = db.Column(db.UnicodeText, nullable = False)

class ProblemComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable = False)
    datetime = db.Column(db.DateTime, nullable = False)
    text = db.Column(db.UnicodeText)
    author = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)
    in_reply_to = db.Column(db.Integer)

class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    statement = db.Column(db.UnicodeText, nullable = False)
    creator = db.Column(db.Integer, db.ForeignKey('user.id'))
    parent = db.Column(db.Integer)
    last_modified = db.Column(db.DateTime)
    clones = db.Column(db.Text)
    author_comment = db.Column(db.Text)
    topics = db.Column(db.Text)
    concepts = db.Column(db.Text)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.Text)
    level = db.Column(db.Integer)
    parent = db.Column(db.Integer)
    connected_topics = db.Column(db.Text)
    comment = db.Column(db.Text)

class Concept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    concept = db.Column(db.Text)
    comment = db.Column(db.Text)

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable = False)
    user = db.Column(db.Integer, db.ForeignKey('user.id'))
    problem = db.Column(db.Integer, db.ForeignKey('problem.id'))
    event = db.Column(db.String(100))
    comment = db.Column(db.Text)

class TestLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime)
    user = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_number = db.Column(db.Integer)
    problems = db.Column(db.Text)

class Trajectory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topics = db.Column(db.Text)
    comment = db.Column(db.Text)

@login_manager.user_loader
def user_loader(id):
    return User.query.filter_by(id = id).first()

@login_manager.request_loader
def request_loader(request):
    user = User.query.filter_by(username = request.form.get('username')).first()
    if user is None:
        return

    user.is_authenticated = False
    if 'pw' in request.form and hasattr(user,'pwdhash') and md5(request.form['pw']) == user.pwdhash:
        user.is_authenticated = True

    return user

@app.route('/add_user', methods=['GET','POST'])
@flask_login.login_required
def calc_md5():
    if flask_login.current_user.username != tpbeta_superuser_username:
        return 'Only supervisor can add users.'

    if request.method == 'GET':
        return '''
               <form action='add_user' method='POST'>
                <input type='text' name='username' id='username' placeholder='логин'></input>
                <input type='text' name='name' id='name' placeholder='Фамилия Имя Отчество'></input>
                <input type='password' name='pw' id='pw' placeholder='предлагаемый пароль'></input>
                <input type='submit' name='submit'></input>
               </form>
               '''

    user = User.query.filter_by(username = request.form['username']).first()
    if user is not None:
        return 'Такой пользователь уже существует'

    u = User()
    u.username = request.form['username']
    u.firstname, u.lastname, u.middlename = parse_person_name(request.form['name'])
    u.pwdhash = md5(request.form['pw'])
    db.session.add(u)
    db.session.commit()

    return 'Пользователь {0} успешно добавлен'.format(u.username)


@app.route('/login', methods=['GET', 'POST'])
def login():
    already_logged = False
    login_successful = False
    bad_login = False
    username = ''
    if request.method == 'GET':
        if flask_login.current_user is not None and hasattr(flask_login.current_user, 'username'):
            already_logged = True
            username = flask_login.current_user.username
    else:
        user = User.query.filter_by(username = request.form['username']).first()
        if user is not None and hasattr(user, 'pwdhash') and md5(request.form['pw']) == user.pwdhash:
            flask_login.login_user(user)
            login_successful = True
            username = request.form['username']
        else:
            bad_login = True

    return render_template(
        'login.html',
        already_logged = already_logged,
        login_successful = login_successful,
        bad_login = bad_login,
        username = username)

@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))

@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login'))

@app.route('/group/<int:group_number>/test/<int:test_number>/ajax_update', methods = ['POST'])
@flask_login.login_required
def ajax_update_group_table(group_number, test_number):
    if flask_login.current_user.username not in teachers:
        return jsonify(result="You need to be logged in as a teacher to update test results")

    data = {}
    for s in request.json:
        if s.startswith('learner'):
            data[int(s[len('learner'):])] = request.json[s].split(',')

    num_updated_items = 0
    num_added_items = 0
    result_translator = { '∅' : 'SEEN' , '□' : 'TRIED', '◩' : 'ALMOST', '■' : 'SUCCESS'}
    for log in TestLog.query.filter_by(test_number = test_number).all():
        if log.user in data:
            problem_numbers = map(int, log.problems.split(','))
            for n,r in zip(problem_numbers,data[log.user]):
                if r in result_translator:
                    h = History.query.filter_by(problem = n, user = log.user, comment = 'TEST{0}'.format(test_number)).first()
                    if h is None:
                        h = History()
                        if result_translator[r] == 'ALMOST':
                            h.datetime = datetime.now()
                        else:
                            h.datetime = log.datetime or datetime(1,1,1)
                        h.comment = 'TEST{0}'.format(test_number)
                        h.user = log.user
                        h.problem = n
                        h.event = result_translator[r]
                        db.session.add(h)
                        num_added_items += 1
                    elif h.event != result_translator[r]:
                        h.event = result_translator[r]
                        num_updated_items += 1

    db.session.commit()
    if num_added_items > 0 and num_updated_items > 0:
        return jsonify(result="Успешно добавлены {0} и обновлены {1} отметок".format(num_added_items, num_updated_items))
    if num_updated_items > 0:
        return jsonify(result="Успешно обновлены {0} отметок".format(num_updated_items))
    if num_added_items > 0:
        return jsonify(result="Успешно добавлены {0} отметок".format(num_added_items))
    return jsonify(result="Нечего обновлять")


@app.route('/group/<int:group_number>/test/<int:test_number>/edit')
@flask_login.login_required
def edit_group_table(group_number, test_number):
    if flask_login.current_user.username not in teachers:
        return "Login required for this URL"

    test_log_items = db.session.query(TestLog)\
        .filter(TestLog.test_number == test_number)\
        .join(Learner, Learner.user_id == TestLog.user)\
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id)\
        .filter(AcademicGroup.number == group_number)\
        .all()

    if len(test_log_items) == 0:
        return 'Похоже, тест с таким номером ещё не проводился: о нём нет информации в базе данных.'

    test_history = History.query.filter_by(comment='TEST{0}'.format(test_number))\
        .join(Learner, Learner.user_id == History.user)\
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id)\
        .filter(AcademicGroup.number == group_number)\
        .all()

    items = []
    for log in test_log_items:
        u = User.query.filter_by(id = log.user).first()
        result_translator = {'SEEN' : '∅', 'TRIED' : '□', 'ALMOST' : '◩', 'SUCCESS' : '■'}
        u_history = {h.problem: result_translator[h.event] for h in test_history if h.user == u.id and h.event in result_translator}
        problem_ids = list(map(int, log.problems.split(',')))
        results = [''] * len(problem_ids)
        for i, p in enumerate(problem_ids):
            if p in u_history:
                results[i] = u_history[p]
            else:
                results[i] = str(problem_ids[i])
        items.append(dict(
            name = '{0} {1}'.format(u.lastname,u.firstname),
            id = u.id,
            marks = [
                {   'id': problem_ids[i],
                    'result': results[i]} for i in range(len(results))]))
    max_problems = max( len(x['marks']) for x in items )
    for x in items:
        if len(x['marks']) < max_problems:
            x['marks'] += [''] * (max_problems - len(x['marks']))

    return render_template(
        'result_table_snippet.html',
        user = flask_login.current_user.username,
        group = group_number,
        test = test_number,
        student_results = items,
        problem_labels = list(range(1, max_problems+1)))

@app.route('/problem/<int:problem_id>')
@flask_login.login_required
def show_problem(problem_id):
    if flask_login.current_user.username not in teachers:
        if not db.session.query(History.id).filter(History.user == flask_login.current_user.id, History.problem == problem_id, History.event.in_(['SEEN', 'TRIED', 'ALMOST', 'SUCCESS'])).first():
            return 'Просматривать задачу могут только преподаватели либо ранее решавшие её студенты.'

    problem = Problem.query.filter_by(id=problem_id).first()
    if problem is None:
        return 'Задача с id {0} не найдена.'.format(problem_id)

    variation = None
    if request.args.get('variation'):
        variation = int(request.args.get('variation'))

    if flask_login.current_user.username in teachers:
        comments = ProblemComment.query.filter_by(problem_id=problem_id).all()
    else:
        comments = ProblemComment.query.filter(ProblemComment.problem_id==problem_id, ProblemComment.author.in_([1,1049,1050]+[flask_login.current_user.id])).all()

    comments_processed = []
    for c in sorted(comments, key=lambda x: x.datetime):
        comments_processed.append({
            'text' : c.text,
            'author' : db.session.query(User.username).filter(User.id == c.author).first()[0],
            'datetime' : c.datetime.isoformat().replace('T', ' ')
        })

    return render_template('single_problem.html',
        problem_statement = latex_to_html(problem.statement, variation),
        comments = comments_processed,
        problem_id = problem_id)

@app.route('/problem/<int:problem_id>/newcomment', methods = ['POST'])
@flask_login.login_required
def new_problem_comment(problem_id):
    if flask_login.current_user.username not in teachers:
        if not db.session.query(History.id).filter(History.user == flask_login.current_user.id, History.problem == problem_id, History.event.in_(['SEEN', 'TRIED', 'ALMOST', 'SUCCESS'])).first():
            return jsonify(result='Комментировать задачу могут только преподаватели либо ранее решавшие её студенты.')

    c = ProblemComment()
    c.problem_id = problem_id
    c.datetime = datetime.now()
    c.text = request.json['comment'];
    c.author = flask_login.current_user.id
    db.session.add(c)
    db.session.commit()
    return jsonify(result='Комментарий успешно добавлен. Обновите страницу для отображения.');

@app.route('/problems/<topic>')
@flask_login.login_required
def show_problems(topic):
    if flask_login.current_user.username not in teachers:
        return 'Только преподаватели имеют доступ к этой странице'

    problems = None
    if topic == 'all':
        problems = Problem.query.all()
        show_filter_prompt = True
    else:
        show_filter_prompt = False
        if not topic.isdecimal():
            topic = db.session.query(Topic.id).filter(Topic.topic == topic).first()
            if topic:
                topic = str(topic[0])
        if topic:
            problems = Problem.query.filter_by(topics = topic).all()

    if problems is None:
        return 'Невозможно загрузить задачи для отображения'
    template_problems = []
    for p in problems:
        if p.topics and p.topics.split(',')[0] and p.topics.split(',')[0].isdecimal():
            t_id = int(p.topics.split(',')[0])
            topic = db.session.query(Topic.topic).filter(Topic.id==t_id).first()
        else:
            topic = ''
        if topic:
            topic = topic[0]
        else:
            topic = ''
        template_problems.append( {
            'topic' : topic,
            'edit_url' : url_for('edit_problem',problem_id=p.id),
            'id' : p.id,
            'statement' : latex_to_html(p.statement),
            'clones' : p.clones })

    return render_template(
        'multiple_problems.html',
        problems = template_problems,
        show_filter_prompt = show_filter_prompt)


@app.route('/problem/new')
@flask_login.login_required
def new_problem():
    if flask_login.current_user.username not in teachers:
        return "Создавать задачи могут только преподаватели."

    existing_problem_id = db.session.query(Problem.id).filter(Problem.statement.like('(Условие задачи)%')).first()
    if existing_problem_id:
        return redirect(url_for('edit_problem',problem_id=existing_problem_id[0]))

    p = Problem()
    p.statement = '(Условие задачи)'
    p.creator = flask_login.current_user.id
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('edit_problem',problem_id=p.id))


@app.route('/problem/<int:problem_id>/edit')
@flask_login.login_required
def edit_problem(problem_id):
    if flask_login.current_user.username not in teachers:
        return "Login required for this URL"

    p = Problem.query.filter_by(id=problem_id).first()
    if p is None:
        return 'Задача с id {0} не найдена.'.format(problem_id)
    if p.topics and p.topics.split(',')[0].isdecimal():
        topic = Topic.query.filter_by(id=int(p.topics.split(',')[0])).first().topic
    else:
        topic = ''

    return render_template('single_problem_edit.html',
        problem_statement=p.statement,
        problem_id = problem_id,
        topic = topic,
        clones = p.clones)

@app.route('/problem/<int:problem_id>/update', methods = ['POST'])
@flask_login.login_required
def update_problem(problem_id):
    if flask_login.current_user.username not in teachers:
        return jsonify(result="You need to be logged in as a teacher to update problem database")

    p = Problem.query.filter_by(id=problem_id).first();
    p.statement = request.json['statement'];
    p.last_modified = datetime.now()
    clones = set(request.json['clones'].strip().split(','))
    if all(x.isdecimal() for x in clones):
        p.clones = ','.join(str(x) for x in sorted(int(y) for y in clones))
    else:
        p.clones = ''
    p.topics = ''
    if request.json['topic']:
        r = db.session.query(Topic.id).filter(Topic.topic==request.json['topic']).first()
        if r:
            p.topics = str(r[0])

    db.session.commit()

    return jsonify(result='Задача успешно обновлена.', processedText = latex_to_html(p.statement));


@app.route('/trajectory/edit', methods=['GET','POST'])
@flask_login.login_required
def edit_trajectory():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to update trajectory"

    if request.method == 'GET':
        r = list(map(int, Trajectory.query.first().topics.split('|')))
        return render_template('trajectory.html', topics = [db.session.query(Topic.topic).filter(Topic.id==i).first()[0] for i in r])

    num_added_new_topics = 0
    if request.json['newtopics']:
        new_topic_names = request.json['newtopics'].split('|')
        for t in new_topic_names:
            if db.session.query(Topic.id).filter(Topic.topic==t).first() is None:
                topic = Topic()
                topic.topic = t
                db.session.add(topic)
                num_added_new_topics += 1

    topic_names = request.json['topics'].split('|')
    r = '|'.join(str(db.session.query(Topic.id).filter(Topic.topic==t).first()[0]) for t in topic_names)
    Trajectory.query.first().topics = r
    db.session.commit()

    if num_added_new_topics > 0:
        return jsonify(result='Траектория успешно обновлена; добавлено {0} новых тем.'.format(num_added_new_topics))
    return jsonify(result='Траектория успешно обновлена.')

@app.route('/autocomplete/topics', methods=['GET'])
def autocomplete_topics():
    search = request.args.get('q')
    query = db.session.query(Topic.topic).filter(Topic.topic.like('%' + str(search) + '%'))
    return jsonify(matching_results=[itm[0] for itm in query.all()])

@app.route('/latex_to_html', methods=['POST'])
@flask_login.login_required
def preprocess_latex_text():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher"
    if request.json and 'text' in request.json and request.json['text']:
        return jsonify(result = latex_to_html(request.json['text']))
    return jsonify(result = '')


@app.route('/test/view/<int:group_number>/<int:test_number>', methods=['GET','POST'])
@flask_login.login_required
def view_test(group_number, test_number):
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to view tests"

    users = db.session.query(User.id, User.firstname, User.lastname)\
        .join(Learner, Learner.user_id == User.id)\
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id)\
        .filter(AcademicGroup.number == group_number)\
        .all()
    if len(users) == 0:
        return 'Нет данных о студентах из группы {0}'.format(group_number)

    users = { u[0] : '{0} {1}'.format(u[1], u[2]) for u in users }

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
        user_problems = {p.id : p.statement for p in Problem.query.filter(Problem.id.in_(user_problem_ids)).all()}
        problem_sets[user_id] = [ {'id': id, 'text': latex_to_html(user_problems[id])} for id in user_problem_ids ]

    return render_template(
        'test_printout.html',
        problems = problem_sets,
        users = users,
        group = group_number,
        suggested_test_number = test_number,
        date = test_date.isoformat()[:10],
        log_info = log_info,
        view_only = True)

@app.route('/test/create/<int:group_number>', methods=['GET','POST'])
@flask_login.login_required
def create_test(group_number):
    max_problems = int(request.args.get('max', 5))
    current_variation = defaultdict(int)

    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to create tests"

    if request.method == 'POST':
        if not request.json or 'test_number' not in request.json:
            return jsonify(result = 'Ошибка сохранения.')
        test_number = int(request.json['test_number'])
        test_date = datetime(*map(int, request.json['test_date'].split('-')))
        for s in request.json['problems'].split('|'):
            s_user, s_problems = s.split(':')
            if not s_user or db.session.query(TestLog.id).filter(TestLog.test_number == int(test_number), TestLog.user == int(s_user)).first():
                db.session.rollback()
                return jsonify(result = 'Ошибка: в базе данных уже есть запись о тесте {0} у пользователя #{1}'.format(test_number, s_user))
            testlog = TestLog()
            testlog.test_number = test_number
            testlog.datetime = test_date
            testlog.user = int(s_user)
            testlog.problems = s_problems
            db.session.add(testlog)
        db.session.commit()
        return jsonify(result = 'Информация о тесте сохранена.')

    users = db.session.query(User)\
        .join(Learner, Learner.user_id == User.id)\
        .join(AcademicGroup, Learner.academic_group == AcademicGroup.id)\
        .filter(AcademicGroup.number == group_number)\
        .all()

    suggested_test_number = max(x[0] for x in db.session.query(TestLog.test_number).filter(TestLog.user == users[0].id).all()) + 1

    users = { u.id : '{0} {1}'.format(u.firstname, u.lastname) for u in users }

    event_to_number = { 'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3 }
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

    log_info = ''
    # if flask_login.current_user.username == tpbeta_superuser_username:
    #     log_info = '; '.join(str(cid) + ' : ' +  ','.join(str(t) for t in clones[cid]) for cid in clones)

    problem_sets = dict()

    for user_id in users:
        user_history = { i: -1 for i in problem_ids }
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
                'text': latex_to_html(p.statement, variation=current_variation[p.id])
            })
            current_variation[p.id] += 1

    return render_template(
        'test_printout.html',
        problems = problem_sets,
        users = users,
        group = group_number,
        suggested_test_number = suggested_test_number,
        date = date.today().isoformat(),
        max_problems = max_problems,
        log_info = log_info)


@app.route('/learnerdashboard')
@flask_login.login_required
def learner_dashboard():
    if not flask_login.current_user or not hasattr(flask_login.current_user, 'username'):
        return redirect(url_for('login'))
    username = flask_login.current_user.username
    logs = TestLog.query.filter_by(user = flask_login.current_user.id).all()
    if len(logs) == 0:
        return 'Не найдено записей о результатах контрольных работ пользователя <em>{0}</em>'.format(username)
    return 'Найдены записи о тестах, проводившихся в следующие даты:<br>' + '<br>'.join( '<a href="{1}">{0}</a>'.format(log.datetime.isoformat()[:10], url_for('test_results', test_number = log.test_number )) for log in logs)

@app.route('/learnerdashboard/test/<int:test_number>', methods = ['GET'])
@flask_login.login_required
def test_results(test_number):
    user_id = flask_login.current_user.id
    if ('user' in request.args) and flask_login.current_user.username in teachers:
        user_id = int(request.args['user'])

    log = TestLog.query.filter_by(user = user_id, test_number = test_number).first()
    if not log:
        return "Не найдена информация о тесте"
    test_history = History.query.filter_by(user = user_id, comment = 'TEST{0}'.format(test_number)).all()
    result_translator = {'SEEN' : '∅', 'TRIED' : '□', 'ALMOST' : '◩', 'SUCCESS' : '■'}
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
        name = db.session.query(User.username).filter(User.id == user_id).first()[0],
        test = test_number,
        marks = marks
    )

@app.route('/learnerdashboard/trajectory', methods=['GET'])
@flask_login.login_required
def trajectory_progress():
    user_id = flask_login.current_user.id
    if ('user' in request.args) and flask_login.current_user.username in teachers:
        user_id = int(request.args['user'])

    event_to_number = { 'SEEN': 0, 'TRIED': 1, 'ALMOST': 2, 'SUCCESS': 3 }
    number_to_square = {-1 : '□', 0 : '□', 1 : '□', 2 : '◩', 3 : '■'}
    all_topics = Topic.query.all()
    topic_names = { t.id: t.topic for t in all_topics }
    topic_levels = { t.id: t.level for t in all_topics }
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
    user_history = { i: -1 for i in problem_ids }
    review_requests = dict()
    for h in user_history_items:
        if h.event == 'REVIEW_REQUEST':
            review_requests[h.problem] = h
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
            'result' : number_to_square[trajectory_results[i]],
            'witness' : result_witnesses[i],
            'status' : ''
        }
        if trajectory_results[i] == 2:
            problem_id = result_witnesses[i]
            h = db.session.query(History.datetime).filter(History.user == user_id, History.problem == problem_id, History.event == 'ALMOST').first()
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
        results = results,
        user = user_id
    )

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
        users = sorted(users, key=lambda u: u.name),
        superuser = (flask_login.current_user.username == tpbeta_superuser_username))

@app.route('/recover_password', methods=['POST'])
@flask_login.login_required
def recover_password():
    if flask_login.current_user.username != tpbeta_superuser_username:
        return jsonify(result = 'Login error')

    if 'user_id' not in request.json:
        return jsonify(result = 'Error')

    user_id = int(request.json['user_id'])
    user = User.query.filter_by(id=user_id).first()

    if not user.email:
        return jsonify(result = 'Невозможно выслать пароль: не указан email.')

    random.seed(str(datetime.now()))
    letters = 'qwertyuiopasdfghjklzxcvbnm1029384756'
    new_password = ''.join(letters[int(random.random()*len(letters))] for _ in range(8))

    msg = Message(  subject = 'Временный пароль к информационной системе по курсу ДС',
                    body = '''Ваше имя пользователя для входа в систему: {0}\nВаш пароль для входа: {1}'''.format(user.username,new_password),
                    recipients = [user.email])
    mail.send(msg)

    user.pwdhash = md5(new_password)
    db.session.commit()

    return jsonify(result = 'Успешно выслан пароль "{0}"'.format(new_password))

@app.route('/corrections', methods=['GET', 'POST'])
@flask_login.login_required
def corrections_interface():
    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to mark corrections"

    if request.method == 'POST':
        if not request.json or 'user' not in request.json or 'problem' not in request.json or 'result' not in request.json:
            return jsonify(result = 'Ошибка сохранения.')
        user = int(request.json['user'])
        problem = int(request.json['problem'])
        result = int(request.json['result'])
        if result == 1:
            new_item = History()
            new_item.user = user
            new_item.problem = problem
            new_item.event = 'SUCCESS'
            new_item.comment = 'CORRECTION'
            new_item.datetime = datetime.now()
            db.session.add(new_item)
            db.session.commit()
            return jsonify(result = 'Задача {0} помечена как зачтённая'.format(problem))
        else:
            item = History.query.filter_by(user=user, problem=problem, event='SUCCESS', comment = 'CORRECTION').first()
            if not item:
                return jsonify(result = 'Задача {0} не найдена среди помеченных зачтённых задач'.format(problem))
            db.session.delete(item)
            db.session.commit()
            return jsonify(result = 'Задача {0} удалена из зачтённых'.format(problem))

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
        latex_project_url = db.session.query(Learner.latex_project_url).filter(Learner.user_id==uid).first()
        if latex_project_url:
            latex_project_url = latex_project_url[0]
        if not latex_project_url:
            latex_project_url = ''
        data.append({
            'id': uid,
            'name': usernames[uid],
            'url': latex_project_url,
            'problems': sorted(({'id': pid, 'result': res} for pid,res in remaining_corrections[uid].items()), key=lambda x: x['id'])
        })
    data.sort( key = lambda x: usernames[x['id']] )
    return render_template('corrections.html', data=data)

@app.route('/review', methods=['POST','GET'])
@flask_login.login_required
def review_interface():
    if request.method == 'POST':
        if not request.json or 'user' not in request.json or 'problem' not in request.json or 'action' not in request.json:
            return jsonify(result = 'Ошибка сохранения')
        user = int(request.json['user'])
        problem = int(request.json['problem'])
        action = request.json['action']
        if action == 'SEND_FOR_REVIEW':
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if h:
                return jsonify(result = 'Запрос на проверку уже был отправлен ранее.')
            h = History()
            h.datetime = datetime.now()
            h.user = user
            h.problem = problem
            h.event = 'REVIEW_REQUEST'
            db.session.add(h)
            db.session.commit()
            return jsonify(result = 'Запрос отправлен')
        elif action == 'RESEND_FOR_REVIEW':
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if not h:
                return jsonify(result = 'Запрос на проверку ранее не отправлялся.')
            tokens = h.comment.split('|')
            tokens[1] = 'REVIEW_REQUEST_RESENT'
            h.comment = '|'.join(tokens[:2])
            db.session.commit()
            return jsonify(result = 'Запрос отправлен')
        elif action == 'TAKE_FOR_REVIEW' and flask_login.current_user.username in teachers:
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            h.comment = flask_login.current_user.username
            db.session.commit()
            return jsonify(result = 'Успешно изменён проверяющий для задачи', reviewer = flask_login.current_user.username)
        elif action == 'DELETE_REQUEST' and flask_login.current_user.username in teachers:
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            db.session.delete(h)
            db.session.commit()
            return jsonify(result = 'Запрос на проверку закрыт')
        elif action == 'SEND_FOR_REWORK' and flask_login.current_user.username in teachers:
            h = History.query.filter_by(user=user, problem=problem, event='REVIEW_REQUEST').first()
            if 'comment' in request.json:
                comment = request.json['comment']
            else:
                comment = 'Проверяющий {0} затребовал доработку решения'.format(flask_login.current_user.username)
            h.comment = '{0}|{1}|{2}'.format(flask_login.current_user.username, 'REWORK_REQUIRED', comment)
            db.session.commit()
            return jsonify(result = 'Запрос на доработку отправлен')
        elif action == 'REMOVE_EXPIRED':
            if flask_login.current_user.username != tpbeta_superuser_username:
                return jsonify(result = 'Только суперпользователь может выполнять этот запрос')
            n_deleted = 0
            n_close_to_expiration = 0
            for i in History.query.filter_by(event='ALMOST').all():
                if db.session.query(History.id).filter(History.user==i.user, History.problem==i.problem, History.event.in_(['SUCCESS','REVIEW_REQUEST'])).first():
                    continue
                if not i.datetime:
                    continue
                delta = datetime.now() - i.datetime
                if delta.days <= 21:
                    continue
                if delta.days > 18:
                    n_close_to_expiration += 1
                db.session.delete(i)
                n_deleted += 1
            db.session.commit()
            return jsonify(result = 'Удалено {0} просроченных заданий; {1} заданий близки к просроченным'.format(n_deleted, n_close_to_expiration))

    if flask_login.current_user.username not in teachers:
        return "You need to be logged in as a teacher to mark corrections"
    history_items = History.query.filter_by(event='REVIEW_REQUEST').all()
    items = []
    for h in history_items:
        username = db.session.query(User.username).filter(User.id == h.user).first()[0]
        reviewer = ''
        state = 'Ожидает проверки с {0}'.format(h.datetime)
        formal_state = 'PENDING'

        if h.comment:
            tokens = h.comment.split('|', maxsplit=2)
            reviewer = tokens[0]
            if len(tokens) > 1:
                formal_state = tokens[1]
                if formal_state == 'REWORK_REQUIRED':
                    state = 'Находится на доработке'
                if formal_state == 'REVIEW_REQUEST_RESENT':
                    state = 'Студент доработал решение и отправил запрос на перепроверку'

        latex_project_url = db.session.query(Learner.latex_project_url).filter(Learner.user_id==h.user).first()
        if latex_project_url:
            latex_project_url = latex_project_url[0]
        if not latex_project_url:
            latex_project_url = ''

        items.append({
            'username' : username,
            'url': latex_project_url,
            'user_id' : h.user,
            'problem': h.problem,
            'reviewer': reviewer,
            'state': state,
            'formal_state' : formal_state
        })
    return render_template('review_requests_list.html',
        items = items,
        show_remove_expired_ui = (flask_login.current_user.username == tpbeta_superuser_username))


@app.route('/topic_stats')
def show_topic_stats():
    trajectory_topic_ids = list(map(int, Trajectory.query.first().topics.split('|')))
    topics = Topic.query.filter( Topic.id.in_(trajectory_topic_ids) )

    data = []
    for topic in topics:
        topic_problem_ids = [x[0] for x in db.session.query(Problem.id).filter(Problem.topics == str(topic.id)).all()]
        history_items_users = [x[0] for x in db.session.query(History.user).filter(History.problem.in_(topic_problem_ids), History.event.in_(['SUCCESS', 'ALMOST'])).all()]
        user_progress = defaultdict(int)
        for u in history_items_users:
            user_progress[u] += 1

        qty_in_trajectory = sum(1 for i in trajectory_topic_ids if i == topic.id)
        data.append({
            'topic' : topic.topic,
            'qty_in_trajectory' : qty_in_trajectory,
            'num_problems' : len(topic_problem_ids),
            'num_tries' : db.session.query(History.id).filter(History.problem.in_(topic_problem_ids)).count(),
            'num_successful_tries' : len(history_items_users),
            'num_clears' : sum( 1 for u in user_progress if user_progress[u] == qty_in_trajectory )
        })

    return render_template('problem_stats.html',data=data)


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
            'text' : c.text if len(c.text) < 1000 else c.text[:1000] + '…',
            'author_username' : usernames[c.author],
            'author_id' : c.author,
            'datetime' : c.datetime.isoformat().replace('T', '<br>').replace('-','&#8209;'),
            'problem_id' : c.problem_id
        })

    return render_template('view_all_comments.html', comments = comments_processed)


@app.route('/')
def root():
    if not flask_login.current_user or not hasattr(flask_login.current_user, 'username'):
        mode = ''
    elif flask_login.current_user.username in teachers:
        mode = 'teacher'
    else:
        mode = 'learner'

    return render_template('landing.html', mode = mode)
