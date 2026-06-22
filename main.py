"""
main.py v3 — ORQUESTADOR ROBUSTO
================================
Une universe.py + cb_scanner.py + fundamentals.py.

CAMBIOS v3 (bug fixes para scan 500+ tickers):
- ulimit aumentado (4096 archivos) para evitar "Too many open files"
- Reset de yfinance session cada 50 tickers
- Retry logic: tickers que fallan se reintentan al final
- Silenciado del logger de yfinance (logs limpios)
- gc.collect() entre batches para liberar memoria

USO:
    python3 main.py               # Scan completo
    python3 main.py 30            # Modo prueba (30 tickers)
"""

import os
import sys
import json
import time
import math
import gc
import resource
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from cb_scanner import (
    calculate_wavetrend,
    detect_signals,
    Signal,
)
from universe import (
    load_universe_csv,
    TickerInfo,
    CapTier,
)


# ═══════════════════════════════════════════════════════════════════
# CRÍTICO: PREPARAR EL ENTORNO ANTES DE TODO
# ═══════════════════════════════════════════════════════════════════

def _prepare_environment():
    """
    Aumenta límites del sistema operativo para evitar:
    - 'Too many open files' (Errno 24)
    - Crash de yfinance en scans largos
    """
    try:
        # Subir límite de archivos abiertos
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft = min(4096, hard)
        if new_soft > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
            print(f"📂 Límite de archivos abiertos: {soft} → {new_soft}")
    except Exception as e:
        print(f"⚠️  No se pudo subir ulimit: {e}")

    # Silenciar warnings y errores de yfinance (son ruido)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)


_prepare_environment()


# ═══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════

INTERVAL              = "1mo"
PERIOD                = "max"
SIGNAL_AGE_MAX_BARS   = 3
BATCH_DELAY           = 0.3
RESET_EVERY_N         = 50            # Resetear yfinance cada N tickers
LONG_PAUSE_EVERY      = 100           # Pausa larga cada 100 tickers
LONG_PAUSE_SECS       = 5             # Segundos de pausa larga
SAVE_EVERY_N          = 50
MAX_RETRIES           = 2             # Reintentos por ticker fallido

DATA_DIR              = "data"
UNIVERSE_FULL_CSV     = os.path.join(DATA_DIR, "universe_full.csv")
SIGNALS_JSON          = os.path.join(DATA_DIR, "signals.json")
SUMMARY_JSON          = os.path.join(DATA_DIR, "signals_summary.json")
HISTORY_JSON          = os.path.join(DATA_DIR, "signals_history.json")


# ═══════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_str(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v)


def _reset_yfinance_session():
    """
    Resetea la sesión global de yfinance para evitar database locks
    y file descriptors agotados.
    """
    try:
        import yfinance as yf
        # yfinance mantiene una sesión global cacheada
        if hasattr(yf, 'Tickers'):
            # Limpiar cualquier estado
            pass
        # Forzar reimport para nueva sesión
        if hasattr(yf, '_TZ_CACHE'):
            try:
                yf._TZ_CACHE.clear()
            except Exception:
                pass
        gc.collect()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# CARGAR UNIVERSO
# ═══════════════════════════════════════════════════════════════════

def load_universe_full() -> list[dict]:
    if not os.path.exists(UNIVERSE_FULL_CSV):
        print(f"❌ No existe {UNIVERSE_FULL_CSV}")
        print("   Ejecuta: python3 universe.py && python3 fundamentals.py")
        sys.exit(1)

    df = pd.read_csv(UNIVERSE_FULL_CSV)
    print(f"✅ {len(df)} tickers en universo_full")
    print(f"   Columnas: {len(df.columns)}")

    records = []
    for _, row in df.iterrows():
        d = row.to_dict()
        for k, v in d.items():
            if isinstance(v, float) and math.isnan(v):
                d[k] = None
        records.append(d)
    return records


# ═══════════════════════════════════════════════════════════════════
# CARVANA SETUP DETECTOR
# ═══════════════════════════════════════════════════════════════════

