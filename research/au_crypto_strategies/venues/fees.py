"""Venue fee models for AU brokers and crypto exchanges (retail base tiers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Venue:
    id: str
    name: str
    asset_class: str  # "asx_equity" | "asx_cfd" | "crypto_spot" | "crypto_perp"
    # fee(notional, is_open) -> AUD/USD fee for one fill
    commission_fn: Callable[[float, bool], float]
    # fractional slippage applied to price (one-way)
    slippage_bps: float
    # daily financing rate on long notional (0 for cash equities / spot)
    long_financing_daily: float = 0.0
    short_financing_daily: float = 0.0
    # crypto: optional taker rate if commission_fn unused
    notes: str = ""


def _commsec_cdia(notional: float, _is_open: bool) -> float:
    n = abs(notional)
    if n <= 1000:
        return 5.0
    if n <= 3000:
        return 10.0
    if n <= 10000:
        return 19.95
    if n <= 25000:
        return 29.95
    return n * 0.0012


def _selfwealth(notional: float, _is_open: bool) -> float:
    return 9.50


def _stake(notional: float, _is_open: bool) -> float:
    n = abs(notional)
    if n <= 30000:
        return 3.0
    return n * 0.0001


def _ibkr_au(notional: float, _is_open: bool) -> float:
    return max(6.0, abs(notional) * 0.0008)


def _pct_side(rate: float) -> Callable[[float, bool], float]:
    def _fn(notional: float, _is_open: bool) -> float:
        return abs(notional) * rate

    return _fn


# RBA cash ~3.60% mid-2026 proxy + 2.5% CFD markup ≈ 6.1% p.a. long
_CFD_LONG_DAILY = 0.061 / 365.0
_CFD_SHORT_DAILY = 0.02 / 365.0  # shorts often credit; keep mild debit to stay conservative


def asx_venues() -> list[Venue]:
    return [
        Venue("commsec", "CommSec (CDIA)", "asx_equity", _commsec_cdia, 5.0, notes="Tiered online CDIA"),
        Venue("selfwealth", "SelfWealth", "asx_equity", _selfwealth, 5.0, notes="Flat A$9.50"),
        Venue("stake", "Stake", "asx_equity", _stake, 5.0, notes="A$3 to 30k then 0.01%"),
        Venue("ibkr_au", "IBKR Australia", "asx_equity", _ibkr_au, 5.0, notes="max(A$6, 0.08%)"),
        Venue(
            "pepperstone_cfd",
            "Pepperstone Share CFD",
            "asx_cfd",
            _pct_side(0.0007),
            5.0,
            long_financing_daily=_CFD_LONG_DAILY,
            short_financing_daily=_CFD_SHORT_DAILY,
            notes="0.07%/side + overnight financing proxy",
        ),
        Venue(
            "ig_au_cfd",
            "IG Australia Share CFD",
            "asx_cfd",
            _pct_side(0.0010),
            5.0,
            long_financing_daily=_CFD_LONG_DAILY,
            short_financing_daily=_CFD_SHORT_DAILY,
            notes="0.10%/side + overnight financing proxy",
        ),
    ]


def crypto_spot_venues() -> list[Venue]:
    # taker both sides
    return [
        Venue("binance_spot", "Binance Spot", "crypto_spot", _pct_side(0.0010), 3.0, notes="VIP0 10bps taker"),
        Venue("bybit_spot", "Bybit Spot", "crypto_spot", _pct_side(0.0010), 3.0, notes="VIP0 10bps taker"),
        Venue("okx_spot", "OKX Spot", "crypto_spot", _pct_side(0.0010), 3.0, notes="VIP0 10bps taker (maker 8bps unused)"),
        Venue("kraken_spot", "Kraken Spot", "crypto_spot", _pct_side(0.0026), 4.0, notes="Conservative ~26bps taker proxy"),
    ]


def crypto_perp_venues() -> list[Venue]:
    return [
        Venue("binance_perp", "Binance USDT-Perp", "crypto_perp", _pct_side(0.0005), 2.0, notes="VIP0 5bps taker"),
        Venue("bybit_perp", "Bybit USDT-Perp", "crypto_perp", _pct_side(0.00055), 2.0, notes="VIP0 5.5bps taker"),
        Venue("okx_perp", "OKX USDT-Perp", "crypto_perp", _pct_side(0.0005), 2.0, notes="VIP0 5bps taker"),
        Venue("kraken_perp", "Kraken Perp", "crypto_perp", _pct_side(0.0005), 3.0, notes="~5bps taker proxy"),
    ]


ALL_VENUES: dict[str, Venue] = {
    v.id: v for v in asx_venues() + crypto_spot_venues() + crypto_perp_venues()
}
