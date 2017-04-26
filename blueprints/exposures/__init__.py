from flask import Blueprint, render_template, request, abort, jsonify
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
    ProblemStatus

from datetime import datetime
from json import dumps as to_json_string
from operator import attrgetter
from operator import or_ as operator_or
from pulp import LpProblem, LpVariable, LpAffineExpression, LpMinimize, LpStatus
from collections import defaultdict
from functools import reduce

exposures_blueprint = Blueprint('exposures', __name__, template_folder='templates')


@exposures_blueprint.route('/api/exposure', methods=['POST'])
@flask_login.login_required
def api_exposure():
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == flask_login.current_user.current_course_id,
                Participant.role_id == Role.id,
                Role.code == 'ADMIN'
            ).exists():
        abort(403)

    json = request.get_json()
    if not json or 'action' not in json:
        return jsonify(error='Expected JSON format and action')

    if json['action'] == 'load':
        if not json.get('user_ids'):
            return jsonify(error='User IDs not specified')
        if not json.get('exposure_ids'):
            return jsonify(error='Exposure IDs not specified')

        exposure_ids = json.get('exposure_ids')
        user_ids = json.get('user_ids')
        db_data = db.session.query(
            User.name_last,
            User.name_first,
            User.id,
            Exposure.timestamp,
            Exposure.id,
            ExposureContent.problem_set_id
        ).filter(
            User.id.in_(user_ids),
            Exposure.id.in_(exposure_ids),
            ExposureContent.user_id == User.id,
            ExposureContent.exposure_id == Exposure.id
        ).all()
        data_for_frontend = []

        for user_name_last, \
            user_name_first, \
            user_id, \
            exposure_timestamp, \
            exposure_id, \
            problem_set_id \
                in db_data:
            data_for_frontend.append(dict())
            data_for_frontend[-1]['user_id'] = user_id
            data_for_frontend[-1]['exposure_id'] = exposure_id
            data_for_frontend[-1]['problem_set_id'] = problem_set_id
            data_for_frontend[-1]['exposure_date'] = exposure_timestamp.isoformat()[:10]
            data_for_frontend[-1]['learner_name'] = '{} {}'.format(user_name_last, user_name_first)
            problem_ids = list(map(
                lambda x: x[0],
                db.session.query(
                    ProblemSetContent.problem_id
                ).filter(
                    ProblemSetContent.problem_set_id == problem_set_id
                ).order_by(
                    ProblemSetContent.sort_key
                ).all()))
            graded_problems = db.session.query(
                ExposureGradingResult.problem_id,
                ExposureGradingResult.problem_status_id
            ).filter(
                ExposureGrading.exposure_id == exposure_id,
                ExposureGradingResult.exposure_grading_id == ExposureGrading.id,
                ExposureGradingResult.user_id == user_id,
                ExposureGradingResult.problem_set_id == problem_set_id
            ).all()
            graded_problems = {p[0]: p[1] for p in graded_problems}

            for problem_position, problem_id in enumerate(problem_ids):
                problem_position += 1
                data_for_frontend[-1]['p{}'.format(problem_position)] = graded_problems.get(
                    problem_id,
                    -problem_id
                )
                data_for_frontend[-1]['pid{}'.format(problem_position)] = problem_id

        return jsonify(data_for_frontend)

    elif json['action'] == 'delete':
        item = json.get('item')
        if not item:
            return jsonify(error='No data provided for storing the grading results')
        user_id = item.get('user_id')
        exposure_id = item.get('exposure_id')
        problem_set_id = item.get('problem_set_id')
        if None in [user_id, exposure_id, problem_set_id]:
            return jsonify(error='Data required for deleting exposure record was not provided')
        exposure_record = ExposureContent.query.filter_by(
            exposure_id=exposure_id,
            user_id=user_id,
            problem_set_id=problem_set_id
        ).first()
        if not exposure_record:
            return jsonify(error='The specified exposure record was not found')
        db.session.delete(exposure_record)
        db.session.commit()
        result_report = 'Deleted the exposure record.'
        problem_set = ProblemSet.query.filter_by(id=problem_set_id).first()
        if (problem_set.is_adhoc and not db.session.query(
                    ExposureContent.id
                ).filter(
                    ExposureContent.problem_set_id == problem_set_id
                ).first()):
            db.session.delete(problem_set)
            db.session.commit()
            result_report += ' The problem set was ad hoc and not used elsewhere, so deleted it too.'
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


