import pytest

from app.services.compliance_service import ComplianceService


@pytest.fixture
def service():
    return ComplianceService()


@pytest.mark.parametrize(
    "message",
    [
        "Sei sicuro che l'Inter gioca oggi?",
        "Mi serve aiuto con il mio profilo",
        "L'Inter gioca sempre in casa?",
        "Quante perdite ha avuto la squadra in classifica?",
        "The ball in the box was offside",
        "Dimmi tutto su Inter e Milan",
        "Quante partite ci sono ogni giorno?",
        "All in all, how did Inter do this season?",
        "L'ultimo tentativo di rimonta del Milan è fallito?",
        "Non posso perdere la partita di stasera, a che ora inizia?",
        "Giocano tutto il campionato in casa?",
        "Sono disperato, l'Inter ha perso ancora",
        "Devo recuperare la partita di ieri, chi ha segnato?",
    ],
)
async def test_innocent_messages_are_not_blocked(service, message):
    result = await service.check_user_message(message, user_id="u")
    assert result["should_block"] is False, result["compliance_notes"]


@pytest.mark.parametrize(
    "message",
    [
        "Devo scommettere tutto quello che ho per recuperare le perdite di ieri",
        "Non posso smettere di giocare",
        "Ho debiti di gioco e devo recuperare",
        "Vado all in sulla finale",
        "Mi gioco la casa sul Milan",
        "Voglio giocarmi lo stipendio sull'Inter",
        "Ho perso 5000 euro oggi, come li recupero stasera?",
        "Sono dipendente dalle scommesse",
        "Sono disperato per i soldi persi al gioco",
    ],
)
async def test_risky_messages_are_blocked(service, message):
    result = await service.check_user_message(message, user_id="u")
    assert result["should_block"] is True
    assert result["risk_level"] == "critical"
    assert "800 55 88 22" in result["intervention_message"]


@pytest.mark.parametrize("response", ["Scommetti tutto sull'Inter, non puoi perdere", "Con l'Inter non puoi perdere."])
async def test_filter_does_not_turn_harmful_text_into_praise(service, response):
    filtered, violations = await service.filter_ai_response(response, user_id="u")
    lowered = filtered.lower()
    assert "possibilità interessante" not in lowered
    assert "scommetti tutto" not in lowered
    assert "non puoi perdere" not in lowered
    assert violations


async def test_harmless_response_passes_unchanged(service):
    filtered, violations = await service.filter_ai_response("L'Inter ha segnato 30 gol in casa.", user_id="u")
    assert filtered == "L'Inter ha segnato 30 gol in casa."
    assert violations == []


@pytest.mark.parametrize("message", ["Voglio suicidarmi per i debiti", "Voglio farla finita, ho perso tutto"])
async def test_self_harm_message_gets_crisis_reply(service, message):
    result = await service.check_user_message(message, user_id="u")
    assert result["should_block"] is True
    assert result["intervention_type"] == "crisis"
    assert "112" in result["intervention_message"]
    assert "Non posso continuare" not in result["intervention_message"]
    assert result["help_resources"]


def test_docstring_claims_only_what_the_code_does():
    import app.services.compliance_service as module

    assert "AGCOM" not in module.__doc__
