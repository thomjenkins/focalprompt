"""Span alignment and strict subtractive deletion."""

from utils.span_alignment import (
    align_quote,
    classify_foci_for_ablation,
    collapse_deletion_boundary,
    delete_span,
    verify_foci,
)


def test_exact_match_offsets():
    prompt = "Alpha. Bravo. Charlie."
    quote = "Bravo."
    start, end = align_quote(prompt, quote)
    assert prompt[start:end] == quote
    assert (start, end) == (7, 13)


def test_internal_whitespace_maps_to_original_offsets():
    prompt = "Always  cite   the source."
    quote = "Always cite the source."
    start, end = align_quote(prompt, quote)
    assert prompt[start:end] == "Always  cite   the source."
    assert (start, end) == (0, len(prompt))


def test_curly_quotes_map_to_original_offsets():
    prompt = "He said \u201cHello world\u201d today."
    quote = 'He said "Hello world" today.'
    start, end = align_quote(prompt, quote)
    assert prompt[start:end] == prompt
    assert prompt[start] == 'H'
    assert '\u201c' in prompt[start:end]
    assert '\u201d' in prompt[start:end]


def test_trailing_punctuation_truncation_extends_original_span():
    prompt = "Always cite the source of any medical claim."
    quote = "Always cite the source of any medical claim"
    start, end = align_quote(prompt, quote)
    assert prompt[start:end] == prompt
    assert prompt[end - 1] == '.'


def test_unaligned_quote_returns_none():
    assert align_quote("Hello world", "not in the prompt") is None


def test_verify_foci_flags_unaligned():
    prompt = "Keep this sentence. Drop that one."
    foci = [
        {'focus': 'Keep', 'prompt_section': 'Keep this sentence.'},
        {'focus': 'Paraphrase', 'prompt_section': 'a summary that never appears'},
    ]
    out = verify_foci(prompt, foci)
    assert out[0]['verified'] is True
    assert prompt[out[0]['char_start']:out[0]['char_end']] == 'Keep this sentence.'
    assert out[1]['verified'] is False
    assert out[1]['char_start'] is None
    assert out[1]['char_end'] is None


def test_delete_span_is_strict_subset_of_original():
    prompt = "AAA BBB CCC"
    start, end = align_quote(prompt, "BBB")
    ablated, empty, collapsed = delete_span(prompt, start, end)
    assert not empty
    assert not collapsed
    assert ablated == prompt[:start] + prompt[end:]
    assert set(ablated) <= set(prompt)


def test_boundary_blank_line_collapse_only():
    prompt = "Keep A.\n\nDelete me.\n\nKeep B.\n\nKeep C."
    start, end = align_quote(prompt, "Delete me.")
    raw = prompt[:start] + prompt[end:]
    assert raw == "Keep A.\n\n\n\nKeep B.\n\nKeep C."
    ablated, empty, collapsed = delete_span(prompt, start, end)
    assert collapsed is True
    assert empty is False
    assert ablated == "Keep A.\n\nKeep B.\n\nKeep C."
    # Unrelated blank line between Keep B and Keep C is untouched.
    assert "Keep B.\n\nKeep C." in ablated
    assert ablated != prompt[:start] + prompt[end:]
    assert set(ablated) <= set(prompt)


def test_single_newline_join_is_not_collapsed():
    prompt = "AAA\nBBB\nCCC"
    start, end = align_quote(prompt, "BBB")
    ablated, _, collapsed = delete_span(prompt, start, end)
    assert collapsed is False
    assert ablated == "AAA\n\nCCC"


def test_classify_dynamic_excluded():
    prompt = "Static instruction. Chat goes here."
    foci = [
        {'focus': 'Static', 'prompt_section': 'Static instruction.', 'is_dynamic': False},
        {
            'focus': 'Chat',
            'prompt_section': 'Chat goes here.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
    ]
    out = classify_foci_for_ablation(prompt, foci)
    assert out[0]['attributable'] is True
    assert out[1]['attributable'] is False
    assert out[1]['reason'] == 'dynamic_slot'


def test_classify_overlap_refused():
    prompt = "The quick brown fox jumps."
    foci = [
        {'focus': 'A', 'prompt_section': 'The quick brown fox'},
        {'focus': 'B', 'prompt_section': 'brown fox jumps.'},
    ]
    out = classify_foci_for_ablation(prompt, foci)
    assert out[0]['verified'] is True
    assert out[1]['verified'] is True
    assert out[0]['attributable'] is False
    assert out[1]['attributable'] is False
    assert out[0]['reason'] == 'overlap'
    assert out[1]['reason'] == 'overlap'
    assert 'B' in out[0]['overlap_with']
    assert 'A' in out[1]['overlap_with']


def test_adjacent_spans_do_not_overlap():
    prompt = "AAAA BBBB"
    foci = [
        {'focus': 'A', 'prompt_section': 'AAAA'},
        {'focus': 'B', 'prompt_section': 'BBBB'},
    ]
    out = classify_foci_for_ablation(prompt, foci)
    assert out[0]['attributable'] is True
    assert out[1]['attributable'] is True


def test_collapse_helper_requires_both_sides():
    joined, collapsed = collapse_deletion_boundary("AAA\n\n", "\n\nBBB")
    assert collapsed is True
    assert joined == "AAA\n\nBBB"
