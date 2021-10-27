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
    User, \
    TopicLevelAssignment

from collections import defaultdict

finals_blueprint = Blueprint('finals', __name__, template_folder='templates')

def get_final_grade(num_topics_per_level, num_checked_topics_per_level):
    # Закрыты все задачи -- ставим 10,
    # не закрыта ровно 1 задача 2 или 3 уровня -- ставим 9,
    # не закрыто ровно 2 кубка или не закрыты 1 кубок и 1 шляпка -- 8.
    # Во всех остальных случаях действуем по алгоритму:
    #   Нужны все закрытые листики, чтобы было минимум 3.
    #   Две шляпки закрывают 1 листик, но 1 кубок закрывает 1 листик. Два кубка закрывают одну шляпку.
    #   Получается, действие должно быть таким:
    #   Не хватает листиков -- покрываем их сколько можем шляпками, если покрылись -- все хорошо,
    #    продолжаем считать шляпки и кубки (следующие пункты).
    #    Пусть есть непокрытые листики, а шляпка осталась максимум одна, тогда начинаем с помощью кубков покрывать листики.
    #   Если в итоге все листики после сгорания шляпок или кубков покрылись, то: оценка  3 -- осталось 0 шляпок и кубков.
    #   Иначе покрываем кубками все недостающие шляпки (2 на 1). Если шляпки покрылись не все, ставим оценку 4.
    #   Пусть покрылись все шляпки. Дальше если кубков не осталось -- оценка 5, если один кубок -- 6, кубков хотя бы 2 -- 7.

    diffs = {i: num_topics_per_level[i]-num_checked_topics_per_level[i] for i in [1, 2, 3]}
    if sum(diffs.values()) == 0:
        return 10
    if sum(diffs.values()) == 1 and diffs[1] == 0:
        return 9
    if sum(diffs.values()) == 2 and diffs[1] == 0 and diffs[2] <= 1:
        return 8

    while num_checked_topics_per_level[1] < num_topics_per_level[1]:
        if num_checked_topics_per_level[2] >= 2:
            num_checked_topics_per_level[2] -= 2
            num_checked_topics_per_level[1] += 1
            continue
        if num_checked_topics_per_level[3] >= 1:
            num_checked_topics_per_level[3] -= 1
            num_checked_topics_per_level[1] += 1
            continue
        break

    if num_checked_topics_per_level[1] < num_topics_per_level[1]:
        return max(1, 3 + num_checked_topics_per_level[1] - num_topics_per_level[1])

    while num_checked_topics_per_level[2] < num_topics_per_level[2]:
        if num_checked_topics_per_level[3] >= 2:
            num_checked_topics_per_level[3] -= 2
            num_checked_topics_per_level[2] += 1
            continue
        break
    if num_checked_topics_per_level[2] + num_checked_topics_per_level[3] == 0:
        return 3
    if num_checked_topics_per_level[2] < num_topics_per_level[2]:
        return 4
    if num_checked_topics_per_level[3] == 0:
        return 5
    if num_checked_topics_per_level[3] == 1:
        return 6
    if num_checked_topics_per_level[3] >= 2:
        return 7

    assert False


@finals_blueprint.route('/course-<int:course_id>/finals', methods=['GET'])
@finals_blueprint.route('/course-<int:course_id>/finals/', methods=['GET'])
@flask_login.login_required
def view_final_grades(course_id):
    role = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == course_id,
        Participant.role_id == Role.id
    ).scalar()

    if (role not in ['ADMIN', 'INSTRUCTOR']):
        abort(403)

    final_grades = []
    for user_id, user_username in db.session.query(User.id, User.username).filter(
                User.id == Participant.user_id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code == 'LEARNER'
            ).all():

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

        final_grades.append({
            'username': user_username,
            'final_grade': final_grade,
            'final_grade_with_revision': final_grade_with_revision
        })

    return render_template(
        'view_final_grades.html',
        final_grades=final_grades
    )
