# -*- coding: utf-8 -*-
from collections import defaultdict
from os.path import isfile
from itertools import combinations
import lzma

LOG_FILE_NAME = 'log.txt'

MAX_PROBLEMS = 8
MAX_PROBLEMS_IN_HANDOUT = 5

PARTIALLY_SOLVED = 2
SOLVED = 3
UNSOLVED = 1
NEW_TO_STUDENT = 0

# printingOrder = [
#                     1, 3, 4, 2, 5, 6, 14, 15, 16, 20, 21, 22, 26, 27, 28, 32, 33, 34, 38, 39, 40
#                 ] + [9, 8, 42, 43, 11, 12, 13, 17, 18, 19, 23, 24, 25, 29, 30, 31, 35, 36, 37, 41, 44]

#Это нужно печатать по два варианта на лист, а затем разрезать и ничего не перекладывать, а так две полученные кучи и раздать:
printingOrder = list(range(1,48))

similarProblems = defaultdict(set)

blockedProblems = defaultdict(set)

problemPopularity = defaultdict(int)

defaultTrajectory = list()
personalTrajectories = dict()

topicNameToRussianName = defaultdict(str)

nameToId = dict()
idToName = dict()

idToTopic = dict()

history = defaultdict(lambda: defaultdict(int))

problemStatements = dict()
topics = defaultdict(list)

studentGroup = defaultdict(int)

allProblemSets = dict()

obligatoryLiveTasks = [1, 2, 3, 4, 5, 14]


def checkNCD(str_dict, threshold):
    new_dict = dict()
    complen_dict = dict()
    pairs = set()
    for i in str_dict:
        s = str_dict[i].lower().replace(' ', '').encode()
        new_dict[i] = s
        complen_dict[i] = len(lzma.compress(s))

    for (i1, s1), (i2, s2) in combinations(new_dict.items(), 2):
        l1 = complen_dict[i1]
        l2 = complen_dict[i2]
        if (len(lzma.compress(s1 + s2)) - min(l1, l2)) / max(l1, l2) <= threshold:
            pairs.add((i1, i2))
    return pairs


def printToLog(params, clear=False):
    with open(LOG_FILE_NAME, mode='w' if clear else 'a', encoding='utf-8') as outfile:
        outfile.write(str(params) + '\n')


def loadTopicNames():
    with open('topic_names.txt', 'r', encoding='utf-8') as inputFile:
        for line in inputFile:
            tokens = line.strip().split()
            eName, rName = tokens[0], ' '.join(tokens[1:])
            topicNameToRussianName[eName] = rName


def loadTrajectories():
    global defaultTrajectory, personalTrajectories, idToName
    with open('trajectory.txt', 'r', encoding='utf-8') as inputFile:
        for line in inputFile:
            s, n = line.strip().split()
            defaultTrajectory.append((s.strip(), int(n.strip())))
    for id in idToName:
        filename = 'trajectory_{0}.txt'.format(id)
        if isfile(filename):
            with open(filename, 'r', encoding='utf-8') as inputFile:
                printToLog('Student {0} ({1}) has a personal trajectory. Loaded it.'.format(id, idToName[id]))
                personalTrajectories[id] = []
                for line in inputFile:
                    s, n = line.strip().split()
                    personalTrajectories[id].append((s.strip(), int(n.strip())))


def loadProblems(filename):
    global problemStatements
    seenIds = set()
    currentId = -1
    currentTopic = ''
    currentStatement = ''
    with open(filename, 'r', encoding='utf-8') as inputFile:
        for line in inputFile:
            if line.startswith('%id '):
                if currentStatement != '' and currentId >= 0:
                    topics[currentTopic].append(currentId)
                    problemStatements[currentId] = currentStatement
                    idToTopic[currentId] = currentTopic
                    currentTopic = ''
                currentId = int(line[len('%id '):].strip())
                if currentId in seenIds:
                    printToLog('Two problems with same id {0}'.format(currentId))
                seenIds.add(currentId)
                currentStatement = ''
            elif line.startswith('%topic '):
                currentTopic = line[len('%topic '):].strip()
            elif line.startswith('%block for '):
                blockedGroup = int(line[len('%block for '):].strip())
                blockedProblems[blockedGroup].add(currentId)
            elif line.startswith('%similar to '):
                similarId = int(line[len('%similar to '):].strip())
                if similarId not in similarProblems:
                    similarProblems[similarId].add(similarId)
                similarProblems[similarId].add(currentId)
                similarProblems[currentId] = similarProblems[similarId]
            elif currentId >= 0:
                currentStatement += line
    # checkForDuplicateProblems()


