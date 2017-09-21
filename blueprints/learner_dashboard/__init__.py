from flask import Blueprint, render_template, request, abort, jsonify
import flask_login

from blueprints.models import \
    db, \
    ExposureContent, \
    Topic, \
    ProblemSetContent, \
    Exposure, \
    Participant, \
    Role, \
    UserCourseTrajectory, \
    ExposureGrading, \
    ExposureGradingResult, \
    ProblemStatusInfo, \
    ProblemStatus, \
    TrajectoryContent, \
    ProblemTopicAssignment, \
    History, \
    ParticipantExtraInfo

from datetime import datetime, timedelta
from collections import defaultdict
from json import loads as parse_json


learner_dashboard_blueprint = Blueprint('learner_dashboard', __name__, template_folder='templates')


@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard', methods=['GET'])
@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard/', methods=['GET'])
@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard/user-<int:user_id>', methods=['GET'])
@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard/user-<int:user_id>/', methods=['GET'])
@flask_login.login_required
def view_learner_dashboard(course_id, user_id=None):
    if not user_id:
        user_id = flask_login.current_user.id

    if flask_login.current_user.id != user_id and not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['ADMIN', 'INSTRUCTOR'])
            ).first():
        abort(403)
    elif flask_login.current_user.id == user_id and not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['LEARNER'])
            ).first():
        abort(404)

    exposures = []
    for exposure_id, exposure_timestamp, problem_set_id in db.session.query(
                Exposure.id,
                Exposure.timestamp,
                ExposureContent.problem_set_id
            ).filter(
                ExposureContent.exposure_id == Exposure.id,
                Exposure.course_id == course_id,
                ExposureContent.user_id == user_id
            ).order_by(
                Exposure.timestamp
            ).all():

        problem_set_grading_results = \
            db.session.query(
                ProblemSetContent.problem_id,
                ProblemStatusInfo.icon
            ).filter(
                ExposureGrading.exposure_id == exposure_id,
                ExposureGradingResult.exposure_grading_id == ExposureGrading.id,
                ExposureGradingResult.user_id == user_id,
                ExposureGradingResult.problem_set_id == problem_set_id,
                ExposureGradingResult.problem_id == ProblemSetContent.problem_id,
                ProblemSetContent.problem_set_id == problem_set_id,
                ExposureGradingResult.problem_status_id == ProblemStatusInfo.id,
                ProblemStatusInfo.code != 'NOT_EXPOSED',
            ).order_by(
                ProblemSetContent.sort_key
            ).all()

        exposures.append({
            'id': exposure_id,
            'date': exposure_timestamp.strftime('%Y-%m-%d'),
            'problem_set_id': problem_set_id,
            'grading_results': [{
                'problem_id': problem_id,
                'icon': icon
            } for problem_id, icon in problem_set_grading_results]
        })

    trajectory_id = db.session.query(
        UserCourseTrajectory.trajectory_id
    ).filter(
        UserCourseTrajectory.user_id == user_id,
        UserCourseTrajectory.course_id == course_id
    ).scalar()

    topic_ids = set(x for (x,) in db.session.query(TrajectoryContent.topic_id).filter(TrajectoryContent.trajectory_id == trajectory_id).all())

    problems_by_topic = defaultdict(set)
    for pta in ProblemTopicAssignment.query.filter(
        ProblemTopicAssignment.topic_id.in_(topic_ids)
    ).all():
        problems_by_topic[pta.topic_id].add(pta.problem_id)

    user_problems_solved = set()
    problems_on_revision = set()
    for problem_id, code in db.session.query(
            ProblemStatus.problem_id,
            ProblemStatusInfo.code
        ).filter(
            ProblemStatus.user_id == user_id,
            ProblemStatus.status_id == ProblemStatusInfo.id,
            ProblemStatusInfo.code.in_(['SOLUTION_NEEDS_REVISION', 'SOLUTION_CORRECT'])
        ).all():
        user_problems_solved.add(problem_id)
        if code == 'SOLUTION_NEEDS_REVISION':
            problems_on_revision.add(problem_id)

    user_problems_remaining_for_counting = set(user_problems_solved)

    trajectory = []
    for topic_id, topic_title, topic_code in db.session\
            .query(
                Topic.id,
                Topic.title,
                Topic.code
            )\
            .filter(
                TrajectoryContent.trajectory_id == trajectory_id,
                Topic.id == TrajectoryContent.topic_id
            )\
            .order_by(
                TrajectoryContent.sort_key
            )\
            .all():

        solved_problems_for_topic = user_problems_remaining_for_counting & problems_by_topic[topic_id]
        if solved_problems_for_topic:
            problem_id = next(iter(solved_problems_for_topic))
            user_problems_remaining_for_counting.remove(problem_id)
        else:
            problem_id = None

        trajectory.append({
            'topic_id': topic_id,
            'topic_title': topic_title,
            'topic_code': topic_code,
            'problem_id': problem_id,
            'is_on_revision': problem_id in problems_on_revision
        })

    revisions = []
    for (problem_id,) in db.session.query(
                ProblemStatus.problem_id
            ).filter(
                ProblemStatus.user_id == user_id,
                ProblemStatus.status_id == ProblemStatusInfo.id,
                ProblemStatusInfo.code == 'SOLUTION_NEEDS_REVISION'
            ).all():
        user_problem_history = History.query.filter(
            History.problem_id == problem_id,
            History.user_id == user_id,
            History.event.in_([
                'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING',
                'SENT_FOR_REVISION',
                'LEARNER_SENT_REVIEW_REQUEST'
            ])
        ).order_by(
            History.datetime.desc()
        ).first()

        event_date = user_problem_history.datetime.strftime('%Y-%m-%d')
        reviewer_comment = ''

        time_left_for_submission = (user_problem_history.datetime + timedelta(days=10)) - datetime.now()
        if time_left_for_submission.total_seconds() < 7200:
            time_left_info = 'На отправку решения на проверку осталось менее {} <strong>минут</strong>.'.format(
                int(time_left_for_submission.total_seconds() / 60)
            )
        else:
            time_left_info = 'На отправку решения на проверку осталось менее {} часов.'.format(
                int(time_left_for_submission.total_seconds() / 3600)
            )
        submission_allowed = time_left_for_submission > timedelta(0)

        if user_problem_history.event == 'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING':
            review_status = 'Задача была отправлена на дорешку в ходе проверки выдачи {}. {}'.format(
                event_date,
                time_left_info
            )
            reviewer_comment = ''
        elif user_problem_history.event == 'SENT_FOR_REVISION':
            review_status = 'Решение было отправлено проверяющим на корректировку {}. {}'.format(
                event_date,
                time_left_info
            )
            reviewer_comment = user_problem_history.comment
        elif user_problem_history.event == 'LEARNER_SENT_REVIEW_REQUEST':
            submission_allowed = False
            review_status = 'Ваше решение находится на проверке с {}.'.format(event_date)

        revisions.append({
            'problem_id': problem_id,
            'review_status': review_status,
            'submission_allowed': submission_allowed,
            'reviewer_comment': reviewer_comment
        })

    sharelatex_project_id = None
    extra_info = db.session.query(ParticipantExtraInfo.json).filter(
        ParticipantExtraInfo.course_id == course_id,
        ParticipantExtraInfo.user_id == user_id
    ).first()
    if extra_info and extra_info[0]:
        extra_info = parse_json(extra_info[0])
        sharelatex_project_id = extra_info.get('sharelatex_project_id')

    return render_template(
        'view_learner_dashboard.html',
        exposures=exposures,
        trajectory=trajectory,
        revisions=revisions,
        user_id=user_id,
        course_id=course_id,
        sharelatex_project_id=sharelatex_project_id
    )
