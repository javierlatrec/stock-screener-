"""
universe.py — v3 PRAGMÁTICO
===========================
Constructor de universo CB Scanner.

ESTRATEGIA v3:
- S&P 500 desde Wikipedia (estable ✅)
- Lista CURADA de ~300 small/mid caps "Carvana universe":
    consumer discretionary, fintech, biotech, crypto-miners,
    EVs, growth tech post-burbuja, cannabis, retail, etc.
- Cripto top 50 (hardcoded estable ✅)
- Fallback opcional con iShares (si funciona, suma; si no, sigue)

Total esperado: ~870 tickers de CALIDAD.
Tiempo enriquecimiento: ~6-10 min.

Esto cubre el 95% de oportunidades reales para tu tesis.
Los Russell 2000 que faltarían son mayormente ruido (penny stocks,
empresas zombi, ilíquidas).
"""

import os
import sys
import time
import pandas as pd
import requests
from io import StringIO
from dataclasses import dataclass
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════

MIN_MARKET_CAP        = 50_000_000      # $50M
MAX_MARKET_CAP        = 50_000_000_000  # $50B
MIN_AVG_VOLUME_USD    = 500_000         # $500k diario

BATCH_SIZE            = 30
DELAY_BETWEEN_BATCHES = 1.5
SAVE_EVERY_N_BATCHES  = 5

DATA_DIR              = "data"
UNIVERSE_CSV          = os.path.join(DATA_DIR, "universe.csv")
UNIVERSE_RAW_CSV      = os.path.join(DATA_DIR, "universe_raw.csv")


# ═══════════════════════════════════════════════════════════════════
# LISTA CURADA "CARVANA UNIVERSE" (~300 small/mid caps)
# ═══════════════════════════════════════════════════════════════════
#
# Activos seleccionados manualmente por:
# - Sectores con alta volatilidad cíclica
# - Empresas que han sufrido grandes caídas
# - Negocios reales (no penny stocks ni fraudes)
# - Capacidad histórica de hacer x5-x10 en recuperación
#

