from flask import Blueprint, render_template, request, abort, jsonify, url_for
import flask_login

from blueprints.models import \
    db, \
    Topic, \
    Participant, \
    Role, \
    TrajectoryContent, \
    Trajectory, \
    TopicLevelAssignment

trajectory_blueprint = Blueprint('trajectory', __name__, template_folder='templates')


@trajectory_blueprint.route('/api/trajectory', methods=['POST'])
@flask_login.login_required
def api_trajectory():
    json = request.get_json()
    if not json or 'action' not in json or 'trajectory_id' not in json:
        abort(400)

    trajectory_id = json['trajectory_id']
    action = json['action']

    course_id = db.session.query(
        Participant.course_id
    ).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == Trajectory.course_id,
        Trajectory.id == trajectory_id,
        Participant.role_id == Role.id,
        Role.code.in_(['ADMIN', 'INSTRUCTOR'])
    ).first()

    if not course_id:
        abort(403)
    course_id = course_id[0]

    if action == 'load':
        data = db.session.query(
            TrajectoryContent.sort_key,
            TrajectoryContent.id,
            TrajectoryContent.topic_id,
            Topic.code
        ).filter(
            TrajectoryContent.trajectory_id == trajectory_id,
            Topic.id == TrajectoryContent.topic_id
        ).order_by(
            TrajectoryContent.sort_key
        ).all()

        topic_levels = dict(db.session.query(
            TopicLevelAssignment.topic_id,
            TopicLevelAssignment.level
        ).filter(
            TopicLevelAssignment.course_id == course_id
        ).all())

        result = []
        for sort_key, item_id, topic_id, topic_code in data:
            result.append({
                'sort_key': sort_key,
                'id': item_id,
                'topic_id': topic_id,
                'topic_code': topic_code,
                'topic_level': topic_levels.get(topic_id)
            })

        return jsonify(result)

    elif json['action'] == 'reorder':
        if not json.get('ids'):
            abort(400)

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
        if not json.get('topic_id') and not json.get('topic_code'):
            abort(400)
        trajectory_id = json['trajectory_id']
        sort_key = json.get('sort_key')
        topic_id = json.get('topic_id')
        topic_code = json.get('topic_code')
        topic_level = json.get('topic_level')
        if not topic_code:
            topic_code = Topic.query.filter_by(id=topic_id).first().code
        elif not topic_id:
            topic_id = Topic.query.filter_by(code=topic_code).first().id
        if topic_level:
            tla = TopicLevelAssignment.query.filter(
                TopicLevelAssignment.course_id == course_id,
                TopicLevelAssignment.topic_id == topic_id
            ).first()
            if not tla:
                tla = TopicLevelAssignment(course_id, topic_id, topic_level)
                db.session.add(tla)
            else:
                tla.level = topic_level

        tc = TrajectoryContent(trajectory_id, topic_id, sort_key)
        db.session.add(tc)
        db.session.commit()

        return jsonify(
            id=tc.id,
            topic_id=tc.topic_id,
            topic_code=topic_code,
            sort_key=tc.sort_key,
            topic_level=topic_level
        )

    elif json['action'] == 'update':
        if not json.get('id'):
            abort(400)
        if not json.get('topic_id') and not json.get('topic_code'):
            abort(400)

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

        topic_level = json.get('topic_level')
        if topic_level:
            tla = TopicLevelAssignment.query.filter(
                TopicLevelAssignment.course_id == course_id,
                TopicLevelAssignment.topic_id == topic_id
            ).first()
            if not tla:
                tla = TopicLevelAssignment(course_id, topic_id, topic_level)
                db.session.add(tla)
            else:
                tla.level = topic_level

        tc.topic_id = topic_id
        tc.sort_key = sort_key
        db.session.commit()

        return jsonify(
            id=tc.id,
            topic_id=tc.topic_id,
            topic_code=topic_code,
            sort_key=tc.sort_key,
            topic_level=topic_level
        )

    elif json['action'] == 'delete':
        if not json.get('id'):
            return jsonify(error='ID not specified')
        tc = TrajectoryContent.query.filter_by(id=json['id']).first()
        if not tc:
            return jsonify(error='Item with specified ID not found')
        db.session.delete(tc)
        db.session.commit()
        return jsonify(result='Item successfuly deleted')

    abort(400, 'Your request should be insert/delete/reorder/update')


@trajectory_blueprint.route('/api/trajectories', methods=['POST'])
@flask_login.login_required
def api_trajectories():
    json = request.get_json()
    if not json:
        abort(400)

    course_id = json.get('course_id')
    if not course_id:
        abort(400)

    action = json.get('action')
    if not action:
        abort(400)

    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['ADMIN', 'INSTRUCTOR'])
            ).first():
        abort(403)

    if action == 'load':
        return jsonify(list(
            {
                'id': id,
                'title': title,
                'comment': comment,
                'url': url_for('trajectory.view_trajectory', trajectory_id=id)
            }
            for id, title, comment in db.session.query(
                Trajectory.id,
                Trajectory.title,
                Trajectory.comment
            ).filter(
                Trajectory.course_id == course_id
            ).all()))

    elif action == 'insert':
        item = json.get('item')
        if not item:
            abort(400)

        trajectory = Trajectory()
        trajectory.course_id = course_id
        if item.get('title'):
            trajectory.title = item['title']
        if item.get('comment'):
            trajectory.comment = item['comment']
        db.session.add(trajectory)
        db.session.commit()
        return jsonify({
            'id': trajectory.id,
            'title': trajectory.title,
            'comment': trajectory.comment
        })

    elif action == 'update':
        item = json.get('item')
        if not item:
            abort(400)
        if not item.get('id'):
            abort(400)

        trajectory = Trajectory.query.filter_by(id=item['id'], course_id=course_id).first()
        if not trajectory:
            abort(404)

        if item.get('title'):
            trajectory.title = item['title']
        if item.get('comment'):
            trajectory.comment = item['comment']

        db.session.commit()

        return jsonify({
            'id': trajectory.id,
            'title': trajectory.title,
            'comment': trajectory.comment
        })

    elif action == 'delete':
        item = json.get('item')
        if not item:
            abort(400)
        if not item.get('id'):
            abort(400)

        trajectory = Trajectory.query.filter_by(id=item['id'], course_id=course_id).first()
        if not trajectory:
            abort(404)

        db.session.delete(trajectory)
        db.session.commit()
        return jsonify(result='Success')


@trajectory_blueprint.route('/trajectory/trajectory-<int:trajectory_id>/', methods=['GET'])
@trajectory_blueprint.route('/trajectory/trajectory-<int:trajectory_id>', methods=['GET'])
@flask_login.login_required
def view_trajectory(trajectory_id):
    if not db.session.query(
                Participant
            ).filter(
                Participant.user_id == flask_login.current_user.id,
                Participant.course_id == Trajectory.course_id,
                Participant.role_id == Role.id,
                Role.code.in_(['ADMIN', 'INSTRUCTOR'])
            ).first():
        abort(403)

    trajectory_title = Trajectory.query.filter_by(id=trajectory_id).first().title

    return render_template(
        'view_trajectory.html',
        trajectory_id=trajectory_id,
        trajectory_title=trajectory_title
    )