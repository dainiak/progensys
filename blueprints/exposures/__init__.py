from flask import Blueprint, render_template, request, abort, jsonify, redirect, url_for
import flask_login

from blueprints.models import \
    db, \
    User, \
    ExposureContent, \
    Problem, \
    ProblemSet, \
    ProblemSetContent, \
    Exposure, \
    Participant, \
    Role, \
    ExposureGrading, \
    ExposureGradingResult, \
    ProblemStatusInfo, \
    UserCourseTrajectory, \
    Trajectory, \
    TrajectoryContent, \
    ProblemTopicAssignment, \
    ProblemRelation, \
    ProblemRelationType, \
    ProblemStatus, \
    GroupMembership, \
    Group, \
    ProblemSetExtra, \
    History, \
    TopicLevelAssignment


from datetime import datetime
from json import dumps as to_json_string
from operator import attrgetter
from operator import or_ as operator_or
from pulp import LpProblem, LpVariable, LpAffineExpression, LpMinimize, LpStatus
from collections import defaultdict
from functools import reduce

from text_tools import process_problem_statement, latex_to_html

exposures_blueprint = Blueprint('exposures', __name__, template_folder='templates')


@exposures_blueprint.route('/course-<int:course_id>/exposure-<exposure_string>/', methods=['GET'])
@exposures_blueprint.route('/course-<int:course_id>/exposure-<exposure_string>', methods=['GET'])
def view_exposure(course_id, exposure_string):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['ADMIN', 'INSTRUCTOR', 'GRADER'])
            ).first():
        abort(403)

    if '-' in exposure_string:
        exposures = Exposure.query.filter_by(course_id=course_id).all()
        exposure_ids = list(map(
            attrgetter('id'),
            filter(lambda x: x.timestamp.isoformat()[:10] == exposure_string, exposures)
        ))
        if exposure_ids:
            exposure_id = exposure_ids[0]
        else:
            abort(404)
    elif exposure_string.isdecimal():
        exposure_id = int(exposure_string)
    else:
        abort(400)

    exposure = Exposure.query.filter_by(course_id=course_id, id=exposure_id).first()
    if not exposure:
        abort(404)

    # TODO: make this a single SQL query instead of SQL&Python mix
    max_problems_per_set = max(x[1] for x in db.session.query(
        ProblemSetContent.problem_set_id, db.func.count(ProblemSetContent.problem_id)
    ).group_by(
        ProblemSetContent.problem_set_id
    ).filter(
        ProblemSetContent.problem_set_id == ExposureContent.problem_set_id,
        ExposureContent.exposure_id == exposure.id
    ).all())

    return render_template(
        'view_exposure.html',
        exposure_id=exposure_id,
        course_id=course_id,
        exposure_date=exposure.timestamp.strftime('%Y-%m-%d'),
        max_problems_per_set=max_problems_per_set
    )


