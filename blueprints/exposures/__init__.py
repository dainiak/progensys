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
    ProblemStatusInfo

from datetime import datetime
from json import dumps as to_json_string
from operator import attrgetter

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
