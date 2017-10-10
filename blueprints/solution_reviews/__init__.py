from flask import Blueprint, render_template, request, abort, jsonify, current_app
from flask_mail import Message
import flask_login

from blueprints.models import \
    db, \
    User, \
    Participant, \
    Role, \
    ProblemStatusInfo, \
    ProblemStatus, \
    History, \
    ExtraData

from datetime import datetime, timedelta
from json import dumps as to_json_string
from json import loads as parse_json

from text_tools import latex_to_html


solution_reviews_blueprint = Blueprint('solution_reviews', __name__, template_folder='templates')


def notify_user(user_id, problem_id, status):
    email = db.session.query(User.email).filter(User.id == user_id).scalar()
    msg = Message(subject=f'Дискретные структуры: дорешка задачи #{problem_id}',
                  body=
f'''{status}
Письмо сформировано автоматически; пожалуйста, не отвечайте на него. При необходимости напишите лично проверяющему.''',
                  recipients=[email])
    current_app.config['MAILER'].send(msg)


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
                    'take_for_review',
                    'accept_solution',
                    'send_for_revision',
                    'submit_for_review',
                    'load_review_history'
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

        if action == 'load_review_history':
            review_history = db.session.query(
                History.event,
                History.comment,
                History.datetime
            ).filter(
                History.problem_id == json.get('problem_id'),
                History.user_id == json.get('user_id'),
                History.event.in_([
                    'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING',
                    'SENT_FOR_REVISION',
                    'LEARNER_SENT_REVIEW_REQUEST',
                    'TAKEN_FOR_REVIEW',
                    'SOLUTION_ACCEPTED'
                ])
            ).order_by(
                History.datetime.desc()
            ).all()

            descriptions = {
                'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING': 'Задача отправлена с контрольной на дорешку',
                'SENT_FOR_REVISION': 'Преподаватель отправил решение на переделку',
                'LEARNER_SENT_REVIEW_REQUEST': 'Студент отправил решение на проверку',
                'TAKEN_FOR_REVIEW': 'Преподаватель взял решение на проверку',
                'SOLUTION_ACCEPTED': 'Решение зачтено'
            }

            history = []
            for event, comment, timestamp in review_history:
                if comment and comment.strip():
                    comment = latex_to_html(comment)
                    history.append(
                        f'{timestamp.strftime("%Y-%m-%d")}: {descriptions[event]} с комментарием “{comment}”'
                    )
                else:
                    history.append(f'{timestamp.strftime("%Y-%m-%d")}: {descriptions[event]}')

            return jsonify(history=history)

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

        if json.get('notify_learner'):
            if action == 'accept_solution':
                notify_user(
                    h.user_id,
                    h.problem_id,
                    f'Решение зачтено с комментарием “{latex_to_html(h.comment)}”'
                )
            elif action == 'send_for_revision':
                notify_user(
                    h.user_id,
                    h.problem_id,
                    f'Решение отправлено на доработку с комментарием “{latex_to_html(h.comment)}”. Крайний срок см. в личном кабинете.'
                )

        return jsonify(result='Изменения успешно сохранены')

    if current_user_role not in ['ADMIN', 'INSTRUCTOR', 'GRADER']:
        abort(403)

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

        sharelatex_project_id = db.session.query(
            ExtraData.value
        ).filter(
            ExtraData.user_id == user_id,
            ExtraData.course_id == course_id,
            ExtraData.key == 'sharelatex_project_id'
        ).first()
        sharelatex_project_id = sharelatex_project_id and sharelatex_project_id[0]

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