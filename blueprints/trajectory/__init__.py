from flask import Blueprint, render_template, request, abort, jsonify
import flask_login

from blueprints.models import \
    db, \
    Topic, \
    Participant, \
    Role, \
    TrajectoryContent

trajectory_blueprint = Blueprint('trajectory', __name__, template_folder='templates')


@trajectory_blueprint.route('/api/trajectory', methods=['POST'])
@flask_login.login_required
def api_trajectory():
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
        if not json.get('trajectory_id'):
            return jsonify(error='Trajectory ID not specified')

        trajectory_id = json['trajectory_id']

        data = sorted(db.session.query(
            TrajectoryContent.sort_key,
            TrajectoryContent.id,
            TrajectoryContent.topic_id,
            Topic.code
        ).filter(
            TrajectoryContent.trajectory_id == trajectory_id,
            Topic.id == TrajectoryContent.topic_id
        ).all())
        result = []
        for sort_key, item_id, topic_id, topic_code in data:
            result.append({
                'sort_key': sort_key,
                'id': item_id,
                'topic_id': topic_id,
                'topic_code': topic_code
            })

        return jsonify(result)

    elif json['action'] == 'reorder':
        if not json.get('trajectory_id') or not json.get('ids'):
            return jsonify(error='Trajectory ID or reordering not specified')

        trajectory_id = json['trajectory_id']
        new_order = json['ids']
        items = {tc.id: tc for tc in db.session.query(
            TrajectoryContent
        ).filter(
            TrajectoryContent.trajectory_id == trajectory_id,
            TrajectoryContent.id.in_(new_order)
        ).all()}

        for i, item_id in enumerate(new_order):
            items[item_id].sort_key = 10 * (i + 1)

        db.session.commit()
        return jsonify(result='Successfully reordered items')

    elif json['action'] == 'insert':
        if not json.get('trajectory_id'):
            return jsonify(error='Trajectory ID not specified')
        if not json.get('topic_id') and not json.get('topic_code'):
            return jsonify(error='Neither topic ID not code is specified')
        trajectory_id = json['trajectory_id']
        sort_key = json.get('sort_key')
        topic_id = json.get('topic_id')
        topic_code = json.get('topic_code')
        if not topic_code:
            topic_code = Topic.query.filter_by(id=topic_id).first().code
        elif not topic_id:
            topic_id = Topic.query.filter_by(code=topic_code).first().id
        tc = TrajectoryContent(trajectory_id, topic_id, sort_key)
        db.session.add(tc)
        db.session.commit()

        return jsonify(id=tc.id, topic_id=tc.topic_id, topic_code=topic_code, sort_key=tc.sort_key)

    elif json['action'] == 'update':
        if not json.get('trajectory_id'):
            return jsonify(error='Trajectory ID not specified')
        if not json.get('id'):
            return jsonify(error='Item ID not specified')
        if not json.get('topic_id') and not json.get('topic_code'):
            return jsonify(error='Neither topic ID not code is specified')

        sort_key = json.get('sort_key')
        topic_id = json.get('topic_id')
        topic_code = json.get('topic_code')
        if not topic_code:
            topic_code = Topic.query.filter_by(id=topic_id).first().code
        elif not topic_id:
            topic_id = Topic.query.filter_by(code=topic_code).first().id
        tc = TrajectoryContent.query.filter_by(trajectory_id=json['trajectory_id'], id=json['id']).first()
        if not tc:
            abort(400, 'Specified item not found or does not belong to the trajectory')
        tc.topic_id = topic_id
        tc.sort_key = sort_key
        db.session.commit()

        return jsonify(id=tc.id, topic_id=tc.topic_id, topic_code=topic_code, sort_key=tc.sort_key)

    elif json['action'] == 'delete':
        if not json.get('id'):
            return jsonify(error='ID not specified')
        tc = TrajectoryContent.query.filter_by(id=json['id']).first()
        if not tc:
            return jsonify(error='Item with specified ID not found')
        db.session.delete(tc)
        db.session.commit()
        return jsonify(result='Item successfuly deleted')

    abort(400, 'Your request should be insert/delete/reorder')


@trajectory_blueprint.route('/trajectory/trajectory-<int:trajectory_id>', methods=['GET'])
@flask_login.login_required
def view_trajectory(trajectory_id):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == flask_login.current_user.current_course_id,
                Participant.role_id == Role.id,
                Role.code == 'ADMIN'
            ).exists():
        abort(403)

    return render_template('view_trajectory.html', trajectory_id=trajectory_id)