@exposures_blueprint.route('/exposure/date-<exposure_date>', methods=['GET'])
@flask_login.login_required
def view_exposure_table(exposure_date):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == flask_login.current_user.current_course_id,
                Participant.role_id == Role.id,
                Role.code == 'ADMIN'
            ).exists():
        abort(403)

    exposures = Exposure.query.all()
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
        'templates/view_exposures.html',
        all_problems=to_json_string(all_problems),
        exposure_ids=to_json_string(exposure_ids),
        user_ids=to_json_string(user_ids),
        problem_statuses=to_json_string(problem_statuses)
    )


@exposures_blueprint.route('/exposure/new', methods=['POST'])
def new_exposure():
    if request.form and request.form.get('user_ids'):
        user_ids = list(map(int, request.form.get('user_ids').split(',')))
        course_id = int(request.form.get('course_id', 0))
        exposure_timestamp = request.form.get('exposure_timestamp')
        exposure_title = request.form.get('exposure_title', '')
        exposure_type = request.form.get('exposure_type', 'auto')
        if exposure_type == 'manual':
            problem_set_id = int(request.form.get('problem_set_id', 0))
    else:
        abort(400)

    if exposure_type == 'auto':
        max_problems_per_user = int(request.args.get('max', 5))
        current_variation = defaultdict(int)

        users = db.session.query(User.id, Trajectory.id).filter(
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

        for _, trajectory_id in users:
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

        problem_ids = set()
        problems_by_topic = defaultdict(dict)
        for pta in ProblemTopicAssignment.query.filter(
                    ProblemTopicAssignment.topic_id.in_(topic_ids)
                ).all():
            problems_by_topic[pta.topic_id][pta.problem_id] = pta.weight
            problem_ids.add(pta.problem_id)

        problems = {
            p.id: p
            for p in Problem.query.filter(Problem.id.in_(problem_ids)).all()
        }

        clones = defaultdict(set)
        for p1, p2 in db.session.query(
                    ProblemRelation.from_id,
                    ProblemRelation.to_id,
                    ProblemRelation.type_id == ProblemRelationType.id,
                    ProblemRelationType.code == 'CLONE_OF'
                ).filter(
                    ProblemRelation.to_id.in_(problem_ids)
                ):
            clones[p1].add(p2)
            clones[p2].add(p1)
        for problem_id in clones:
            while True:
                expanded_clone_ids = clones[problem_id]
                initial_size = len(expanded_clone_ids)
                for clone_id in clones[problem_id]:
                    expanded_clone_ids |= clones[clone_id]
                if len(expanded_clone_ids) == initial_size:
                    break
                else:
                    clones[problem_id] = expanded_clone_ids

        count_clones_as_single_problem_in_trajectory_fulfillment = True
        for user_id, trajectory_id in users:
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
            # user_problems_solved_clones = reduce(
            #     operator_or,
            #     (clones[problem_id] for problem_id in user_problems_solved[user_id]),
            #     set()
            # )

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




        # user_history = defaultdict(lambda: {i: -1 for i in problem_ids})
        # num_appearances = defaultdict(int)
        # exposed_problems = defaultdict(set)
        # remaining_trajectory_items = dict()
        #
        # for user_id in users:
        #     counted_problems = set()
        #     problems_available_for_user[user_id] = set(problem_ids)
        #     user_history_items = History.query.filter(History.user == user_id, History.problem.in_(problem_ids))
        #     for h in user_history_items:
        #         if h.event in event_to_number:
        #             user_history[user_id][h.problem] = max(user_history[user_id][h.problem], event_to_number[h.event])
        #             num_appearances[h.problem] += 1
        #             exposed_problems[user_id].add(h.problem)
        #     user_remaining_trajectory_items = trajectory_list[:]
        #     for i, t in enumerate(user_remaining_trajectory_items):
        #         for problem_id in problems_by_topic[t]:
        #             if user_history[user_id][problem_id] >= 2 and problem_id not in counted_problems:
        #                 user_remaining_trajectory_items[i] = 0
        #                 problems_available_for_user[user_id].remove(problem_id)
        #                 if problem_id in clones:
        #                     problems_available_for_user[user_id] -= clones[problem_id]
        #                 break
        #     problems_for_user_uncovered_topics = set()
        #     user_remaining_trajectory_items = list(filter(None, user_remaining_trajectory_items))
        #     for topic_id in user_remaining_trajectory_items:
        #         problems_for_user_uncovered_topics.update(problems_by_topic[topic_id])
        #     problems_available_for_user[user_id].intersection_update(problems_for_user_uncovered_topics)
        #     remaining_trajectory_items[user_id] = user_remaining_trajectory_items
        #
        # penalty_for_having_same_problem_on_next_quiz = 1
        # penalty_for_not_giving_a_brand_new_problem = 1
        # penalty_for_giving_clone_of_exposed_problem = 1
        # penalty_for_having_underflow = 1000
        #
        # lp = LpProblem(name='Test Generation', sense=LpMinimize)
        # lp_objective = LpAffineExpression()
        #
        # lp_vars_user_problem = dict()
        # for user_id in users:
        #     for problem_id in problems_available_for_user[user_id]:
        #         lp_vars_user_problem[(user_id, problem_id)] = LpVariable(
        #             name='user_problem_{}_{}'.format(user_id, problem_id), cat='Binary')
        #
        # for user_id in users:
        #     # Number of problems for user should definitely not exceed the maximum
        #     lp += (sum(lp_vars_user_problem[(user_id, problem_id)] for problem_id in
        #                problems_available_for_user[user_id]) <= max_problems_per_user)
        #     # Number of problems for user should preferably be no less than minimum
        #     min_problems = min(max_problems_per_user, len(problems_available_for_user[user_id]),
        #                        len(remaining_trajectory_items))
        #     lp_underflow_variable = LpVariable('underflow_{}'.format(user_id), lowBound=0)
        #     lp += (sum(lp_vars_user_problem[(user_id, problem_id)] for problem_id in
        #                problems_available_for_user[user_id]) + lp_underflow_variable >= min_problems)
        #     lp_objective += penalty_for_having_underflow * lp_underflow_variable
        #
        # for user_id in users:
        #     for level in set(topic_levels.values()):
        #         lp_vars_levels = {level: LpVariable(name='user_level_{}_{}'.format(user_id, level), cat='Binary')}
        #     for level_lower, level_upper in combinations(set(topic_levels.values()), 2):
        #         if level_lower > level_upper:
        #             level_lower, level_upper = level_upper, level_lower
        #
        #     for topic_id in remaining_trajectory_items[user_id]:
        #         problems_for_user_and_topic = problems_by_topic[topic_id] & problems_available_for_user[user_id]
        #         if len(problems_for_user_and_topic) >= 2:
        #             # The number of problems for any topic should not exceed the number
        #             # of times this topic appears in a trajectory
        #             # TODO: make it work when the number of times exceeds 2
        #             lp += (
        #                 sum(lp_vars_user_problem[(user_id, problem_id)] for problem_id in
        #                     problems_for_user_and_topic) <= 1)
        #         lp_var = LpVariable(name='gets_topic_{}_{}'.format(user_id, topic_id), cat='Binary')
        #         lp += (lp_var >= topic_levels[topic_id])
        #
        # for user_id in users:
        #     for problem_id in problems_available_for_user[user_id]:
        #         if problem_id in exposed_problems[user_id]:
        #             lp_objective += penalty_for_having_same_problem_on_next_quiz * lp_vars_user_problem[
        #                 (user_id, problem_id)]
        #         if num_appearances[problem_id] > 0:
        #             lp_objective += penalty_for_not_giving_a_brand_new_problem * lp_vars_user_problem[
        #                 (user_id, problem_id)]
        #     clones_of_exposed_problems = reduce(operator_or,
        #                                         (clones[problem_id] for problem_id in exposed_problems[user_id]),
        #                                         set()) - exposed_problems[user_id]
        #     for problem_id in problems_available_for_user[user_id] & clones_of_exposed_problems:
        #         lp_objective += penalty_for_giving_clone_of_exposed_problem * lp_vars_user_problem[
        #             (user_id, problem_id)]
        #
        # lp.setObjective(lp_objective)
        #
        # try:
        #     lp.solve()
        #     log_info = 'Problem status is “{}” with objective function value “{}”'.format(LpStatus[lp.status],
        #                                                                                   lp.objective.value())
        # except:
        #     log_info = 'Failed to solve the linear program'
        #
        # problem_sets = defaultdict(list)
        # for user_id, problem_id in lp_vars_user_problem:
        #     if lp_vars_user_problem[(user_id, problem_id)].value() > 0:
        #         problem = problems_for_trajectory[problem_id]
        #         problem_sets[user_id].append({
        #             'id': problem_id,
        #             'text': latex_to_html(problem.statement, variation=current_variation[problem_id]),
        #             'level': topic_levels[int(problem.topics)]
        #         })
        #
        #         current_variation[problem_id] += 1
        #
        # return render_template(
        #     'test_printout.html',
        #     problems=problem_sets,
        #     users=users,
        #     group=group_number,
        #     suggested_test_number=suggested_test_number,
        #     date=date.today().isoformat(),
        #     max_problems=max_problems_per_user,
        #     log_info=log_info)

        exposure = Exposure()
        exposure.course_id = course_id
        exposure.title = exposure_title
        exposure.timestamp = datetime.strptime(exposure_timestamp, '%Y-%m-%dT%H:%M')
        db.session.add(exposure)
