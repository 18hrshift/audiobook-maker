import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from preprocessor import preprocess_for_tts, _expand_abbreviations, _convert_numbers


def test_abbreviation_dr():
    assert "Doctor Smith" in _expand_abbreviations("Dr. Smith")


def test_abbreviation_etc():
    assert "etcetera" in _expand_abbreviations("fruits, vegetables, etc.")


def test_abbreviation_vs():
    assert "versus" in _expand_abbreviations("cats vs. dogs")


def test_number_basic():
    result = _convert_numbers("There were 42 apples.")
    assert "forty-two" in result


def test_number_ordinal():
    result = _convert_numbers("He finished 1st in the race.")
    assert "first" in result


def test_year_protected():
    result = _convert_numbers("Published in 1984.")
    assert "1984" in result
    assert "one thousand" not in result


def test_year_2000s_protected():
    result = _convert_numbers("In 2023, things changed.")
    assert "2023" in result


def test_decimal():
    result = _convert_numbers("Pi is 3.14.")
    assert "3 point 14" in result or "three point" in result


def test_full_pipeline():
    text = "Dr. Johnson published 3 papers in 1999, etc."
    result = preprocess_for_tts(text)
    assert "Doctor Johnson" in result
    assert "three" in result
    assert "1999" in result   # year protected
    assert "etcetera" in result