def checkForDuplicateProblems():
    suspiciousPairs = checkNCD(problemStatements, 0.1)
    for id1, id2 in suspiciousPairs:
        printToLog('Please check statements for problems {0} and {1}. They look similar.'.format(id1, id2))


def loadStudentIds():
    global nameToId, idToName, studentGroup
    with open('student_ids.txt', 'r', encoding='utf-8') as inputFile:
        for line in inputFile:
            name, id = line.strip().split('\t')
            id = int(id)
            nameToId[name] = id
            idToName[id] = name
    with open('groups.txt', 'r', encoding='utf-8') as inputFile:
        for line in inputFile:
            id, group = line.strip().split('\t')
            id = int(id)
            studentGroup[id] = int(group)


def loadHistory(check = False):
    global history
    with open('history.txt', 'r', encoding='utf-8') as file:
        for line in file:
            studentId, problemId, result, dateId = ((s.isdecimal() and int(s)) for s in line.strip().split())
            if problemId not in history[studentId] or history[studentId][problemId] < result:
                if check and dateId == 100 and history[studentId][problemId] != 2:
                    printToLog('Student {0} tried to re-solve a problem {1} he have not solved before.'.format(studentId, problemId))
                history[studentId][problemId] = result
    for studentId in history:
        for problemId in history[studentId]:
            if history[studentId][problemId] != NEW_TO_STUDENT:
                problemPopularity[problemId] += 1

def getLeastPopularSimilarProblem(problemId):
    # return problemId
    if len(similarProblems[problemId]) <= 1:
        return problemId
    return (min((problemPopularity[id], id) for id in similarProblems[problemId]))[1]

def getProblemSet(studentId):
    problemSet = []
    studentProgress = defaultdict(int)
    problemsForbiddenDueToSimilarity = set()

    for problemId in history[studentId]:
        if (history[studentId][problemId] == SOLVED) or (history[studentId][problemId] == PARTIALLY_SOLVED):
            problemsForbiddenDueToSimilarity |= similarProblems[problemId]
        if (history[studentId][problemId] == SOLVED) or (
                history[studentId][problemId] == PARTIALLY_SOLVED and problemId not in obligatoryLiveTasks):
            studentProgress[idToTopic[problemId]] += 1

    trajectory = defaultTrajectory if studentId not in personalTrajectories else personalTrajectories[studentId]
    totalRequiredProblems = 0

    for topicName, nRequiredProblems in trajectory:
        if topicName in topics:
            k = min(studentProgress[topicName], nRequiredProblems)
            nRequiredProblems -= k
            studentProgress[topicName] -= k
            totalRequiredProblems += nRequiredProblems

            for type in [PARTIALLY_SOLVED, NEW_TO_STUDENT, UNSOLVED]:
                if nRequiredProblems > 0:
                    for problemId in topics[topicName]:
                        if problemId in blockedProblems[studentGroup[studentId]]:
                            printToLog('Skipped problem {0} for student {1} since it is blocked for group {2}.'.format(problemId, studentId, studentGroup[studentId]))
                            continue
                        if nRequiredProblems > 0 \
                                and problemId not in problemSet and problemId not in problemsForbiddenDueToSimilarity \
                                and ((type != PARTIALLY_SOLVED) or (problemId in obligatoryLiveTasks)) \
                                and history[studentId][problemId] == type:
                            leastPopularId = getLeastPopularSimilarProblem(problemId)
                            if leastPopularId != problemId:
                                printToLog('Found less popular problem {0} instead of {1}'.format(leastPopularId,problemId));

                            problemSet.append(leastPopularId)
                            problemsForbiddenDueToSimilarity |= similarProblems[leastPopularId]
                            problemPopularity[leastPopularId] += 1
                            if type == UNSOLVED:
                                printToLog(
                                    'Adding formerly unsolved problem {0} for ({1}) due to lack of problems on {2}.'.format(
                                        leastPopularId, idToName[studentId], topicName))
                            if len(problemSet) >= MAX_PROBLEMS:
                                return problemSet
                            nRequiredProblems -= 1

    if len(problemSet) == 0:
        printToLog('No problems left for student {0} ({1}). Please add something to the trajectory.'.format(studentId,
                                                                                                            idToName[
                                                                                                                studentId]))
    if totalRequiredProblems < MAX_PROBLEMS_IN_HANDOUT:
        printToLog('Too few problems left for student {0} ({1}): main variant is truncated.'.format(studentId, idToName[
            studentId]))
    elif totalRequiredProblems < MAX_PROBLEMS:
        printToLog('Too few problems left for student {0} ({1}): extra variant is truncated.'.format(studentId,
                                                                                                     idToName[
                                                                                                         studentId]))

    return problemSet


