from app.services.minigames import SESSIONS, check_answer, start_game


def test_all_mini_games_start_and_have_valid_answers():
    kinds = ["math", "code", "word", "sequence", "logic", "anagram", "tower", "algorithm", "counter", "space", "quiz", "chain"]
    user_id = 987654321

    for kind in kinds:
        SESSIONS.clear()
        game = start_game(user_id, kind)
        assert game.kind == kind
        assert game.prompt
        assert game.attempts_left > 0

        if kind != "chain":
            assert game.answer != ""

        if kind == "code":
            assert len(game.answer) == 4
            assert game.answer.isdigit()
            assert len(set(game.answer)) == 4

        if kind == "algorithm":
            assert game.answer.split() == sorted(game.answer.split(), key=int)

        if kind == "chain":
            assert game.meta["required_first"].isalpha()


def test_code_returns_exact_and_partial_matches():
    user_id = 987654322
    SESSIONS.clear()
    game = start_game(user_id, "code")

    wrong = next(
        value for value in ("1234", "5678", "9012", "4321", "8765")
        if value != game.answer and len(set(value)) == 4
    )
    status, _, data = check_answer(user_id, wrong)

    assert status == "progress"
    assert "exact" in data
    assert "partial" in data
    assert data["attempts_left"] == 5


def test_chain_accepts_any_word_with_required_first_letter():
    user_id = 987654323
    SESSIONS.clear()
    game = start_game(user_id, "chain")
    first = game.meta["required_first"]

    status, finished, _ = check_answer(user_id, first + "а")
    assert status == "win"
    assert finished is game


def test_tower_requires_five_floors():
    user_id = 987654324
    SESSIONS.clear()
    game = start_game(user_id, "tower")

    for floor in range(1, 6):
        current = SESSIONS[user_id]
        assert current.meta["floor"] == floor
        status, finished, data = check_answer(user_id, current.answer)
        if floor < 5:
            assert status == "tower_progress"
            assert finished is current
            assert data["floor"] == floor + 1
        else:
            assert status == "win"
            assert finished is current
            assert data["floors"] == 5

    assert user_id not in SESSIONS
