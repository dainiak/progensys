from flask import escape
import random

import re


def process_problem_variations_mathmode(text, variation=None):
    return re.compile(r'\{\{(.*?)\}\}', re.DOTALL).sub(lambda m: ''.join(r'\class{problem-variation-' + str(
                                                               i) + '}{ ' + opt + ' } ' for i, opt in
                                                                   enumerate(m.group(1).split('||')))
                                                       , text)


def process_problem_variations_textmode(text, variation=None):
    return re.compile(r'\{\{(.*?)\}\}', re.DOTALL).sub(lambda m: \
                                                           ''.join(
                                                               r'<span class="problem-variation-{0}">{1}</span>'.format(
                                                                   i, opt) for i, opt in
                                                               enumerate(m.group(1).split('||'))) \
                                                       , text)


def gcd(x, y):
    if x % y == 0:
        return y
    if y % x == 0:
        return x
    return gcd(min(x, y), max(x, y) % min(x, y))


def lcm(seq):
    cur_lcm = 1
    for k in seq:
        cur_lcm = k * cur_lcm // gcd(k, cur_lcm)
    return cur_lcm


def process_problem_variations(text, variation=None):
    if variation is not None:
        def variation_chooser(match_object):
            options = match_object.group(1).split('||')
            return options[variation % len(options)]

        return re.compile(r'\{\{(.*?)\}\}', re.DOTALL).sub(variation_chooser, text)

    num_variations = list(set(len(s.split('||')) for s in re.compile(r'\{\{(.*?)\}\}', re.DOTALL).findall(text)))
    text = re.compile(r'\$\$(.*?)\$\$', re.DOTALL).sub(
        lambda m: r'$${0}$$'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = re.compile(r'\$(.*?)\$', re.DOTALL).sub(
        lambda m: r'${0}$'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = re.compile(r'\\\((.*?)\\\)', re.DOTALL).sub(
        lambda m: r'\({0}\)'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = re.compile(r'\\\[(.*?)\\\]', re.DOTALL).sub(
        lambda m: r'\[{0}\]'.format(process_problem_variations_mathmode(m.group(1)), variation), text)
    text = process_problem_variations_textmode(text, variation)

    if (variation is not None) or len(num_variations) == 0:
        return text

    max_variations = max(num_variations)
    if max_variations <= 1:
        return text

    buttons_html = '\n'.join('''
        <button
        class="problem-variation-control btn btn-default"
        data-variation="{0}"
        onclick="
            for(var i = 0; i < {1}; ++i) {{
                $(event.target).parent().parent().find('.problem-variation-' + i.toString()).hide(0);
            }}
            $(event.target).parent().parent().find('.problem-variation-' + event.target.dataset.variation).css('display','inline');
        ">{0}</button>'''.replace('\n', ''). \
                             format(i, max_variations) for i in range(lcm(num_variations)))

    return r'<div class="dontprint">Вариация {0}</div>{1}'.format(buttons_html, text)


def process_latex_lists(text):
    def shuffler(s):
        s = s.split(r'\item')[1:]
        random.shuffle(s)
        return r'\begin{itemize} \item' + r' \item '.join(s) + r'\end{itemize}'

    text = re.compile(r'\\begin{shuffledlist}(.*?)\\end{shuffledlist}', re.DOTALL).sub(lambda m: shuffler(m.group(1)),
                                                                                       text)

    return text \
        .replace(r'\begin{enumerate}', '<ol>') \
        .replace(r'\end{enumerate}', '</ol>') \
        .replace(r'\begin{itemize}', '<ul>') \
        .replace(r'\end{itemize}', '</ul>') \
        .replace(r'\item', '<li>')


def process_xypic_macros(text):
    return re.compile(r'\\edge{(.*?)}', re.DOTALL).sub(lambda m: r'\ar@{{-}}[{0}]'.format(m.group(1)), text) \
        .replace(r'\vrtxf', r'*[o]{\bullet}') \
        .replace(r'\vrtx', r'*[o]{\circ}')


def latex_to_html(text, variation=None):
    text = re.compile(r'(?<!\\)%.*$', re.MULTILINE).sub('', text)
    text = escape(text)
    text = re.compile(r'\\emph{(.*?)}', re.DOTALL).sub(lambda m: r'<em>{0}</em>'.format(m.group(1)), text)
    text = re.compile(r'\\textit{(.*?)}', re.DOTALL).sub(lambda m: r'<em>{0}</em>'.format(m.group(1)), text)
    text = re.compile(r'\\textbf{(.*?)}', re.DOTALL).sub(lambda m: r'<strong>{0}</strong>'.format(m.group(1)), text)
    text = re.sub(r'\\,', ' ', text).replace('---', '—').replace('--', '–').replace('~', '&nbsp;')

    text = process_latex_lists(text)
    text = process_problem_variations(text, variation)

    return text


def process_problem_statement(text):
    return latex_to_html(text)
