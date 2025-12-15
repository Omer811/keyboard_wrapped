from scripts.word_checker import WordChecker


def test_hebrew_word_is_recognized():
    checker = WordChecker(languages=["he"])
    assert checker.is_correct("מקלדת")
    assert checker.is_correct("אני")


def test_mixed_language_checker_supports_both():
    checker = WordChecker(languages=["en", "he"])
    assert checker.is_correct("the")
    assert checker.is_correct("שיר")
    assert not checker.is_correct("שכחתי_היער")  # unreachable word to make sure fallback doesn't overmatch
