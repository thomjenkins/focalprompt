import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def run_prompt_edit_case(previous, next_text, spans):
    js = REPO / 'static' / 'js' / 'prompt_edit.js'
    script = (
        "const edit = require(%s);"
        "const previous = %s;"
        "const nextText = %s;"
        "const spans = %s;"
        "const detected = edit.detectPromptEdit(previous, nextText);"
        "const adjusted = spans.map((span) => edit.adjustSpanForPromptEdit(span, detected));"
        "console.log(JSON.stringify({detected, adjusted}));"
    ) % (
        json.dumps(str(js)),
        json.dumps(previous),
        json.dumps(next_text),
        json.dumps(spans),
    )
    proc = subprocess.run(
        ['node', '-e', script],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_replacement_inside_dynamic_span_extends_it_and_shifts_following_spans():
    previous = 'Intro\nChat: My pup needs a booster.\nReply JSON.'
    next_text = previous.replace('pup', 'canine')
    chat_start = previous.index('My pup')
    chat_end = previous.index('\nReply')
    reply_start = previous.index('Reply')
    result = run_prompt_edit_case(
        previous,
        next_text,
        [
            {'char_start': chat_start, 'char_end': chat_end},
            {'char_start': reply_start, 'char_end': len(previous)},
        ],
    )

    chat, reply = result['adjusted']
    assert result['detected']['delta'] == len('canine') - len('pup')
    assert chat['span']['char_start'] == chat_start
    assert chat['span']['char_end'] == chat_end + 3
    assert chat['changed'] is True
    assert chat['needsReview'] is False
    assert reply['span']['char_start'] == reply_start + 3
    assert reply['span']['char_end'] == len(next_text)
    assert reply['changed'] is True
    assert reply['needsReview'] is False


def test_same_length_replacement_inside_span_refreshes_snapshot():
    previous = 'Chat: My pup needs a booster.\nReply JSON.'
    next_text = previous.replace('pup', 'dog')
    span = {'char_start': previous.index('My pup'), 'char_end': previous.index('\nReply')}
    result = run_prompt_edit_case(previous, next_text, [span])

    adjusted = result['adjusted'][0]
    assert result['detected']['delta'] == 0
    assert adjusted['span'] == span
    assert adjusted['changed'] is True
    assert adjusted['needsReview'] is False


def test_edit_before_span_shifts_span_by_delta():
    previous = 'Intro\nChat: My pup needs a booster.'
    next_text = 'Short intro\nChat: My pup needs a booster.'
    span = {'char_start': previous.index('My pup'), 'char_end': len(previous)}
    result = run_prompt_edit_case(previous, next_text, [span])

    delta = len('Short intro') - len('Intro')
    adjusted = result['adjusted'][0]
    assert adjusted['span']['char_start'] == span['char_start'] + delta
    assert adjusted['span']['char_end'] == span['char_end'] + delta
    assert adjusted['changed'] is True
    assert adjusted['needsReview'] is False


def test_boundary_overlap_is_marked_for_review():
    previous = 'abcFOCUSdef'
    next_text = 'abZZCUSdef'
    span = {'char_start': 3, 'char_end': 8}
    result = run_prompt_edit_case(previous, next_text, [span])

    adjusted = result['adjusted'][0]
    assert adjusted['changed'] is True
    assert adjusted['needsReview'] is True


def test_template_loads_prompt_edit_before_app():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
    assert html.index('js/prompt_edit.js') < html.index('js/app.js')
