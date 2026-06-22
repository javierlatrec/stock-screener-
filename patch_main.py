#!/usr/bin/env python3
"""
Patch para main.py — añade los 5 campos nuevos al output JSON.

Lo que hace:
1. Lee main.py
2. Busca la sección de "next_earnings_date" (último campo actual)
3. Añade después: long_summary, industry, country, website, employees, dividend_yield
4. Guarda

Uso:
    python3 patch_main.py
"""

import os
import sys
import re

MAIN_FILE = "main.py"

if not os.path.exists(MAIN_FILE):
    print(f"❌ No existe {MAIN_FILE} en este directorio")
    print(f"   Asegúrate de estar en ~/Desktop/cb-scanner/")
    sys.exit(1)

# Leer main.py
with open(MAIN_FILE, "r") as f:
    content = f.read()

# Buscar el patrón "next_earnings_date" y añadir los campos después
marker = '"next_earnings_date": _safe_str(ticker_data.get("next_earnings_date")),'

if marker not in content:
    print("❌ No encontré el patrón esperado en main.py")
    print("   Tu main.py puede tener una versión diferente.")
    print("   Pásame captura del fichero y te ayudo manualmente.")
    sys.exit(1)

# Comprobar si ya está parcheado
if '"long_summary"' in content:
    print("✅ main.py YA tiene los campos nuevos. No hace falta parchear.")
    sys.exit(0)

# El reemplazo: añadimos los 6 campos nuevos después de next_earnings_date
new_fields = '''"next_earnings_date": _safe_str(ticker_data.get("next_earnings_date")),
            # ─── NUEVOS v4: Datos de empresa ──────────────
            "long_summary":   _safe_str(ticker_data.get("long_summary")),
            "industry":       _safe_str(ticker_data.get("industry")) or _safe_str(ticker_data.get("industry_universe")),
            "country":        _safe_str(ticker_data.get("country")),
            "website":        _safe_str(ticker_data.get("website")),
            "employees":      _safe_float(ticker_data.get("employees")),
            "dividend_yield": _safe_float(ticker_data.get("dividend_yield")),'''

new_content = content.replace(marker, new_fields)

# Backup primero
with open(MAIN_FILE + ".backup", "w") as f:
    f.write(content)
print(f"💾 Backup creado: {MAIN_FILE}.backup")

# Escribir el nuevo
with open(MAIN_FILE, "w") as f:
    f.write(new_content)

print(f"✅ main.py parcheado correctamente")
print()
print("Próximos pasos:")
print("  1. python3 main.py            # Re-scan (6-8 min)")
print("  2. python3 html_generator.py  # Generar HTML")
print("  3. open docs/index.html       # Comprobar")
print("  4. git add . && git commit -m 'v4 main.py with new fields' && git push")
