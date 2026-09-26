from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

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
        return datetime.now(timezone.utc) - self.started_at > timedelta(minutes=5)

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


def _shuffle_word(word: str) -> str:
    chars = list(word)
    for _ in range(8):
        random.shuffle(chars)
        scrambled = "".join(chars)
        if scrambled != word:
            return scrambled
    return word[::-1]


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


def _tower_floor(floor: int) -> tuple[str, str]:
    a = random.randint(4 + floor, 12 + floor * 2)
    b = random.randint(2, 8 + floor)
    if floor % 2:
        return f"{a} × {b} + {floor}", str(a * b + floor)
    return f"{a * b} − {b}² + {floor}", str(a * b - b * b + floor)


def start_game(user_id: int, kind: str) -> MiniGame:
    now = datetime.utcnow()

    if kind == "math":
        prompt, answer, difficulty = _math_task()
        game = MiniGame("math", f"🧮 Реши: <b>{prompt}</b>", answer, 3, now, {"difficulty": difficulty})

    elif kind == "code":
        answer = _unique_digits(4)
        game = MiniGame(
            "code",
            "🔐 Взломай 4-значный код. Все цифры разные. После каждой попытки я покажу точные и частичные совпадения.",
            answer, 6, now, {"difficulty": "hard"},
        )

    elif kind == "word":
        answer = random.choice(WORDS)
        game = MiniGame("word", f"🔤 Расшифруй слово: <b>{_shuffle_word(answer)}</b>", answer, 3, now, {"difficulty": "hard"})

    elif kind == "sequence":
        mode = random.choice(("step", "double", "fibonacci"))
        if mode == "step":
            start, step = random.randint(1, 12), random.randint(2, 7)
            seq = [start + step * i for i in range(4)]
            answer = str(seq[-1] + step)
            prompt = f"🔢 Продолжи последовательность: <b>{', '.join(map(str, seq))}, ?</b>"
        elif mode == "double":
            start = random.randint(2, 6)
            seq = [start * (2 ** i) for i in range(4)]
            answer = str(seq[-1] * 2)
            prompt = f"🔢 Продолжи последовательность: <b>{', '.join(map(str, seq))}, ?</b>"
        else:
            a, b = random.randint(1, 8), random.randint(1, 8)
            seq = [a, b, a + b, a + 2 * b, 2 * a + 3 * b]
            answer = str(seq[-1] + seq[-2])
            prompt = f"🔢 Продолжи последовательность: <b>{', '.join(map(str, seq))}, ?</b>"
        game = MiniGame("sequence", prompt, answer, 3, now, {"difficulty": "expert", "mode": mode})

    elif kind == "logic":
        pattern = random.choice(("square", "double", "add"))
        a, b, c = random.sample(range(2, 10), 3)
        if pattern == "square":
            prompt = f"🧩 Закономерность: {a} → {a*a}, {b} → ?, {c} → {c*c}. Ответ?"
            answer = str(b * b)
        elif pattern == "double":
            prompt = f"🧩 Закономерность: {a} → {a*2}, {b} → ?, {c} → {c*2}. Ответ?"
            answer = str(b * 2)
        else:
            add = random.randint(2, 6)
            prompt = f"🧩 Закономерность: {a} → {a+add}, {b} → ?, {c} → {c+add}. Ответ?"
            answer = str(b + add)
        game = MiniGame("logic", prompt, answer, 2, now, {"difficulty": "hard"})

    elif kind == "anagram":
        answer = random.choice(WORDS)
        game = MiniGame("anagram", f"🔀 Анаграмма PRO: <b>{_shuffle_word(answer)}</b>", answer, 2, now, {"difficulty": "expert"})

    elif kind == "tower":
        floor = 1
        prompt, answer = _tower_floor(floor)
        game = MiniGame(
            "tower",
            f"🧱 <b>Башня — этаж {floor}/5</b>\n\nРеши: <b>{prompt}</b>",
            answer, 2, now, {"difficulty": "hard", "floor": floor, "max_floor": 5},
        )

    elif kind == "algorithm":
        canonical = ["проверить данные", "обработать запрос", "сохранить результат", "отправить ответ"]
        items = canonical.copy()
        random.shuffle(items)
        answer = " ".join(str(items.index(item) + 1) for item in canonical)
        prompt = "🧪 <b>Алгоритм!</b>\n\nРасставь этапы в правильном порядке:\n" + "\n".join(
            f"{i+1}. {item}" for i, item in enumerate(items)
        ) + "\n\nОтвет: номера через пробел."
        game = MiniGame("algorithm", prompt, answer, 2, now, {"difficulty": "expert"})

    elif kind == "counter":
        count = random.randint(5, 9)
        total, parts = 0, []
        for _ in range(count):
            a, b = random.randint(2, 20), random.randint(2, 12)
            op = random.choice(("+", "-"))
            value = a + b if op == "+" else a - b
            total += value
            parts.append(f"{a}{op}{b}")
        game = MiniGame("counter", "🧮 <b>Счётчик!</b>\n\nВычисли сумму:\n" + "\n".join(parts), str(total), 2, now, {"difficulty": "hard"})

    elif kind == "space":
        sectors = ["A1", "B2", "C3", "D4", "E5"]
        random.shuffle(sectors)
        answer = str(sectors.index("C3") + 1)
        game = MiniGame("space", "🌌 <b>Космический маршрут!</b>\n\nМаршрут:\n" + " → ".join(sectors) + "\n\nКаким по счёту будет C3?", answer, 2, now, {"difficulty": "hard"})

    elif kind == "quiz":
        questions = [
            ("Какая планета ближе всего к Солнцу?", "меркурий"),
            ("Сколько сторон у правильного шестиугольника?", "6"),
            ("Какой океан самый большой?", "тихий"),
            ("Сколько байт в одном килобайте по классическому двоичному исчислению?", "1024"),
        ]
        question, answer = random.choice(questions)
        game = MiniGame("quiz", f"🏆 <b>Викторина!</b>\n\n{question}", answer, 2, now, {"difficulty": "normal"})

    elif kind == "chain":
        words = ["алгоритм", "модератор", "сервер", "репутация", "игрок", "космос", "маршрут", "телеграм"]
        word = random.choice(words)
        required = word[-1].lower()
        game = MiniGame(
            "chain",
            f"🔤 <b>Словесная цепочка!</b>\n\nНачальное слово: <b>{word}</b>\n\nНапиши любое русское слово на букву <b>{required.upper()}</b>.",
            "", 1, now, {"difficulty": "normal", "required_first": required},
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

    value = " ".join(value.strip().lower().split())
    if not value:
        return "invalid", game, {}

    if game.kind == "code":
        if len(value) != 4 or not value.isdigit() or len(set(value)) != 4:
            return "invalid", game, {}
        exact = sum(a == b for a, b in zip(value, game.answer))
        partial = sum(min(value.count(d), game.answer.count(d)) for d in set(value)) - exact
        if value == game.answer:
            cancel_game(user_id)
            return "win", game, {"exact": 4, "partial": 0}
        game.attempts_left -= 1
        if game.attempts_left <= 0:
            cancel_game(user_id)
            return "loss", game, {"answer": game.answer, "exact": exact, "partial": partial}
        return "progress", game, {"exact": exact, "partial": partial, "attempts_left": game.attempts_left}

    if game.kind == "chain":
        cleaned = "".join(ch for ch in value if ch.isalpha())
        if len(cleaned) < 2 or not cleaned[0].isalpha():
            return "invalid", game, {}
        if cleaned[0] != game.meta["required_first"]:
            cancel_game(user_id)
            return "loss", game, {"answer": f"слово на букву {game.meta['required_first'].upper()}"}
        cancel_game(user_id)
        return "win", game, {}

    if value == game.answer:
        if game.kind == "tower":
            floor = int(game.meta["floor"])
            max_floor = int(game.meta["max_floor"])
            if floor >= max_floor:
                cancel_game(user_id)
                return "win", game, {"floors": max_floor}
            floor += 1
            prompt, answer = _tower_floor(floor)
            game.meta["floor"] = floor
            game.prompt = f"🧱 <b>Башня — этаж {floor}/{max_floor}</b>\n\nРеши: <b>{prompt}</b>"
            game.answer = answer
            game.attempts_left = 2
            return "tower_progress", game, {"floor": floor, "max_floor": max_floor, "prompt": game.prompt}
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
        "🧮 <b>Штурм</b> — математические задачи 3 сложности.\n"
        "🔐 <b>Взломщик</b> — 4-значный код, точные и частичные совпадения.\n"
        "🔤 <b>Шифровальщик</b> — восстанови перемешанное слово.\n"
        "🔢 <b>Последовательность</b> — найди закономерность и следующий элемент.\n"
        "🧩 <b>Логика</b> — реши закономерность.\n"
        "🔀 <b>Анаграмма PRO</b> — сложная анаграмма.\n"
        "🧱 <b>Башня</b> — пройди 5 этажей без ошибки.\n"
        "🧪 <b>Алгоритм</b> — выстрой этапы в правильном порядке.\n"
        "🧮 <b>Счётчик</b> — посчитай сумму выражений.\n"
        "🌌 <b>Космический маршрут</b> — найди нужный сектор.\n"
        "🏆 <b>Викторина</b> — ответь на вопрос.\n"
        "🔤 <b>Словесная цепочка</b> — придумай слово на нужную букву.\n\n"
        "⏱ Игра живёт 5 минут. Одновременно активна только одна игра."
    )