@exposures_blueprint.route('/course-<int:course_id>/exposure-<exposure_string>/print/', methods=['GET'])
@exposures_blueprint.route('/course-<int:course_id>/exposure-<exposure_string>/print', methods=['GET'])
def print_exposure(course_id, exposure_string):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['ADMIN', 'INSTRUCTOR', 'GRADER'])
            ).first():
        abort(403)

    if '-' in exposure_string:
        exposures = Exposure.query.filter_by(course_id=course_id).all()
        exposure_ids = list(map(
            attrgetter('id'),
            filter(lambda x: x.timestamp.isoformat()[:10] == exposure_string, exposures)
        ))
        if exposure_ids:
            exposure_id = exposure_ids[0]
        else:
            abort(404)
    elif exposure_string.isdecimal():
        exposure_id = int(exposure_string)
        if not Exposure.query.filter_by(course_id=course_id, id=exposure_id).first():
            abort(404)
    else:
        abort(400)

    exposure_date = str(db.session.query(Exposure.timestamp).filter(Exposure.id == exposure_id).scalar())[:10]
    results = []
    for firstname, lastname, user_id, problem_set_id, problem_set_is_adhoc in db.session.query(
                User.name_first,
                User.name_last,
                User.id,
                ProblemSet.id,
                ProblemSet.is_adhoc
            ).filter(
                ExposureContent.exposure_id == exposure_id,
                ExposureContent.user_id == User.id,
                ProblemSet.id == ExposureContent.problem_set_id
            ).order_by(
                ExposureContent.sort_key
            ).all():

        groups_string = ", ".join(
            x[0] for x in db.session.query(Group.code).filter(
                    Group.id == GroupMembership.group_id,
                    GroupMembership.user_id == user_id
                ).all()
        )
        results.append({
            'name_first': firstname,
            'name_last': lastname,
            'groups': groups_string,
            'problem_set_id': problem_set_id,
            'problem_set_is_adhoc': problem_set_is_adhoc,
            'problem_set_content': []
        })
        for problem_id, problem_statement, sort_key in db.session.query(
                    Problem.id,
                    Problem.statement,
                    ProblemSetContent.sort_key
                ).filter(
                    Problem.id == ProblemSetContent.problem_id,
                    ProblemSetContent.problem_set_id == problem_set_id
                ).all():

            problem_level = db.session.query(
                TopicLevelAssignment.level
            ).filter(
                TopicLevelAssignment.course_id == course_id,
                TopicLevelAssignment.topic_id == ProblemTopicAssignment.topic_id,
                ProblemTopicAssignment.problem_id == problem_id
            ).first()
            if problem_level:
                problem_level = problem_level[0]

            results[-1]['problem_set_content'].append({
                'sort_key': sort_key,
                'problem_id': problem_id,
                'problem_statement': process_problem_statement(problem_statement),
                'problem_level': problem_level
            })
        for sort_key, extra_content in db.session.query(
                    ProblemSetExtra.sort_key,
                    ProblemSetExtra.content
                ).filter(
                    ProblemSetExtra.problem_set_id == problem_set_id
                ).all():
            results[-1]['problem_set_content'].append({
                'sort_key': sort_key,
                'extra_content': latex_to_html(extra_content)
            })
        results[-1]['problem_set_content'].sort(key=lambda x: x['sort_key'])
        problem_count = 0
        for item in results[-1]['problem_set_content']:
            if item.get('problem_id'):
                problem_count += 1
                item['problem_number'] = problem_count
        results[-1]['problem_count'] = problem_count

    results.sort(key=lambda x: x['groups'] + "---" + x['name_last'])

    return render_template(
        'print_exposure.html',
        exposure_id=exposure_id,
        exposure_content=results,
        exposure_date=exposure_date,
        course_id=course_id
    )