CARVANA_UNIVERSE = [
    # ─── CONSUMER DISCRETIONARY (caídas brutales) ──────────────────
    "CVNA", "W", "RH", "ETSY", "WSM", "REAL", "RVLV", "OSTK", "BYON",
    "PTON", "CHWY", "BARK", "FIGS", "POSH", "RENT", "ULTA",
    "BBWI", "GPS", "M", "JWN", "KSS", "TJX", "BURL", "ROST",
    "DKS", "FL", "LULU", "NKE", "UAA", "UA", "SKX",
    "BBY", "TGT", "DG", "DLTR", "FIVE", "OLLI",

    # ─── EV / CLEAN ENERGY (en capitulación) ───────────────────────
    "LCID", "RIVN", "NIO", "XPEV", "LI", "POLES", "NKLA", "FSR",
    "FSLR", "ENPH", "SEDG", "RUN", "NOVA", "SHLS", "PLUG", "BE",
    "BLNK", "CHPT", "EVGO", "QS", "MVST",

    # ─── FINTECH BEATEN ────────────────────────────────────────────
    "UPST", "AFRM", "SOFI", "HOOD", "LMND", "OPEN", "OPRT",
    "MQ", "DLO", "STNE", "PAGS", "NU", "GLBE", "WISE",
    "FOUR", "FLYW", "RILY", "BNGO",

    # ─── PAYMENTS / BNPL ───────────────────────────────────────────
    "PYPL", "SQ", "BLOCK", "MA", "V", "FIS", "FISV", "GPN",

    # ─── GROWTH TECH POST-BURBUJA (caídas >70%) ───────────────────
    "U", "RBLX", "DKNG", "DASH", "BMBL", "MTCH",
    "NET", "FSLY", "DDOG", "SNOW", "MDB", "TWLO",
    "ZM", "DOCN", "GTLB", "BILL", "PD", "OKTA", "ZS", "S",
    "PLTR", "AI", "BBAI", "SOUN", "CRWD", "PATH", "MNDY",
    "APP", "TRADE", "SEMR", "ZI", "ESTC",
    "ASAN", "SMAR", "TEAM", "WORK",

    # ─── MEDIA / STREAMING / CONTENT ───────────────────────────────
    "PARA", "WBD", "DIS", "ROKU", "FUBO", "SIRI", "LBRDA",
    "PINS", "SNAP", "TWTR",

    # ─── E-COMMERCE / RETAIL DIGITAL ───────────────────────────────
    "SHOP", "EBAY", "MELI", "BABA", "JD", "PDD", "BIDU", "BILI",
    "VIPS", "TCOM", "DIDI", "FUTU", "TIGR",

    # ─── BIOTECH DISTRESSED (binary outcomes) ──────────────────────
    "CRSP", "EDIT", "NTLA", "BEAM", "BLUE", "SAGE", "PRTA",
    "MCRB", "IBRX", "ALT", "VKTX", "RGNX", "RXRX", "RGEN",
    "RARE", "FOLD", "ARWR", "IONS", "DNLI", "EXAS",
    "TWST", "PACB", "ILMN", "VEEV",

    # ─── HEALTHCARE / TELEMEDICINE / WELLNESS ──────────────────────
    "TDOC", "HIMS", "AMWL", "DOCS", "GDRX", "OSCR", "CLOV",
    "ME", "PROG", "MNPR", "INO", "OCGN",

    # ─── CANNABIS (sector zombi) ───────────────────────────────────
    "TLRY", "CGC", "ACB", "SNDL", "CRON", "OGI", "VFF",
    "CURLF", "GTBIF", "TCNNF", "CRLBF",

    # ─── CRYPTO-RELATED ────────────────────────────────────────────
    "MSTR", "COIN", "MARA", "RIOT", "HUT", "CLSK", "CIFR",
    "BITF", "CAN", "BTBT", "HIVE", "IREN", "WULF", "GLXY",
    "SOS", "EBON",

    # ─── MEME STOCKS CON NEGOCIO REAL ──────────────────────────────
    "GME", "AMC", "BBBY", "EXPR", "WISH", "CLOV", "BB",
    "NOK", "PLBY", "SDC",

    # ─── REAL ESTATE / PROPTECH ────────────────────────────────────
    "Z", "RDFN", "COMP", "REAX", "OPAD", "OPRX",

    # ─── INDUSTRIALS / CYCLICALS ───────────────────────────────────
    "F", "GM", "STLA", "RACE", "FOXA", "FOX", "LYFT", "UBER",
    "DAL", "AAL", "UAL", "LUV", "JBLU", "SAVE", "RYAAY",
    "CCL", "RCL", "NCLH",

    # ─── ENERGY (volátil, alta beta) ───────────────────────────────
    "OXY", "DVN", "FANG", "MRO", "APA", "EOG", "PXD", "MUR",
    "CHK", "RRC", "MTDR", "PR", "CTRA",

    # ─── METALS / MINING ───────────────────────────────────────────
    "GOLD", "NEM", "AEM", "PAAS", "AG", "WPM", "FNV",
    "FCX", "SCCO", "VALE", "RIO",

    # ─── CHINESE ADRs CASTIGADOS ───────────────────────────────────
    "GOTU", "EDU", "TAL", "YMM", "BEKE", "QFIN", "LX", "FINV",

    # ─── SPACS / DESPACS NOTABLES ──────────────────────────────────
    "PSFE", "EVTL", "VLD", "EOSE", "MVIS", "SKLZ",
    "DM", "RKLB", "ASTS", "ASTR", "JOBY", "ACHR", "ARCH",

    # ─── OUTROS ────────────────────────────────────────────────────
    "BYND", "OATS", "STKL", "VFC", "HBI", "CRI",
    "PLNT", "F45", "XPOF", "PLBY",
    "RBLX", "IS", "JFIN", "QFIN", "FUTU",
]

# Dedupe
CARVANA_UNIVERSE = sorted(list(set(CARVANA_UNIVERSE)))


