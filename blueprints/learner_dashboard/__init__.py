from flask import Blueprint, render_template, request, abort, jsonify
import flask_login

from blueprints.models import \
    db, \
    User, \
    ExposureContent, \
    ProblemSet, \
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


learner_dashboard_blueprint = Blueprint('learner_dashboard', __name__, template_folder='templates')

@learner_dashboard_blueprint.route('/course-<int:course_id>/exposure-<exposure_string>/grading', methods=['GET'])
@flask_login.login_required
def view_grading_table(exposure_string, course_id, group=None):
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
    elif exposure_string.isdecimal():
        exposure_ids = [int(exposure_string)]
    else:
        abort(400)

    if len(exposure_ids) == 0:
        abort(404)

    if group is not None and not db.session.query(db.exists().where(Group.code == group)).scalar():
        return jsonify(error='Group not found')

    user_query = db.session.query(User.id).filter(
        ExposureContent.exposure_id.in_(exposure_ids),
        ExposureContent.user_id == User.id
    )

    if group is not None:
        group_id = Group.query.filter_by(code=group).first().id
        user_query = user_query.filter(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == User.id
        )

    user_ids = list(map(lambda x: x[0], user_query.all()))
    problem_statuses = [{'icon': ps.icon, 'id': ps.id} for ps in ProblemStatusInfo.query.all()]

    return render_template(
        'view_grading_results.html',
        exposure_ids=to_json_string(exposure_ids),
        user_ids=to_json_string(user_ids),
        problem_statuses=to_json_string(problem_statuses),
        course_id=course_id
    )
