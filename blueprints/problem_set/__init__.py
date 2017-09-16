from flask import Blueprint, render_template, request, abort, jsonify, redirect, url_for
from blueprints.models import \
    db, \
    Role, \
    Problem, \
    Participant, \
    ProblemSetExtra, \
    ProblemSet, \
    Course, \
    ProblemSetContent
from text_tools import process_problem_statement, latex_to_html
import flask_login
from datetime import datetime

problem_set_blueprint = Blueprint('problem_sets', __name__, template_folder='templates')


@problem_set_blueprint.route('/problem-set-<int:problem_set_id>/', methods=['GET'])
@problem_set_blueprint.route('/problem-set-<int:problem_set_id>', methods=['GET'])
def view_problem_set(problem_set_id):
    return render_template('view_problem_set.html', problem_set_id=problem_set_id)

@problem_set_blueprint.route('/problem-set-new', methods=['GET'])
def new_problem_set():
    problem_set = ProblemSet()
    problem_set.is_adhoc = False
    problem_set.owner_id = flask_login.current_user.id
    problem_set.timestamp_created = datetime.now()
    db.session.add(problem_set)
    db.session.commit()
    return redirect(url_for('problem_sets.view_problem_set', problem_set_id=problem_set.id))


@problem_set_blueprint.route('/problem-set-<int:problem_set_id>/print/', methods=['GET'])
@problem_set_blueprint.route('/problem-set-<int:problem_set_id>/print', methods=['GET'])
def print_problem_set(problem_set_id):
    return render_template('print_problem_set.html', problem_set_id=problem_set_id)


@problem_set_blueprint.route('/api/problem-set', methods=['POST'])
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
                'problem_set_extra_content_raw': problem_set_content_raw,
                'problem_set_extra_content': latex_to_html(problem_set_content_raw)
            })

        data.sort(key=(lambda x: x['sort_key']))

        return jsonify(data)

    elif action == 'delete':
        item = json.get('item')
        if not item:
            abort(400)
        if item.get('problem_set_extra_id'):
            db.session.delete(
                ProblemSetExtra.query.filter_by(id=item['problem_set_extra_id']).first()
            )
        elif item.get('problem_id'):
            db.session.delete(
                ProblemSetContent.query.filter_by(
                    problem_set_id=problem_set_id,
                    problem_id=item['problem_id']
                ).first()
            )
        else:
            abort(400)
        db.session.commit()
        return jsonify(result='Success')

    elif action == 'insert':
        item = json.get('item')
        if not item:
            abort(400)
        if item.get('problem_id'):
            problem_id = item['problem_id']
            problem = Problem.query.filter_by(id=problem_id).first()

            if (problem and not db.session.query(ProblemSetContent.problem_id).filter(
                        ProblemSetContent.problem_id == problem_id,
                        ProblemSetContent.problem_set_id == problem_set_id
                    ).first()):
                db.session.add(ProblemSetContent(problem_set_id, problem_id, item.get('sort_key', 0)))
                db.session.commit()
                return jsonify({
                    'sort_key': item.get('sort_key', 0),
                    'problem_id': problem.id,
                    'problem_statement_raw': problem.statement,
                    'problem_statement': process_problem_statement(problem.statement)
                })
            else:
                abort(400)
        elif item.get('problem_set_extra_content_raw'):
            pse = ProblemSetExtra()
            pse.problem_set_id = problem_set_id
            pse.content = item.get('problem_set_extra_content_raw')
            pse.sort_key = item.get('sort_key', 0)
            db.session.add(pse)
            db.session.commit()
            item['problem_set_extra_content'] = latex_to_html(pse.content)
            item['problem_set_extra_id'] = pse.id
            return jsonify(item)
        else:
            abort(400)

    elif action == 'update':
        item = json.get('item')
        if not item:
            abort(400)
        if item.get('problem_id'):
            problem_id = item['problem_id']
            psc = ProblemSetContent.query.filter_by(problem_set_id=problem_set_id, problem_id=problem_id).first()
            psc.sort_key = item['sort_key']
            db.session.commit()
            return jsonify(item)

        elif item.get('problem_set_extra_content_raw'):
            pse = ProblemSetExtra.query.filter_by(id=item['problem_set_extra_id']).first()
            pse.content = item.get('problem_set_extra_content_raw')
            pse.sort_key = item.get('sort_key', 0)
            db.session.commit()
            item['problem_set_extra_content'] = latex_to_html(pse.content)
            return jsonify(item)
        else:
            abort(400)

    elif action == 'reorder':
        items = json.get('items')
        if not items:
            abort(400)
        for i, item in enumerate(items):
            problem_id = item.get('problem_id')
            problem_set_extra_id = item.get('problem_set_extra_id')
            if not problem_id and not problem_set_extra_id:
                abort(400)
            if problem_id:
                ProblemSetContent.query.filter_by(
                    problem_id=problem_id,
                    problem_set_id=problem_set_id
                ).first().sort_key = 10 * (i + 1)
            else:
                ProblemSetExtra.query.filter_by(
                    id=problem_set_extra_id
                ).first().sort_key = 10 * (i + 1)
        db.session.commit()
        return jsonify(result='Success')

    abort(400)
