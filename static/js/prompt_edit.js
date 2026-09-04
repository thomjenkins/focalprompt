(function (global) {
    'use strict';

    function detectPromptEdit(previousText, nextText) {
        previousText = previousText || '';
        nextText = nextText || '';
        if (previousText === nextText) {
            return null;
        }

        var prefix = 0;
        var minLen = Math.min(previousText.length, nextText.length);
        while (prefix < minLen && previousText[prefix] === nextText[prefix]) {
            prefix += 1;
        }

        var suffix = 0;
        while (
            suffix < previousText.length - prefix &&
            suffix < nextText.length - prefix &&
            previousText[previousText.length - 1 - suffix] === nextText[nextText.length - 1 - suffix]
        ) {
            suffix += 1;
        }

        var oldStart = prefix;
        var oldEnd = previousText.length - suffix;
        var newEnd = nextText.length - suffix;
        return {
            old_start: oldStart,
            old_end: oldEnd,
            new_end: newEnd,
            delta: (newEnd - oldStart) - (oldEnd - oldStart)
        };
    }

    function adjustSpanForPromptEdit(span, edit) {
        if (!span || !edit) return { span: span, changed: false, needsReview: false };
        var start = Number(span.char_start != null ? span.char_start : span.start);
        var end = Number(span.char_end != null ? span.char_end : span.end);
        if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
            return { span: span, changed: false, needsReview: true };
        }

        var oldStart = edit.old_start;
        var oldEnd = edit.old_end;
        var delta = edit.delta;
        var isInsertion = oldStart === oldEnd && delta > 0;
        var touchesSpan = isInsertion
            ? oldStart >= start && oldStart <= end
            : oldStart < end && oldEnd > start;
        var nextStart = start;
        var nextEnd = end;
        var needsReview = false;

        if (isInsertion && oldStart >= start && oldStart <= end) {
            nextEnd += delta;
        } else if (end <= oldStart) {
            // Span is fully before a replacement/deletion.
        } else if (start >= oldEnd) {
            nextStart += delta;
            nextEnd += delta;
        } else if (start <= oldStart && end >= oldEnd) {
            nextEnd += delta;
        } else {
            nextStart = start > oldStart ? oldStart : start;
            nextEnd = Math.max(nextStart, end + delta);
            needsReview = true;
        }

        return {
            span: Object.assign({}, span, {
                char_start: Math.max(0, nextStart),
                char_end: Math.max(Math.max(0, nextStart), nextEnd)
            }),
            changed: nextStart !== start || nextEnd !== end || touchesSpan,
            needsReview: needsReview
        };
    }

    global.FocalPromptPromptEdit = {
        detectPromptEdit: detectPromptEdit,
        adjustSpanForPromptEdit: adjustSpanForPromptEdit
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = global.FocalPromptPromptEdit;
    }
})(typeof window !== 'undefined' ? window : globalThis);
