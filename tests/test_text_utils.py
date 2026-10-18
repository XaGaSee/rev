"""Tests for text utils: HTML escaping, markdown conversion, safe splitting."""

from __future__ import annotations

from bot.utils.text import escape_html, markdown_to_html, split_html


def test_escape_html():
    assert escape_html("<b> & </b>") == "&lt;b&gt; &amp; &lt;/b&gt;"


def test_markdown_conversions():
    html = markdown_to_html("**bold** `code`\n```py\nprint(1)\n```")
    assert "<b>bold</b>" in html
    assert "<code>code</code>" in html
    assert "<pre><code>print(1)</code></pre>" in html
    assert escape_html("<script>") in markdown_to_html("<script>")


def test_split_long_code_keeps_tags_balanced():
    long = "<pre><code>" + "x" * 5000 + "</code></pre>"
    chunks = split_html(long)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.count("<pre><code>") == chunk.count("</code></pre>")
    assert all(len(c) <= 4096 for c in chunks)


def test_split_reassembles_content():
    text = escape_html("word " * 3000)
    chunks = split_html(f"<b>{text}</b>")
    joined = "".join(chunks)
    # every chunk's tags must be closed or re-opened -> reconstruct stays balanced
    opens = joined.count("<b>") - joined.count("</b>")
    assert opens == 0
    assert all(len(c) <= 4096 for c in chunks)


def test_split_short_text_untouched():
    assert split_html("привет") == ["привет"]