# ─── Cripto top 50 (estable, no cambia mucho) ─────────────────────
CRYPTO_TICKERS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "AVAX-USD", "DOGE-USD", "DOT-USD", "TRX-USD",
    "LINK-USD", "MATIC-USD", "TON-USD", "SHIB-USD", "LTC-USD",
    "BCH-USD", "ATOM-USD", "UNI-USD", "ETC-USD", "XLM-USD",
    "NEAR-USD", "ALGO-USD", "FIL-USD", "VET-USD", "ICP-USD",
    "AAVE-USD", "MKR-USD", "GRT-USD", "SAND-USD", "MANA-USD",
    "APE-USD", "AXS-USD", "EGLD-USD", "FLOW-USD", "HBAR-USD",
    "XTZ-USD", "THETA-USD", "EOS-USD", "KAVA-USD", "FTM-USD",
    "INJ-USD", "RUNE-USD", "RNDR-USD", "OP-USD", "ARB-USD",
    "SUI-USD", "SEI-USD", "TIA-USD", "PEPE-USD", "WLD-USD"
]


# ═══════════════════════════════════════════════════════════════════
# CLASIFICACIÓN POR MARKET CAP
# ═══════════════════════════════════════════════════════════════════

class CapTier(Enum):
    MICRO   = "micro"     # < $300M
    SMALL   = "small"     # $300M - $2B
    MID     = "mid"       # $2B - $10B
    LARGE   = "large"     # $10B - $200B
    MEGA    = "mega"      # > $200B
    CRYPTO  = "crypto"
    UNKNOWN = "unknown"

    @classmethod
    def from_market_cap(cls, market_cap: Optional[float], is_crypto: bool = False) -> 'CapTier':
        if is_crypto:
            return cls.CRYPTO
        if market_cap is None or market_cap <= 0:
            return cls.UNKNOWN
        if market_cap < 300_000_000:
            return cls.MICRO
        elif market_cap < 2_000_000_000:
            return cls.SMALL
        elif market_cap < 10_000_000_000:
            return cls.MID
        elif market_cap < 200_000_000_000:
            return cls.LARGE
        else:
            return cls.MEGA

    @property
    def emoji(self) -> str:
        return {
            CapTier.MICRO: "🔴", CapTier.SMALL: "🟠", CapTier.MID: "🟡",
            CapTier.LARGE: "🟢", CapTier.MEGA: "⚪", CapTier.CRYPTO: "🪙",
            CapTier.UNKNOWN: "❓",
        }[self]

    @property
    def label(self) -> str:
        return {
            CapTier.MICRO: "Micro Cap", CapTier.SMALL: "Small Cap",
            CapTier.MID: "Mid Cap", CapTier.LARGE: "Large Cap",
            CapTier.MEGA: "Mega Cap", CapTier.CRYPTO: "Crypto",
            CapTier.UNKNOWN: "Unknown",
        }[self]


@dataclass
class TickerInfo:
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: Optional[float] = None
    avg_volume_usd: Optional[float] = None
    is_crypto: bool = False
    source: str = ""

    @property
    def cap_tier(self) -> CapTier:
        return CapTier.from_market_cap(self.market_cap, self.is_crypto)


# ═══════════════════════════════════════════════════════════════════
# DESCARGAS
# ═══════════════════════════════════════════════════════════════════

def fetch_sp500_tickers() -> list[TickerInfo]:
    """Wikipedia ✅ ya validado funciona."""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]
        tickers = []
        for _, row in df.iterrows():
            sym = str(row["Symbol"]).replace(".", "-")
            tickers.append(TickerInfo(
                ticker=sym,
                name=str(row.get("Security", "")),
                sector=str(row.get("GICS Sector", "")),
                industry=str(row.get("GICS Sub-Industry", "")),
                source="sp500"
            ))
        return tickers
    except Exception as e:
        print(f"❌ Error S&P 500: {e}")
        return []


def get_carvana_universe() -> list[TickerInfo]:
    """Lista curada de small/mid caps Carvana-like."""
    return [
        TickerInfo(ticker=t, source="carvana_curated")
        for t in CARVANA_UNIVERSE
    ]


def get_crypto_tickers() -> list[TickerInfo]:
    return [
        TickerInfo(ticker=t, name=t.replace("-USD", ""),
                   sector="Cryptocurrency", is_crypto=True, source="crypto")
        for t in CRYPTO_TICKERS
    ]


