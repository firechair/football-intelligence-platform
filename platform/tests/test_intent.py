import pytest

from app.services.intent_detection import ConfidenceLevel, IntentDetector, IntentType

LOWEST = ConfidenceLevel.VERY_LOW.value


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Mostrami le quote per Inter vs Milan", IntentType.ODDS_QUERY),
        ("Quali sono le quote di Inter Milan?", IntentType.ODDS_QUERY),
        ("Quali partite ci sono oggi di Serie A?", IntentType.GENERIC_MATCH_REQUEST),
        ("Quali sono le predizioni per Juventus Napoli?", IntentType.PREDICTIONS),
        ("Ciao", IntentType.GREETING),
    ],
)
def test_intent_cases(text, expected):
    match = IntentDetector().detect_intent(text)
    assert match.intent_type == expected, match
    assert match.confidence > LOWEST


def test_show_me_a_team_still_finds_the_team():
    match = IntentDetector().detect_intent("Mostrami Inter")
    assert match.intent_type == IntentType.TEAM_INFO
    assert match.entities["team_name"] == "inter"