@exposures_blueprint.route('/api/exposure', methods=['POST'])
@flask_login.login_required
def api_exposure():
    json = request.get_json()
    if not json or 'action' not in json:
        return jsonify(error='Expected JSON format and action')

    if not json or 'action' not in json or 'course_id' not in json:
        abort(400)

    course_id = json['course_id']

    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code == 'ADMIN'
            ).first():
        abort(403)

    if json['action'] == 'change_exposure_date':
        if not json.get('exposure_id') or not json.get('exposure_date'):
            abort(400)
        exposure_id = json.get('exposure_id')
        exposure = Exposure.query.filter_by(id=exposure_id).first()
        exposure.timestamp = datetime.strptime(json.get('exposure_date'), '%Y-%m-%d')
        db.session.commit()
        return jsonify(result='Success')

    if json['action'] == 'delete_exposure':
        if not json.get('exposure_id') or not json.get('course_id'):
            abort(400)
        exposure_id = json.get('exposure_id')
        course_id = json.get('course_id')
        exposure = Exposure.query.filter_by(id=exposure_id, course_id=course_id).first()
        if not exposure:
            abort(400)
        db.session.delete(exposure)
        db.session.commit()
        return jsonify(result='Success')

    elif json['action'] == 'load':
        if not json.get('exposure_id'):
            abort(400)

        exposure_id = json.get('exposure_id')
        db_data = db.session.query(
            User.name_last,
            User.name_first,
            User.id,
            ProblemSet.id,
            ProblemSet.is_adhoc
        ).filter(
            Exposure.id == exposure_id,
            Exposure.course_id == course_id,
            ExposureContent.user_id == User.id,
            ExposureContent.exposure_id == Exposure.id,
            ExposureContent.problem_set_id == ProblemSet.id
        ).all()

        data_for_frontend = []

        for user_name_last, \
            user_name_first, \
            user_id, \
            problem_set_id, \
            problem_set_is_adhoc \
                in db_data:
            data_for_frontend.append(dict())
            data_for_frontend[-1]['user_id'] = user_id
            data_for_frontend[-1]['problem_set_id'] = problem_set_id
            data_for_frontend[-1]['problem_set_is_adhoc'] = problem_set_is_adhoc
            data_for_frontend[-1]['learner_name'] = '{} {}'.format(user_name_last, user_name_first)
            problem_ids = map(
                lambda x: x[0],
                db.session.query(
                    ProblemSetContent.problem_id
                ).filter(
                    ProblemSetContent.problem_set_id == problem_set_id
                ).order_by(
                    ProblemSetContent.sort_key
                ).all())
            for problem_position, problem_id in enumerate(problem_ids):
                problem_position += 1
                data_for_frontend[-1]['pid{}'.format(problem_position)] = problem_id

        return jsonify(data_for_frontend)

    elif json['action'] == 'delete':
        item = json.get('item')
        if not item:
            abort(200)
        user_id = item.get('user_id')
        exposure_id = item.get('exposure_id')
        problem_set_id = item.get('problem_set_id')
        if None in [user_id, exposure_id, problem_set_id]:
            abort(200)
        exposure_record = ExposureContent.query.filter_by(
            exposure_id=exposure_id,
            user_id=user_id,
            problem_set_id=problem_set_id
        ).first()
        if not exposure_record:
            abort(200)
        db.session.delete(exposure_record)

        result_report = 'Deleted the exposure record.'

        grading_results = ExposureGradingResult.query.filter(
            ExposureGradingResult.user_id == user_id,
            ExposureGradingResult.problem_set_id == problem_set_id,
            ExposureGradingResult.exposure_grading_id == ExposureGrading.id,
            ExposureGrading.exposure_id == exposure_id
        ).all()

        if len(grading_results) > 0:
            result_report += ' There were grading results associated with this exposure item. Deleted them.'
            for gr in grading_results:
                db.session.delete(gr)

        problem_set = ProblemSet.query.filter_by(id=problem_set_id).first()
        if (problem_set.is_adhoc and not db.session.query(
                    ExposureContent.exposure_id
                ).filter(
                    ExposureContent.problem_set_id == problem_set_id
                ).first()):
            ProblemSetContent.query.filter_by(problem_set_id=problem_set_id).delete()
            ProblemSetExtra.query.filter_by(problem_set_id=problem_set_id).delete()

            db.session.delete(problem_set)
            result_report += ' The problem set was ad hoc and not used elsewhere, so deleted it too.'

        db.session.commit()
        return jsonify(result=result_report)

    elif json['action'] == 'update':
        item = json.get('item')
        if not item:
            return jsonify(error='No data provided for storing the grading results')
        grader_id = flask_login.current_user.id
        user_id = item.get('user_id')
        exposure_id = item.get('exposure_id')
        problem_set_id = item.get('problem_set_id')
        if None in [grader_id, user_id, exposure_id, problem_set_id]:
            return jsonify(error='Data required for storing the grading result was not provided')

        grading = ExposureGrading.query.filter_by(grader_id=grader_id, exposure_id=exposure_id).first()
        if not grading:
            grading = ExposureGrading(exposure_id, grader_id)
            grading.timestamp = datetime.now()
            db.session.add(grading)
            db.session.commit()
            grading = ExposureGrading.query.filter_by(grader_id=grader_id, exposure_id=exposure_id).first()

        existing_grading_results = ExposureGradingResult.query.filter_by(
            exposure_grading_id=grading.id,
            user_id=user_id,
            problem_set_id=problem_set_id
        ).all()
        existing_grading_results = {egc.problem_id: egc for egc in existing_grading_results}

        for field_name in item:
            if field_name.startswith('pid'):
                problem_no = field_name[len('pid'):]
                problem_id = int(item[field_name])
                problem_status_id = item.get('p{}'.format(problem_no))
                if problem_status_id >= 0:
                    if problem_id in existing_grading_results:
                        existing_grading_results[problem_id].problem_status_id = problem_status_id
                    else:
                        grading_result = ExposureGradingResult(
                            grading.id,
                            user_id,
                            problem_set_id,
                            problem_id,
                            problem_status_id
                        )
                        db.session.add(grading_result)
                else:
                    item['p{}'.format(problem_no)] = -problem_id

        db.session.commit()
        return jsonify(item)


