"""
telegram_alert.py
=================
Envía alertas de Telegram con los 💎 ASH HIGH CONVICTION NUEVOS del último scan.

"Nuevos" = HIGH que aparecen en el scan actual pero NO estaban en el anterior.
Así no te llega cada día la misma lista repetida; solo te avisa cuando entra
un setup nuevo de alta convicción.

Lee:
    data/signals.json           (scan actual)
    data/alerted_high.json      (HIGH ya avisados, persistente)

Variables de entorno (secrets de GitHub):
    TELEGRAM_TOKEN
    TELEGRAM_CHAT_ID

Uso:
    python3 telegram_alert.py
"""

import os
import json
import urllib.request
import urllib.parse

DATA_DIR      = "data"
SIGNALS_JSON  = os.path.join(DATA_DIR, "signals.json")
ALERTED_JSON  = os.path.join(DATA_DIR, "alerted_high.json")

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(text: str) -> bool:
    """Envía un mensaje a Telegram. Devuelve True si OK."""
    if not TOKEN or not CHAT_ID:
        print("⚠️  TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados. No se envía.")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")
        return False


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def get_current_highs(signals: dict) -> dict:
    """Devuelve {ticker: info} de los que tienen 💎 ASH HIGH activo ahora."""
    highs = {}
    for r in signals.get("results", []):
        ch = r.get("carvana_hunter")
        if ch and ch.get("active_entry") == "ASH_HIGH":
            highs[r["ticker"]] = {
                "name": r.get("name", ""),
                "price": r.get("current_price"),
                "drawdown": r.get("drawdown_from_ath_pct"),
                "sector": r.get("sector", ""),
                "mfi": ch.get("mfi_value"),
                "score": (r.get("carvana_setup") or {}).get("score", 0),
            }
    return highs


def fmt_high(ticker: str, info: dict) -> str:
    price = info.get("price")
    price_s = f"${price:.2f}" if isinstance(price, (int, float)) else "—"
    dd = info.get("drawdown")
    dd_s = f"{dd:.0f}%" if isinstance(dd, (int, float)) else "—"
    mfi = info.get("mfi")
    mfi_s = f"{mfi:.0f}" if isinstance(mfi, (int, float)) else "—"
    name = info.get("name", "")
    sector = info.get("sector", "")
    score = info.get("score", 0)
    return (f"💎 <b>{ticker}</b> — {name}\n"
            f"   {price_s} · DD {dd_s} · MFI {mfi_s} · Score {score}/19\n"
            f"   <i>{sector}</i>\n"
            f"   📊 https://www.tradingview.com/chart/?symbol={ticker}")


def main():
    signals = load_json(SIGNALS_JSON, {"results": []})
    current = get_current_highs(signals)

    already = set(load_json(ALERTED_JSON, {}).get("tickers", []))
    current_tickers = set(current.keys())

    new_tickers = current_tickers - already

    sent_ok = True  # por defecto, si no hay nada nuevo, está "ok"
    if new_tickers:
        scan_date = signals.get("scan_date_human", "")
        lines = [f"🎯 <b>CB Scanner — {len(new_tickers)} nuevo(s) 💎 HIGH CONVICTION</b>",
                 f"<i>{scan_date}</i>", ""]
        for t in sorted(new_tickers):
            lines.append(fmt_high(t, current[t]))
            lines.append("")
        msg = "\n".join(lines)
        sent_ok = send_telegram(msg)
        if sent_ok:
            print(f"✅ Alerta enviada: {len(new_tickers)} nuevos HIGH → {', '.join(sorted(new_tickers))}")
        else:
            print("⚠️  No se pudo enviar la alerta. NO se guarda el estado (se reintentará).")
    else:
        print("ℹ️  No hay HIGH nuevos respecto al scan anterior. No se envía nada.")

    # Persistir el estado SOLO si el envío fue exitoso (o no había nada que enviar).
    # Si el envío falló, no guardamos → el próximo scan reintentará la alerta.
    if sent_ok:
        with open(ALERTED_JSON, "w") as f:
            json.dump({"tickers": sorted(current_tickers)}, f, indent=2)


if __name__ == "__main__":
    main()
