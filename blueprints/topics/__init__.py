from flask import Blueprint, render_template, request, abort, jsonify
from blueprints.models import db, Role, Participant, Course, Topic
import flask_login

topics_blueprint = Blueprint("topics", __name__, template_folder="templates")


@topics_blueprint.route("/topics/", methods=["GET"])
@topics_blueprint.route("/topics", methods=["GET"])
def view_topics():
    return render_template("view_topics.html")


@topics_blueprint.route("/api/topic", methods=["POST"])
def api():
    if not request.get_json() or not request.get_json().get("action"):
        abort(400)

    if not flask_login.current_user or not flask_login.current_user.username:
        abort(400)

    user_id = flask_login.current_user.id
    course_id = flask_login.current_user.current_course_id or Course.query.first().id
    json = request.get_json()
    action = json.get("action")

    role_code = (
        db.session.query(Role.code)
        .filter(Participant.user_id == user_id, Participant.course_id == course_id, Role.id == Participant.role_id)
        .scalar()
    )

    if role_code not in ["INSTRUCTOR", "ADMIN"]:
        abort(403)

    if action == "load":
        topic_query = Topic.query
        filter_params = json.get("filter")
        if filter_params.get("id"):
            topic_query = topic_query.filter(Topic.id == filter_params.get("id"))
        if filter_params.get("title"):
            topic_query = topic_query.filter(Topic.title.like(f"%{filter_params.get('title')}%"))
        if filter_params.get("comment"):
            topic_query = topic_query.filter(Topic.comment.like(f"%{filter_params.get('comment')}%"))
        if filter_params.get("code"):
            topic_query = topic_query.filter(Topic.code.like(f"%{filter_params.get('code')}%"))

        return jsonify(
            list(
                {"id": topic.id, "code": topic.code, "title": topic.title, "comment": topic.comment}
                for topic in topic_query.all()
            )
        )

    elif action == "delete":
        item = json.get("item")
        if not item:
            abort(400)
        if item.get("id"):
            db.session.delete(Topic.query.filter_by(id=item["id"]).first())
            db.session.commit()
        else:
            abort(400)
        db.session.commit()
        return jsonify(result="Success")

    elif action == "insert":
        item = json.get("item")
        if not item:
            abort(400)
        if item.get("code"):
            topic = Topic()
            topic.title = item.get("title")
            topic.code = item.get("code")
            topic.comment = item.get("comment")
            db.session.add(topic)
            db.session.commit()
            return jsonify({"id": topic.id, "code": topic.code, "title": topic.title, "comment": topic.comment})
        else:
            abort(400)

    elif action == "update":
        item = json.get("item")
        if not item or not item.get("id") or not item.get("code"):
            abort(400)

        topic = Topic.query.filter_by(id=item["id"]).first()
        if not topic:
            abort(400)

        topic.comment = item.get("comment")
        topic.code = item.get("code")
        topic.title = item.get("title")
        db.session.commit()

        return jsonify(item)

    abort(400)
