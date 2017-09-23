from flask import Blueprint, render_template, request, abort, jsonify, redirect, url_for
from blueprints.models import \
    db, \
    Role, \
    Problem, \
    Participant, \
    ProblemTopicAssignment, \
    Topic, \
    Course, \
    ExposureGrading,\
    Exposure,\
    ExposureGradingResult
from text_tools import process_problem_statement
import flask_login

problems_blueprint = Blueprint('problems', __name__, template_folder='templates')


@problems_blueprint.route('/problems/all', methods=['GET'])
@problems_blueprint.route('/problems/', methods=['GET'])
@problems_blueprint.route('/problems', methods=['GET'])
@problems_blueprint.route('/problem-<int:problem_id>/', methods=['GET'])
@problems_blueprint.route('/problem-<int:problem_id>', methods=['GET'])
def view_problems(problem_id=None):
    (role_code,) = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == flask_login.current_user.id,
        Role.id == Participant.role_id
    ).first()

    if role_code == 'LEARNER':
        return redirect(url_for('problems.print_problem', course_id=2, problem_id=problem_id))

    if role_code not in ['INSTRUCTOR', 'ADMIN']:
        abort(403)
    return render_template('view_problems.html', problem_id=problem_id)


@problems_blueprint.route('/course-<int:course_id>/problem-<int:problem_id>/print', methods=['GET'])
def print_problem(course_id, problem_id):
    user_id = flask_login.current_user.id
    role_code = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == user_id,
        Participant.course_id == course_id,
        Role.id == Participant.role_id
    ).scalar()
    problem = None
    if role_code == 'LEARNER':
        problem = Problem.query.filter(
            Problem.id == problem_id,
            ExposureGradingResult.user_id == user_id,
            ExposureGradingResult.problem_id == problem_id,
            ExposureGradingResult.exposure_grading_id == ExposureGrading.id,
            ExposureGrading.exposure_id == Exposure.id,
            Exposure.course_id == course_id
        ).first()
    elif role_code in ['ADMIN', 'GRADER', 'INSTRUCTOR']:
        problem = Problem.query.filter(Problem.id == problem_id).first()

    if not problem:
        abort(404)

    return render_template(
        'print_problem.html',
        problem_id=problem_id,
        problem_statement=process_problem_statement(problem.statement)
    )


@problems_blueprint.route('/api/problems', methods=['POST'])
def api():
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
            Problem.statement
        )

        if json.get('filter'):
            filter_params = json.get('filter')
            if filter_params.get('problem_id'):
                query = query.filter(Problem.id == filter_params.get('problem_id'))
            if filter_params.get('topic_codes'):
                topic_codes = filter_params.get('topic_codes').strip().split()
                query = query.filter(
                    ProblemTopicAssignment.problem_id == Problem.id,
                    ProblemTopicAssignment.topic_id == Topic.id,
                    Topic.code.in_(topic_codes)
                )
            if filter_params.get('problem_statement'):
                statement_filter = filter_params.get('problem_statement')
                query = query.filter(Problem.statement.like('%{}%'.format(statement_filter)))

            if filter_params.get('page_index') is not None and filter_params.get('page_size'):
                page_index = filter_params['page_index'] - 1
                page_size = filter_params['page_size']
                query = query.slice(page_index * page_size, page_index * page_size + page_size)

        data = query.all()

        return jsonify({
            'itemsCount': len(data),
            'data': list(
                {
                    'problem_id': problem_id,
                    'problem_statement_raw': problem_statement,
                    'problem_statement': process_problem_statement(problem_statement),
                    'topic_codes': '\n'.join(x[0] for x in db.session.query(Topic.code).filter(
                        Topic.id == ProblemTopicAssignment.topic_id,
                        ProblemTopicAssignment.problem_id == problem_id
                    ).all())
                }
                for problem_id, problem_statement in data
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
