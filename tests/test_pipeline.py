import json
from unittest.mock import patch

import config
from main import run
from src.dedupe import dedupe_deals
from src.models import Deal


def _deal(**overrides):
    fields = dict(
        id="deal-1",
        source="ozbargain",
        title="Shokz OpenFit 2",
        url="https://www.ozbargain.com.au/node/1",
        merchant_url="https://www.amazon.com.au/dp/ABC",
        sale_price=100.0,
        original_price=200.0,
        discount_pct=50.0,
        llm_score=9,
        llm_genuine=True,
    )
    fields.update(overrides)
    return Deal(**fields)


def _run(tmp_path, monkeypatch, deals, analyse, slack_ok=True, verify=True):
    monkeypatch.setattr(config, "CACHE_FILE", str(tmp_path / "cache.json"))

    with patch("main.OzBargainFetcher") as ozb, \
         patch("main.OzBargainFreebieFetcher") as free, \
         patch("main.RetailerFetcher") as retail, \
         patch("main.DealAnalyser") as analyser, \
         patch("main.SlackNotifier") as slack, \
         patch("main.verify_deal_price", return_value=verify):
        ozb.return_value.fetch.return_value = deals
        free.return_value.fetch.return_value = []
        retail.return_value.fetch.return_value = []
        analyser.return_value.analyse_deals.side_effect = analyse
        slack.return_value.send_slack_alerts.return_value = slack_ok
        return run(), slack.return_value


def _score(deals, score, error=False):
    for deal in deals:
        deal.llm_score = score
        deal.analysis_error = error
        deal.llm_genuine = score >= 6 and not error
    return [] if score < 6 or error else list(deals)


def test_slack_failure_does_not_settle_the_deal(tmp_path, monkeypatch):
    code, slack = _run(
        tmp_path, monkeypatch, [_deal()],
        lambda deals: _score(deals, 9),
        slack_ok=False,
    )
    assert code == 1
    assert not (tmp_path / "cache.json").exists()
    slack.send_slack_alerts.assert_called_once()


def test_low_score_is_rejected_and_not_sent(tmp_path, monkeypatch):
    code, slack = _run(tmp_path, monkeypatch, [_deal()], lambda deals: _score(deals, 2))
    assert code == 0
    slack.send_slack_alerts.assert_not_called()
    saved = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert saved["deal-1"]["status"] == "rejected"


def test_model_outage_is_left_open_for_the_next_run(tmp_path, monkeypatch):
    code, _slack = _run(
        tmp_path, monkeypatch, [_deal()],
        lambda deals: _score(deals, 1, error=True),
    )
    assert code == 0
    assert not (tmp_path / "cache.json").exists()


def test_successful_alert_is_cached_and_not_sent_twice(tmp_path, monkeypatch):
    code, slack = _run(tmp_path, monkeypatch, [_deal()], lambda deals: _score(deals, 9))
    assert code == 0
    saved = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert saved["deal-1"]["status"] == "alerted"
    assert saved["deal-1"]["sale_price"] == 100
    slack.send_slack_alerts.assert_called_once()

    code, slack = _run(tmp_path, monkeypatch, [_deal()], lambda deals: _score(deals, 9))
    assert code == 0
    slack.send_slack_alerts.assert_not_called()


def test_bad_live_price_is_rejected(tmp_path, monkeypatch):
    code, slack = _run(
        tmp_path, monkeypatch, [_deal()],
        lambda deals: _score(deals, 9),
        verify=False,
    )
    assert code == 0
    slack.send_slack_alerts.assert_not_called()
    saved = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert saved["deal-1"]["status"] == "rejected"


def test_a_real_price_drop_is_sent_again(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, [_deal()], lambda deals: _score(deals, 9))[0] == 0
    cheaper = _deal(sale_price=80, discount_pct=60)
    code, slack = _run(tmp_path, monkeypatch, [cheaper], lambda deals: _score(deals, 9))
    assert code == 0
    slack.send_slack_alerts.assert_called_once()


def test_same_listing_from_ozbargain_and_shopping_collapses():
    post = _deal()
    shopping = _deal(
        id="retail_abc",
        source="amazon_au",
        url="https://www.amazon.com.au/dp/ABC?tag=tracking",
        merchant_url="",
        votes=0,
    )
    kept = dedupe_deals([shopping, post])
    assert len(kept) == 1
    assert kept[0].source == "ozbargain"
