"""
Testes do CrosshairCoachAnalyzer.
Execute com: pytest tests/test_crosshair_coach.py -v
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from analyzers.crosshair_coach.analyzer import CrosshairCoachAnalyzer


def make_crosshair_event(player_id: str, offset_degrees: float, match_id: str = "match-1") -> dict:
    return {
        "event_type": "CrosshairMoved",
        "schema_version": "1.0",
        "occurred_at": "2024-01-15T20:00:00Z",
        "match_id": match_id,
        "player_id": player_id,
        "game": "cs2",
        "payload": {
            "crosshair_offset_degrees": offset_degrees,
            "is_on_target": False,
            "weapon_in_hand": "ak47",
            "round_number": 1,
            "tick": 1000,
        },
    }


def make_round_ended_event(match_id: str = "match-1") -> dict:
    return {
        "event_type": "RoundEnded",
        "schema_version": "1.0",
        "occurred_at": "2024-01-15T20:02:00Z",
        "match_id": match_id,
        "game": "cs2",
        "payload": {"round_number": 1, "winner": "t", "win_condition": "elimination"},
    }


@pytest.fixture
def analyzer():
    return CrosshairCoachAnalyzer(redis_url="redis://localhost:6379/0")


@pytest.mark.asyncio
async def test_low_crosshair_generates_feedback(analyzer):
    """Jogador com mira consistentemente baixa deve gerar feedback."""
    # 30 amostras com mira abaixo de -5°
    for _ in range(30):
        await analyzer.analyze(make_crosshair_event("player1", offset_degrees=-15.0))

    result = await analyzer.analyze(make_round_ended_event())

    assert result is not None
    assert result["category"] == "aim"
    assert result["severity"] == "warning"
    assert "baixo" in result["title"].lower()
    assert result["confidence_score"] > 0.5


@pytest.mark.asyncio
async def test_good_crosshair_no_feedback(analyzer):
    """Jogador com mira boa não deve gerar feedback."""
    # 30 amostras com mira no nível correto
    for _ in range(30):
        await analyzer.analyze(make_crosshair_event("player1", offset_degrees=1.0))

    result = await analyzer.analyze(make_round_ended_event())

    assert result is None


@pytest.mark.asyncio
async def test_insufficient_samples_no_feedback(analyzer):
    """Poucos dados não devem gerar feedback."""
    for _ in range(5):  # Menos de 20 amostras
        await analyzer.analyze(make_crosshair_event("player1", offset_degrees=-20.0))

    result = await analyzer.analyze(make_round_ended_event())

    assert result is None


@pytest.mark.asyncio
async def test_state_cleared_after_round(analyzer):
    """Estado deve ser limpo após o fim do round."""
    for _ in range(30):
        await analyzer.analyze(make_crosshair_event("player1", offset_degrees=-15.0))

    await analyzer.analyze(make_round_ended_event())

    # No segundo round, sem amostras suficientes → sem feedback
    result = await analyzer.analyze(make_round_ended_event())
    assert result is None
