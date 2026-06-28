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
# CARVANA HUNTER — PARÁMETROS (validado: 393 trades, 95 tickers, 20 años)
# ═══════════════════════════════════════════════════════════════════
# ENTRADA SEMANAL  : ASH L21 S3 WMA → BUY STRONG (+ 💎 HIGH si MFI confirma)
# ENTRADA MENSUAL  : WaveTrend BUY_GOLD (wt2 ≤ -60, wt1 cruza arriba de wt2)
# SALIDA (ambas)   : WaveTrend SELL_PLUS (wt2 ≥ 60, wt1 cruza debajo de wt2)
# Sin stop loss. Solo salida por señal.

ASH_LENGTH = 21          # Length del Absolute Strength Histogram
ASH_SMOOTH = 3           # Smooth (segunda media encadenada)
MFI_LENGTH = 60          # Money Flow Index (Market Liberator: length 60)
MFI_LOOKBACK = 3         # comparar finalMFI vs finalMFI[N] para detectar recuperación
MFI_DEEP_THRESHOLD = -10 # finalMFI por debajo = zona de capitulación
ASH_BUY_COOLDOWN = 5     # mínimo de barras entre BUY STRONG (como el Pine)

# WaveTrend específico de Carvana Hunter (umbrales distintos a CB Buy v1)
CH_BUY_GOLD_THRESHOLD = -60   # wt2 ≤ -60 para BUY_GOLD mensual
CH_SELL_PLUS_THRESHOLD = 60   # wt2 ≥ 60 para SELL_PLUS (salida)


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
# CARVANA HUNTER — ASH (Absolute Strength Histogram) + MFI
# ═══════════════════════════════════════════════════════════════════

def wma(series: pd.Series, length: int) -> pd.Series:
    """Weighted Moving Average idéntico a ta.wma() de Pine.
    Pesos lineales: la barra más reciente pesa `length`, la más antigua 1.
    fillna(0) evita que el NaN inicial (de close.diff()) contamine el doble WMA."""
    s = series.fillna(0.0)
    weights = np.arange(1, length + 1)
    wsum = weights.sum()
    return s.rolling(length).apply(
        lambda x: np.dot(x, weights) / wsum, raw=True
    )


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _ma(ma_type: str, series: pd.Series, length: int) -> pd.Series:
    """Selector de media idéntico a la función ma() del Pine."""
    if ma_type == "SMA":
        return sma(series, length)
    if ma_type == "EMA":
        return _ema(series, length)
    return wma(series, length)


def ash_signals(df: pd.DataFrame, length: int = ASH_LENGTH,
                smooth: int = ASH_SMOOTH, ma_type: str = "WMA") -> dict:
    """
    Réplica EXACTA del bloque ASH de Carvana Hunter v2 (Pine).

        ashDiff    = close - close[1]
        bulls      = 0.5 * (|ashDiff| + ashDiff)
        bears      = 0.5 * (|ashDiff| - ashDiff)
        smthBulls  = ma(ma(bulls, length), smooth)     ← doble media
        smthBears  = ma(ma(bears, length), smooth)
        difference = |smthBulls - smthBears|           ← VALOR ABSOLUTO
        ashBullish = difference > smthBears            (compradores dominan)
        ashBearish = difference > smthBulls            (vendedores dominan)
        BUY STRONG = ashBullish AND NOT ashBullish[1]  (acaba de volverse verde)

    Devuelve dict con difference, smth_bulls/bears, ash_bullish/bearish,
    buy_strong y sell_strong (todas Series).
    """
    close = df["Close"]
    ash_diff = close - close.shift(1)
    bulls = 0.5 * (ash_diff.abs() + ash_diff)
    bears = 0.5 * (ash_diff.abs() - ash_diff)

    smth_bulls = _ma(ma_type, _ma(ma_type, bulls, length), smooth)
    smth_bears = _ma(ma_type, _ma(ma_type, bears, length), smooth)
    difference = (smth_bulls - smth_bears).abs()

    ash_bullish = difference > smth_bears
    ash_bearish = difference > smth_bulls
    buy_strong = ash_bullish & (~ash_bullish.shift(1).fillna(False))
    sell_strong = ash_bearish & (~ash_bearish.shift(1).fillna(False))

    return {
        "difference": difference, "smth_bulls": smth_bulls, "smth_bears": smth_bears,
        "ash_bullish": ash_bullish, "ash_bearish": ash_bearish,
        "buy_strong": buy_strong, "sell_strong": sell_strong,
    }


def absolute_strength_histogram(df: pd.DataFrame,
                                length: int = ASH_LENGTH,
                                smooth: int = ASH_SMOOTH) -> pd.Series:
    """Compat: devuelve el histograma firmado (smthBulls - smthBears).
    El verde/rojo real se decide en ash_signals() comparando con smthBears/Bulls."""
    s = ash_signals(df, length, smooth)
    return s["smth_bulls"] - s["smth_bears"]


