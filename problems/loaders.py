def loadProblems(filename='problems/problems_db.tex'):
    currentId = -1
    with open(filename, 'r', encoding='utf-8') as inputFile:
        p_class = None
        for line in inputFile:
            if line.startswith('%id '):
                currentId = int(line[len('%id '):].strip())
                if currentId == 1000:
                    break
                p_class = flask_app.Problem.query.filter_by(id=currentId).first()
                if p_class is None:
                    p_class = flask_app.Problem()
                    flask_app.db.session.add(p_class)
                p_class.statement = ''
            elif line.startswith('%topic '):
                t_name = line.strip()[len('%topic '):]
                t = flask_app.Topic.query.filter_by(topic=t_name).first()
                if t is None and t != t_name:
                    t = flask_app.Topic()
                    t.topic = t_name
                    flask_app.db.session.add(t)
                    p_class.topics = str(t.id)
                else:
                    p_class.topics = str(t.id)
            elif line.startswith('%block for '):
                pass
            elif line.startswith('%similar to '):
                pass
            elif currentId >= 0:
                if p_class is not None:
                    p_class.statement += line