@exposures_blueprint.route('/course-<int:course_id>/exposure/date-<exposure_date>', methods=['GET'])
@flask_login.login_required
def view_exposure_table(course_id, exposure_date):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code == 'ADMIN'
            ).first():
        abort(403)

    exposures = Exposure.query.filter(Exposure.course_id == course_id).all()
    exposure_ids = list(map(
        attrgetter('id'),
        filter(lambda x: x.timestamp.isoformat()[:10] == exposure_date, exposures)
    ))
    if len(exposure_ids) == 0:
        return jsonify(error='No exposures with specified date were found')

    user_ids = list(map(lambda x: x[0], db.session.query(User.id).all()))

    all_problems = list(map(
        lambda x: x[0],
        db.session.query(
            Problem.id
        ).filter(
            ExposureContent.problem_set_id == ProblemSetContent.problem_set_id,
            Problem.id == ProblemSetContent.problem_id,
            ExposureContent.exposure_id.in_(exposure_ids),
            ExposureContent.user_id.in_(user_ids)
        ).all()))
    problem_statuses = [{'name': ps.icon, 'id': ps.id} for ps in ProblemStatusInfo.query.all()]

    return render_template(
        'view_exposures.html',
        all_problems=to_json_string(all_problems),
        exposure_ids=to_json_string(exposure_ids),
        user_ids=to_json_string(user_ids),
        problem_statuses=to_json_string(problem_statuses)
    )


