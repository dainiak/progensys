from flask import Blueprint, render_template, request, abort, jsonify
from blueprints.models import \
    db, \
    Role, \
    Problem, \
    Participant, \
    ProblemSet, \
    ProblemSetExtra, \
    Course, \
    ProblemSetContent
from text_tools import process_problem_statement, latex_to_html
import flask_login

problem_set_blueprint = Blueprint('problem_sets', __name__, template_folder='templates')

@problem_set_blueprint.route('/problem-set-<int:problem_set_id>/', methods=['GET'])
@problem_set_blueprint.route('/problem-set-<int:problem_set_id>', methods=['GET'])
def view_problem_set(problem_set_id):
    return render_template('view_problem_set.html', problem_set_id=problem_set_id)

@problem_set_blueprint.route('/api/problem_set', methods=['POST'])
def api():
    if not request.get_json() or not request.get_json().get('action'):
        abort(400)

    if not flask_login.current_user or not flask_login.current_user.username:
        abort(400)

    user_id = flask_login.current_user.id
    course_id = flask_login.current_user.current_course_id or Course.query.first().id
    json = request.get_json()
    action = json.get('action')
    problem_set_id = json.get('problem_set_id')

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
        problems = db.session.query(
            ProblemSetContent.sort_key,
            Problem.id,
            Problem.statement
        ).filter(
            ProblemSetContent.problem_set_id == problem_set_id,
            ProblemSetContent.problem_id == Problem.id
        ).all()
        extras = db.session.query(
            ProblemSetExtra.sort_key,
            ProblemSetExtra.id,
            ProblemSetExtra.content
        ).filter(
            ProblemSetExtra.problem_set_id == problem_set_id
        ).all()

        data = []
        for sort_key, problem_id, problem_statement_raw in problems:
            data.append({
                'sort_key': sort_key,
                'problem_id': problem_id,
                'problem_statement_raw': problem_statement_raw,
                'problem_statement': process_problem_statement(problem_statement_raw)
            })
        for sort_key, problem_set_extra_id, problem_set_content_raw in extras:
            data.append({
                'sort_key': sort_key,
                'problem_set_extra_id': problem_set_extra_id,
                'problem_set_content_raw': problem_set_content_raw,
                'problem_set_content': latex_to_html(problem_set_content_raw)
            })

        data.sort(key=lambda x: x[0])

        return jsonify({
            'itemsCount': len(data),
            'data': list(
                {
                    'problem_id': problem_id,
                    'problem_statement_raw': problem_statement,
                    'problem_statement': process_problem_statement(problem_statement),
                    'topic_codes': topic_codes
                }
                for problem_id, problem_statement, topic_codes in data
            )
        })