def makeVariant(studentId, dateId, problemIds):
    tabular_line = ' & '.join([r'\phantom{XXXX}'] * len(problemIds))
    number_line = ' & '.join('${{ {0} }}_{{ ({1}) }}$'.format(i + 1, id) for i, id in enumerate(problemIds))
    spec_line = '|'.join(['c'] * len(problemIds))
    return r'''\begin{{pagebreakprevent}}
\par\noindent \textbf{{Студент: }} {student}\hfill\textbf{{Группа: }} {group}  \\
\par\noindent \textbf{{ID варианта: }} {variantId}  \\ \smallskip
\begin{{tabular}}{{|l|{specLine}|}}\hline
№ & {numberLine}\\ \hline
результат & {tabularLine}\\ \hline
\end{{tabular}}\\
\begin{{enumerate}}
{statements}
\end{{enumerate}}
\end{{pagebreakprevent}}
'''.format(
        student=idToName[studentId],
        group=studentGroup[studentId],
        variantId='{0}/{1}'.format(studentId, dateId),
        specLine=spec_line,
        numberLine=number_line,
        tabularLine=tabular_line,
        statements='\n'.join(r'\item ({0}) {1}'.format(topicNameToRussianName[idToTopic[id]], problemStatements[id]) for id in problemIds))


def makeExtraVariant(studentId, dateId, problemIds):
    problemIds = problemIds[MAX_PROBLEMS_IN_HANDOUT:]
    nProblems = len(problemIds)
    tabular_line = ' & '.join([r'\phantom{XXXX}'] * nProblems)
    number_line = ' & '.join(
        '${{ {0} }}_{{ ({1}) }}$'.format(i + 1 + MAX_PROBLEMS_IN_HANDOUT, id) for i, id in enumerate(problemIds))
    spec_line = '|'.join(['c'] * nProblems)
    return r'''\begin{{pagebreakprevent}}
\par\noindent \textbf{{Студент: }} {student}\hfill\textbf{{Группа: }} {group}  \\
\par\noindent \textbf{{ID варианта: }} {variantId} (\textbf{{дополнительный}})  \\ \smallskip
\begin{{tabular}}{{|l|{specLine}|}}\hline
№ & {numberLine}\\ \hline
результат & {tabularLine}\\ \hline
\end{{tabular}}\\
\begin{{enumerate}}\setcounter{{enumi}}{{{enumstart}}}
{statements}
\end{{enumerate}}
\end{{pagebreakprevent}}
'''.format(
        student=idToName[studentId],
        group=studentGroup[studentId],
        variantId='{0}/{1}'.format(studentId, dateId),
        enumstart=MAX_PROBLEMS_IN_HANDOUT,
        specLine=spec_line,
        numberLine=number_line,
        tabularLine=tabular_line,
        statements='\n'.join(r'\item ({0}) {1}'.format(topicNameToRussianName[idToTopic[id]], problemStatements[id]) for id in problemIds))