@exposures_blueprint.route('/exposure/new', methods=['POST'])
@flask_login.login_required
def new_exposure():
    if not (request.form and request.form.get('user_ids')):
        abort(400)

    course_id = int(request.form.get('course_id', 0))
    user_ids = list(map(int, request.form.get('user_ids').split(',')))
    exposure_timestamp = request.form.get('exposure_timestamp')
    exposure_title = request.form.get('exposure_title', '')
    exposure_type = request.form.get('exposure_type', 'auto')
    if exposure_type == 'manual':
        problem_set_id = int(request.form.get('problem_set_id', 0))
        exposure = Exposure()
        exposure.course_id = course_id
        exposure.title = exposure_title
        exposure.timestamp = datetime.strptime(exposure_timestamp, '%Y-%m-%dT%H:%M')
        db.session.add(exposure)
        db.session.flush()
        for user_id in user_ids:
            db.session.add(ExposureContent(exposure.id, user_id, problem_set_id))

        db.session.commit()
        return redirect(url_for(
            'exposures.view_exposure',
            exposure_string=str(exposure.id),
            course_id=course_id,
            group=None))

    if exposure_type == 'auto':
        user_trajectories = db.session.query(User.id, Trajectory.id).filter(
            User.id.in_(user_ids),
            Participant.user_id == User.id,
            Participant.course_id == course_id,
            Participant.role_id == Role.id,
            Role.code == 'LEARNER',
            UserCourseTrajectory.user_id == User.id,
            UserCourseTrajectory.course_id == course_id,
            UserCourseTrajectory.trajectory_id == Trajectory.id
        ).all()

        trajectory_contents_dict = dict()

        for _, trajectory_id in user_trajectories:
            if trajectory_id not in trajectory_contents_dict:
                trajectory_topic_ids = [x[0] for x in db.session.query(TrajectoryContent.topic_id).filter(
                    TrajectoryContent.trajectory_id == trajectory_id
                ).order_by(TrajectoryContent.sort_key).all()]
                trajectory_contents_dict[trajectory_id] = trajectory_topic_ids

        topic_ids = reduce(
            operator_or,
            map(
                set,
                trajectory_contents_dict.values()
            ),
            set()
        )

        topic_levels = dict(db.session.query(
            TopicLevelAssignment.topic_id,
            TopicLevelAssignment.level
        ).filter(
            TopicLevelAssignment.course_id == course_id,
            TopicLevelAssignment.topic_id.in_(topic_ids)
        ).all())

        problem_ids = set()
        problems_by_topic = defaultdict(set)
        for pta in ProblemTopicAssignment.query.filter(
                    ProblemTopicAssignment.topic_id.in_(topic_ids)
                ).all():
            problems_by_topic[pta.topic_id].add(pta.problem_id)
            problem_ids.add(pta.problem_id)

        clones = defaultdict(set)
        for p1, p2 in db.session.query(
                    ProblemRelation.from_id,
                    ProblemRelation.to_id
                ).filter(
                    ProblemRelation.type_id == ProblemRelationType.id,
                    ProblemRelationType.code == 'CLONE_OF',
                    ProblemRelation.to_id.in_(problem_ids)
                ):
            clones[p1].add(p2)
            clones[p2].add(p1)
        for problem_id in clones:
            while True:
                expanded_clone_ids = reduce(
                    operator_or,
                    (clones[clone_id] for clone_id in clones[problem_id]),
                    clones[problem_id]
                )
                if len(expanded_clone_ids) == len(clones[problem_id]):
                    break
                else:
                    clones[problem_id] = expanded_clone_ids

        problems_count = {p_id: p_count for p_id, p_count in db.session.query(
            ProblemStatus.problem_id, db.func.count(ProblemStatus.user_id)
        ).filter(
            ProblemStatus.problem_id.in_(problem_ids),
            ProblemStatus.user_id.in_(user_ids),
            ProblemStatus.status_id == ProblemStatusInfo.id,
            ProblemStatusInfo.code != 'NOT_EXPOSED'
        ).group_by(ProblemStatus.problem_id).all()}

        count_clones_as_single_problem_in_trajectory_fulfillment = False
        penalty_for_having_same_problem_on_next_quiz = 1
        penalty_for_not_giving_a_brand_new_problem = 1
        penalty_for_giving_clone_of_exposed_problem = 1
        penalty_for_giving_clones = 10
        penalty_for_having_underflow = 1000
        penalty_for_including_harder_topic_while_leaving_out_easier = 100
        max_problems_per_user = int(request.args.get('max', 5))

        lp = LpProblem(name='Test Generation', sense=LpMinimize)
        lp_objective = LpAffineExpression()

        lp_vars_user_problem = dict()

        for user_id, trajectory_id in user_trajectories:
            user_problems_solved = set(x[0] for x in db.session.query(ProblemStatus.problem_id).filter(
                ProblemStatus.user_id == user_id,
                ProblemStatus.status_id == ProblemStatusInfo.id,
                ProblemStatusInfo.code.in_(['SOLUTION_NEEDS_REVISION', 'SOLUTION_CORRECT'])
            ).all())
            user_problems_seen = set(x[0] for x in db.session.query(ProblemStatus.problem_id).filter(
                ProblemStatus.user_id == user_id,
                ProblemStatus.status_id == ProblemStatusInfo.id,
                ProblemStatusInfo.code.in_(['EXPOSED', 'SOLUTION_WRONG'])
            ).all())
            user_problems_solved_clones = reduce(
                operator_or,
                (clones[problem_id] for problem_id in user_problems_solved),
                set()
            ) - user_problems_solved

            user_problems_remaining_for_counting = set(user_problems_solved)
            user_remaining_trajectory_topics = []
            for topic_id in trajectory_contents_dict[trajectory_id]:
                solved_problems_for_topic = user_problems_remaining_for_counting & problems_by_topic[topic_id]
                if solved_problems_for_topic:
                    problem_id = next(iter(solved_problems_for_topic))
                    user_problems_remaining_for_counting.remove(problem_id)
                    if count_clones_as_single_problem_in_trajectory_fulfillment:
                        user_problems_remaining_for_counting -= clones[problem_id]
                else:
                    user_remaining_trajectory_topics.append(topic_id)

            if count_clones_as_single_problem_in_trajectory_fulfillment:
                user_problems_solved |= user_problems_solved_clones

            problems_available_for_user = reduce(
                operator_or,
                (problems_by_topic[topic_id] for topic_id in user_remaining_trajectory_topics),
                set()
            ) - user_problems_solved

            for problem_id in problems_available_for_user:
                lp_vars_user_problem[(user_id, problem_id)] = LpVariable(
                    name='user_problem_{}_{}'.format(user_id, problem_id),
                    cat='Binary'
                )

            # Number of problems for user should definitely not exceed the maximum
            lp += (
                sum(
                    lp_vars_user_problem[(user_id, problem_id)]
                    for problem_id in problems_available_for_user
                )
                <=
                max_problems_per_user
            )

            min_problems = min(
                max_problems_per_user,
                len(problems_available_for_user),
                len(user_remaining_trajectory_topics)
            )

            lp_underflow_variable = LpVariable(
                'underflow_{}'.format(user_id),
                lowBound=0
            )
            lp += (
                sum(
                    lp_vars_user_problem[(user_id, problem_id)]
                    for problem_id in problems_available_for_user
                )
                + lp_underflow_variable
                >=
                min_problems
            )
            lp_objective += penalty_for_having_underflow * lp_underflow_variable

            lp_vars_user_topic = dict()
            num_occurrences_of_topic_in_remaining_trajectory = defaultdict(int)

            # Number of problems for each topic should not exceed the number required by the trajectory
            for topic_id in set(user_remaining_trajectory_topics):
                num_occurrences_of_topic_in_remaining_trajectory[topic_id] = sum(
                    1
                    for i in user_remaining_trajectory_topics if i == topic_id
                )

                lp_vars_user_topic[(user_id,topic_id)] = LpVariable(
                    'user_topic_{}_{}'.format(user_id, topic_id)
                )

                lp += (
                    sum(
                        lp_vars_user_problem[(user_id, problem_id)]
                        for problem_id in problems_by_topic[topic_id] & problems_available_for_user
                    ) == lp_vars_user_topic[(user_id,topic_id)]
                )

                lp += (
                    lp_vars_user_topic[(user_id,topic_id)]
                    <=
                    num_occurrences_of_topic_in_remaining_trajectory[topic_id]
                )


            # Introduce penalty for giving clones at the same time
            family_of_clone_sets = list()
            problems_available_for_user_copy = set(problems_available_for_user)
            while problems_available_for_user_copy:
                problem_id = next(iter(problems_available_for_user_copy))
                next_part = ({problem_id} | clones[problem_id]) & problems_available_for_user_copy
                if len(next_part) > 1:
                    family_of_clone_sets.append(next_part)
                problems_available_for_user_copy -= next_part

            for clone_set in family_of_clone_sets:
                lp_clone_variable = LpVariable(
                    'user_clones_{}_{}'.format(user_id, next(iter(clone_set))),
                    lowBound=0
                )
                lp += (
                    sum(
                        lp_vars_user_problem[(user_id, problem_id)]
                        for problem_id in clone_set
                    )
                    <=
                    1 + lp_clone_variable
                )
                lp_objective += lp_clone_variable * penalty_for_giving_clones


            # Introduce penalty for giving a user problems that he/she might have seen
            for problem_id in problems_available_for_user:
                if problem_id in user_problems_seen:
                    lp_objective += (
                        penalty_for_having_same_problem_on_next_quiz
                        *
                        lp_vars_user_problem[(user_id, problem_id)]
                    )
                if problems_count.get(problem_id, 0) > 2:
                    lp_objective += (
                        penalty_for_not_giving_a_brand_new_problem
                        *
                        lp_vars_user_problem[(user_id, problem_id)]
                    )

            user_problems_seen_clones = reduce(
                operator_or,
                (clones[problem_id] for problem_id in user_problems_seen),
                set()
            ) - user_problems_seen - user_problems_solved

            for problem_id in problems_available_for_user & user_problems_seen_clones:
                lp_objective += (
                    penalty_for_giving_clone_of_exposed_problem
                    *
                    lp_vars_user_problem[(user_id, problem_id)]
                )

            # Introduce penalty for giving problems on topics that were downvoted by the user
            # and/or are hard while there are some easier/upvoted topics left out of exposure
            topics_having_levels = set(user_remaining_trajectory_topics) & set(topic_levels.keys())
            active_levels = sorted(set(map(topic_levels.get, topics_having_levels)))
            lp_vars_level_fulfilled = dict()
            lp_var_including_harder_topic_while_leaving_out_easier = LpVariable(
                'user_including_harder_topic_while_leaving_out_easier_{}'.format(user_id),
                cat='Binary',
            )
            for i, level in enumerate(active_levels):
                topics_of_current_level = \
                    set(user_remaining_trajectory_topics) \
                    & set(
                        topic_id
                        for topic_id, topic_level in topic_levels.items()
                        if topic_level == level
                    )

                lp_vars_level_fulfilled[(user_id, level)] = LpVariable(
                    'user_level_fulfilled_{}_{}'.format(user_id, level),
                    cat='Binary'
                )

                for topic_id in topics_of_current_level:
                    lp += (
                        lp_vars_level_fulfilled[(user_id, level)]
                        *
                        num_occurrences_of_topic_in_remaining_trajectory[topic_id]
                        <=
                        lp_vars_user_topic[(user_id, topic_id)]
                    )

                    if i > 0:
                        lp += (
                            lp_vars_user_topic[(user_id, topic_id)]
                            <=
                            num_occurrences_of_topic_in_remaining_trajectory[topic_id]
                            *
                            lp_vars_level_fulfilled[(user_id, active_levels[i-1])]
                            +
                            num_occurrences_of_topic_in_remaining_trajectory[topic_id]
                            *
                            lp_var_including_harder_topic_while_leaving_out_easier
                        )

            lp_objective += (
                penalty_for_including_harder_topic_while_leaving_out_easier
                *
                lp_var_including_harder_topic_while_leaving_out_easier
            )

        lp.setObjective(lp_objective)

        try:
            lp.solve()
            log_info = 'Problem status is “{}” with objective function value “{}”'.format(
                LpStatus[lp.status],
                lp.objective.value()
            )
        except:
            log_info = 'Failed to solve the linear program'
            return jsonify(error='Failed to solve the linear program', program=str(lp))

        problem_sets = defaultdict(list)
        for user_id, problem_id in lp_vars_user_problem:
            if lp_vars_user_problem[(user_id, problem_id)].value() > 0:
                problem_sets[user_id].append(problem_id)

        exposure = Exposure()
        exposure.course_id = course_id
        exposure.title = exposure_title
        exposure.timestamp = datetime.strptime(exposure_timestamp, '%Y-%m-%dT%H:%M')
        db.session.add(exposure)
        db.session.flush()

        exposure_preamble = request.form.get('exposure_preamble')
        if exposure_preamble:
            exposure_preamble.strip()

        for user_id in problem_sets:
            problem_set = ProblemSet()
            problem_set.is_adhoc = True
            problem_set.title = \
                f'Автоматически сгенерированный вариант для пользователя #{user_id} выдачи #{exposure.id}'
            db.session.add(problem_set)
            db.session.flush()
            db.session.add(ExposureContent(exposure.id, user_id, problem_set.id))
            if exposure_preamble:
                pse = ProblemSetExtra()
                pse.content = exposure_preamble
                pse.sort_key = 1
                pse.problem_set_id = problem_set.id
                db.session.add(pse)

            for sort_key, problem_id in enumerate(problem_sets[user_id]):
                db.session.add(ProblemSetContent(problem_set.id, problem_id, sort_key + 10))

        db.session.commit()
        return redirect(url_for(
            'exposures.view_exposure',
            exposure_string=str(exposure.id),
            course_id=course_id,
            group=None,
            log_info=log_info
        ))