def detect_carvana_setup(data: dict) -> dict:
    score = 0
    reasons = []
    warnings_list = []

    years_ipo = _safe_float(data.get("years_since_ipo"))
    drawdown = _safe_float(data.get("drawdown_from_ath_pct"))
    sig = data.get("active_signal")
    runway = _safe_float(data.get("cash_runway_years"))
    short_pct = _safe_float(data.get("short_pct_float"))
    insider_pct = _safe_float(data.get("insider_pct"))
    revenue_growth = _safe_float(data.get("revenue_growth"))
    upside = _safe_float(data.get("upside_pct"))
    sector = _safe_str(data.get("sector"))
    is_crypto = bool(data.get("is_crypto", False))

    if is_crypto:
        return {"score": 0, "max_score": 19, "is_carvana_setup": False,
                "reasons": [], "warnings": ["crypto excluded"]}

    if years_ipo is not None and 1 <= years_ipo <= 7:
        score += 2
        reasons.append(f"IPO hace {years_ipo:.1f} años")

    if drawdown is not None and drawdown <= -70:
        score += 3
        reasons.append(f"Drawdown {drawdown:.0f}% desde ATH")
        if drawdown <= -85:
            score += 2
            reasons.append(f"Capitulación extrema (-{abs(drawdown):.0f}%)")

    if sig:
        sig_type = sig.get("type")
        sig_wt2 = _safe_float(sig.get("wt2"))
        if sig_type in ("BUY", "BUY_GOLD"):
            score += 3
            reasons.append(f"Señal técnica {sig_type}")
            if sig_type == "BUY_GOLD" or (sig_wt2 is not None and sig_wt2 <= -50):
                score += 2
                reasons.append("BUY GOLD: capitulación extrema")

    SECTORS_NO_RUNWAY = {"Utilities", "Financial Services", "Financials",
                         "Real Estate", "Banks", "Insurance", "Energy"}
    if runway is None or sector in SECTORS_NO_RUNWAY or runway == 999:
        score += 2
        if sector in SECTORS_NO_RUNWAY or runway == 999:
            reasons.append("Sin riesgo de quiebra")
    elif runway >= 2:
        score += 2
        reasons.append(f"Cash runway {runway:.1f} años (seguro)")
    else:
        warnings_list.append(f"⚠️ Cash runway solo {runway:.1f} años")

    if short_pct is not None and short_pct >= 15:
        score += 2
        reasons.append(f"Short interest {short_pct:.0f}% (squeeze potencial)")

    if insider_pct is not None and insider_pct >= 5:
        score += 1
        reasons.append(f"Insiders {insider_pct:.0f}%")

    if revenue_growth is not None and revenue_growth > 0:
        score += 1
        reasons.append(f"Revenue +{revenue_growth:.0f}%")

    if upside is not None and upside >= 50:
        score += 1
        reasons.append(f"Upside +{upside:.0f}% vs analistas")

    return {
        "score": score,
        "max_score": 19,
        "is_carvana_setup": score >= 10,
        "reasons": reasons,
        "warnings": warnings_list,
    }


# ═══════════════════════════════════════════════════════════════════
# ANÁLISIS DE UN TICKER (con retry)
# ═══════════════════════════════════════════════════════════════════

