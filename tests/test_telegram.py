from app.telegram.formatter import to_telegram_html, truncate_message
from app.telegram.handlers import should_respond


def test_should_respond_private_chat():
    assert should_respond("hello", "private") is True


def test_should_respond_group_without_mention():
    assert should_respond("hello everyone", "group") is False


def test_should_respond_group_with_mention():
    from app.config import settings

    text = f"@{settings.telegram.bot_username} help me"
    assert should_respond(text, "group") is True


def test_to_telegram_html_bold():
    result = to_telegram_html("**bold text**")
    assert "<b>bold text</b>" in result


def test_to_telegram_html_code():
    result = to_telegram_html("`some code`")
    assert "<code>some code</code>" in result


def test_to_telegram_html_code_block():
    result = to_telegram_html("```python\nprint('hello')\n```")
    assert "<pre>" in result
    assert "print" in result


def test_to_telegram_html_escapes_html():
    result = to_telegram_html("use <div> tag")
    assert "&lt;div&gt;" in result


def test_truncate_message_short():
    assert truncate_message("hello", 100) == "hello"


def test_truncate_message_long():
    text = "a" * 5000
    result = truncate_message(text, 4096)
    assert len(result) == 4096
    assert result.endswith("...")