def final_mfi(df: pd.DataFrame, mfi_length: int = MFI_LENGTH) -> pd.Series:
    """
    Réplica del finalMFI compuesto del Market Liberator (Pine), SIN Heikin Ashi
    (el RSI-MFI se calcula sobre velas normales, decisión acordada).

        rawMF      = hlc3 * volume
        posMF/negMF = acumulados condicionales (hlc3 > / < hlc3[1])
        mfIndex    = 100 - 100/(1 + sma(posMF)/sma(negMF)) - 50
        rsiMFI     = sma((close-open)/range * 250, length)
        mf1        = ((sma(mfIndex,21)+ema(mfIndex,9))/2 + mfIndex*2.6)/2
        mfComposite= (mf1 + rsiMFI + (rsiMFI + ema(mf1,14))/2)/3
        finalMFI   = ema(mfComposite,5)  (con fallback a rsiMFI*1.05)
    """
    if "Volume" not in df.columns:
        return pd.Series(0.0, index=df.index)

    high, low, close, op = df["High"], df["Low"], df["Close"], df["Open"]
    vol = df["Volume"].fillna(1.0)
    hlc3 = (high + low + close) / 3
    raw_mf = hlc3 * vol

    pos = np.zeros(len(df))
    neg = np.zeros(len(df))
    h = hlc3.values
    rmf = raw_mf.values
    for i in range(1, len(df)):
        pos[i] = pos[i - 1] + rmf[i] if h[i] > h[i - 1] else pos[i - 1]
        neg[i] = neg[i - 1] + rmf[i] if h[i] < h[i - 1] else neg[i - 1]
    pos = pd.Series(pos, index=df.index)
    neg = pd.Series(neg, index=df.index)

    mf_ratio = sma(pos, mfi_length).fillna(0) / sma(neg, mfi_length).fillna(0).clip(lower=0.0001)
    mf_index = (100 - 100 / (1 + mf_ratio) - 50).fillna(0)

    rng = (high - low).replace(0, 1.0)
    rsi_mfi = sma((close - op) / rng * 250, mfi_length).fillna(0)

    mf1 = ((sma(mf_index, 21).fillna(0) + _ema(mf_index, 9).fillna(0)) / 2 + mf_index * 2.6) / 2
    ema_mf1_14 = _ema(mf1, 14).fillna(0)
    mf_comp = (mf1 + rsi_mfi + (rsi_mfi + ema_mf1_14) / 2) / 3
    ema_c5 = _ema(mf_comp, 5).fillna(0)
    final = np.where(ema_c5.abs() < 0.001, rsi_mfi * 1.05, mf_comp)
    return pd.Series(final, index=df.index)


def money_flow_index(df: pd.DataFrame, length: int = MFI_LENGTH) -> pd.Series:
    """Compat: alias de final_mfi (la versión real del Market Liberator)."""
    return final_mfi(df, length)


@dataclass
class CarvanaHunterResult:
    """Resultado del análisis Carvana Hunter para un ticker."""
    # Entrada semanal (ASH)
    ash_value: Optional[float] = None       # histograma ASH última barra
    ash_buy_strong: bool = False            # BUY STRONG en última barra
    ash_buy_strong_recent_bars: Optional[int] = None  # nº barras desde el BUY STRONG
    high_conviction: bool = False           # 💎 HIGH CONVICTION
    mfi_value: Optional[float] = None
    # Entrada mensual (WaveTrend)
    wt_buy_gold: bool = False               # BUY_GOLD mensual en última barra
    wt_buy_gold_recent_bars: Optional[int] = None
    # Salida mensual (WaveTrend)
    wt_sell_plus: bool = False              # SELL_PLUS (salida) en última barra
    wt_sell_plus_recent_bars: Optional[int] = None
    # Estado consolidado
    active_entry: Optional[str] = None      # "ASH_BUY_STRONG" | "ASH_HIGH" | "WT_BUY_GOLD" | None
    active_exit: Optional[str] = None       # "WT_SELL_PLUS" | None


