"""Bounded package adapter. ZIP members are read in memory, never extracted.

Current format: problem.json, statement.md and tests/*.in/*.out.
New package dialects should translate into ProblemIn here, leaving ORM/routes intact.
"""

import io
import json
import zipfile
from .. import schemas as S


def read_package(blob: bytes) -> S.ProblemIn:
    if len(blob) > 1_000_000:
        raise ValueError("Archive too large")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos = z.infolist()
            if len(infos) > 104 or sum(i.file_size for i in infos) > 1_000_000:
                raise ValueError()
            names = [i.filename for i in infos]
            if len(set(names)) != len(names):
                raise ValueError()
            for i in infos:
                if (
                    i.filename.startswith(("/", "\\"))
                    or "\\" in i.filename
                    or ":" in i.filename
                    or ".." in i.filename.split("/")
                    or i.flag_bits & 1
                    or (i.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ValueError()
                if i.file_size > max(i.compress_size, 1) * 100:
                    raise ValueError()
            data = json.loads(z.read("problem.json"))
            # Count references too: a small archive must not expand into an
            # unbounded list by referring to the same large member repeatedly.
            entries = data.get("tests")
            if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
                raise ValueError()
            by_name = {i.filename: i for i in infos}
            referenced_size = sum(
                by_name[t[key]].file_size
                for t in entries
                for key in ("input", "output")
            )
            if referenced_size > 512_000:
                raise ValueError()
            data["description"] = z.read("statement.md").decode("utf-8")
            data["tests"] = [
                {
                    "input_data": z.read(t["input"]).decode("utf-8"),
                    "expected": z.read(t["output"]).decode("utf-8"),
                    "is_sample": t.get("is_sample", False),
                    "weight": t.get("weight", 1),
                }
                for t in data["tests"]
            ]
            return S.ProblemIn.model_validate(data)
    except Exception as exc:
        raise ValueError("Invalid or unsafe problem archive") from exc
