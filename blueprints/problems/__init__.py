from flask import Blueprint, render_template, request, abort, jsonify
from blueprints.models import db, Role, Problem, Participant, ProblemTopicAssignment, Topic, Course
from text_tools import process_problem_statement
import flask_login

problems_blueprint = Blueprint('problems', __name__, template_folder='templates')

@problems_blueprint.route('/problems/all', methods=['GET'])
@problems_blueprint.route('/problems', methods=['GET'])
def view():
    return render_template('view.html')


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