def detect_ash_signals_weekly(df_weekly: pd.DataFrame,
                              recent_bars: int = 3) -> dict:
    """
    Señales ASH BUY STRONG y 💎 HIGH CONVICTION sobre datos SEMANALES,
    réplica exacta de Carvana Hunter v2 (Pine).

    BUY STRONG     : ashBullish AND NOT ashBullish[1] (histograma a verde),
                     con cooldown de ASH_BUY_COOLDOWN barras.
    HIGH CONVICTION: BUY STRONG + (mfiDeepRecovery OR mfiNegRecovering)
        mfiDeepRecovery = finalMFI<0 AND subiendo AND finalMFI[lookback] < deep
        mfiNegRecovering = finalMFI<0 AND subiendo

    `recent_bars`: cuántas barras hacia atrás se considera "señal activa".
    """
    out = {
        "ash_value": None, "ash_buy_strong": False,
        "ash_buy_strong_recent_bars": None,
        "high_conviction": False, "mfi_value": None,
    }
    if df_weekly is None or len(df_weekly) < (ASH_LENGTH + ASH_SMOOTH + MFI_LENGTH):
        return out

    sig = ash_signals(df_weekly)
    buy_strong_raw = sig["buy_strong"]
    difference = sig["difference"]

    mfi = final_mfi(df_weekly)
    mfi_prev = mfi.shift(MFI_LOOKBACK)
    recovering = mfi > mfi_prev
    deep_recovery = (mfi < 0) & recovering & (mfi_prev < MFI_DEEP_THRESHOLD)
    neg_recovering = (mfi < 0) & recovering
    conviction = (deep_recovery | neg_recovering).fillna(False)

    # Cooldown de BUY STRONG (igual que el Pine: ≥ ASH_BUY_COOLDOWN barras entre señales)
    bs = buy_strong_raw.fillna(False).values
    n = len(df_weekly)
    buy_strong = np.zeros(n, dtype=bool)
    last = -10 ** 9
    for i in range(n):
        if bs[i] and (i - last) >= ASH_BUY_COOLDOWN:
            buy_strong[i] = True
            last = i

    hc_vals = (pd.Series(buy_strong, index=df_weekly.index) & conviction).values

    out["ash_value"] = float(difference.iloc[-1]) if not np.isnan(difference.iloc[-1]) else None
    out["mfi_value"] = float(mfi.iloc[-1]) if not np.isnan(mfi.iloc[-1]) else None

    for back in range(0, min(recent_bars + 1, n)):
        idx = n - 1 - back
        if buy_strong[idx]:
            out["ash_buy_strong"] = True
            out["ash_buy_strong_recent_bars"] = back
            if hc_vals[idx]:
                out["high_conviction"] = True
            break

    return out


def detect_wt_signals_monthly(df_monthly: pd.DataFrame,
                             wt1: pd.Series = None, wt2: pd.Series = None,
                             recent_bars: int = 3) -> dict:
    """
    Calcula BUY_GOLD y SELL_PLUS de Carvana Hunter sobre datos del df dado.

    BUY_GOLD  : wt2 ≤ -60  AND  wt1 cruza por encima de wt2
    SELL_PLUS : wt2 ≥  60  AND  wt1 cruza por debajo de wt2

    Carvana Hunter usa wt2 = sma(wt1, 4) (smooth 4, como el Pine), distinto
    del smooth 3 del sistema CB. Por eso recalcula su propio WT salvo que se
    pasen wt1/wt2 explícitos.
    """
    out = {
        "wt_buy_gold": False, "wt_buy_gold_recent_bars": None,
        "wt_sell_plus": False, "wt_sell_plus_recent_bars": None,
    }
    if wt1 is None or wt2 is None:
        wt1, wt2 = calculate_wavetrend(df_monthly, nSmooth=4)

    cross_up, cross_dn = detect_crossovers(wt1, wt2)
    n = len(wt2)

    buy_gold = cross_up & (wt2 <= CH_BUY_GOLD_THRESHOLD)
    sell_plus = cross_dn & (wt2 >= CH_SELL_PLUS_THRESHOLD)

    bg_vals = buy_gold.fillna(False).values
    sp_vals = sell_plus.fillna(False).values

    for back in range(0, min(recent_bars + 1, n)):
        idx = n - 1 - back
        if bg_vals[idx] and out["wt_buy_gold_recent_bars"] is None:
            out["wt_buy_gold"] = True
            out["wt_buy_gold_recent_bars"] = back
        if sp_vals[idx] and out["wt_sell_plus_recent_bars"] is None:
            out["wt_sell_plus"] = True
            out["wt_sell_plus_recent_bars"] = back

    return out


def build_carvana_hunter(ash_part: dict, wt_part: dict) -> CarvanaHunterResult:
    """Consolida las señales ASH (semanal) y WaveTrend (mensual) en un estado."""
    chr_ = CarvanaHunterResult(
        ash_value=ash_part.get("ash_value"),
        ash_buy_strong=ash_part.get("ash_buy_strong", False),
        ash_buy_strong_recent_bars=ash_part.get("ash_buy_strong_recent_bars"),
        high_conviction=ash_part.get("high_conviction", False),
        mfi_value=ash_part.get("mfi_value"),
        wt_buy_gold=wt_part.get("wt_buy_gold", False),
        wt_buy_gold_recent_bars=wt_part.get("wt_buy_gold_recent_bars"),
        wt_sell_plus=wt_part.get("wt_sell_plus", False),
        wt_sell_plus_recent_bars=wt_part.get("wt_sell_plus_recent_bars"),
    )

    # Estado de entrada ACTIVA: SOLO 💎 HIGH CONVICTION (ASH+MFI).
    # El WT BUY_GOLD ya NO cuenta como entrada (pertenece a la vista mensual,
    # no a la semanal). El ASH BUY STRONG suelto tampoco (queda guardado).
    if chr_.high_conviction:
        chr_.active_entry = "ASH_HIGH"

    # Estado de salida (semanal): WT SELL+
    if chr_.wt_sell_plus:
        chr_.active_exit = "WT_SELL_PLUS"

    return chr_


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