def writeOutput(filename, dateId):
    global printingOrder, allProblemSets
    if len(allProblemSets) == 0:
        allProblemSets = {studentId: getProblemSet(studentId) for studentId in printingOrder}

    with open(filename, 'w', encoding='utf-8') as file:
        file.write(r'''\documentclass[russian,a4paper,10pt,twocolumn,landscape]{{extarticle}}
\usepackage[left=15mm,right=15mm, top=10mm,bottom=10mm,bindingoffset=0cm,columnsep=1cm]{{geometry}}
\usepackage{{amsmath,amssymb,amsthm,amsfonts,tabularx}}
\usepackage{{tikz}}
\usetikzlibrary{{patterns}}
\usepackage{{dsfont}}
\usepackage{{ifxetex,ifluatex}}
\ifnum 0\ifxetex 1\fi\ifluatex 1\fi>0
  \usepackage[no-math]{{fontspec}}
  \setmainfont[Ligatures=TeX]{{Calibri}}
  \setmonofont{{Consolas}}
  \usepackage[cal=boondoxo,bb=fourier]{{mathalfa}} % mathcal
  \usepackage{{polyglossia}}
  \setdefaultlanguage{{russian}}
  \setotherlanguage{{english}}
\else
  \usepackage{{cmap}}
  \usepackage[T2A]{{fontenc}}
  \usepackage[utf8]{{inputenc}}

  \usepackage[libertine,bigdelims,vvarbb]{{newtxmath}} % bb from STIX
  \usepackage[cal=boondoxo]{{mathalfa}} % mathcal

  \usepackage{{ucs}}
  \usepackage[russian]{{babel}}
  \usepackage[babel = true]{{microtype}}
\fi

\usepackage{{nopageno,indentfirst}}


\newcommand*{{\hm}}[1]{{
    #1\nobreak\discretionary{{}}{{\hbox{{$#1$}}}}{{}}
}}

\renewcommand{{\le}}{{\leqslant}}
\renewcommand{{\ge}}{{\geqslant}}
\renewcommand{{\hat}}{{\widehat}}
\renewcommand{{\emptyset}}{{\varnothing}}
\renewcommand{{\epsilon}}{{\varepsilon}}

\newcommand{{\Sum}}{{\displaystyle\sum\limits}}
\newcommand{{\Int}}{{\displaystyle\int\limits}}
\newcommand{{\Prod}}{{\displaystyle\prod\limits}}
\newcommand{{\Max}}{{\max\limits}}
\newcommand{{\Min}}{{\min\limits}}
\newcommand{{\Sup}}{{\sup\limits}}
\newcommand{{\Inf}}{{\inf\limits}}

\newcommand{{\setdelta}}{{\bigtriangleup}}

\DeclareMathOperator*{{\argmax}}{{argmax}}
\DeclareMathOperator*{{\ex}}{{ex}}
\DeclareMathOperator*{{\rk}}{{rk}}
\DeclareMathOperator*{{\diam}}{{diam}}
\DeclareMathOperator*{{\const}}{{const}}
\DeclareMathOperator*{{\dist}}{{dist}}
\DeclareMathOperator*{{\per}}{{per}}
\DeclareMathOperator*{{\coef}}{{coef}}
\DeclareMathOperator*{{\rate}}{{rate}}
\DeclareMathOperator*{{\exc}}{{exc}}

\newcommand{{\floor}}[1]{{\left\lfloor{{#1}}\right\rfloor}}
\newcommand{{\ceil}}[1]{{\left\lceil{{#1}}\right\rceil}}

\newcommand{{\stirling}}[2]{{\genfrac{{\{{}}{{\}}}}{{0pt}}{{}}{{#1}}{{#2}}}}

\newcommand{{\eqmod}}[3]{{{{#1}} \equiv {{#2}}\:(\mathrm{{mod}} \: {{#3}})}}
\newcommand{{\fromto}}[3]{{{{#1}}=\overline{{{{#2}},\,{{#3}}}}}}

\newcommand{{\tild}}[1]{{\widetilde{{#1}}}}
\newcommand{{\ol}}[1]{{{{\overline{{#1}}}}}}

\newcommand{{\indicator}}[1]{{\mathds{{1}}_{{#1}}}}

\newcommand{{\transpose}}[1]{{{{#1}}^{{\mathrm{{T}}}}}}

\newcommand{{\rmT}}{{\mathrm{{T}}}}

\newcommand{{\E}}{{\mathbb{{E}}}}

\newcommand{{\bbA}}{{\mathbb{{A}}}}
\newcommand{{\bbB}}{{\mathbb{{B}}}}
\newcommand{{\bbF}}{{\mathbb{{F}}}}
\newcommand{{\bbN}}{{\mathbb{{N}}}}
\newcommand{{\bbP}}{{\mathbb{{P}}}}
\newcommand{{\bbQ}}{{\mathbb{{Q}}}}
\newcommand{{\bbR}}{{\mathbb{{R}}}}
\newcommand{{\bbZ}}{{\mathbb{{Z}}}}

\newcommand{{\calw}}{{w}}
\newcommand{{\calA}}{{\mathcal{{A}}}}
\newcommand{{\calB}}{{\mathcal{{B}}}}
\newcommand{{\calC}}{{\mathcal{{C}}}}
\newcommand{{\calF}}{{\mathcal{{F}}}}
\newcommand{{\calG}}{{\mathcal{{G}}}}
\newcommand{{\calI}}{{\mathcal{{I}}}}
\newcommand{{\calK}}{{\mathcal{{K}}}}
\newcommand{{\calM}}{{\mathcal{{M}}}}
\newcommand{{\calN}}{{\mathcal{{N}}}}
\newcommand{{\calO}}{{\mathcal{{O}}}}
\newcommand{{\calR}}{{\mathcal{{R}}}}
\newcommand{{\calS}}{{\mathcal{{S}}}}

\newcommand{{\bfA}}{{\mathbf{{A}}}}
\newcommand{{\bfa}}{{\mathbf{{a}}}}
\newcommand{{\bfb}}{{\mathbf{{b}}}}
\newcommand{{\bfc}}{{\mathbf{{c}}}}
\newcommand{{\bfe}}{{\mathbf{{e}}}}
\newcommand{{\bfw}}{{\mathbf{{w}}}}
\newcommand{{\bfx}}{{\mathbf{{x}}}}
\newcommand{{\bfy}}{{\mathbf{{y}}}}
\newcommand{{\bfz}}{{\mathbf{{z}}}}
\newcommand{{\bfzero}}{{\mathbf{{0}}}}

\newcommand{{\sop}}{{с.\,о.\,п.}}
\newcommand{{\srp}}{{с.\,р.\,п.}}

\newenvironment{{system}}[1]{{\left\{{ \begin{{array}} {{#1}}}}{{\end{{array}} \right.}}

\newcommand{{\vrtx}}{{
    *[o]{{\circ}}
}}
\newcommand{{\vrtxf}}{{
    *[o]{{\bullet}}
}}

\newcommand{{\edge}}[1]{{
    \ar@{{-}}[#1]
}}


\newenvironment{{pagebreakprevent}}{{\par\nobreak\vfil\penalty0\vfilneg\vtop\bgroup}}{{\par\xdef\tpd{{\the\prevdepth}}\egroup\prevdepth=\tpd}}

\nofiles
\begin{{document}}
{0}
\end{{document}}
'''.format('\n\\pagebreak\n'.join(
            makeVariant(studentId, dateId, allProblemSets[studentId][:MAX_PROBLEMS_IN_HANDOUT]) for studentId in
            printingOrder if len(allProblemSets[studentId]) > 0)))
    with open('test_{0}_log.txt'.format(dateId), 'w') as file:
        file.write('\n'.join(
            str(studentId) + ' ' + ' '.join(str(x) for x in allProblemSets[studentId]) for studentId in printingOrder));