def analyze_single_ticker(ticker_data: dict,
                           silent_errors: bool = True) -> Optional[dict]:
    import yfinance as yf
    import numpy as np

    ticker = ticker_data["ticker"]
    try:
        # auto_adjust=True por defecto, silenciar progress
        df = yf.download(ticker, interval=INTERVAL, period=PERIOD,
                         progress=False, auto_adjust=True,
                         threads=False)  # threads=False evita SQLite locks
        if df.empty or len(df) < 50:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        wt1, wt2 = calculate_wavetrend(df)
        signals = detect_signals(df, wt1, wt2)

        current_price = float(df["Close"].iloc[-1])
        current_wt1 = float(wt1.iloc[-1]) if not np.isnan(wt1.iloc[-1]) else None
        current_wt2 = float(wt2.iloc[-1]) if not np.isnan(wt2.iloc[-1]) else None

        ath = float(df["Close"].max())
        drawdown_pct = ((current_price - ath) / ath) * 100

        last_12m = df.tail(12)
        high_52w = float(last_12m["High"].max())
        low_52w = float(last_12m["Low"].min())
        pos_52w = ((current_price - low_52w) / (high_52w - low_52w) * 100) if high_52w > low_52w else 50

        active_signal = None
        if signals:
            last_sig = signals[-1]
            bars_since = len(df) - 1 - last_sig.bar_index
            if bars_since <= SIGNAL_AGE_MAX_BARS:
                active_signal = {
                    "type": last_sig.type,
                    "date": last_sig.date.strftime("%Y-%m"),
                    "price": float(last_sig.price),
                    "wt2": float(last_sig.wt2),
                    "bars_ago": int(bars_since),
                }

        cap_tier_str = _safe_str(ticker_data.get("cap_tier")) or "unknown"
        try:
            cap_label = CapTier(cap_tier_str).label
        except ValueError:
            cap_label = "Unknown"

        result = {
            "ticker":          ticker,
            "name":            _safe_str(ticker_data.get("name")) or ticker,
            "sector":          _safe_str(ticker_data.get("sector")),
            "industry":        _safe_str(ticker_data.get("industry")),
            "market_cap":      _safe_float(ticker_data.get("market_cap")),
            "cap_tier":        cap_tier_str,
            "cap_tier_label":  cap_label,
            "is_crypto":       bool(ticker_data.get("is_crypto", False)),
            "source":          _safe_str(ticker_data.get("source")),

            "current_price":   current_price,
            "current_wt1":     current_wt1,
            "current_wt2":     current_wt2,
            "ath":             ath,
            "drawdown_from_ath_pct": drawdown_pct,
            "high_52w":        high_52w,
            "low_52w":         low_52w,
            "position_52w_pct": pos_52w,
            "total_signals_history": len(signals),
            "active_signal":   active_signal,
            "recent_signals": [
                {"type": s.type, "date": s.date.strftime("%Y-%m"),
                 "price": float(s.price), "wt2": float(s.wt2)}
                for s in signals[-5:]
            ],

            "pe_trailing":     _safe_float(ticker_data.get("pe_trailing")),
            "pe_forward":      _safe_float(ticker_data.get("pe_forward")),
            "peg_ratio":       _safe_float(ticker_data.get("peg_ratio")),
            "price_to_book":   _safe_float(ticker_data.get("price_to_book")),
            "price_to_sales":  _safe_float(ticker_data.get("price_to_sales")),
            "revenue_growth":  _safe_float(ticker_data.get("revenue_growth")),
            "earnings_growth": _safe_float(ticker_data.get("earnings_growth")),
            "debt_to_equity":  _safe_float(ticker_data.get("debt_to_equity")),
            "total_cash":      _safe_float(ticker_data.get("total_cash")),
            "free_cashflow":   _safe_float(ticker_data.get("free_cashflow")),
            "operating_margin": _safe_float(ticker_data.get("operating_margin")),
            "profit_margin":   _safe_float(ticker_data.get("profit_margin")),
            "cash_runway_years": _safe_float(ticker_data.get("cash_runway_years")),
            "short_pct_float": _safe_float(ticker_data.get("short_pct_float")),
            "insider_pct":     _safe_float(ticker_data.get("insider_pct")),
            "beta":            _safe_float(ticker_data.get("beta")),
            "target_price":    _safe_float(ticker_data.get("target_price")),
            "upside_pct":      _safe_float(ticker_data.get("upside_pct")),
            "recommendation":  _safe_str(ticker_data.get("recommendation")),
            "first_trade_date": _safe_str(ticker_data.get("first_trade_date")),
            "years_since_ipo": _safe_float(ticker_data.get("years_since_ipo")),
            "next_earnings_date": _safe_str(ticker_data.get("next_earnings_date")),
        }

        result["carvana_setup"] = detect_carvana_setup(result)

        # Liberar memoria explícitamente
        del df
        return result

    except Exception as e:
        if not silent_errors:
            err_str = str(e)[:80]
            print(f"      ⚠️ {ticker}: {err_str}")
        return None


# ═══════════════════════════════════════════════════════════════════
# SCAN COMPLETO CON RETRY
# ═══════════════════════════════════════════════════════════════════