@exposures_blueprint.route('/course-<int:course_id>/exposures', methods=['GET'])
@exposures_blueprint.route('/course-<int:course_id>/exposures/', methods=['GET'])
@flask_login.login_required
def view_exposures(course_id):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['ADMIN', 'INSTRUCTOR', 'GRADER'])
            ).first():
        abort(403)
    exposures = []
    for exposure in Exposure.query.filter(Exposure.course_id == course_id).order_by(Exposure.timestamp.desc()).all():
        exposures.append({
            'id': exposure.id,
            'date': exposure.timestamp.strftime('%Y-%m-%d'),
            'title': exposure.title
        })
    return render_template(
        'view_exposures.html',
        exposures=exposures,
        course_id=course_id
    )


@exposures_blueprint.route('/course-<int:course_id>/mark-topic-priority-for-learner', methods=['POST'])
@flask_login.login_required
def mark_topic_priority_for_learner(course_id):
    json = request.get_json()
    user_id = json.get('user_id')
    topic_id = json.get('topic_id')
    if None in [user_id, topic_id]:
        abort(400)

    role = db.session.query(
        Role.code
    ).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == course_id,
        Participant.role_id == Role.id
    ).scalar()

    if not(
            (user_id == flask_login.current_user.id and role == 'LEARNER')
            or role in ['ADMIN', 'INSTRUCTOR']
            ):
        abort(403)

    if not json or json.get('action') not in ['mark_topic_as_unwanted', 'mark_topic_as_favourable']:
        abort(400)

    h = History()
    h.user_id = user_id
    h.event = 'MARKED_TOPIC_AS_UNWANTED' if json['action'] == 'mark_topic_as_unwanted' else 'MARKED_TOPIC_AS_FAVOURABLE'
    h.comment = str(topic_id)
    h.datetime = datetime.now()
    db.session.add(h)

    return jsonify(result="Запрос сохранён до ближайшей письменной работы")