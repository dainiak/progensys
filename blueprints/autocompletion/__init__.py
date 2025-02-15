from flask import Blueprint, request, jsonify

from blueprints.models import db, Topic

autocompletion_blueprint = Blueprint("autocompletion", __name__, template_folder="templates")


@autocompletion_blueprint.route("/api/autocomplete/topic_code", methods=["POST"])
def autocomplete_topic_code():
    query = request.get_json("query")
    topic_codes = db.session.query(Topic.code).filter(Topic.code.like(f"%{query}%")).all()
    return jsonify(matches=[item[0] for item in topic_codes])
