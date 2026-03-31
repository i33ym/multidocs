import re


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_telegram_html(text: str) -> str:
    code_blocks: list[str] = []
    inline_codes: list[str] = []

    def save_block(match: re.Match[str]) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        if lang:
            code_blocks.append(
                f'<pre><code class="language-{lang}">{_escape_html(code)}</code></pre>'
            )
        else:
            code_blocks.append(f"<pre>{_escape_html(code)}</pre>")
        return f"\x00CB{len(code_blocks) - 1}\x00"

    def save_inline(match: re.Match[str]) -> str:
        inline_codes.append(f"<code>{_escape_html(match.group(1))}</code>")
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"```(\w*)\n?([\s\S]*?)```", save_block, text)
    text = re.sub(r"`([^`]+)`", save_inline, text)
    text = _escape_html(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CB{i}\x00", block)
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00IC{i}\x00", code)

    return text


def truncate_message(text: str, max_length: int = 4096) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