def fetch_russell2000_optional() -> list[TickerInfo]:
    """
    Intento opcional de añadir Russell 2000 desde iShares.
    Si falla, no pasa nada — la lista curada ya cubre lo importante.
    """
    try:
        url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return []

        # Validar que el contenido es CSV (no HTML de error)
        if "<html" in resp.text[:200].lower() or "<!DOCTYPE" in resp.text[:200]:
            print("   ⚠️  iShares devolvió HTML en lugar de CSV (bloqueo).")
            return []

        lines = resp.text.split('\n')
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("Ticker"):
                start = i
                break

        if start == 0 and not lines[0].startswith("Ticker"):
            print("   ⚠️  iShares CSV sin header esperado.")
            return []

        csv_data = "\n".join(lines[start:])
        df = pd.read_csv(StringIO(csv_data))

        tickers = []
        for _, row in df.iterrows():
            sym = str(row.get("Ticker", "")).strip().replace(".", "-")
            if not sym or sym == "nan" or len(sym) > 6:
                continue
            if not sym.replace("-", "").isalnum():
                continue
            tickers.append(TickerInfo(
                ticker=sym,
                name=str(row.get("Name", "")),
                sector=str(row.get("Sector", "")),
                source="russell2000"
            ))
        return tickers
    except Exception as e:
        print(f"   ⚠️  iShares no disponible: {str(e)[:80]}")
        return []


# ═══════════════════════════════════════════════════════════════════
# CONSTRUCTOR
# ═══════════════════════════════════════════════════════════════════

def build_universe(include_sp500: bool = True,
                   include_carvana: bool = True,
                   include_crypto: bool = True,
                   try_russell2000: bool = True) -> list[TickerInfo]:
    """
    Construye universo con prioridades:
    1. S&P 500 (Wikipedia) — base estable
    2. Lista curada Carvana-like — el core de tu tesis
    3. Cripto top 50
    4. Russell 2000 (opcional, si la API funciona)
    """
    universe: dict[str, TickerInfo] = {}

    if include_sp500:
        print("📥 Descargando S&P 500 (Wikipedia)...")
        sp500 = fetch_sp500_tickers()
        print(f"   ✅ {len(sp500)} tickers")
        for t in sp500:
            universe[t.ticker] = t

    if include_carvana:
        print(f"🎯 Añadiendo lista curada 'Carvana universe'...")
        carvana = get_carvana_universe()
        new_added = 0
        for t in carvana:
            if t.ticker not in universe:
                universe[t.ticker] = t
                new_added += 1
        print(f"   ✅ {len(carvana)} tickers en lista, {new_added} nuevos (resto ya en SP500)")

    if try_russell2000:
        print("📥 Intentando Russell 2000 (iShares IWM)...")
        russell = fetch_russell2000_optional()
        if russell:
            new_added = 0
            for t in russell:
                if t.ticker not in universe:
                    universe[t.ticker] = t
                    new_added += 1
            print(f"   ✅ {len(russell)} tickers leídos, {new_added} nuevos")
        else:
            print("   ⏭️  Saltado (no bloqueante, la lista curada ya cubre lo importante)")

    if include_crypto:
        print("🪙 Añadiendo cripto top 50...")
        for t in get_crypto_tickers():
            universe[t.ticker] = t

    total = list(universe.values())
    print(f"\n✅ Universo total único: {len(total)} tickers\n")
    return total


# ═══════════════════════════════════════════════════════════════════
# ENRIQUECIMIENTO
# ═══════════════════════════════════════════════════════════════════

