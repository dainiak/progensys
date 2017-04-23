from flask import Blueprint, render_template, request, abort, jsonify
import flask_login

from blueprints.models import \
    db, \
    User, \
    ExposureContent, \
    Problem, \
    GroupMembership, \
    ProblemSetContent, \
    Exposure, \
    Participant, \
    Role, \
    Group, \
    ExposureGrading, \
    ExposureGradingResult, \
    ProblemStatusInfo

from operator import attrgetter
from datetime import datetime
from json import dumps as to_json_string

grading_blueprint = Blueprint('grading', __name__, template_folder='templates')


@grading_blueprint.route('/api/grading', methods=['POST'])
@flask_login.login_required
def api_grading():
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


@grading_blueprint.route('/grading/date-<exposure_date>/group-<group>', methods=['GET'])
@grading_blueprint.route('/grading/date-<exposure_date>', methods=['GET'])
@flask_login.login_required
def view_grading_table(exposure_date, group=None):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == flask_login.current_user.current_course_id,
                Participant.role_id == Role.id,
                Role.code == 'ADMIN'
            ).exists():
        abort(403)

    if group is not None and not db.session.query(db.exists().where(Group.code == group)).scalar():
        return jsonify(error='Group not found')

    exposures = Exposure.query.all()
    exposure_ids = list(map(
        attrgetter('id'),
        filter(lambda x: x.timestamp.isoformat()[:10] == exposure_date, exposures)
    ))
    if len(exposure_ids) == 0:
        return jsonify(error='No exposures with specified date were found')

    if group is not None:
        group_id = Group.query.filter_by(code=group).first().id

        user_ids = list(map(
            lambda x: x[0],
            db.session.query(User.id).filter(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id == User.id,
                ExposureContent.exposure_id.in_(exposure_ids),
                ExposureContent.user_id == User.id)
            .all()))
    else:
        user_ids = list(map(lambda x: x[0], db.session.query(User.id).all()))

    all_problems = list(map(
        lambda x: x[0],
        db.session.query(
            Problem.id
        ).filter(
            Problem.id == ProblemSetContent.problem_id,
            ExposureContent.problem_set_id == ProblemSetContent.problem_set_id,
            ExposureContent.exposure_id.in_(exposure_ids),
            ExposureContent.user_id.in_(user_ids))
        .all()))
    problem_statuses = [{'name': ps.icon, 'id': ps.id} for ps in ProblemStatusInfo.query.all()]

    return render_template(
        'templates/view_grading_results.html',
        all_problems=to_json_string(all_problems),
        exposure_ids=to_json_string(exposure_ids),
        user_ids=to_json_string(user_ids),
        problem_statuses=to_json_string(problem_statuses)
    )
