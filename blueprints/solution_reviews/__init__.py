from flask import Blueprint, render_template, request, abort, jsonify
import flask_login

from blueprints.models import \
    db, \
    User, \
    Participant, \
    Role, \
    ProblemStatusInfo, \
    ProblemStatus, \
    History, \
    ParticipantExtraInfo

from operator import attrgetter
from datetime import datetime, timedelta
from json import dumps as to_json_string
from json import loads as parse_json
from collections import defaultdict


solution_reviews_blueprint = Blueprint('solution_reviews', __name__, template_folder='templates')


@solution_reviews_blueprint.route('/course-<int:course_id>/solution_reviews/', methods=['GET', 'POST'])
@solution_reviews_blueprint.route('/course-<int:course_id>/solution_reviews', methods=['GET', 'POST'])
def view_solution_review_requests(course_id):
    current_user_role = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == course_id,
        Participant.role_id == Role.id
    ).scalar()

    if request.method == 'POST':
        json = request.get_json()
        if not json:
            abort(400)
        action = json.get('action')
        if not (current_user_role in ['ADMIN', 'INSTRUCTOR', 'GRADER']
                and action in [
                    'take_for_review', 'accept_solution', 'send_for_revision', 'submit_for_review'
                ]
                or current_user_role == 'LEARNER' and action == 'submit_for_review'):
            abort(400)

        if current_user_role == 'LEARNER':
            user_id = flask_login.current_user.id
        else:
            user_id = json.get('user_id')

        if json.get('action') == 'submit_for_review':
            json = request.get_json()
            h = History()
            h.user_id = user_id
            h.problem_id = json.get('problem_id')
            h.datetime = datetime.now()
            h.event = 'LEARNER_SENT_REVIEW_REQUEST'
            db.session.add(h)
            db.session.commit()
            return jsonify(result='Запрос на проверку отправлен.')

        grader_username = flask_login.current_user.username
        h = History()
        h.user_id = user_id
        h.problem_id = json.get('problem_id')
        h.datetime = datetime.now()
        h.comment = '{} ({})'.format(json.get('comment', ''), grader_username)

        if action == 'take_for_review':
            h.event = 'TAKEN_FOR_REVIEW',
        elif action == 'accept_solution':
            h.event = 'SOLUTION_ACCEPTED'
            status_id = ProblemStatusInfo.query.filter_by(code='SOLUTION_CORRECT').first().id
            ps = ProblemStatus.query.filter_by(user_id=h.user_id, problem_id=h.problem_id).first()
            ps.status_id = status_id
            ps.timestamp_last_changed = datetime.now()
        elif action == 'send_for_revision':
            h.event = 'SENT_FOR_REVISION'
        else:
            abort(400)

        db.session.add(h)
        db.session.commit()
        return jsonify(result='Изменения успешно сохранены')

    review_requests = []
    for user_id, name_first, name_last, problem_id in db.session.query(
                User.id,
                User.name_first,
                User.name_last,
                ProblemStatus.problem_id
            ).filter(
                ProblemStatus.user_id == User.id,
                ProblemStatus.status_id == ProblemStatusInfo.id,
                ProblemStatusInfo.code == 'SOLUTION_NEEDS_REVISION',
                Participant.user_id == User.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code == 'LEARNER'
            ).all():
        user_problem_history = History.query.filter(
            History.problem_id == problem_id,
            History.user_id == user_id,
            History.event.in_([
                'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING',
                'SENT_FOR_REVISION',
                'LEARNER_SENT_REVIEW_REQUEST',
                'TAKEN_FOR_REVIEW'
            ])
        ).order_by(
            History.datetime.desc()
        ).first()

        event_date = user_problem_history.datetime.strftime('%Y-%m-%d')

        deadline_passed = True
        if user_problem_history.event == 'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING':
            review_status = 'Находится на дорешке с {}.'.format(event_date)
            deadline_passed = (datetime.now() - user_problem_history.datetime) >= timedelta(days=10)
        elif user_problem_history.event == 'SENT_FOR_REVISION':
            review_status = 'Находится на переделке с {}.'.format(event_date)
            deadline_passed = (datetime.now() - user_problem_history.datetime) >= timedelta(days=10)
        elif user_problem_history.event == 'LEARNER_SENT_REVIEW_REQUEST':
            review_status = 'Обучающийся отправил запрос на проверку решения {}.'.format(event_date)
        elif user_problem_history.event == 'TAKEN_FOR_REVIEW':
            review_status = 'Взято на проверку ({}, {}).'.format(user_problem_history.comment, event_date)

        sharelatex_project_id = None
        extra_info = db.session.query(ParticipantExtraInfo.json).filter(
            ParticipantExtraInfo.course_id == course_id,
            ParticipantExtraInfo.user_id == user_id
        ).first()
        if extra_info and extra_info[0]:
            extra_info = parse_json(extra_info[0])
            sharelatex_project_id = extra_info.get('sharelatex_project_id')

        review_requests.append({
            'user_id': user_id,
            'user_name': '{} {}'.format(name_last, name_first),
            'problem_id': problem_id,
            'review_status': review_status,
            'deadline_passed': deadline_passed,
            'sharelatex_project_id': sharelatex_project_id
        })

    return render_template(
        'view_solution_review_requests.html',
        review_requests=to_json_string(review_requests),
        course_id=course_id
    )