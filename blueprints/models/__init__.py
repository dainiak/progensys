from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin as LoginUserMixin

db = SQLAlchemy()


class User(db.Model, LoginUserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password_hash = db.Column(db.String(32))
    name_first = db.Column(db.Unicode(80))
    name_last = db.Column(db.Unicode(80))
    name_middle = db.Column(db.Unicode(80))
    email = db.Column(db.Unicode(80))
    current_course_id = 0

    def __repr__(self):
        return '<User {0}>'.format(self.username)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText, nullable=False)
    description = db.Column(db.UnicodeText)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True)
    title = db.Column(db.UnicodeText)
    description = db.Column(db.UnicodeText)

    def __init__(self, code):
        self.code = code


class Participant(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)

    def __init__(self, user_id, course_id, role_id):
        self.user_id = user_id
        self.course_id = course_id
        self.role_id = role_id


class ParticipantExtraInfo(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    json = db.Column(db.UnicodeText)

    def __init__(self, user_id, course_id, json):
        self.user_id = user_id
        self.course_id = course_id
        self.json = json


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100))
    title = db.Column(db.UnicodeText)
    suggested_role = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)
    suggested_course = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)


class GroupMembership(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), primary_key=True)
    suggested_course = db.Column(db.Integer, db.ForeignKey('course.id'))

    def __init__(self, user_id, group_id):
        self.user_id = user_id
        self.group_id = group_id


class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    statement = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp_created = db.Column(db.DateTime)
    timestamp_last_modified = db.Column(db.DateTime)
    is_adhoc = db.Column(db.Boolean)


class ProblemRelation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    to_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('problem_relation_type.id'), nullable=False)
    weight = db.Column(db.Float)

    def __init__(self, from_id, to_id, relation_type_id, weight=1.0):
        self.from_id = from_id
        self.to_id = to_id
        self.type_id = relation_type_id
        self.weight = weight


class ProblemRelationType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True)
    description = db.Column(db.UnicodeText)


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100))
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)


class TopicLevelAssignment(db.Model):
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    level = db.Column(db.Integer, nullable=False)

    def __init__(self, course_id, topic_id, level):
        self.course_id = course_id
        self.topic_id = topic_id
        self.level = level


class ProblemTopicAssignment(db.Model):
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), primary_key=True)
    weight = db.Column(db.Float)

    def __init__(self, problem_id, topic_id, weight=1.0):
        self.problem_id = problem_id
        self.topic_id = topic_id
        self.weight = weight


class Concept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    description = db.Column(db.UnicodeText)


class ProblemConceptAssignment(db.Model):
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    concept_id = db.Column(db.Integer, db.ForeignKey('concept.id'), primary_key=True)
    weight = db.Column(db.Float)

    def __init__(self, problem_id, concept_id, weight=1):
        self.problem_id = problem_id
        self.concept_id = concept_id
        self.weight = weight


class ProblemSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_adhoc = db.Column(db.Boolean)
    timestamp_created = db.Column(db.DateTime)
    timestamp_last_modified = db.Column(db.DateTime)


class ProblemSetContent(db.Model):
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'), primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    sort_key = db.Column(db.Integer)

    def __init__(self, problem_set_id, problem_id, sort_key=0):
        self.problem_id = problem_id
        self.problem_set_id = problem_set_id
        self.sort_key = sort_key


class ProblemSetExtra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'))
    content = db.Column(db.UnicodeText)
    sort_key = db.Column(db.Integer)


class Exposure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)


class ExposureContent(db.Model):
    exposure_id = db.Column(db.Integer, db.ForeignKey('exposure.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'), primary_key=True)
    sort_key = db.Column(db.Integer)

    def __init__(self, exposure_id, user_id, problem_set_id, sort_key=0):
        self.exposure_id = exposure_id
        self.user_id = user_id
        self.problem_set_id = problem_set_id
        self.sort_key = sort_key


class ExposureGrading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exposure_id = db.Column(db.Integer, db.ForeignKey('exposure.id'), nullable=False)
    grader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime)
    comment = db.Column(db.UnicodeText)
    feedback = db.Column(db.UnicodeText)

    def __init__(self, exposure_id, grader_id):
        self.exposure_id = exposure_id
        self.grader_id = grader_id


class ExposureGradingResult(db.Model):
    exposure_grading_id = db.Column(db.Integer, db.ForeignKey('exposure_grading.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    problem_set_id = db.Column(db.Integer, db.ForeignKey('problem_set.id'), primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    problem_status_id = db.Column(db.Integer, db.ForeignKey('problem_status_info.id'), nullable=False)
    comment = db.Column(db.UnicodeText)
    feedback = db.Column(db.UnicodeText)

    def __init__(self, exposure_grading_id, user_id, problem_set_id, problem_id, problem_status_id):
        self.exposure_grading_id = exposure_grading_id
        self.user_id = user_id
        self.problem_set_id = problem_set_id
        self.problem_id = problem_id
        self.problem_status_id = problem_status_id


class Trajectory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    comment = db.Column(db.UnicodeText)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))


class TrajectoryContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trajectory_id = db.Column(db.Integer, db.ForeignKey('trajectory.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    sort_key = db.Column(db.Integer)

    def __init__(self, trajectory_id, topic_id, sort_key=None):
        self.trajectory_id = trajectory_id
        self.topic_id = topic_id
        if sort_key is not None:
            self.sort_key = sort_key


class UserCourseTrajectory(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    trajectory_id = db.Column(db.Integer, db.ForeignKey('trajectory.id'))

    def __init__(self, user_id, course_id):
        self.user_id = user_id
        self.course_id = course_id


class ProblemStatus(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), primary_key=True)
    status_id = db.Column(db.Integer, db.ForeignKey('problem_status_info.id'), nullable=False)
    timestamp_last_changed = db.Column(db.DateTime)

    def __init__(self, user_id, problem_id, status_id):
        self.user_id = user_id
        self.problem_id = problem_id
        self.status_id = status_id


class ProblemStatusInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True)
    title = db.Column(db.UnicodeText)
    icon = db.Column(db.Unicode(100), unique=True)
    description = db.Column(db.UnicodeText)

    def __init__(self, code, title, icon, description=''):
        self.code = code
        self.title = title
        self.icon = icon
        self.description = description


class ProblemSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    statement = db.Column(db.UnicodeText, nullable=False)
    comment = db.Column(db.UnicodeText)


class ProblemComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    content = db.Column(db.UnicodeText)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    in_reply_to = db.Column(db.Integer, db.ForeignKey('problem_comment.id'))


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'))
    event = db.Column(db.Text)
    comment = db.Column(db.UnicodeText)


class SystemAdministrator(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    extra_info = db.Column(db.Text)
