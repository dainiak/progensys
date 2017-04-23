from flask import Blueprint, render_template, request, abort, jsonify, url_for
from blueprints.models import db, Role, Participant, Course, User, SystemAdministrator, Group, GroupMembership
import flask_login

from json import dumps as to_json_string

courses_blueprint = Blueprint('courses', __name__, template_folder='templates')


@courses_blueprint.route('/api/courses', methods=['POST'])
def api_courses():
    if not request.get_json() or not request.get_json().get('action'):
        abort(400)

    if not flask_login.current_user or not flask_login.current_user.username:
        abort(400)

    user_username = flask_login.current_user.username
    user_id = flask_login.current_user.id
    json = request.get_json()
    action = json.get('action')

    if action == 'get_available_courses':
        data = db.session.query(
            Course.id,
            Course.title,
            Course.description,
            Role.title,
            Role.description
        ).filter(
            User.username == user_username,
            Participant.user_id == User.id,
            Participant.course_id == Course.id,
            Role.id == Participant.role_id
        ).all()

        return jsonify(list(
            {
                'course_id': course_id,
                'course_title': course_title,
                'course_description': course_description,
                'role_title': role_title,
                'role_description': role_description
            }
            for course_id, course_title, course_description, role_title, role_description in data
        ))
    elif action == 'get_available_actions' and json.get('course_id'):
        course_id = json.get('course_id')
        role_code = db.session.query(Role.code).filter(
            Participant.user_id == user_id,
            Participant.course_id == course_id,
            Participant.role_id == Role.id
        ).scalar()
        if not role_code:
            abort(403)
        action_list = []
        if role_code == 'ADMIN':
            action_list.append({
                'title': 'Управление участниками',
                'url': url_for('courses.participant_management_view', course_id=course_id)
            })
        if role_code in ['ADMIN', 'INSTRUCTOR']:
            action_list.append({
                'title': 'Редактирование задач',
                'url': url_for('problems.view')
            })

        return jsonify(action_list)


@courses_blueprint.route('/courses/', methods=['GET'])
@courses_blueprint.route('/courses', methods=['GET'])
def view_courses():
    return render_template('view_available_courses.html')


@courses_blueprint.route('/course-<int:course_id>/')
@courses_blueprint.route('/course-<int:course_id>')
def view_course(course_id):
    if not flask_login.current_user or not flask_login.current_user.username:
        abort(403)
    role_code = db.session.query(Role.code).filter(
        Participant.user_id == flask_login.current_user.id,
        Participant.course_id == course_id,
        Participant.role_id == Role.id
    ).scalar()
    if not role_code:
        abort(403)

    return render_template(
        'view_course.html',
        course_id=course_id
    )


@courses_blueprint.route('/course-<int:course_id>/participants', methods=['GET'])
@flask_login.login_required
def participant_management_view(course_id):
    if not(flask_login.current_user
            and flask_login.current_user.id
            and SystemAdministrator.query.filter_by(user_id=flask_login.current_user.id)):
        abort(403)

    course_title = Course.query.filter_by(id=course_id).first().title
    roles = to_json_string(list(
        {'role_id': role_id, 'role_title': role_title}
        for role_id, role_title in db.session.query(Role.id, Role.title).all()
    ))

    return render_template('view_participants.html', course_id=course_id, roles=roles, course_title=course_title)


