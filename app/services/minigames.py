from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

WORDS = (
    "алгоритм", "сервер", "команда", "модератор", "сообщество",
    "игрок", "профиль", "репутация", "клавиатура", "телеграм",
)

@dataclass
class MiniGame:
    kind: str
    prompt: str
    answer: str
    attempts_left: int
    started_at: datetime
    meta: dict

    @property
    def expired(self) -> bool:
        return datetime.utcnow() - self.started_at > timedelta(minutes=5)

    @property
    def difficulty(self) -> str:
        return str(self.meta.get("difficulty", "normal"))

SESSIONS: dict[int, MiniGame] = {}


def _unique_digits(length: int = 4) -> str:
    digits = list("0123456789")
    random.shuffle(digits)
    if digits[0] == "0":
        digits[0], digits[1] = digits[1], digits[0]
    return "".join(digits[:length])


def _math_task() -> tuple[str, str, str]:
    difficulty = random.choice(("normal", "hard", "expert"))
    if difficulty == "normal":
        a, b, c = random.randint(12, 39), random.randint(7, 25), random.randint(2, 9)
        return f"{a} × {b} + {c}", str(a * b + c), difficulty
    if difficulty == "hard":
        a, b, c = random.randint(20, 70), random.randint(8, 35), random.randint(2, 12)
        return f"{a} × {b} − {c}²", str(a * b - c * c), difficulty
    a, b, c = random.randint(15, 45), random.randint(3, 12), random.randint(2, 9)
    return f"({a} + {b}) × {c} − {b}²", str((a + b) * c - b * b), difficulty


def start_game(user_id: int, kind: str) -> MiniGame:
    if kind == "math":
        prompt, answer, difficulty = _math_task()
        game = MiniGame("math", f"Реши: <b>{prompt}</b>", answer, 3, datetime.utcnow(), {"difficulty": difficulty})
    elif kind == "code":
        answer = _unique_digits(4)
        game = MiniGame(
            "code",
            "Взломай 4-значный код. Все цифры разные. После каждой попытки я скажу, сколько цифр на правильных местах.",
            answer,
            6,
            datetime.utcnow(),
            {"difficulty": "hard", "attempts": []},
        )
    elif kind == "word":
        answer = random.choice(WORDS)
        scrambled = "".join(random.sample(answer, len(answer)))
        game = MiniGame(
            "word",
            f"Расшифруй слово: <b>{scrambled}</b>",
            answer,
            3,
            datetime.utcnow(),
            {"difficulty": "hard"},
        )
    elif kind == "sequence":
        length = random.randint(5, 9)
        seq = [random.randint(1, 9) for _ in range(length)]
        answer = "".join(map(str, seq))
        game = MiniGame(
            "sequence",
            f"🔢 Восстанови последовательность. Первые числа: <b>{answer[:3]}…</b>",
            answer,
            4,
            datetime.utcnow(),
            {"difficulty": "expert", "length": length},
        )
    elif kind == "logic":
        a, b, c = random.sample(range(2, 10), 3)
        answer = str(b)
        game = MiniGame(
            "logic",
            f"🧩 Если {a} → {a*a}, {b} → ?, {c} → {c*c}, какое число должно стоять вместо ?",
            answer,
            2,
            datetime.utcnow(),
            {"difficulty": "hard"},
        )
    elif kind == "anagram":
        answer = random.choice(WORDS)
        scrambled = "".join(random.sample(answer, len(answer)))
        game = MiniGame(
            "anagram",
            f"🔀 Слово зашифровано перестановкой букв: <b>{scrambled}</b>",
            answer,
            2,
            datetime.utcnow(),
            {"difficulty": "expert"},
        )
    elif kind == "memory":
        length = random.randint(5, 8)
        sequence = "".join(str(random.randint(0, 9)) for _ in range(length))
        game = MiniGame(
            "memory",
            f"Запомни последовательность и введи её через 3 секунды: <b>{sequence}</b>",
            sequence,
            1,
            datetime.utcnow(),
            {"difficulty": "expert", "length": length},
        )
    else:
        raise ValueError("unknown mini-game")
    SESSIONS[user_id] = game
    return game


def get_game(user_id: int) -> MiniGame | None:
    game = SESSIONS.get(user_id)
    if game and game.expired:
        SESSIONS.pop(user_id, None)
        return None
    return game


def cancel_game(user_id: int) -> None:
    SESSIONS.pop(user_id, None)


def check_answer(user_id: int, value: str) -> tuple[str, MiniGame | None, dict]:
    game = get_game(user_id)
    if game is None:
        return "none", None, {}

    value = value.strip().lower()
    if not value:
        return "wrong", game, {}

    if game.kind == "code":
        if len(value) != 4 or not value.isdigit() or len(set(value)) != 4:
            return "invalid", game, {}
        exact = sum(a == b for a, b in zip(value, game.answer))
        if value == game.answer:
            cancel_game(user_id)
            return "win", game, {"exact": 4}
        game.attempts_left -= 1
        if game.attempts_left <= 0:
            cancel_game(user_id)
            return "loss", game, {"answer": game.answer, "exact": exact}
        return "progress", game, {"exact": exact, "attempts_left": game.attempts_left}

    if value == game.answer:
        cancel_game(user_id)
        return "win", game, {}

    game.attempts_left -= 1
    if game.attempts_left <= 0:
        cancel_game(user_id)
        return "loss", game, {"answer": game.answer}
    return "wrong", game, {"attempts_left": game.attempts_left}


def game_catalog_text() -> str:
    return (
        "🕹 <b>Мини-игры</b>\n\n"
        "🧠 <b>Математический штурм</b> — 3 попытки, сложность Normal/Hard/Expert.\n"
        "🔐 <b>Взломщик</b> — угадай 4-значный код за 6 попыток по подсказкам.\n"
        "🔤 <b>Шифровальщик</b> — восстанови перемешанное слово за 3 попытки.\n"
        "🧠 <b>Память</b> — запомни последовательность из 5–8 цифр.\n"
        "🔢 <b>Последовательность</b> — восстанови скрытую закономерность.\n"
        "🧩 <b>Логика</b> — реши задачу на закономерность за 2 попытки.\n"
        "🔀 <b>Анаграмма PRO</b> — восстанови сложное слово за 2 попытки.\n\n"
        "За победу начисляется XP. Одновременно активна только одна игра."
    )
