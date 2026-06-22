"""
fundamentals.py — v2
====================
Enriquece el universo con datos fundamentales para análisis Carvana-like.

CAMBIOS v2 (bugfixes):
- IPO date: prueba varios campos de yfinance (firstTradeDateEpochUtc,
  firstTradeDateMilliseconds, startDate) — antes solo cubría 1%, ahora >80%
- Cash runway: solo aplica a Small/Mid Cap NO utility/finance — antes
  daba falsos positivos en utilities (Alliant, AWK, etc.)
- Datetime: usa timezone-aware (compatible Python 3.14, sin warnings)

USO:
    python3 fundamentals.py
"""

import os
import sys
import time
import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd


# ═══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════

DATA_DIR              = "data"
UNIVERSE_CSV          = os.path.join(DATA_DIR, "universe.csv")
FUNDAMENTALS_CSV      = os.path.join(DATA_DIR, "fundamentals.csv")
UNIVERSE_FULL_CSV     = os.path.join(DATA_DIR, "universe_full.csv")

BATCH_SIZE            = 25
DELAY_BETWEEN_BATCHES = 1.5
SAVE_EVERY_N_BATCHES  = 4

# Sectores donde el "cash runway" NO aplica (tienen ingresos estables/
# acceso fácil al capital o están regulados)
SECTORS_NO_RUNWAY = {
    "Utilities", "Financial Services", "Financials", "Real Estate",
    "Banks", "Insurance", "Energy"  # Energy también: refinerías estables
}


# ═══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE FUNDAMENTALES
# ═══════════════════════════════════════════════════════════════════

def _safe(value, default=None):
    """Convierte yfinance values en algo serializable."""
    if value is None:
        return default
    try:
        if isinstance(value, (int, float)):
            if math.isnan(value) or math.isinf(value):
                return default
            return float(value)
        return value
    except (TypeError, ValueError):
        return default


