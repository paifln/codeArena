"""Explainable comment markers for human review, never an authorship verdict."""

import io
import re
import tokenize

PATTERNS = (
    (
        "assistant_attribution",
        re.compile(
            r"(?:generated|written|created|produced)\s+(?:with|by)\s+(?:chatgpt|gpt[-\w]*|claude|copilot|gemini)|(?:сгенерирован|написан|создан)\w*\s+(?:с помощью\s+)?(?:chatgpt|claude|copilot|gemini|ии)",
            re.I,
        ),
    ),
    (
        "assistant_phrase",
        re.compile(
            r"as an ai (?:language model|assistant)|как (?:языковая модель|ии[ -]ассистент)",
            re.I,
        ),
    ),
    (
        "embedded_instruction",
        re.compile(
            r"ignore (?:all )?(?:previous|prior) instructions|игнорируй (?:все )?предыдущие инструкции",
            re.I,
        ),
    ),
)


def comment_review(source, language):
    comments = []
    if language == "python3":
        try:
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT:
                    comments.append((token.start[0], token.string))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
    else:
        # Skip quoted strings, including JS templates and C# verbatim strings.
        lexer = re.compile(
            r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*[\s\S]*?\*/',
            re.S,
        )
        for match in lexer.finditer(source):
            if match[0].startswith(("//", "/*")):
                comments.append((source.count("\n", 0, match.start()) + 1, match[0]))
    findings = []
    for line, comment in comments:
        for offset, text in enumerate(comment.splitlines()):
            for rule, pattern in PATTERNS:
                if pattern.search(text):
                    findings.append(
                        {"line": line + offset, "rule": rule, "excerpt": text[:240]}
                    )
    return {
        "method": "comment-markers-v1",
        "findings": findings[:20],
        "authorship_determined": False,
    }
