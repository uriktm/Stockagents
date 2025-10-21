from stockagents.tools.volume_and_technicals import VolumeAndTechnicalsTool


def test_volume_and_technicals_returns_intraday_structure_for_empty_symbol():
    result = VolumeAndTechnicalsTool("")
    assert "intraday" in result

    intraday = result["intraday"]
    expected_keys = {"last_price", "change_percent", "short_term_rsi", "volume_ratio", "last_update"}
    assert expected_keys.issubset(set(intraday))

    for key in expected_keys:
        assert intraday[key] is None
