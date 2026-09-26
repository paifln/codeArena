def normalize(output: str) -> str:
    """Normalize line endings, trailing horizontal space and final empty lines only."""
    lines = output.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    return '\n'.join(line.rstrip(' \t') for line in lines).rstrip('\n')


def equivalent(actual: str, expected: str) -> bool:
    return normalize(actual) == normalize(expected)