def writeOutputExtra(filename, dateId):
    global printingOrder, allProblemSets
    if len(allProblemSets) == 0:
        allProblemSets = {studentId: getProblemSet(studentId) for studentId in printingOrder}

    with open(filename, 'w', encoding='utf-8') as file:
        file.write(r'''\documentclass[russian,a4paper,10pt,twocolumn,landscape]{{extarticle}}
\usepackage[left=15mm,right=15mm, top=10mm,bottom=10mm,bindingoffset=0cm]{{geometry}}
\usepackage{{amsmath,amssymb,amsthm,amsfonts,tabularx}}
\usepackage{{tikz}}
\usetikzlibrary{{patterns}}
\usepackage{{dsfont}}
\usepackage{{ifxetex,ifluatex}}
\ifnum 0\ifxetex 1\fi\ifluatex 1\fi>0
  \usepackage[no-math]{{fontspec}}
  \setmainfont[Ligatures=TeX]{{Calibri}}
  \setmonofont{{Consolas}}
  \usepackage[cal=boondoxo,bb=fourier]{{mathalfa}} % mathcal
  \usepackage{{polyglossia}}
  \setdefaultlanguage{{russian}}
  \setotherlanguage{{english}}
\else
  \usepackage{{cmap}}
  \usepackage[T2A]{{fontenc}}
  \usepackage[utf8]{{inputenc}}

  \usepackage[libertine,bigdelims,vvarbb]{{newtxmath}} % bb from STIX
  \usepackage[cal=boondoxo]{{mathalfa}} % mathcal

  \usepackage{{ucs}}
  \usepackage[russian]{{babel}}
  \usepackage[babel = true]{{microtype}}
\fi

\usepackage{{nopageno,indentfirst}}


\newcommand*{{\hm}}[1]{{
    #1\nobreak\discretionary{{}}{{\hbox{{$#1$}}}}{{}}
}}

\renewcommand{{\le}}{{\leqslant}}
\renewcommand{{\ge}}{{\geqslant}}
\renewcommand{{\hat}}{{\widehat}}
\renewcommand{{\emptyset}}{{\varnothing}}
\renewcommand{{\epsilon}}{{\varepsilon}}

\newcommand{{\Sum}}{{\displaystyle\sum\limits}}
\newcommand{{\Int}}{{\displaystyle\int\limits}}
\newcommand{{\Prod}}{{\displaystyle\prod\limits}}
\newcommand{{\Max}}{{\max\limits}}
\newcommand{{\Min}}{{\min\limits}}
\newcommand{{\Sup}}{{\sup\limits}}
\newcommand{{\Inf}}{{\inf\limits}}

\newcommand{{\setdelta}}{{\bigtriangleup}}

\DeclareMathOperator*{{\argmax}}{{argmax}}
\DeclareMathOperator*{{\ex}}{{ex}}
\DeclareMathOperator*{{\rk}}{{rk}}
\DeclareMathOperator*{{\diam}}{{diam}}
\DeclareMathOperator*{{\const}}{{const}}
\DeclareMathOperator*{{\dist}}{{dist}}
\DeclareMathOperator*{{\per}}{{per}}
\DeclareMathOperator*{{\coef}}{{coef}}
\DeclareMathOperator*{{\rate}}{{rate}}
\DeclareMathOperator*{{\exc}}{{exc}}

\newcommand{{\floor}}[1]{{\left\lfloor{{#1}}\right\rfloor}}
\newcommand{{\ceil}}[1]{{\left\lceil{{#1}}\right\rceil}}

\newcommand{{\stirling}}[2]{{\genfrac{{\{{}}{{\}}}}{{0pt}}{{}}{{#1}}{{#2}}}}

\newcommand{{\eqmod}}[3]{{{{#1}} \equiv {{#2}}\:(\mathrm{{mod}} \: {{#3}})}}
\newcommand{{\fromto}}[3]{{{{#1}}=\overline{{{{#2}},\,{{#3}}}}}}

\newcommand{{\tild}}[1]{{\widetilde{{#1}}}}
\newcommand{{\ol}}[1]{{{{\overline{{#1}}}}}}

\newcommand{{\indicator}}[1]{{\mathds{{1}}_{{#1}}}}

\newcommand{{\transpose}}[1]{{{{#1}}^{{\mathrm{{T}}}}}}

\newcommand{{\rmT}}{{\mathrm{{T}}}}

\newcommand{{\E}}{{\mathbb{{E}}}}

\newcommand{{\bbA}}{{\mathbb{{A}}}}
\newcommand{{\bbB}}{{\mathbb{{B}}}}
\newcommand{{\bbF}}{{\mathbb{{F}}}}
\newcommand{{\bbN}}{{\mathbb{{N}}}}
\newcommand{{\bbP}}{{\mathbb{{P}}}}
\newcommand{{\bbQ}}{{\mathbb{{Q}}}}
\newcommand{{\bbR}}{{\mathbb{{R}}}}
\newcommand{{\bbZ}}{{\mathbb{{Z}}}}

\newcommand{{\calw}}{{w}}
\newcommand{{\calA}}{{\mathcal{{A}}}}
\newcommand{{\calB}}{{\mathcal{{B}}}}
\newcommand{{\calC}}{{\mathcal{{C}}}}
\newcommand{{\calF}}{{\mathcal{{F}}}}
\newcommand{{\calG}}{{\mathcal{{G}}}}
\newcommand{{\calI}}{{\mathcal{{I}}}}
\newcommand{{\calK}}{{\mathcal{{K}}}}
\newcommand{{\calM}}{{\mathcal{{M}}}}
\newcommand{{\calN}}{{\mathcal{{N}}}}
\newcommand{{\calO}}{{\mathcal{{O}}}}
\newcommand{{\calR}}{{\mathcal{{R}}}}
\newcommand{{\calS}}{{\mathcal{{S}}}}

\newcommand{{\bfA}}{{\mathbf{{A}}}}
\newcommand{{\bfa}}{{\mathbf{{a}}}}
\newcommand{{\bfb}}{{\mathbf{{b}}}}
\newcommand{{\bfc}}{{\mathbf{{c}}}}
\newcommand{{\bfe}}{{\mathbf{{e}}}}
\newcommand{{\bfw}}{{\mathbf{{w}}}}
\newcommand{{\bfx}}{{\mathbf{{x}}}}
\newcommand{{\bfy}}{{\mathbf{{y}}}}
\newcommand{{\bfz}}{{\mathbf{{z}}}}
\newcommand{{\bfzero}}{{\mathbf{{0}}}}

\newcommand{{\sop}}{{с.\,о.\,п.}}
\newcommand{{\srp}}{{с.\,р.\,п.}}

\newenvironment{{system}}[1]{{\left\{{ \begin{{array}} {{#1}}}}{{\end{{array}} \right.}}

\newcommand{{\vrtx}}{{
    *[o]{{\circ}}
}}
\newcommand{{\vrtxf}}{{
    *[o]{{\bullet}}
}}

\newcommand{{\edge}}[1]{{
    \ar@{{-}}[#1]
}}


\newenvironment{{pagebreakprevent}}{{\par\nobreak\vfil\penalty0\vfilneg\vtop\bgroup}}{{\par\xdef\tpd{{\the\prevdepth}}\egroup\prevdepth=\tpd}}

\nofiles
\begin{{document}}
{0}
\end{{document}}
'''.format('\n\n'.join(
            makeExtraVariant(studentId, dateId, allProblemSets[studentId]) for studentId in sorted(printingOrder) if
            len(allProblemSets[studentId]) > MAX_PROBLEMS_IN_HANDOUT)))
        # with open('test_{0}_extra_log.txt'.format(dateId), 'w') as file:
        #    file.write('\n'.join( str(studentId) + ' ' + ' '.join(str(x) for x in allProblemSets[studentId][MAX_PROBLEMS_IN_HANDOUT:]) for studentId in printingOrder));


