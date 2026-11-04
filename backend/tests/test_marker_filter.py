"""The streaming `[n]` marker filter (PRD §12.7, task 7.12).

`_MarkerStreamFilter` is private, but this module is its sanctioned consumer:
the filter is tested directly, exactly where the model text is cleaned chunk
by chunk. Every test compares the chunked path (several `feed()` calls plus
`flush()`) with the same text fed at once — the equivalence the streaming
route relies on when the model splits a marker across two chunks.
"""

import re

import pytest

from app.services.rag_service import _MarkerStreamFilter

MARKER_PATTERN = re.compile(r'\[\d+\]')

# Representative texts whose bracket markers are all numeric (plus one with a
# literal `[anexo]`): none may leak a `\[\d+\]` marker after the filter.
EQUIVALENCE_TEXTS = [
    'The deadline is 30 days [1].',
    'O prazo é de 30 dias [1, 2] contados da compra.',
    'Desligue [1-3] e aguarde [4].',
    'First [1] then [2], finally [3].',
    'a [1] [3] b [2], c',
    'sem espaço[2]antes',
    'Markdown:\n- item one [1]\n- item two [2].\n\nFim [3].',
    'a [1]\n[2] b',
    'see [anexo] and [1] here',
]


def _filter_whole(text):
    """The filter applied to the whole text at once (one feed + flush)."""
    marker_filter = _MarkerStreamFilter()
    return marker_filter.feed(text) + marker_filter.flush()


def _filter_pieces(text, pieces):
    """The filter fed piece by piece (model chunks), then flushed."""
    assert ''.join(pieces) == text
    marker_filter = _MarkerStreamFilter()
    fed = ''.join(marker_filter.feed(piece) for piece in pieces)
    return fed + marker_filter.flush()


def _chunk_splits(text):
    """Chunk splits worth exercising: the whole text, single characters,
    every one-cut split and cuts that break a marker open (`[` / `3]`)."""
    yield [text]
    yield list(text)
    for cut in range(1, len(text)):
        yield [text[:cut], text[cut:]]
    for marker in MARKER_PATTERN.finditer(text):
        start, end = marker.span()
        yield [text[: start + 1], text[start + 1 :]]
        yield [text[: end - 1], text[end - 1 :]]
        yield [text[:start], text[start:end], text[end:]]


def test_complete_marker_is_removed():
    assert _filter_whole('[1]') == ''
    assert _filter_whole('The deadline is 30 days [1].') == 'The deadline is 30 days.'


def test_marker_index_split_across_chunks():
    # A marker index split between model chunks: `[` in one, `3]` in the next
    # (PRD §12.11), and also split right before the closing bracket.
    assert _filter_pieces('a [3] b', ['a [', '3] b']) == 'a b'
    assert _filter_pieces('a [3] b', ['a [3', '] b']) == 'a b'
    assert _filter_whole('a [3] b') == 'a b'


def test_marker_lists_and_ranges_are_removed():
    # `MODEL_MARKER_PATTERN` also covers lists, ranges and separators.
    text = 'a [1, 2] b [1-3] c [1–2] d [1; 2] e.'

    assert _filter_whole(text) == 'a b c d e.'


def test_adjacent_removals_collapse_to_one_space():
    assert _filter_whole('a [1] [3] b') == 'a b'
    # the cleanup is local: a double space far from a removal is content
    assert _filter_whole('a  b [1] c') == 'a  b c'


def test_removal_does_not_leave_space_before_punctuation():
    assert _filter_whole('texto [3], resto') == 'texto, resto'
    assert _filter_whole('a [1] [3], b') == 'a, b'
    assert _filter_whole('fim [2].') == 'fim.'


def test_bracket_with_non_numeric_content_is_kept():
    text = 'Veja o [anexo] para detalhes.'

    assert _filter_whole(text) == text
    # also when the `[` and the content arrive in separate chunks
    assert _filter_pieces(text, ['Veja o [', 'anexo] para detalhes.']) == text


def test_incomplete_bracket_at_the_end_is_kept():
    # Real content is never removed: an unterminated bracket survives.
    assert _filter_whole('Termina com [') == 'Termina com ['
    assert _filter_whole('Aguarde [1') == 'Aguarde [1'


def test_removal_inside_a_markdown_list_keeps_the_line_structure():
    text = '- item one [1]\n- item two [2], noted\n- item three [3] ends'
    filtered = _filter_whole(text)

    assert filtered == '- item one\n- item two, noted\n- item three ends'
    # the three list lines survive as list lines: no reflow, no blank line
    assert filtered.split('\n') == [
        '- item one',
        '- item two, noted',
        '- item three ends',
    ]
    # local cleanup only: no double spaces, no space before punctuation
    assert '  ' not in filtered
    assert re.search(r'\s+[.,;:!?…]', filtered) is None


def test_removal_keeps_paragraph_breaks():
    assert _filter_whole('Primeiro [1].\n\nSegundo [2].') == 'Primeiro.\n\nSegundo.'


@pytest.mark.parametrize('text', EQUIVALENCE_TEXTS)
def test_chunked_filtering_equals_whole_text_filtering(text):
    expected = _filter_whole(text)

    # no numeric marker survives when the text's markers are all numeric
    assert MARKER_PATTERN.search(expected) is None

    for pieces in _chunk_splits(text):
        assert _filter_pieces(text, pieces) == expected, pieces