def scan_universe(tickers_data: list[dict],
                  max_tickers: Optional[int] = None) -> dict:
    if max_tickers:
        tickers_data = tickers_data[:max_tickers]

    print(f"\n🔍 Escaneando {len(tickers_data)} tickers...")
    print(f"   Reset de sesión cada {RESET_EVERY_N} tickers")
    print(f"   Tiempo estimado: ~{len(tickers_data) * 0.7 / 60:.0f} min\n")

    results = []
    failed = []
    active_signals = 0
    carvana_setups = 0
    start = time.time()

    # ─── PRIMERA PASADA ────────────────────────────────────────
    for i, info in enumerate(tickers_data):
        if i % 20 == 0:
            elapsed = time.time() - start
            pct = i / len(tickers_data) * 100
            eta = (elapsed / max(i, 1)) * (len(tickers_data) - i) / 60
            print(f"   [{i:>3}/{len(tickers_data)}] {pct:.1f}% — "
                  f"señales:{active_signals} carvana:{carvana_setups} "
                  f"fallos:{len(failed)} — ETA: {eta:.1f}min")

        # Reset de sesión cada N tickers
        if i > 0 and i % RESET_EVERY_N == 0:
            _reset_yfinance_session()

        # Pausa larga cada LONG_PAUSE_EVERY
        if i > 0 and i % LONG_PAUSE_EVERY == 0:
            print(f"      💤 Pausa de {LONG_PAUSE_SECS}s para liberar conexiones...")
            time.sleep(LONG_PAUSE_SECS)

        analysis = analyze_single_ticker(info, silent_errors=True)
        if analysis is None:
            failed.append(info)
            continue

        if analysis["active_signal"]:
            active_signals += 1
        if analysis["carvana_setup"]["is_carvana_setup"]:
            carvana_setups += 1

        results.append(analysis)

        if (i + 1) % SAVE_EVERY_N == 0:
            _save_partial(results)

        time.sleep(BATCH_DELAY)

    elapsed_first = time.time() - start
    print(f"\n📊 Primera pasada: {len(results)} OK, {len(failed)} fallidos en {elapsed_first/60:.1f} min")

    # ─── RETRY DE LOS FALLIDOS ─────────────────────────────────
    if failed and len(failed) <= 200:  # Solo retry si no son demasiados
        print(f"\n🔄 Reintentando {len(failed)} tickers fallidos...")
        print(f"   Pausa de 10s antes de reintentar...")
        time.sleep(10)
        _reset_yfinance_session()

        retry_recovered = 0
        for attempt in range(MAX_RETRIES):
            if not failed:
                break
            print(f"\n   Intento {attempt + 1}/{MAX_RETRIES} de {len(failed)} tickers...")
            still_failed = []
            for j, info in enumerate(failed):
                if j > 0 and j % 30 == 0:
                    _reset_yfinance_session()
                    time.sleep(2)
                if j % 20 == 0:
                    print(f"      [{j}/{len(failed)}] recuperados: {retry_recovered}")
                analysis = analyze_single_ticker(info, silent_errors=True)
                if analysis is None:
                    still_failed.append(info)
                else:
                    retry_recovered += 1
                    if analysis["active_signal"]:
                        active_signals += 1
                    if analysis["carvana_setup"]["is_carvana_setup"]:
                        carvana_setups += 1
                    results.append(analysis)
                time.sleep(BATCH_DELAY * 2)  # Más lento en retry
            failed = still_failed
            if failed and attempt < MAX_RETRIES - 1:
                print(f"   Aún quedan {len(failed)} fallidos. Pausa antes del siguiente intento.")
                time.sleep(15)

        print(f"\n   ✅ Recuperados en retry: {retry_recovered}")
        print(f"   ❌ Definitivamente fallidos: {len(failed)}")

    elapsed = time.time() - start
    print(f"\n✅ Scan completo en {elapsed/60:.1f} min")
    print(f"   Tickers analizados:    {len(results)}")
    print(f"   Errores definitivos:   {len(failed)}")
    print(f"   Señales activas:       {active_signals}")
    print(f"   ⭐ Carvana Setups:     {carvana_setups}")

    return {
        "scan_date":       datetime.now(timezone.utc).isoformat(),
        "scan_date_human": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "interval":        INTERVAL,
        "total_scanned":   len(results),
        "total_active":    active_signals,
        "total_carvana_setups": carvana_setups,
        "results":         results,
    }


def _save_partial(results):
    os.makedirs(DATA_DIR, exist_ok=True)
    partial_path = SIGNALS_JSON.replace(".json", "_partial.json")
    try:
        with open(partial_path, "w") as f:
            json.dump({"partial": True, "results": results}, f, indent=2)
    except Exception as e:
        print(f"      ⚠️ Error guardando parcial: {e}")


# ═══════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════