def processTestResults(test_log_filename, results_filename):
    global nameToId
    signToNumber = {'∅': NEW_TO_STUDENT, '': UNSOLVED, '?': UNSOLVED, '□': UNSOLVED, '◩': PARTIALLY_SOLVED, '■': SOLVED}
    processedResults = list()
    allProblemSets = dict()
    with open(test_log_filename, 'r', encoding='utf-8') as file:
        for line in file:
            tokens = line.strip().split()
            allProblemSets[int(tokens[0])] = [int(s) for s in tokens[1:]]
    with open(results_filename, 'r', encoding='utf-8') as file:
        for line in file:
            tokens = line.replace('\n', '').split('\t')
            studentId = nameToId[tokens[0]]
            for i, s in enumerate(tokens[1:]):
                if i < len(allProblemSets[studentId]):
                    processedResults.append((studentId, allProblemSets[studentId][i], signToNumber[s]))
    return processedResults


def accumulateHistoryForTest(dateId):
    loadStudentIds()
    results = processTestResults('test_{0}_log.txt'.format(dateId), 'test_{0}_results.txt'.format(dateId))
    with open('test_{0}_history.txt'.format(dateId), 'w') as file:
        file.write('\n'.join('{0} {1} {2} {3}'.format(x[0], x[1], x[2], dateId) for x in results))


