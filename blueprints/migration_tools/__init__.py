from flask import Blueprint, render_template, request, abort, jsonify, current_app
import flask_login
from flask_mail import Message

from json import dumps as dump_json
import random
from datetime import datetime

from hashlib import md5 as md5hasher
def md5(s):
    m = md5hasher()
    m.update(s.encode())
    return m.hexdigest()

from blueprints.models import \
    db, \
    Group, \
    Participant, \
    Role, \
    User, \
    GroupMembership, \
    ParticipantExtraInfo, \
    SystemAdministrator

migration_tools_blueprint = Blueprint('migration_tools', __name__, template_folder='templates')


@migration_tools_blueprint.route('/migration_tools', methods=['POST', 'GET'])
@flask_login.login_required
def interface():
    if not SystemAdministrator.query.filter_by(user_id=flask_login.current_user.id).first():
        abort(403)

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
            return 'Добавление пользователей произведено'

        elif user_request == 'add_learners':
            course_id = json_data.get('course_id')
            usernames = json_data.get('usernames')
            role_id = Role.query.filter_by(code='LEARNER').first().id
            for username in usernames:
                user_id = User.query.filter_by(username=username).first().id
                p = Participant(user_id, course_id, role_id)
                db.session.add(p)

            db.session.commit()
            return 'Добавление студентов произведено'

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

        elif user_request == 'add_extra_participant_info':
            course_id = json_data.get('course_id')
            for item in json_data.get('data'):
                user_id = User.query.filter_by(username=item['username']).first().id
                pef = ParticipantExtraInfo(user_id, course_id, dump_json(item['extra_participant_info']))
                db.session.add(pef)
            db.session.commit()
            return 'Данные внесены успешно'
        elif user_request == 'recover_password':
            if 'usernames' not in json_data:
                return 'Error'

            num_sent_mails = 0
            for user in User.query.filter(User.username.in_(json_data.get('usernames'))).all():
                if not user.email:
                    return jsonify(result='Невозможно выслать пароль: не указан email.')

                random.seed(str(datetime.now()))
                letters = 'qwertyuiopasdfghjklzxcvbnm1029384756'
                new_password = ''.join(letters[int(random.random() * len(letters))] for _ in range(8))

                msg = Message(subject='Временный пароль к информационной системе',
                              body='''Ваше имя пользователя для входа в систему progensys.dainiak.com: “{}”\nВаш пароль для входа: “{}”'''.format(user.username, new_password),
                              recipients=[user.email])
                current_app.config['MAILER'].send(msg)
                num_sent_mails += 1

                user.password_hash = md5(new_password)

            db.session.commit()
            return 'Восстановление паролей прошло успешно, отправлено {} писем.'.format(num_sent_mails)

        return 'Запрос не распознан'
