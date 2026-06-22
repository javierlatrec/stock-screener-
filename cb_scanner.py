"""
cb_scanner.py
============
Implementación Python del sistema CB Buy v1 + CB Sell v1.
Idéntica lógica a los indicadores Pine Script validados en TradingView.

FASE 1: Validación de lógica contra TradingView.

Uso:
    from cb_scanner import analyze_ticker

    result = analyze_ticker("BTC-USD", interval="1mo")
    print(result)
"""

import numpy as np
import pandas as pd
import yfinance as yf
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# PARÁMETROS — IDÉNTICOS A CB Buy v1 / CB Sell v1
# ═══════════════════════════════════════════════════════════════════

# WaveTrend (LazyBear)
WT_CHANNEL_LENGTH = 10
WT_AVERAGE_LENGTH = 21
WT_SIGNAL_SMOOTH  = 3  # default v14.2 (LazyBear original es 4)

# Niveles
OB_LEVEL_EXTREME = 60
OB_LEVEL_NORMAL  = 53
OS_LEVEL_EXTREME = -60
OS_LEVEL_NORMAL  = -53

# BUY Thresholds
BUY_THRESHOLD      = 0     # wt2 ≤ 0 para BUY
BUY_GOLD_THRESHOLD = -50   # wt2 ≤ -50 para BUY GOLD

# SELL Thresholds (CB Sell v1)
SELL_THRESHOLD = 60  # wt2 ≥ 60 para SELL

# Divergencia bajista (SELL+)
DIV_PIVOT_PERIOD  = 5
DIV_MAX_BARS      = 120
DIV_MIN_BARS      = 6
MAX_PIVOTS_CHECK  = 8
MIN_PRIOR_PIVOT_OB = 53  # solo pivots en OB cuentan para divergencia

# SELL window
SELL_WINDOW = 6

# Cooldown
COOLDOWN_BARS = 6


# ═══════════════════════════════════════════════════════════════════
# CÁLCULO DEL WAVETREND (LazyBear) — IDÉNTICO A PINE SCRIPT
# ═══════════════════════════════════════════════════════════════════

def ema(series: pd.Series, length: int) -> pd.Series:
    """EMA igual que ta.ema() de Pine: alpha = 2/(length+1)."""
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    """SMA igual que ta.sma()."""
    return series.rolling(window=length).mean()


def calculate_wavetrend(df: pd.DataFrame,
                        n1: int = WT_CHANNEL_LENGTH,
                        n2: int = WT_AVERAGE_LENGTH,
                        nSmooth: int = WT_SIGNAL_SMOOTH) -> tuple[pd.Series, pd.Series]:
    """
    Calcula WaveTrend con la fórmula exacta de LazyBear:

        ap  = hlc3
        esa = ema(ap, n1)
        d   = ema(abs(ap - esa), n1)
        ci  = (ap - esa) / (0.015 * d)
        tci = ema(ci, n2)
        wt1 = tci
        wt2 = sma(wt1, nSmooth)

    Returns: (wt1, wt2) como Series.
    """
    ap  = (df["High"] + df["Low"] + df["Close"]) / 3
    esa = ema(ap, n1)
    d   = ema((ap - esa).abs(), n1)
    # Evitar división por cero (cuando el activo no tiene volatilidad)
    d_safe = d.replace(0, np.nan)
    ci  = (ap - esa) / (0.015 * d_safe)
    tci = ema(ci, n2)
    wt1 = tci
    wt2 = sma(wt1, nSmooth)
    return wt1, wt2


# ═══════════════════════════════════════════════════════════════════
# DETECCIÓN DE CRUCES
# ═══════════════════════════════════════════════════════════════════

