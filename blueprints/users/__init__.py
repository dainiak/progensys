from flask import Blueprint, render_template, request, abort, jsonify, current_app, redirect, url_for
from flask_api import status as http_status_codes

from blueprints.models import \
    db, \
    Participant, \
    User, \
    ExposureContent, \
    GroupMembership, \
    ProblemStatus, \
    SystemAdministrator
import flask_login
from flask_mail import Message

import random
from hashlib import md5 as md5hasher
from datetime import datetime


def md5(s):
    m = md5hasher()
    m.update(s.encode())
    return m.hexdigest()

users_blueprint = Blueprint('users', __name__, template_folder='templates')


@users_blueprint.route('/users', methods=['GET'])
@flask_login.login_required
def user_management_view():
    if flask_login.current_user \
            and flask_login.current_user.id \
            and SystemAdministrator.query.filter_by(user_id=flask_login.current_user.id):
        return render_template('view_users.html')
    abort(403)


@users_blueprint.route('/api/user', methods=['POST'])
@flask_login.login_required
def api_user_management():
    if not (flask_login.current_user
            and flask_login.current_user.id
            and SystemAdministrator.query.filter_by(user_id=flask_login.current_user.id)):
        abort(403)

    json = request.get_json()
    if json and 'action' in json:
        if json['action'] == 'load':
            query = User.query

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

            users = query.limit(100).all()

            return jsonify(list({
                'id': u.id,
                'username': u.username,
                'name_first': u.name_first,
                'name_last': u.name_last,
                'name_middle': u.name_middle,
                'email': u.email
            } for u in users))
        elif json['action'] == 'update':
            changed = False
            if not json.get('item'):
                return jsonify(error='No item specified')
            item = json['item']
            if not item.get('id'):
                return jsonify(error='No ID specified')
            user = User.query.filter_by(id=item['id']).first()
            if not user:
                return jsonify(error='User with this id not found')
            if 'name_first' in item and item['name_first'] != user.name_first:
                changed = True
                user.name_first = item['name_first']
            if 'name_last' in item and item['name_last'] != user.name_last:
                changed = True
                user.name_last = item['name_last']
            if 'name_middle' in item and item['name_middle'] != user.name_middle:
                changed = True
                user.name_middle = item['name_middle']
            if 'username' in item and item['username'] and item['username'] != user.username:
                if db.session.query(db.exists().where(User.username == item['username'])).scalar():
                    if changed:
                        db.session.commit()
                    return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                                    'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
                changed = True
                user.username = item['username']

            if 'email' in item and item['email'] and item['email'] != user.email:
                if db.session.query(db.exists().where(User.email == item['email'])).scalar():
                    if changed:
                        db.session.commit()
                    return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                                    'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
                changed = True
                user.email = item['email']

            if changed:
                db.session.commit()
            return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                            'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
        elif json['action'] == 'insert':
            if not json.get('item'):
                return jsonify(error='No item specified')

            item = json['item']
            user = User()
            user.name_first = item.get('name_first', '')
            user.name_last = item.get('name_last', '')
            user.name_middle = item.get('name_middle', '')

            if not item.get('username'):
                return jsonify(error="Username not specified")
            if db.session.query(db.exists().where(User.username == item['username'])).scalar():
                return jsonify(error="Username already exists")
            user.username = item['username']

            if not item.get('email'):
                return jsonify(error="Email not specified")
            if db.session.query(db.exists().where(User.username == item['email'])).scalar():
                return jsonify(error="Email already exists")
            user.email = item['email']

            db.session.add(user)
            db.session.commit()
            return jsonify({'id': user.id, 'username': user.username, 'name_first': user.name_first,
                            'name_last': user.name_last, 'name_middle': user.name_middle, 'email': user.email})
        elif json['action'] == 'delete':
            if not json.get('item'):
                return jsonify(error='No item specified')
            item = json['item']
            if not item.get('id'):
                return jsonify(error='No ID specified')
            user = User.query.filter_by(id=item['id']).first()
            if not user:
                return jsonify(error='User with this id not found')

            db.session.query(
                ExposureContent
            ).filter(
                ExposureContent.user_id == user.id
            ).delete()

            db.session.query(
                Participant
            ).filter(
                Participant.user_id == user.id
            ).delete()

            db.session.query(
                GroupMembership
            ).filter(
                GroupMembership.user_id == user.id
            ).delete()

            db.session.query(
                ProblemStatus
            ).filter(
                ProblemStatus.user_id == user.id
            ).delete()

            db.session.delete(user)
            db.session.commit()
            return jsonify(result='Success')
        elif json['action'] == 'recover_password':
            if not (flask_login.current_user
                    and flask_login.current_user.id
                    and SystemAdministrator.query.filter_by(id=flask_login.current_user.id)):
                abort(403)

            if 'user_id' not in request.json:
                return jsonify(result='Error')

            user_id = int(request.json['user_id'])
            user = User.query.filter_by(id=user_id).first()

            if not user.email:
                return jsonify(result='Невозможно выслать пароль: не указан email.')

            random.seed(str(datetime.now()))
            letters = 'qwertyuiopasdfghjklzxcvbnm1029384756'
            new_password = ''.join(letters[int(random.random() * len(letters))] for _ in range(8))

            msg = Message(subject='Временный пароль к информационной системе',
                          body='''Ваше имя пользователя для входа в систему progensys.dainiak.com: {}\nВаш пароль для входа: {}'''.format(
                              user.username, new_password),
                          recipients=[user.email])
            current_app.config['MAILER'].send(msg)

            user.password_hash = md5(new_password)
            db.session.commit()

            return jsonify(result='Успешно выслан пароль "{0}"'.format(new_password))

    abort(400, 'Action not supported')


@users_blueprint.route('/api/authorization', methods=['POST'])
def api_authorization():
    if request.form and request.form.get('username') and request.form.get('password'):
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user is not None and hasattr(user, 'password_hash') and md5(request.form.get('password')) == user.password_hash:
            flask_login.login_user(user)
            return redirect(url_for('courses.view_courses'))
        else:
            abort(403)

    json = request.get_json()
    if not json:
        abort(400)
    if json.get('action') == 'login' and json.get('username'):
        user = User.query.filter_by(username=json.get('username')).first()
        if user is not None and hasattr(user, 'password_hash') and md5(json.get('password')) == user.password_hash:
            flask_login.login_user(user)
            return jsonify('Logged in'), http_status_codes.HTTP_200_OK
        else:
            abort(401)

    elif json.get('action') == 'logout':
        flask_login.logout_user()
        return jsonify('Logged out'), http_status_codes.HTTP_200_OK

    elif json.get('action') == 'get_authorized_user':
        if flask_login.current_user and hasattr(flask_login.current_user, 'username'):
            return jsonify({
                'id': flask_login.current_user.id,
                'username': flask_login.current_user.username,
                'name_first': flask_login.current_user.name_first,
                'name_last': flask_login.current_user.name_last
            }), http_status_codes.HTTP_200_OK
        return jsonify({
            'id': 0,
            'username': None
        }), http_status_codes.HTTP_200_OK

    abort(400)
