"""Create one optional demo contest. Does not create users or change passwords.

Run: python -m app.demo --author-id 1
The transaction is idempotent; the contest stays a draft until manually started.
"""

import argparse
import time


from .db import SessionLocal, lock_write
from .models import (
    Announcement,
    AuditLog,
    Contest,
    ContestGroup,
    ContestProblem,
    Group,
    Problem,
    SystemSetting,
    TestCase,
    User,
)

DEMO_KEY = "demo_contest_python_v1"
PROBLEMS = [
    {
        "title": "Сумма двух чисел",
        "description": "Первое знакомство с CodeArena!\n\nПрочитайте два целых числа **a** и **b** и выведите их сумму.\n\nЧисла могут быть отрицательными или равняться нулю.",
        "input_fmt": "Одна строка: два целых числа a и b через пробел. −10⁹ ≤ a, b ≤ 10⁹.",
        "output_fmt": "Одно целое число — сумма a и b.",
        "difficulty": "EASY",
        "tags": ["демо", "ввод и вывод", "арифметика"],
        "tests": [
            ("2 3\n", "5\n", True),
            ("-7 4\n", "-3\n", True),
            ("0 0\n", "0\n", False),
            ("1000000000 1000000000\n", "2000000000\n", False),
            ("-1000000000 1000000000\n", "0\n", False),
        ],
    },
    {
        "title": "Лучший результат",
        "description": "Команда записала результаты **n** тренировок. Найдите наибольший результат.\n\nРезультат может быть отрицательным: не считайте, что максимум обязательно равен нулю или больше него.",
        "input_fmt": "В первой строке число n (1 ≤ n ≤ 1000). Во второй — n целых чисел от −10⁹ до 10⁹.",
        "output_fmt": "Одно целое число — максимальный результат.",
        "difficulty": "EASY",
        "tags": ["демо", "списки", "максимум"],
        "tests": [
            ("5\n4 12 7 3 9\n", "12\n", True),
            ("3\n-8 -2 -5\n", "-2\n", True),
            ("1\n-42\n", "-42\n", False),
            ("4\n7 7 7 7\n", "7\n", False),
            ("5\n-1000000000 0 1000000000 -1 2\n", "1000000000\n", False),
        ],
    },
    {
        "title": "Уникальные значки",
        "description": "У участников есть значки с числовыми номерами. Некоторые номера повторяются.\n\nПо списку из **n** номеров определите, сколько **различных** номеров встречается хотя бы один раз.",
        "input_fmt": "В первой строке число n (1 ≤ n ≤ 1000). Во второй — n целых чисел от 0 до 10⁹.",
        "output_fmt": "Количество различных номеров.",
        "difficulty": "MEDIUM",
        "tags": ["демо", "множества"],
        "tests": [
            ("6\n1 2 2 3 1 4\n", "4\n", True),
            ("4\n5 5 5 5\n", "1\n", True),
            ("1\n0\n", "1\n", False),
            ("5\n0 1 2 3 1000000000\n", "5\n", False),
            ("8\n0 10 0 10 20 20 30 30\n", "4\n", False),
        ],
    },
]


def create_demo(db, author_id: int):
    lock_write(db)
    owner = db.get(User, author_id)
    if not owner or owner.role not in ("ADMIN", "TEACHER") or not owner.active:
        raise ValueError("Choose an existing active administrator or teacher")
    marker = db.get(SystemSetting, DEMO_KEY)
    if marker and db.get(Contest, marker.value["contest_id"]):
        return marker.value["contest_id"], False

    group = Group(name="Демо-группа · Первые шаги", author_id=owner.id)
    db.add(group)
    db.flush()
    now = time.time()
    contest = Contest(
        title="Первый шаг · Демо-соревнование по Python",
        description="Три небольшие задачи, чтобы освоиться в CodeArena: от суммы чисел до множеств. Спокойный старт, 90 минут и настоящая проверка решений.",
        rules="Python 3.12 · 3 задачи · 90 минут · ICPC. Run проверяет примеры или ваш ввод; Submit — все тесты. За неверные попытки до первого Accepted начисляется 20 минут штрафа. Преподаватель запускает соревнование кнопкой «Начать».",
        author_id=owner.id,
        start_time=now,
        end_time=now + 90 * 60,
        status="DRAFT",
        scoreboard_enabled=True,
    )
    db.add(contest)
    db.flush()
    db.add(ContestGroup(contest_id=contest.id, group_id=group.id))
    for ordinal, item in enumerate(PROBLEMS):
        data = {key: value for key, value in item.items() if key != "tests"}
        problem = Problem(
            **data,
            slug=f"demo-{contest.id}-{ordinal + 1}",
            author_id=owner.id,
            time_limit=2,
            mem_limit=128,
        )
        db.add(problem)
        db.flush()
        db.add(
            ContestProblem(
                contest_id=contest.id, problem_id=problem.id, ordinal=ordinal
            )
        )
        for index, (input_data, expected, sample) in enumerate(item["tests"]):
            db.add(
                TestCase(
                    problem_id=problem.id,
                    ordinal=index,
                    input_data=input_data,
                    expected=expected,
                    is_sample=sample,
                )
            )
    db.add(
        Announcement(
            contest_id=contest.id,
            author_id=owner.id,
            level="INFO",
            message="Добро пожаловать! Начните с задачи A. Код сохраняется на этом устройстве автоматически. Ctrl+Enter — запуск примеров, Ctrl+Shift+Enter — отправка решения. Если что-то непонятно, задайте вопрос во вкладке сообщений.",
        )
    )
    data = {"contest_id": contest.id}
    if marker:
        marker.value = data
    else:
        db.add(SystemSetting(key=DEMO_KEY, value=data))
    db.add(
        AuditLog(
            user_id=owner.id,
            action="demo.create",
            entity_id=contest.id,
            detail={"problems": 3, "group_id": group.id},
        )
    )
    db.commit()
    return contest.id, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-id", type=int, required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        cid, created = create_demo(db, args.author_id)
        print(
            f"Demo contest {cid}: {'created (DRAFT)' if created else 'already exists'}"
        )


if __name__ == "__main__":
    main()
