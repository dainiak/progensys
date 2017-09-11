from flask import Blueprint, render_template, request, abort, jsonify, url_for
import flask_login
from json import loads as load_json

from blueprints.models import \
    db, \
    Group, \
    Participant, \
    Role, \
    TrajectoryContent, \
    Trajectory, \
    User, \
    GroupMembership

migration_tools_blueprint = Blueprint('migration_tools', __name__, template_folder='templates')


@migration_tools_blueprint.route('/migration_tools', methods=['POST', 'GET'])
@flask_login.login_required
def interface():
    if request.method == 'GET':
        return render_template('form.html')
    else:
        json_data = request.get_json()
        if not json_data or not json_data.get('request'):
            return 'Пустой запрос'
        user_request = json_data['request']
        if user_request == 'add_users':
            users = json_data.get('users')
            for u in users:
                username = u['name']
                if len(username.split()) == 2:
                    new_user = User()
                    new_user.name_last, new_user.name_first = username.split()
                    new_user.email = u.get('email', '')
                    new_user.username = u.get('username', u['name'])
                    db.session.add(new_user)

            db.session.commit()
            return 'Добавлено пользователей произведено'

        elif user_request == 'add_learners':
            course_id = json_data.get('course_id')
            usernames = json_data.get('usernames')
            role_id = Role.query.filter_by(code='LEARNER').first().id
            for username in usernames:
                user_id = User.query.filter_by(username=username).first().id
                p = Participant(user_id, course_id, role_id)
                db.session.add(p)

            db.session.commit()
            return 'Добавлено студентов произведено'

        elif user_request == 'assign_groups':
            usernames = json_data.get('usernames')
            group_code = json_data.get('group_code')
            group_id = Group.query.filter_by(code=group_code).first().id
            if not group_id:
                return 'Несуществующая группа'

            for username in usernames:
                user_id = User.query.filter_by(username=username).first().id
                gm = GroupMembership(user_id, group_id)
                db.session.add(gm)

            db.session.commit()
            return 'Распределение по группам выполнено'

        return 'Запрос не распознан'