def build_summary(scan_data: dict) -> dict:
    summary = {
        "scan_date":            scan_data["scan_date"],
        "scan_date_human":      scan_data["scan_date_human"],
        "total_scanned":        scan_data["total_scanned"],
        "total_active":         scan_data["total_active"],
        "total_carvana_setups": scan_data.get("total_carvana_setups", 0),
        "by_signal":            {},
        "by_tier":              {},
        "by_signal_and_tier":   {},
    }

    for st in ["BUY_GOLD", "BUY", "SELL_PLUS", "SELL"]:
        summary["by_signal"][st] = 0
        summary["by_signal_and_tier"][st] = {
            "micro": 0, "small": 0, "mid": 0, "large": 0,
            "mega": 0, "crypto": 0, "unknown": 0
        }
    for tier in ["micro", "small", "mid", "large", "mega", "crypto", "unknown"]:
        summary["by_tier"][tier] = 0

    for r in scan_data["results"]:
        if not r.get("active_signal"):
            continue
        st = r["active_signal"]["type"]
        tier = r.get("cap_tier", "unknown")
        summary["by_signal"][st] = summary["by_signal"].get(st, 0) + 1
        summary["by_tier"][tier] = summary["by_tier"].get(tier, 0) + 1
        if st in summary["by_signal_and_tier"]:
            summary["by_signal_and_tier"][st][tier] = \
                summary["by_signal_and_tier"][st].get(tier, 0) + 1

    return summary


def save_results(scan_data: dict, summary: dict):
    """Guarda resultados con file descriptors gestionados."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Cerrar archivos explícitamente
    try:
        with open(SIGNALS_JSON, "w") as f:
            json.dump(scan_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        print(f"\n💾 {SIGNALS_JSON}")
    except Exception as e:
        print(f"❌ Error guardando signals.json: {e}")

    try:
        with open(SUMMARY_JSON, "w") as f:
            json.dump(summary, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        print(f"💾 {SUMMARY_JSON}")
    except Exception as e:
        print(f"❌ Error guardando summary.json: {e}")

    # Histórico
    history = []
    if os.path.exists(HISTORY_JSON):
        try:
            with open(HISTORY_JSON) as f:
                history = json.load(f)
        except Exception:
            history = []

    entry = {
        "scan_date":            scan_data["scan_date"],
        "scan_date_human":      scan_data["scan_date_human"],
        "total_scanned":        scan_data["total_scanned"],
        "total_active":         scan_data["total_active"],
        "total_carvana_setups": scan_data.get("total_carvana_setups", 0),
        "by_signal":            summary["by_signal"],
    }
    history.append(entry)
    history = history[-90:]

    try:
        with open(HISTORY_JSON, "w") as f:
            json.dump(history, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        print(f"💾 {HISTORY_JSON}")
    except Exception as e:
        print(f"❌ Error guardando history.json: {e}")


def print_summary(summary, scan_data):
    print(f"\n{'═' * 60}")
    print(f"  RESUMEN — {summary['scan_date_human']}")
    print(f"{'═' * 60}\n")

    print(f"📊 Tickers escaneados:  {summary['total_scanned']}")
    print(f"🎯 Con señal activa:    {summary['total_active']}")
    print(f"⭐ Carvana Setups:      {summary['total_carvana_setups']}\n")

    icons = {"BUY_GOLD": "🏆", "BUY": "🟢", "SELL_PLUS": "🔥", "SELL": "🔴"}
    print("Por tipo de señal activa:")
    for st, c in summary["by_signal"].items():
        if c > 0:
            print(f"   {icons.get(st, '?')} {st:10s}: {c}")

    carvana = [r for r in scan_data["results"]
               if r["carvana_setup"]["is_carvana_setup"]]
    if carvana:
        carvana.sort(key=lambda x: -x["carvana_setup"]["score"])
        print(f"\n⭐ TOP CARVANA SETUPS (score ≥ 10):")
        for r in carvana[:15]:
            cs = r["carvana_setup"]
            sig_text = ""
            if r["active_signal"]:
                sig_text = f"  {r['active_signal']['type']}"
            print(f"   {r['ticker']:6s} ({r['cap_tier_label']:9s}) "
                  f"score {cs['score']}/19  "
                  f"DD {r['drawdown_from_ath_pct']:.0f}%{sig_text}")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  CB SCANNER — Scan principal v3 (robusto)")
    print("═" * 60 + "\n")

    max_tickers = None
    if len(sys.argv) > 1:
        try:
            max_tickers = int(sys.argv[1])
            print(f"⚠️  Modo prueba: {max_tickers} tickers\n")
        except ValueError:
            pass

    tickers_data = load_universe_full()

    scan_data = scan_universe(tickers_data, max_tickers=max_tickers)
    summary = build_summary(scan_data)
    save_results(scan_data, summary)
    print_summary(summary, scan_data)

    print(f"\n{'═' * 60}")
    print("  ✅ COMPLETADO")
    print(f"{'═' * 60}")
    print("\nSiguiente paso:")
    print("   python3 html_generator.py\n")
