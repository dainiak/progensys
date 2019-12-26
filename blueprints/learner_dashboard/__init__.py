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
    ExtraData, \
    User, \
    TopicLevelAssignment

from blueprints.finals import get_final_grade
from datetime import datetime, timedelta
from collections import defaultdict
from json import loads as parse_json

from text_tools import latex_to_html

learner_dashboard_blueprint = Blueprint('learner_dashboard', __name__, template_folder='templates')


@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard', methods=['GET'])
@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard/', methods=['GET'])
@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard/user-<int:user_id>', methods=['GET'])
@learner_dashboard_blueprint.route('/course-<int:course_id>/learner-dashboard/user-<int:user_id>/', methods=['GET'])
@flask_login.login_required
def view_learner_dashboard(course_id, user_id=None):
    if not user_id:
        user_id = flask_login.current_user.id

    role = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == course_id,
        Participant.role_id == Role.id
    ).scalar()

    if ((flask_login.current_user.id != user_id and role not in ['ADMIN', 'INSTRUCTOR'])
            or (flask_login.current_user.id == user_id and role != 'LEARNER')):
        abort(403)

    username = ''
    if role in ['ADMIN', 'INSTRUCTOR']:
        instructor_mode = True
        username = db.session.query(
            User.username
        ).filter(
            User.id == user_id
        ).scalar()
    else:
        instructor_mode = False

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
            ).order_by(
                ExposureGrading.timestamp.desc()
            ).all()

        grading_results = []
        newer_results = set()
        for problem_id, icon in problem_set_grading_results:
            if problem_id in newer_results:
                continue
            grading_results.append({
                'problem_id': problem_id,
                'icon': icon
            })
            newer_results.add(problem_id)

        exposures.append({
            'id': exposure_id,
            'date': exposure_timestamp.strftime('%Y-%m-%d'),
            'problem_set_id': problem_set_id,
            'grading_results': grading_results
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

    topic_levels = dict(db.session.query(
        TopicLevelAssignment.topic_id,
        TopicLevelAssignment.level
    ).filter(
        TopicLevelAssignment.course_id == course_id
    ).all())

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
            'topic_level': topic_levels.get(topic_id),
            'topic_code': topic_code,
            'problem_id': problem_id,
            'is_on_revision': problem_id in problems_on_revision
        })

    num_topics_per_level = defaultdict(int)
    num_checked_topics_per_level = defaultdict(int)
    num_checked_topics_per_level_with_revision = defaultdict(int)
    for t in trajectory:
        if t['topic_level'] in [1, 2, 3]:
            num_topics_per_level[t['topic_level']] += 1
            if t['problem_id'] is not None:
                if not t['is_on_revision']:
                    num_checked_topics_per_level[t['topic_level']] += 1
                num_checked_topics_per_level_with_revision[t['topic_level']] += 1

    final_grade = get_final_grade(
        num_topics_per_level,
        num_checked_topics_per_level
    )
    final_grade_with_revision = get_final_grade(
        num_topics_per_level,
        num_checked_topics_per_level_with_revision
    )
    # final_grade = final_grade_with_revision = '—'

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

        # TODO: check for DB integrity here
        if not user_problem_history:
            continue

        event_date = user_problem_history.datetime.strftime('%Y-%m-%d')
        reviewer_comment = ''

        time_left_for_submission = (user_problem_history.datetime + timedelta(days=10)) - datetime.now()
        deadline_passed = time_left_for_submission < timedelta(0)
        if time_left_for_submission.total_seconds() < 7200:
            n_minutes = int(time_left_for_submission.total_seconds() / 60)
            time_left_info = f'На отправку решения на проверку осталось менее {n_minutes} <strong>минут</strong>.'
        else:
            n_hours = int(time_left_for_submission.total_seconds() / 3600)
            time_left_info = f'На отправку решения на проверку осталось менее {n_hours} часов.'

        waiting_for_submission = True

        if user_problem_history.event == 'SENT_FOR_REVISION_DURING_EXPOSURE_GRADING':
            review_status = f'Задача была отправлена на дорешку в ходе проверки выдачи {event_date}. {time_left_info}'
            reviewer_comment = ''
        elif user_problem_history.event == 'SENT_FOR_REVISION':
            review_status = f'Решение было отправлено проверяющим на корректировку {event_date}. {time_left_info}'
            reviewer_comment = user_problem_history.comment
        elif user_problem_history.event == 'LEARNER_SENT_REVIEW_REQUEST':
            waiting_for_submission = False
            review_status = f'Ваше решение находится на проверке с {event_date}.'

        revisions.append({
            'problem_id': problem_id,
            'review_status': review_status,
            'waiting_for_submission': waiting_for_submission,
            'reviewer_comment': latex_to_html(reviewer_comment),
            'deadline_passed': deadline_passed
        })

    sharelatex_project_id = db.session.query(
        ExtraData.value
    ).filter(
        ExtraData.user_id == user_id,
        ExtraData.course_id == course_id,
        ExtraData.key == 'sharelatex_project_id'
    ).first()
    sharelatex_project_id = sharelatex_project_id and sharelatex_project_id[0]

    time_points = db.session.query(
        ExtraData.value
    ).filter(
        ExtraData.user_id == user_id,
        ExtraData.course_id == course_id,
        ExtraData.key == 'time_points'
    ).first()
    time_points = time_points and time_points[0]

    gdrive_scans_folder_id = db.session.query(
        ExtraData.value
    ).filter(
        ExtraData.user_id == user_id,
        ExtraData.course_id == course_id,
        ExtraData.key == 'gdrive_scans_folder_id'
    ).first()
    gdrive_scans_folder_id = gdrive_scans_folder_id and gdrive_scans_folder_id[0]

    return render_template(
        'view_learner_dashboard.html',
        exposures=exposures,
        trajectory=trajectory,
        revisions=revisions,
        user_id=user_id,
        course_id=course_id,
        sharelatex_project_id=sharelatex_project_id,
        instructor_mode=instructor_mode,
        username=username,
        time_points=time_points,
        gdrive_scans_folder_id = gdrive_scans_folder_id,
        final_grade=final_grade,
        final_grade_with_revision=final_grade_with_revision
    )
