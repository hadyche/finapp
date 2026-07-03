"""Tests for company-name → ticker matching (precision-first)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.data.ticker_map import (
    normalize_company_name,
    build_name_index,
    match_recipient,
    cik_to_ticker,
)


def _sample_map():
    return pd.DataFrame([
        {"cik": 936468,  "ticker": "LMT",  "title": "LOCKHEED MARTIN CORP"},
        {"cik": 1101302, "ticker": "MRCY", "title": "MERCURY SYSTEMS INC"},
        {"cik": 1035983, "ticker": "TLS",  "title": "Telos Corp"},
        {"cik": 1836981, "ticker": "BBAI", "title": "BigBear.ai Holdings, Inc."},
        {"cik": 320193,  "ticker": "AAPL", "title": "Apple Inc."},
        {"cik": 1373715, "ticker": "KTOS", "title": "KRATOS DEFENSE & SECURITY SOLUTIONS, INC."},
        # single-word name after normalization ("Eastern Co" → "EASTERN")
        {"cik": 31107,   "ticker": "EML",  "title": "Eastern Co"},
        # deliberate ambiguity: same normalized name, two tickers
        {"cik": 111,     "ticker": "DUP1", "title": "Duplicate Name Corp"},
        {"cik": 222,     "ticker": "DUP2", "title": "Duplicate Name Inc"},
    ]).assign(norm_name=lambda d: d["title"].map(normalize_company_name))


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize_company_name("Lockheed Martin Corp.") == "LOCKHEED MARTIN"
    assert normalize_company_name("BigBear.ai Holdings, Inc.") == "BIGBEAR AI"
    assert normalize_company_name("The Boeing Company") == "BOEING"
    assert normalize_company_name("Telos Corp") == "TELOS"


def test_normalize_strips_stacked_suffixes():
    assert normalize_company_name("Acme Holdings, Inc.") == "ACME"


def test_normalize_never_empties_single_suffix_name():
    # A company literally named "Holdings Inc" keeps one token
    assert normalize_company_name("Holdings Inc") == "HOLDINGS"


def test_exact_match():
    idx = build_name_index(_sample_map())
    hit = match_recipient("LOCKHEED MARTIN CORP", idx)
    assert hit and hit["ticker"] == "LMT" and hit["confidence"] == "exact"


def test_exact_match_different_suffix():
    idx = build_name_index(_sample_map())
    hit = match_recipient("Mercury Systems, Incorporated", idx)
    assert hit and hit["ticker"] == "MRCY" and hit["confidence"] == "exact"


def test_prefix_match_subsidiary():
    idx = build_name_index(_sample_map())
    hit = match_recipient("LOCKHEED MARTIN AERONAUTICS COMPANY", idx)
    assert hit and hit["ticker"] == "LMT" and hit["confidence"] == "prefix"


def test_no_false_positive_on_word_boundary():
    idx = build_name_index(_sample_map())
    # "TELOSA" must not match "TELOS"
    assert match_recipient("TELOSA VENTURES LLC", idx) is None


def test_single_word_names_never_prefix_match():
    idx = build_name_index(_sample_map())
    # The real-world bug: Eastern Shipbuilding (private) must NOT match
    # Eastern Co (EML) just because both start with "EASTERN"
    assert match_recipient("EASTERN SHIPBUILDING GROUP INC", idx) is None


def test_single_word_names_still_match_exactly():
    idx = build_name_index(_sample_map())
    hit = match_recipient("EASTERN CO", idx)
    assert hit and hit["ticker"] == "EML" and hit["confidence"] == "exact"


def test_unknown_recipient_returns_none():
    idx = build_name_index(_sample_map())
    assert match_recipient("STATE UNIVERSITY OF NEW YORK", idx) is None


def test_ambiguous_normalized_names_are_dropped():
    idx = build_name_index(_sample_map())
    assert match_recipient("Duplicate Name LLC", idx) is None


def test_empty_inputs():
    assert match_recipient("", build_name_index(_sample_map())) is None
    assert match_recipient("ANYTHING", build_name_index(pd.DataFrame())) is None


def test_cik_to_ticker():
    m = _sample_map()
    assert cik_to_ticker(320193, m) == "AAPL"
    assert cik_to_ticker(999999999, m) is None
