from flask import Blueprint, render_template, request, abort, jsonify, current_app
import flask_login
from flask_mail import Message

from json import dumps as dump_json
from json import loads as load_json
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
    SystemAdministrator, \
    Problem, \
    ProblemStatus, \
    ExtraData

admin_tools_blueprint = Blueprint('admin_tools', __name__, template_folder='templates')


@admin_tools_blueprint.route('/admin_tools', methods=['POST', 'GET'])
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
            if group_code == 'CLEAR':
                for username in usernames:
                    user_id = User.query.filter_by(username=username).first().id
                    db.session.query(
                        GroupMembership
                    ).filter(
                        GroupMembership.user_id == user_id
                    ).delete()
                db.session.commit()
                return 'Список групп у представленных студентов очищен'

            group_id = Group.query.filter_by(code=group_code).first().id
            if not group_id:
                return 'Несуществующая группа'

            for username in usernames:
                user_id = User.query.filter_by(username=username).first().id
                gm = GroupMembership(user_id, group_id)
                db.session.add(gm)

            db.session.commit()
            return 'Распределение по группам выполнено'

        elif user_request == 'recover_password':
            if 'usernames' not in json_data:
                return 'Error'

            num_sent_mails = 0
            sent_mails_usernames = []
            usernames = json_data.get('usernames', [])
            left_usernames = set(usernames)
            for user in User.query.filter(User.username.in_(usernames)).all():
                if not user.email:
                    return jsonify(result='Невозможно выслать пароль: не указан email.')

                random.seed(str(datetime.now()))
                letters = 'qwertyuiopasdfghjklzxcvbnm1029384756'
                new_password = ''.join(letters[int(random.random() * len(letters))] for _ in range(8))

                msg = Message(subject='Пароль к информационной системе',
                              body=
f'''Ваше имя пользователя для входа в систему progensys.dainiak.com: “{user.username}”
Ваш пароль для входа: “{new_password}”
Письмо выслано автоматически; пожалуйста, не отвечайте на него.''',
                              recipients=[user.email])
                current_app.config['MAILER'].send(msg)
                num_sent_mails += 1
                sent_mails_usernames.append((user.username, new_password))
                left_usernames.discard(user.username)

                user.password_hash = md5(new_password)

            db.session.commit()
            return (
                f'Восстановление паролей прошло успешно, отправлено {num_sent_mails} писем по логинам: {sent_mails_usernames}'
                +'\n' + f'Письма не отправлены на логины: {left_usernames}'
            )

        elif user_request == 'change_dollars_to_brackets':
            import re
            q = Problem.query
            if 'problem_id' in json_data:
                q = q.filter(Problem.id == json_data['problem_id'])
            elif not json_data.get('all'):
                return 'Не указано, какие задачи менять.'

            n = 0
            for problem in q.all():
                problem.statement = re.sub(r'\${2}([^$]+)\${2}', r'\[\1\]', problem.statement)
                problem.statement = re.sub(r'\$([^$]+)\$', r'\(\1\)', problem.statement)
                n += 1
            db.session.commit()
            return 'Запрос выполнен успешно. Просмотрено {} задач.'.format(n)

        elif user_request == 'assign_time_points':
            course_id = json_data.get('course_id')
            if not course_id:
                return 'Не указан курс'
            for user_id, in db.session.query(
                        Participant.user_id
                    ).filter(
                        Participant.course_id == course_id,
                        Participant.role_id == Role.id,
                        Role.code == 'LEARNER'
                    ).all():
                ed = ExtraData()
                ed.user_id = user_id
                ed.course_id = course_id
                ed.key = 'time_points'
                ed.value = '100'
                db.session.add(ed)
            db.session.commit()
            return 'Запрос выполнен успешно.'

        elif user_request == 'add_extra_data':
            course_id = json_data.get('course_id')

            if not course_id:
                return 'Не указан курс'
            for datum in json_data['data']:
                ed = ExtraData()
                ed.course_id = course_id
                if 'user_id' in datum:
                    ed.user_id = datum['user_id']
                else:
                    ed.user_id = User.query.filter_by(username=datum['username']).first().id
                ed.key = datum['key']
                ed.value = datum['value']
                db.session.add(ed)

            db.session.commit()
            return 'Запрос выполнен успешно.'

        elif user_request == 'change_problem_status':
            problem_id = json_data.get('problem_id') or json_data.get('problem')
            user_id = json_data.get('user_id') or json_data.get('user')
            status = json_data.get('status')
            status_id = json_data.get('status_id')

            if not problem_id or not user_id or not status:
                return 'Не указаны данные problem_id, user_id, status'

            if status_id is None:
                if 'incorrect' in status.lower() or 'wrong' in status.lower():
                    status_id = 3
                elif 'revision' in status.lower():
                    status_id = 4
                elif 'correct' in status.lower():
                    status_id = 5
                elif 'not_exposed' in status.lower():
                    status_id = 0
                else:
                    return 'Не указан верный status'

            ps = ProblemStatus.query.filter_by(user_id=user_id,problem_id=problem_id).first()
            if not ps:
                ps = ProblemStatus()
                ps.user_id=user_id
                ps.problem_id=problem_id
                ps.reference_exposure_id = None
                ps.timestamp_last_changed = datetime.now()

            ps.status_id = status_id
            # ps.reference_exposure_id = None
            ps.timestamp_last_changed = datetime.now()
            db.session.add(ps)
            db.session.commit()
            return 'Запрос выполнен успешно.'

        elif user_request == 'bulk_add_learners':
            course_id = json_data.get('course_id')
            username_postfix = json_data.get('username_postfix', '')
            if username_postfix != '':
                username_postfix = '_' + username_postfix

            if not course_id:
                return 'Не указан курс'
            role_id = Role.query.filter_by(code='LEARNER').first().id
            data = json_data.get('data')
            for line in data.strip().splitlines():
                name, surname, email_main, group_code, email_overleaf, id_stepik, id_overleaf = line.split('\t')
                if ('@' not in email_main) or ('@' not in email_overleaf) or ('@' in group_code) or (not id_stepik.isdecimal()):
                    break

                username = f'{surname}_{name}{username_postfix}'
                new_user = User.query.filter_by(username=username).first()
                if not new_user:
                    new_user = User()
                    new_user.name_last, new_user.name_first = surname, name
                    new_user.email = email_main
                    new_user.username = username
                    db.session.add(new_user)
                    db.session.commit()
                user_id = new_user.id

                if not Participant.query.filter_by(user_id=user_id, course_id=course_id, role_id=role_id).first():
                    p = Participant(user_id, course_id, role_id)
                    db.session.add(p)
                    db.session.commit()

                group = Group.query.filter_by(code=group_code).first()
                if group:
                    group_id = group.id
                else:
                    group = Group()
                    group.code = group_code
                    title = group_code
                    suggested_role = role_id
                    suggested_course = course_id
                    db.session.add(group)
                    db.session.commit()
                    group_id = group.id

                if not GroupMembership.query.filter_by(user_id=user_id, group_id=group_id).first():
                    gm = GroupMembership(user_id, group_id)
                    db.session.add(gm)
                    db.session.commit()
                ed = ExtraData()
                ed.course_id = course_id
                ed.user_id = user_id
                ed.key = 'time_points'
                ed.value = 100
                db.session.add(ed)
                ed = ExtraData()
                ed.course_id = course_id
                ed.user_id = user_id
                ed.key = 'sharelatex_project_id'
                ed.value = id_overleaf
                db.session.add(ed)

            db.session.commit()
            return 'Запрос выполнен успешно.'


        return 'Запрос не распознан'

