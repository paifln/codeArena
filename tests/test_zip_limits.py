import io
import json
import zipfile
from test_api import arena, PREFIX


def test_import_bounds_repeated_test_references(arena):
    clients, _, _ = arena
    # No extraction and no execution: repeated archive references are rejected
    # before eagerly constructing the entire test list.
    for count, size in [(51, 1), (50, 6000)]:
        data = {
            "title": "Reference limits",
            "difficulty": "EASY",
            "tests": [
                {"input": "tests/01.in", "output": "tests/01.out", "is_sample": True}
            ]
            * count,
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as z:
            z.writestr("problem.json", json.dumps(data))
            z.writestr("statement.md", "Print the input unchanged.")
            z.writestr("tests/01.in", "a" * size)
            z.writestr("tests/01.out", "a" * size)
        response = clients["teacher"].post(
            PREFIX + "/problems/import",
            files={"file": ("problem.zip", buffer.getvalue(), "application/zip")},
        )
        assert response.status_code == 400