def detect_crossovers(wt1: pd.Series, wt2: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Devuelve (cross_up, cross_down) booleans en cada barra."""
    diff = wt1 - wt2
    diff_prev = diff.shift(1)
    cross_up  = (diff > 0) & (diff_prev <= 0)
    cross_dn  = (diff < 0) & (diff_prev >= 0)
    return cross_up.fillna(False), cross_dn.fillna(False)


# ═══════════════════════════════════════════════════════════════════
# DETECCIÓN DE PIVOTS DEL WT2 (para divergencias)
# ═══════════════════════════════════════════════════════════════════

def find_pivot_highs(series: pd.Series, left: int = DIV_PIVOT_PERIOD,
                     right: int = DIV_PIVOT_PERIOD) -> list[tuple[int, float]]:
    """
    Encuentra pivots altos igual que ta.pivothigh() de Pine.
    Un pivot en index i requiere que series[i] sea mayor que las `left` barras anteriores
    y mayor que las `right` barras posteriores.

    Returns: lista de (index_pos, value) de pivots.
    """
    pivots = []
    arr = series.values
    n = len(arr)
    for i in range(left, n - right):
        if np.isnan(arr[i]):
            continue
        left_max  = arr[i - left:i].max() if left > 0 else -np.inf
        right_max = arr[i + 1:i + right + 1].max() if right > 0 else -np.inf
        if arr[i] > left_max and arr[i] > right_max:
            pivots.append((i, arr[i]))
    return pivots


# ═══════════════════════════════════════════════════════════════════
# DIVERGENCIA BAJISTA DEL WT (CB Sell v1 lógica)
# ═══════════════════════════════════════════════════════════════════

def detect_bearish_divergence(df: pd.DataFrame, wt2: pd.Series,
                              max_bars: int = DIV_MAX_BARS,
                              min_bars: int = DIV_MIN_BARS,
                              max_pivots: int = MAX_PIVOTS_CHECK,
                              min_ob: float = MIN_PRIOR_PIVOT_OB) -> pd.Series:
    """
    Devuelve una Series boolean indicando si en cada barra hay divergencia bajista
    del WT contra algún pivot anterior en zona OB.

    Lógica:
    - Recoge pivots del wt2
    - En cada barra, compara wt2 actual y precio High actual contra los últimos
      `max_pivots` pivots anteriores.
    - Si encuentra un pivot anterior en OB (wt2 >= min_ob) donde:
        wt2_actual < pivot_wt  AND  high_actual > price_at_pivot
      → es divergencia bajista válida.
    """
    pivots = find_pivot_highs(wt2)
    highs = df["High"].values
    wt2_arr = wt2.values
    n = len(wt2_arr)
    div_series = np.zeros(n, dtype=bool)

    # Para cada barra del chart, mira hacia atrás
    for current_idx in range(n):
        if np.isnan(wt2_arr[current_idx]):
            continue
        current_wt = wt2_arr[current_idx]
        current_high = highs[current_idx]

        # Solo nos interesa cuando wt2 está cayendo (para evitar marcar en subidas)
        if current_idx > 0 and current_wt >= wt2_arr[current_idx - 1]:
            continue

        # Buscar pivots anteriores válidos
        pivots_before = [p for p in pivots if p[0] < current_idx]
        # Tomar los últimos `max_pivots` (más recientes primero)
        pivots_before = sorted(pivots_before, key=lambda x: x[0], reverse=True)[:max_pivots]

        for pivot_idx, pivot_wt in pivots_before:
            distance = current_idx - pivot_idx
            if distance > max_bars:
                break  # Demasiado lejos
            if distance < min_bars:
                continue  # Muy cerca
            if pivot_wt < min_ob:
                continue  # El pivot anterior no estaba en OB
            # Comprobar divergencia
            pivot_high = highs[pivot_idx]
            if current_wt < pivot_wt and current_high > pivot_high:
                div_series[current_idx] = True
                break

    return pd.Series(div_series, index=wt2.index)


# ═══════════════════════════════════════════════════════════════════
# DETECCIÓN DE SEÑALES (BUY GOLD, BUY, SELL, SELL+)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Signal:
    """Una señal detectada en una barra concreta."""
    date: pd.Timestamp
    type: str         # "BUY_GOLD", "BUY", "SELL", "SELL_PLUS"
    price: float
    wt2: float
    bar_index: int


def detect_signals(df: pd.DataFrame, wt1: pd.Series, wt2: pd.Series) -> list[Signal]:
    """
    Detecta todas las señales en el histórico aplicando la lógica de
    CB Buy v1 + CB Sell v1 con cooldown.
    """
    cross_up, cross_dn = detect_crossovers(wt1, wt2)
    div_active = detect_bearish_divergence(df, wt2)

    # Mantener "memoria" de divergencia activa durante `SELL_WINDOW` barras
    div_memory = np.zeros(len(wt2), dtype=bool)
    div_set_bar = -1
    for i in range(len(wt2)):
        if div_active.iloc[i]:
            div_set_bar = i
        if div_set_bar >= 0 and (i - div_set_bar) <= SELL_WINDOW:
            div_memory[i] = True

    signals: list[Signal] = []
    last_buy_bar = -COOLDOWN_BARS - 1
    last_sell_bar = -COOLDOWN_BARS - 1
    div_consumed_bar = -1

    for i in range(len(wt2)):
        if np.isnan(wt2.iloc[i]):
            continue

        current_wt = wt2.iloc[i]
        current_price = df["Close"].iloc[i]
        current_date = df.index[i]

        # ─── BUY GOLD: cruce alcista + wt2 ≤ -50 ───
        if cross_up.iloc[i] and current_wt <= BUY_GOLD_THRESHOLD:
            if (i - last_buy_bar) >= COOLDOWN_BARS:
                signals.append(Signal(current_date, "BUY_GOLD",
                                      current_price, current_wt, i))
                last_buy_bar = i
                continue  # No marcar también BUY si ya marcó GOLD

        # ─── BUY: cruce alcista + wt2 ≤ 0 ───
        if cross_up.iloc[i] and current_wt <= BUY_THRESHOLD:
            if (i - last_buy_bar) >= COOLDOWN_BARS:
                signals.append(Signal(current_date, "BUY",
                                      current_price, current_wt, i))
                last_buy_bar = i

        # ─── SELL+ / SELL: cruce bajista en OB ───
        if cross_dn.iloc[i]:
            wt_prev = wt2.iloc[i - 1] if i > 0 else np.nan
            wt_in_ob = (current_wt >= SELL_THRESHOLD) or (not np.isnan(wt_prev) and wt_prev >= SELL_THRESHOLD)

            if wt_in_ob and (i - last_sell_bar) >= COOLDOWN_BARS:
                # ¿Hay divergencia activa NO consumida?
                if div_memory[i] and div_consumed_bar < div_set_bar:
                    signals.append(Signal(current_date, "SELL_PLUS",
                                          current_price, current_wt, i))
                    last_sell_bar = i
                    div_consumed_bar = div_set_bar
                else:
                    signals.append(Signal(current_date, "SELL",
                                          current_price, current_wt, i))
                    last_sell_bar = i

    return signals


# ═══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL: ANALIZAR UN TICKER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TickerAnalysis:
    """Resultado completo del análisis de un ticker."""
    ticker: str
    interval: str
    current_price: float
    current_wt1: float
    current_wt2: float
    last_signal: Optional[Signal]
    all_signals: list[Signal] = field(default_factory=list)
    error: Optional[str] = None


def analyze_ticker(ticker: str, interval: str = "1mo",
                   period: str = "max") -> TickerAnalysis:
    """
    Descarga datos de yfinance y aplica CB Buy/Sell v1.

    Args:
        ticker: símbolo (ej. "BTC-USD", "TSLA", "META")
        interval: "1mo" (mensual), "1wk" (semanal), "1d" (diario)
        period: "max" para todo el histórico

    Returns:
        TickerAnalysis con todas las señales detectadas.
    """
    try:
        df = yf.download(ticker, interval=interval, period=period,
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 50:
            return TickerAnalysis(ticker=ticker, interval=interval,
                                  current_price=0.0, current_wt1=0.0,
                                  current_wt2=0.0, last_signal=None,
                                  error="No data or too few bars")

        # yfinance a veces devuelve MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        wt1, wt2 = calculate_wavetrend(df)
        signals = detect_signals(df, wt1, wt2)

        last_sig = signals[-1] if signals else None

        return TickerAnalysis(
            ticker=ticker,
            interval=interval,
            current_price=float(df["Close"].iloc[-1]),
            current_wt1=float(wt1.iloc[-1]) if not np.isnan(wt1.iloc[-1]) else 0.0,
            current_wt2=float(wt2.iloc[-1]) if not np.isnan(wt2.iloc[-1]) else 0.0,
            last_signal=last_sig,
            all_signals=signals
        )
    except Exception as e:
        return TickerAnalysis(ticker=ticker, interval=interval,
                              current_price=0.0, current_wt1=0.0,
                              current_wt2=0.0, last_signal=None,
                              error=str(e))


# ═══════════════════════════════════════════════════════════════════
# FUNCIÓN DE TEST: VALIDAR CONTRA TRADINGVIEW
# ═══════════════════════════════════════════════════════════════════

def print_analysis(analysis: TickerAnalysis, top_n: int = 20):
    """Imprime el análisis de un ticker de forma legible para validación."""
    print(f"\n{'═' * 70}")
    print(f" {analysis.ticker.upper()}  ({analysis.interval})")
    print(f"{'═' * 70}")

    if analysis.error:
        print(f"❌ Error: {analysis.error}")
        return

    print(f" Precio actual: ${analysis.current_price:,.2f}")
    print(f" wt1: {analysis.current_wt1:.2f}")
    print(f" wt2: {analysis.current_wt2:.2f}")
    print(f"\n Últimas {top_n} señales detectadas:")
    print(f" {'-' * 68}")

    if not analysis.all_signals:
        print("  (Sin señales en el histórico)")
        return

    icons = {
        "BUY_GOLD":  "🏆",
        "BUY":       "🟢",
        "SELL":      "🔴",
        "SELL_PLUS": "🔥"
    }

    for sig in analysis.all_signals[-top_n:]:
        icon = icons.get(sig.type, "?")
        date_str = sig.date.strftime("%Y-%m")
        print(f"  {icon} {date_str}  {sig.type:10s}  ${sig.price:>10,.2f}  wt2:{sig.wt2:>+6.1f}")


if __name__ == "__main__":
    # ─── TEST DE VALIDACIÓN ───
    # Estos tickers ya los validaste en TradingView con CB Buy/Sell v1.
    # Las señales detectadas aquí en Python deben coincidir.

    test_tickers = [
        "BTC-USD",   # Esperado: BUY 2018 wt:-2.5, BUY 2023 wt:-23, SELL+ 2021 múltiples, SELL+ 2025
        "TSLA",      # Esperado: BUY 2019 wt:-31, BUY 2023 wt:-19, SELL+ 2021 wt:85
        "META",      # Esperado: BUY 2023 wt:-36, SELL+ 2021 wt:72
        "NVDA",      # Esperado: BUY 2019 wt:-2, BUY 2023 wt:-1, SELL+ 2020 wt:82
        "CVS",       # Esperado: BUY GOLD 2019-2020 (wt < -50)
    ]

    for ticker in test_tickers:
        analysis = analyze_ticker(ticker, interval="1mo")
        print_analysis(analysis, top_n=15)