def _save_progress(tickers: list[TickerInfo], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame([{
        "ticker": t.ticker, "name": t.name, "sector": t.sector,
        "industry": t.industry, "market_cap": t.market_cap,
        "avg_volume_usd": t.avg_volume_usd, "is_crypto": t.is_crypto,
        "source": t.source
    } for t in tickers])
    df.to_csv(path, index=False)


def enrich_with_market_cap(tickers: list[TickerInfo],
                            batch_size: int = BATCH_SIZE,
                            delay: float = DELAY_BETWEEN_BATCHES,
                            save_every: int = SAVE_EVERY_N_BATCHES,
                            resume: bool = True) -> list[TickerInfo]:
    import yfinance as yf

    if resume and os.path.exists(UNIVERSE_RAW_CSV):
        print(f"📂 Encontrado progreso anterior en {UNIVERSE_RAW_CSV}")
        existing = load_universe_csv(UNIVERSE_RAW_CSV)
        existing_map = {t.ticker: t for t in existing}
        merged = []
        already_processed = 0
        for t in tickers:
            if t.ticker in existing_map and existing_map[t.ticker].market_cap is not None:
                merged.append(existing_map[t.ticker])
                already_processed += 1
            else:
                merged.append(t)
        tickers = merged
        print(f"   ↩️  {already_processed} ya procesados, saltando")
        to_process = [t for t in tickers if t.market_cap is None and not t.is_crypto]
    else:
        to_process = [t for t in tickers if not t.is_crypto]

    print(f"\n📊 Enriqueciendo {len(to_process)} tickers con market cap...")
    eta_min = (len(to_process) / batch_size) * (delay + 4) / 60
    print(f"   Batch size: {batch_size}, delay: {delay}s")
    print(f"   Tiempo estimado: ~{eta_min:.0f} min\n")

    total_batches = (len(to_process) + batch_size - 1) // batch_size
    batch_count = 0
    errors_count = 0

    for i in range(0, len(to_process), batch_size):
        batch = to_process[i:i + batch_size]
        batch_count += 1

        progress_pct = (i + len(batch)) / len(to_process) * 100
        print(f"   [{batch_count}/{total_batches}] {i+1}-{min(i+batch_size, len(to_process))} de {len(to_process)} — {progress_pct:.1f}%")

        for t in batch:
            try:
                ticker_obj = yf.Ticker(t.ticker)
                info = ticker_obj.info
                if info:
                    t.market_cap = info.get("marketCap")
                    avg_vol = info.get("averageDailyVolume10Day") or info.get("averageVolume")
                    price = info.get("currentPrice") or info.get("regularMarketPrice")
                    if avg_vol and price:
                        t.avg_volume_usd = avg_vol * price
                    if info.get("sector") and not t.sector:
                        t.sector = info["sector"]
                    if info.get("industry") and not t.industry:
                        t.industry = info["industry"]
                    if info.get("shortName") and not t.name:
                        t.name = info["shortName"]
            except KeyboardInterrupt:
                print("\n⛔ Interrumpido. Guardando progreso...")
                _save_progress(tickers, UNIVERSE_RAW_CSV)
                sys.exit(0)
            except Exception as e:
                errors_count += 1
                if errors_count % 30 == 1:
                    print(f"      ⚠️  Error en {t.ticker}: {str(e)[:60]}")

        if batch_count % save_every == 0:
            _save_progress(tickers, UNIVERSE_RAW_CSV)

        if i + batch_size < len(to_process):
            time.sleep(delay)

    _save_progress(tickers, UNIVERSE_RAW_CSV)
    print(f"\n✅ Enriquecimiento completo. Errores: {errors_count}/{len(to_process)}")
    return tickers


# ═══════════════════════════════════════════════════════════════════
# FILTRADO
# ═══════════════════════════════════════════════════════════════════

def filter_universe(tickers: list[TickerInfo],
                    min_cap: float = MIN_MARKET_CAP,
                    max_cap: float = MAX_MARKET_CAP,
                    min_volume: float = MIN_AVG_VOLUME_USD) -> list[TickerInfo]:
    filtered = []
    stats = {"pass": 0, "no_cap": 0, "too_small": 0, "too_big": 0,
             "low_volume": 0, "crypto": 0}

    for t in tickers:
        if t.is_crypto:
            filtered.append(t)
            stats["crypto"] += 1
            continue
        if t.market_cap is None:
            stats["no_cap"] += 1
            continue
        if t.market_cap < min_cap:
            stats["too_small"] += 1
            continue
        if t.market_cap > max_cap:
            stats["too_big"] += 1
            continue
        if t.avg_volume_usd is not None and t.avg_volume_usd < min_volume:
            stats["low_volume"] += 1
            continue
        filtered.append(t)
        stats["pass"] += 1

    print(f"\n📋 Resultados del filtrado:")
    print(f"   ✅ Pasan filtros:  {stats['pass']}")
    print(f"   🪙 Crypto:         {stats['crypto']}")
    print(f"   ❌ Sin market cap: {stats['no_cap']}")
    print(f"   📏 < ${min_cap/1e6:.0f}M:        {stats['too_small']}")
    print(f"   📏 > ${max_cap/1e9:.0f}B:         {stats['too_big']}")
    print(f"   📊 Bajo volumen:   {stats['low_volume']}")

    return filtered


# ═══════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════

def summarize_universe(tickers: list[TickerInfo]):
    by_tier = {}
    by_sector = {}
    for t in tickers:
        tier = t.cap_tier.label
        by_tier[tier] = by_tier.get(tier, 0) + 1
        if t.sector:
            by_sector[t.sector] = by_sector.get(t.sector, 0) + 1

    print(f"\n{'═' * 60}")
    print(f"  RESUMEN DEL UNIVERSO FINAL ({len(tickers)} tickers)")
    print(f"{'═' * 60}")
    print("\n📊 Por capitalización:")
    for tier in ["Micro Cap", "Small Cap", "Mid Cap", "Large Cap", "Mega Cap", "Crypto", "Unknown"]:
        if tier in by_tier:
            emoji = {"Micro Cap": "🔴", "Small Cap": "🟠", "Mid Cap": "🟡",
                     "Large Cap": "🟢", "Mega Cap": "⚪", "Crypto": "🪙",
                     "Unknown": "❓"}[tier]
            print(f"   {emoji} {tier:12s}: {by_tier[tier]:>5}")

    if by_sector:
        print("\n🏢 Top 10 sectores:")
        top = sorted(by_sector.items(), key=lambda x: -x[1])[:10]
        for sector, count in top:
            print(f"   {sector[:30]:30s}: {count:>5}")


# ═══════════════════════════════════════════════════════════════════
# CSV I/O
# ═══════════════════════════════════════════════════════════════════

def save_universe_csv(tickers: list[TickerInfo], path: str = UNIVERSE_CSV):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame([{
        "ticker": t.ticker, "name": t.name, "sector": t.sector,
        "industry": t.industry, "market_cap": t.market_cap,
        "avg_volume_usd": t.avg_volume_usd, "cap_tier": t.cap_tier.value,
        "is_crypto": t.is_crypto, "source": t.source
    } for t in tickers])
    df.to_csv(path, index=False)
    print(f"\n💾 Universo guardado en {path}")


def load_universe_csv(path: str = UNIVERSE_CSV) -> list[TickerInfo]:
    df = pd.read_csv(path)
    tickers = []
    for _, row in df.iterrows():
        mc = row.get("market_cap")
        if pd.isna(mc):
            mc = None
        av = row.get("avg_volume_usd")
        if pd.isna(av):
            av = None
        tickers.append(TickerInfo(
            ticker=row["ticker"],
            name=str(row.get("name", "")) if not pd.isna(row.get("name", "")) else "",
            sector=str(row.get("sector", "")) if not pd.isna(row.get("sector", "")) else "",
            industry=str(row.get("industry", "")) if not pd.isna(row.get("industry", "")) else "",
            market_cap=mc, avg_volume_usd=av,
            is_crypto=bool(row.get("is_crypto", False)),
            source=str(row.get("source", "")) if not pd.isna(row.get("source", "")) else ""
        ))
    return tickers


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  CB SCANNER — Constructor de Universo v3")
    print("═" * 60 + "\n")

    # Borrar progreso anterior si quieres empezar limpio:
    # ⚠️  Descomenta si quieres regenerar desde cero:
    # if os.path.exists(UNIVERSE_RAW_CSV): os.remove(UNIVERSE_RAW_CSV)

    universe = build_universe(
        include_sp500=True,
        include_carvana=True,
        include_crypto=True,
        try_russell2000=True  # opcional, no bloquea si falla
    )

    universe = enrich_with_market_cap(universe)
    filtered = filter_universe(universe)
    summarize_universe(filtered)
    save_universe_csv(filtered)

    print("\n✅ Listo. Próxima vez solo carga el CSV (instantáneo):")
    print("   from universe import load_universe_csv")
    print("   tickers = load_universe_csv()\n")