def generatePrintouts(dateId):
    loadStudentIds()
    loadProblems()
    loadHistory()
    loadTrajectories()
    loadTopicNames()
    writeOutput('test_{0}.tex'.format(dateId), dateId)
    writeOutputExtra('test_{0}_extra.tex'.format(dateId), dateId)


def buildBeautifulTable(names_filename):
    global idToName, nameToId, history, idToTopic, topics
    pattern = [ 'GREEK', '\t',
                'PROPOSITIONS', ',', 'CONVERSE', ',', 'CRITERIA', '\t',
                'BASIC_NOTIONS', '\t',
                'PIGEONHOLE', '\t', 'PIGEONHOLE', '\t', 'PIGEONHOLE', '\t',
                'POTENTIALS', '\t',
                'INDUCTION', '\t', 'INDUCTION', '\t',
                'ENUMERATION', ',', 'ENUMERATION', ',', 'ENUMERATION', ',', 'ENUMERATION', '\t', 'INCLEXCL', '\t',
                'SUMS_OF_BINOMIALS', '\t', 'LINEAR_RECURRENT_RELATIONS', '\t',
                'GRAPHS_COUNTING', ',', 'GRAPHS_METRICS', ',', 'GRAPHS_ADVANCED', ',', 'GRAPHS_PIGEONHOLE', ',', 'GRAPHS_CLIQUES', ',',
                'GRAPHS_ISOMORPHIC', ',', 'GRAPHS_PRUFER', ',', 'GRAPHS_COUNTING_ISOMORPHIC', ',', 'GRAPHS_TREES_AND_FORESTS', '\t',
                'GRAPHS_PLANARITY', ',', 'GRAPHS_PLANARITY', '\t',
                'GRAPHS_GREEDY_ALGORITHM', ',', 'GRAPHS_COLORINGS_ADVANCED', ',', 'GRAPHS_COLORINGS_ADVANCED', '\t',
                'GRAPHS_EULERIAN', ',', 'GRAPHS_DEBRUIJN', ',', 'GRAPHS_HAMILTONIAN', '\t',
                'GRAPHS_MATCHINGS', '\t',
                'ASYMPTOTICS_SIMPLE', '\t', 'ASYMPTOTICS', ',', '\t', 'ASYMPTOTICS_ADVANCED', '\t',
                'NUMBER_THEORY_EULER_FERMAT_THEOREM', ',', 'NUMBER_THEORY_EULER_FERMAT_THEOREM', ',', 'NUMBER_THEORY_LINEAR_EQUATIONS', ',',
                'NUMBER_THEORY_LINEAR_EQUATIONS_ADVANCED', ',', 'NUMBER_THEORY_CHINESE_REMAINDER_THEOREM', ',',
                'NUMBER_THEORY_PRIMITIVE_ROOTS', ',', 'NUMBER_THEORY_PRIMITIVE_ROOTS_ADVANCED', ',', 'NUMBER_THEORY_INDEXES' ]

    loadStudentIds()
    loadHistory()
    loadTrajectories()
    loadProblems()
    studentIds = []
    with open(names_filename, 'r', encoding='utf-8') as file:
        studentIds = [nameToId[name.strip()] for name in file]

    resultString = ''
    for studentId in studentIds:
        solvedCompletely = defaultdict(int)
        solvedPartially = defaultdict(int)
        for problemId in history[studentId]:
            if history[studentId][problemId] == SOLVED:
                solvedCompletely[idToTopic[problemId]] += 1
            elif history[studentId][problemId] == PARTIALLY_SOLVED:
                solvedPartially[idToTopic[problemId]] += 1

        if resultString != '':
            resultString += '\n'
        resultString += idToName[studentId] + '\t'
        for s in pattern:
            if not s.isidentifier():
                resultString += s
            elif s in topics:
                if solvedCompletely[s] > 0:
                    solvedCompletely[s] -= 1
                    resultString += '■'
                elif solvedPartially[s] > 0:
                    solvedPartially[s] -= 1
                    resultString += '◩'
                else:
                    resultString += '□'

    with open(names_filename, 'w', encoding='utf-8') as file:
        file.write(resultString.replace(',',' '))


if __name__ == '__main__':
    printToLog('Started logging', clear=True)
    # loadHistory(check=True)
    # buildBeautifulTable('temp.txt')
    loadStudentIds()
    printingOrder = list(sorted(studentGroup.keys(),key=lambda id: str(studentGroup[id])+idToName[id]))
    # printingOrder = [x for x in printingOrder if studentGroup[x] == 491]
    # printingOrder = [27]
    generatePrintouts('21')

    # accumulateHistoryForTest('13')
    # loadProblems()
    # pass