@courses_blueprint.route('/api/participant', methods=['POST'])
@flask_login.login_required
def api_participants():
    json = request.get_json()
    if not json or not json.get('action') or not json.get('course_id'):
        return abort(400)
    action = json['action']
    course_id = json['course_id']
    if not db.session.query(Participant).filter(
                    Participant.user_id == flask_login.current_user.id,
                    Participant.course_id == course_id,
                    Participant.role_id == Role.id,
                    Role.code.in_(['ADMIN', 'INSTRUCTOR'])
            ):
        abort(403)

    if action == 'load':
        query = db.session.query(
            User.id,
            User.username,
            User.name_first,
            User.name_last,
            User.name_middle,
            User.email,
            Participant.role_id
        ).filter(
            Participant.course_id == course_id,
            Participant.user_id == User.id
        )

        if json.get('filter'):
            frontend_filter = json['filter']
            if frontend_filter.get('username'):
                query = query.filter(User.username.like('%' + frontend_filter['username'] + '%'))
            if frontend_filter.get('name_last'):
                query = query.filter(User.name_last.like('%' + frontend_filter['name_last'] + '%'))
            if frontend_filter.get('name_first'):
                query = query.filter(User.name_first.like('%' + frontend_filter['name_first'] + '%'))
            if frontend_filter.get('name_middle'):
                query = query.filter(User.name_middle.like('%' + frontend_filter['name_middle'] + '%'))
            if frontend_filter.get('email'):
                query = query.filter(User.email.like('%' + frontend_filter['email'] + '%'))
            if frontend_filter.get('role_id'):
                query = query.filter(
                    Participant.user_id == User.id,
                    Participant.course_id == course_id,
                    Participant.role_id == frontend_filter['role_id']
                )
            if frontend_filter.get('groups'):
                groups = [x.strip() for x in frontend_filter['groups'].strip().split() if x]
                query = query.filter(
                    GroupMembership.user_id == User.id,
                    GroupMembership.group_id == Group.id, Group.code.in_(groups)
                )

        data = []
        for uid, username, name_first, name_last, name_middle, email, role_id in query.all():
            groups = db.session.query(Group.code).filter(
                Group.id == GroupMembership.group_id,
                GroupMembership.user_id == uid
            ).all()

            groups = ' '.join(g[0] for g in groups) if groups else '—'

            data.append({
                'user_id': uid,
                'username': username,
                'name_first': name_first,
                'name_last': name_last,
                'name_middle': name_middle,
                'email': email,
                'role_id': role_id,
                'groups': groups
            })

        return jsonify(data)
    elif json['action'] == 'insert':
        if not json.get('item') or not json.get('course_id') or not json['item'].get('role_id'):
            abort(400)

        item = json['item']
        query = db.session.query(User.id)

        if item.get('user_id'):
            query = query.filter(User.id == item['user_id'])
        if item.get('username'):
            query = query.filter(User.username == item['username'])
        if item.get('name_first'):
            query = query.filter(User.name_first == item['name_first'])
        if item.get('name_last'):
            query = query.filter(User.name_last == item['name_last'])
        if item.get('name_middle'):
            query = query.filter(User.name_middle == item['name_middle'])
        if item.get('email'):
            query = query.filter(User.email == item['email'])

        user_id = query.scalar()
        if not user_id:
            abort(404)

        course_id = json['course_id']

        if db.session.query(Participant.user_id).filter(Participant.user_id == user_id, Participant.course_id == course_id).first():
            abort(400)

        participant = Participant(user_id, course_id, item['role_id'])
        db.session.add(participant)
        db.session.commit()
        uid, username, name_first, name_last, name_middle, email, role_id = db.session.query(
            User.id,
            User.username,
            User.name_first,
            User.name_last,
            User.name_middle,
            User.email,
            Participant.role_id
        ).filter(
            User.id == user_id,
            Participant.role_id,
            Participant.course_id == course_id,
            Participant.user_id == User.id
        ).first()

        groups = db.session.query(Group.code).filter(
            Group.id == GroupMembership.group_id,
            GroupMembership.user_id == uid
        ).all()

        groups = ' '.join(g[0] for g in groups) if groups else '—'

        return jsonify({
                'user_id': uid,
                'username': username,
                'name_first': name_first,
                'name_last': name_last,
                'name_middle': name_middle,
                'email': email,
                'role_id': role_id,
                'groups': groups
            })

    elif json['action'] == 'delete':
        if not json.get('item') or not json.get('course_id'):
            abort(400)
        item = json['item']
        if not item.get('user_id'):
            abort(400)

        participant = Participant.query.filter_by(user_id=item['user_id'], course_id=json['course_id']).first()
        if not participant:
            abort(404)

        db.session.delete(participant)
        db.session.commit()
        return jsonify(result='Success')

    abort(400, 'Action not supported')