def _now_utc_iso() -> str:
    """ISO UTC timestamp compatible con Python 3.12+/3.14 (sin deprecation)."""
    return datetime.now(timezone.utc).isoformat()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_ipo_date(info: dict) -> Optional[datetime]:
    """
    Extrae fecha de IPO probando varios campos de yfinance.
    Returns: datetime UTC o None.
    """
    # Campo 1: firstTradeDateEpochUtc (segundos)
    ts = info.get("firstTradeDateEpochUtc")
    if ts and isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass

    # Campo 2: firstTradeDateMilliseconds (milisegundos)
    ts_ms = info.get("firstTradeDateMilliseconds")
    if ts_ms and isinstance(ts_ms, (int, float)) and ts_ms > 0:
        try:
            return datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass

    # Campo 3: startDate (algunos cripto/forex)
    sd = info.get("startDate")
    if sd:
        try:
            if isinstance(sd, (int, float)) and sd > 0:
                return datetime.fromtimestamp(int(sd), tz=timezone.utc)
            elif isinstance(sd, str):
                return datetime.fromisoformat(sd.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            pass

    return None


def extract_fundamentals(ticker: str, sector: str = "",
                         is_crypto: bool = False,
                         cap_tier: str = "") -> dict:
    """
    Extrae todos los fundamentales de un ticker.
    `sector` y `cap_tier` se pasan para aplicar lógica de runway correcta.
    """
    out = {
        "ticker": ticker,
        # Valoración
        "pe_trailing":     None,
        "pe_forward":      None,
        "peg_ratio":       None,
        "price_to_book":   None,
        "price_to_sales":  None,
        # Crecimiento
        "revenue_growth":  None,
        "earnings_growth": None,
        # Salud financiera
        "debt_to_equity":  None,
        "total_cash":      None,
        "free_cashflow":   None,
        "operating_margin": None,
        "profit_margin":   None,
        "cash_runway_years": None,
        # Sentimiento
        "short_pct_float": None,
        "insider_pct":     None,
        "beta":            None,
        # Analistas
        "target_price":    None,
        "upside_pct":      None,
        "recommendation":  None,
        # IPO
        "first_trade_date": None,
        "years_since_ipo": None,
        # Earnings
        "next_earnings_date": None,
        # Meta
        "fundamentals_fetched_at": _now_utc_iso(),
        "error": None,
    }

    if is_crypto:
        out["error"] = "crypto_skipped"
        return out

    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info

        if not info or len(info) < 3:
            out["error"] = "no_info"
            return out

        # ─── Valoración ────────────────────────────────────────
        out["pe_trailing"]     = _safe(info.get("trailingPE"))
        out["pe_forward"]      = _safe(info.get("forwardPE"))
        out["peg_ratio"]       = _safe(info.get("pegRatio"))
        out["price_to_book"]   = _safe(info.get("priceToBook"))
        out["price_to_sales"]  = _safe(info.get("priceToSalesTrailing12Months"))

        # ─── Crecimiento (% YoY) ───────────────────────────────
        rg = _safe(info.get("revenueGrowth"))
        out["revenue_growth"]  = rg * 100 if rg is not None else None
        eg = _safe(info.get("earningsGrowth"))
        out["earnings_growth"] = eg * 100 if eg is not None else None

        # ─── Salud financiera ─────────────────────────────────
        out["debt_to_equity"]  = _safe(info.get("debtToEquity"))
        out["total_cash"]      = _safe(info.get("totalCash"))
        out["free_cashflow"]   = _safe(info.get("freeCashflow"))
        om = _safe(info.get("operatingMargins"))
        out["operating_margin"] = om * 100 if om is not None else None
        pm = _safe(info.get("profitMargins"))
        out["profit_margin"]    = pm * 100 if pm is not None else None

        # ─── Cash runway: SOLO para growth small/mid no-utility/finance ──
        # Solo tiene sentido para empresas que queman cash de verdad
        # NO para utilities ni bancos ni inmobiliarias
        should_calc_runway = (
            sector not in SECTORS_NO_RUNWAY
            and cap_tier in ("micro", "small", "mid")
            and out["operating_margin"] is not None
            and out["operating_margin"] < 0  # pierde dinero operativo
            and out["total_cash"] is not None
            and out["free_cashflow"] is not None
        )

        if should_calc_runway:
            if out["free_cashflow"] < 0:
                burn = abs(out["free_cashflow"])
                if burn > 0:
                    runway = round(out["total_cash"] / burn, 1)
                    # Clamp a [0, 50] para evitar valores absurdos
                    out["cash_runway_years"] = max(0, min(runway, 50))
            else:
                out["cash_runway_years"] = 999  # genera cash, no aplica

        # ─── Sentimiento ───────────────────────────────────────
        spf = _safe(info.get("shortPercentOfFloat"))
        out["short_pct_float"] = spf * 100 if spf is not None else None
        ip = _safe(info.get("heldPercentInsiders"))
        out["insider_pct"]     = ip * 100 if ip is not None else None
        out["beta"]            = _safe(info.get("beta"))

        # ─── Analistas ─────────────────────────────────────────
        tp = _safe(info.get("targetMeanPrice"))
        out["target_price"]    = tp
        current_price          = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        if tp and current_price and current_price > 0:
            out["upside_pct"] = round(((tp - current_price) / current_price) * 100, 1)
        out["recommendation"]  = info.get("recommendationKey", None)

        # ─── IPO (con campos múltiples) ────────────────────────
        ipo_date = _extract_ipo_date(info)
        if ipo_date:
            out["first_trade_date"] = ipo_date.strftime("%Y-%m-%d")
            years = (_now_utc() - ipo_date).days / 365.25
            out["years_since_ipo"] = round(years, 1)

        # ─── Earnings ──────────────────────────────────────────
        ed = info.get("earningsDate") or info.get("earningsTimestamp")
        if ed:
            try:
                if isinstance(ed, (int, float)):
                    out["next_earnings_date"] = datetime.fromtimestamp(
                        int(ed), tz=timezone.utc).strftime("%Y-%m-%d")
                elif isinstance(ed, list) and len(ed) > 0:
                    out["next_earnings_date"] = str(ed[0])[:10]
                else:
                    out["next_earnings_date"] = str(ed)[:10]
            except Exception:
                pass

        return out

    except Exception as e:
        out["error"] = str(e)[:100]
        return out


# ═══════════════════════════════════════════════════════════════════
# PROCESO EN BATCHES (resume)
# ═══════════════════════════════════════════════════════════════════

def _save_progress(rows: list[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(FUNDAMENTALS_CSV, index=False)


def _load_existing() -> dict:
    if not os.path.exists(FUNDAMENTALS_CSV):
        return {}
    try:
        df = pd.read_csv(FUNDAMENTALS_CSV)
        result = {}
        for _, row in df.iterrows():
            d = row.to_dict()
            for k, v in d.items():
                if isinstance(v, float) and math.isnan(v):
                    d[k] = None
            result[d["ticker"]] = d
        return result
    except Exception as e:
        print(f"⚠️  No se pudo cargar progreso previo: {e}")
        return {}


def fetch_all_fundamentals(tickers_df: pd.DataFrame,
                            batch_size: int = BATCH_SIZE,
                            delay: float = DELAY_BETWEEN_BATCHES,
                            save_every: int = SAVE_EVERY_N_BATCHES,
                            resume: bool = True,
                            force_refresh: bool = False) -> list[dict]:
    """
    Recorre el CSV de universo y enriquece con fundamentales.
    force_refresh=True ignora progreso anterior (útil tras bugfix).
    """
    existing = _load_existing() if (resume and not force_refresh) else {}
    if existing and not force_refresh:
        print(f"📂 Encontrado progreso anterior: {len(existing)} tickers ya procesados")
    if force_refresh:
        print(f"🔄 Modo force_refresh: re-procesando TODO")

    all_results = []
    to_process = []

    for _, row in tickers_df.iterrows():
        ticker = row["ticker"]
        if not force_refresh and ticker in existing and existing[ticker].get("error") in (None, "no_info", "crypto_skipped"):
            all_results.append(existing[ticker])
        else:
            is_crypto = bool(row.get("is_crypto", False))
            sector = str(row.get("sector", "")) if not pd.isna(row.get("sector", "")) else ""
            cap_tier = str(row.get("cap_tier", "")) if not pd.isna(row.get("cap_tier", "")) else ""
            to_process.append((ticker, sector, is_crypto, cap_tier))

    print(f"\n📊 Procesando {len(to_process)} tickers nuevos...")
    if not to_process:
        print("   ✅ Todos los tickers ya estaban procesados")
        return all_results

    eta_min = (len(to_process) / batch_size) * (delay + 4) / 60
    print(f"   Batch size: {batch_size}, delay: {delay}s")
    print(f"   Tiempo estimado: ~{eta_min:.0f} min\n")

    total_batches = (len(to_process) + batch_size - 1) // batch_size
    batch_count = 0
    errors_count = 0
    start_time = time.time()

    for i in range(0, len(to_process), batch_size):
        batch = to_process[i:i + batch_size]
        batch_count += 1

        elapsed = time.time() - start_time
        eta = (elapsed / max(i, 1)) * (len(to_process) - i) / 60 if i > 0 else eta_min
        pct = (i + len(batch)) / len(to_process) * 100
        print(f"   [{batch_count}/{total_batches}] {i+1}-{min(i+batch_size, len(to_process))} de {len(to_process)} — {pct:.1f}% (ETA {eta:.1f}min)")

        for ticker, sector, is_crypto, cap_tier in batch:
            try:
                fund = extract_fundamentals(ticker, sector=sector,
                                             is_crypto=is_crypto,
                                             cap_tier=cap_tier)
                if fund.get("error") and fund["error"] not in ("crypto_skipped", "no_info"):
                    errors_count += 1
                    if errors_count % 25 == 1:
                        print(f"      ⚠️  Error en {ticker}: {fund['error'][:60]}")
                all_results.append(fund)
            except KeyboardInterrupt:
                print("\n⛔ Interrumpido. Guardando progreso...")
                _save_progress(all_results)
                sys.exit(0)

        if batch_count % save_every == 0:
            _save_progress(all_results)
            print(f"      💾 Progreso guardado")

        if i + batch_size < len(to_process):
            time.sleep(delay)

    _save_progress(all_results)
    print(f"\n✅ Enriquecimiento completo")
    print(f"   Total procesados: {len(all_results)}")
    print(f"   Errores: {errors_count}")
    return all_results


# ═══════════════════════════════════════════════════════════════════
# MERGE
# ═══════════════════════════════════════════════════════════════════

def merge_universe_and_fundamentals():
    if not os.path.exists(UNIVERSE_CSV):
        print(f"❌ No existe {UNIVERSE_CSV}")
        return None
    if not os.path.exists(FUNDAMENTALS_CSV):
        print(f"❌ No existe {FUNDAMENTALS_CSV}")
        return None

    universe_df = pd.read_csv(UNIVERSE_CSV)
    fund_df = pd.read_csv(FUNDAMENTALS_CSV)
    merged = universe_df.merge(fund_df, on="ticker", how="left",
                                suffixes=("", "_fund"))
    merged.to_csv(UNIVERSE_FULL_CSV, index=False)
    print(f"\n💾 Universo completo guardado en {UNIVERSE_FULL_CSV}")
    print(f"   {len(merged)} tickers, {len(merged.columns)} columnas")
    return merged


# ═══════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════

def summarize_fundamentals(df: pd.DataFrame):
    print(f"\n{'═' * 60}")
    print(f"  RESUMEN DE FUNDAMENTALES")
    print(f"{'═' * 60}\n")

    print(f"📊 Total tickers: {len(df)}")

    print("\n📋 Cobertura por dato:")
    fields = [
        ("PER trailing", "pe_trailing"),
        ("PER forward", "pe_forward"),
        ("Revenue growth", "revenue_growth"),
        ("Debt/Equity", "debt_to_equity"),
        ("Short % float", "short_pct_float"),
        ("Insider %", "insider_pct"),
        ("Beta", "beta"),
        ("Target price", "target_price"),
        ("Years since IPO", "years_since_ipo"),
        ("Operating margin", "operating_margin"),
    ]
    for label, col in fields:
        if col in df.columns:
            coverage = df[col].notna().sum()
            pct = coverage / len(df) * 100
            print(f"   {label:20s}: {coverage:>4} ({pct:5.1f}%)")

    print("\n🎯 Hallazgos de tu universo:")

    if "upside_pct" in df.columns:
        top_upside = df.nlargest(5, "upside_pct")[["ticker", "upside_pct"]].dropna()
        if len(top_upside):
            print("\n   📈 Top 5 mayor upside vs analistas:")
            for _, r in top_upside.iterrows():
                print(f"      {r['ticker']:6s}  +{r['upside_pct']:.0f}%")

    if "short_pct_float" in df.columns:
        top_short = df.nlargest(5, "short_pct_float")[["ticker", "short_pct_float"]].dropna()
        if len(top_short):
            print("\n   🔥 Top 5 short interest (squeeze potencial):")
            for _, r in top_short.iterrows():
                print(f"      {r['ticker']:6s}  {r['short_pct_float']:.1f}% float en corto")

    if "years_since_ipo" in df.columns:
        recent_ipos = df[(df["years_since_ipo"] >= 1) &
                         (df["years_since_ipo"] <= 5)]
        recent_ipos = recent_ipos.nsmallest(10, "years_since_ipo")[["ticker", "years_since_ipo"]]
        if len(recent_ipos):
            print("\n   🆕 IPOs recientes (1-5 años, target Carvana pattern):")
            for _, r in recent_ipos.iterrows():
                print(f"      {r['ticker']:6s}  {r['years_since_ipo']:.1f} años")

    if "cash_runway_years" in df.columns:
        burning = df[(df["cash_runway_years"] > 0) &
                     (df["cash_runway_years"] < 5) &
                     (df["cash_runway_years"] != 999)]
        burning = burning.nsmallest(5, "cash_runway_years")[["ticker", "cash_runway_years"]]
        if len(burning):
            print("\n   ⚠️  Top 5 cash runway bajo (growth small/mid, riesgo real):")
            for _, r in burning.iterrows():
                print(f"      {r['ticker']:6s}  {r['cash_runway_years']:.1f} años")

    # NUEVO: PER bajo (value plays)
    if "pe_trailing" in df.columns:
        cheap = df[(df["pe_trailing"] > 0) & (df["pe_trailing"] < 15)]
        cheap = cheap.nsmallest(5, "pe_trailing")[["ticker", "pe_trailing"]]
        if len(cheap):
            print("\n   💰 Top 5 PER más bajo (value plays):")
            for _, r in cheap.iterrows():
                print(f"      {r['ticker']:6s}  PER {r['pe_trailing']:.1f}")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  CB SCANNER — Enriquecimiento Fundamentales v2")
    print("═" * 60 + "\n")

    if not os.path.exists(UNIVERSE_CSV):
        print(f"❌ No existe {UNIVERSE_CSV}")
        print("   Ejecuta primero: python3 universe.py")
        sys.exit(1)

    # IMPORTANTE: --force para re-procesar todo (tras bugfix)
    force = "--force" in sys.argv

    print(f"📂 Cargando {UNIVERSE_CSV}...")
    universe_df = pd.read_csv(UNIVERSE_CSV)
    print(f"   ✅ {len(universe_df)} tickers")

    if force:
        print("\n🔄 Modo force_refresh: re-procesando todo desde cero")

    results = fetch_all_fundamentals(universe_df, force_refresh=force)

    fund_df = pd.read_csv(FUNDAMENTALS_CSV)
    summarize_fundamentals(fund_df)
    merge_universe_and_fundamentals()

    print(f"\n{'═' * 60}")
    print("  ✅ COMPLETADO")
    print(f"{'═' * 60}\n")
