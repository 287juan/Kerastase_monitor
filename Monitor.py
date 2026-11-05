#!/usr/bin/env python3
"""Vigila https://society.kerastase.es y avisa por Telegram si cambia.
Pensado para GitHub Actions: cada ejecución vigila ~4,5 min y guarda el estado en state.json."""
import difflib
import json
import os
import random
import time

import requests
from bs4 import BeautifulSoup

URL = "https://society.kerastase.es"
INTERVALO = 20      # segundos entre comprobaciones
DURACION = 270      # segundos que vigila cada ejecución
ESTADO = "state.json"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "es-ES,es;q=0.9",
    "Cache-Control": "no-cache",
}

PALABRAS_CLAVE = ["entrada", "regístrate", "registrate", "reserva", "inscrib",
                  "hazte miembro", "solicitar", "comprar", "disponible", "agotad"]


def telegram(texto):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": texto[:4000],
                  "disable_web_page_preview": "true"},
            timeout=15,
        )
    except requests.RequestException as e:
        print("Error enviando a Telegram:", e)


def snapshot():
    r = requests.get(URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    scripts = sorted(s["src"] for s in soup.find_all("script", src=True))
    enlaces = sorted(a["href"] for a in soup.find_all("a", href=True))
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    texto = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
    return {"texto": texto, "enlaces": enlaces, "scripts": scripts}


def cargar():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def guardar(estado):
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)


def avisar(anterior, actual):
    cambios = []
    diff = [l for l in difflib.unified_diff(anterior["texto"], actual["texto"], lineterm="", n=0)
            if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    if diff:
        cambios.append("📝 Texto:\n" + "\n".join(diff[:25]))
    nuevos = set(actual["enlaces"]) - set(anterior["enlaces"])
    if nuevos:
        cambios.append("🔗 Enlaces nuevos:\n" + "\n".join(sorted(nuevos)))
    if actual["scripts"] != anterior["scripts"]:
        cambios.append("⚙️ La web se ha redesplegado (cambian los scripts).")
    urgente = any(p in " ".join(actual["texto"]).lower() for p in PALABRAS_CLAVE)
    cab = "🚨🚨 POSIBLE APERTURA DE ENTRADAS 🚨🚨" if urgente else "⚠️ La web ha cambiado"
    telegram(f"{cab}\n{URL}\n\n" + "\n\n".join(cambios))


def main():
    anterior = cargar()
    if anterior is None:
        anterior = snapshot()
        guardar(anterior)
        telegram("✅ Bot activo en GitHub. Vigilando " + URL)

    fin = time.time() + DURACION
    while time.time() < fin:
        try:
            actual = snapshot()
            if actual != anterior:
                avisar(anterior, actual)
                anterior = actual
                guardar(anterior)
        except Exception as e:
            print("Error al descargar:", e)
        time.sleep(INTERVALO + random.uniform(0, 3))


if __name__ == "__main__":
    main()
