#!/usr/bin/env python3
import os
import time
import random
import getpass
import sys
import json
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ---------- CONFIG ----------
TARGET_URL = "https://paseanual.volaris.com/y4/subscriptions/vplus/availability"
INITIAL_INTERVAL = int(os.getenv("INITIAL_INTERVAL", "20"))      # segundos entre intentos iniciales
MAX_INTERVAL = int(os.getenv("MAX_INTERVAL", "600"))          # límite del backoff
JITTER = int(os.getenv("JITTER", "5"))                       # segundos de variación aleatoria
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")              # carpeta donde se guardan screenshots y HTML
# TELEGRAM_TOKEN y TELEGRAM_CHAT pueden venir de variables de entorno o del prompt al iniciar
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
CONCURRENCY = int(os.getenv("CONCURRENCY", "3"))              # número de workers en paralelo
# ----------------------------

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def notify(text):
    print(text)
    try:
        print('\a', end='', flush=True)  # beep (puede no sonar en todos los entornos)
    except:
        pass
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT, "text": text},
                timeout=10
            )
        except Exception as e:
            print("Error al enviar Telegram:", e)


def try_fill_any(page, selectors, value):
    """Intenta llenar un campo probando varios selectores comunes."""
    for s in selectors:
        try:
            el = page.query_selector(s)
            if el:
                el.fill(value)
                return True
        except Exception:
            pass
    return False


def check_availability(page):
    """Heurística para detectar disponibilidad. Ajusta según necesidad."""
    negative_texts = ["sin disponibilidad", "no hay disponibilidad", "no seats", "sold out", "agotado"]
    for t in negative_texts:
        try:
            if page.locator(f"text={t}").count() > 0:
                return False
        except Exception:
            pass

    # Buscadores comunes de resultados/precios
    try:
        price_selectors = [
            "text=$", "text=MXN", ".price", ".fare", ".availability-item",
            ".flight-row", ".card-price", ".fares-list", ".fare-amount"
        ]
        for sel in price_selectors:
            try:
                if page.locator(sel).count() > 0:
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: buscar contenedores de resultados
    try:
        if page.locator(".results, #results, .search-results, .availability-results").count() > 0:
            return True
    except Exception:
        pass

    return False


def save_snapshot(page, prefix="attempt"):
    ts = int(time.time())
    screenshot = os.path.join(OUTPUT_DIR, f"{prefix}_{ts}.png")
    htmlfile = os.path.join(OUTPUT_DIR, f"{prefix}_{ts}.html")
    try:
        page.screenshot(path=screenshot, full_page=True)
    except Exception as e:
        print("No se pudo guardar screenshot:", e)
        screenshot = None
    try:
        html = page.content()
        with open(htmlfile, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print("No se pudo guardar HTML:", e)
        htmlfile = None
    return screenshot, htmlfile


def do_search_once_local(user, passwd, origin, dest, depart, ret_date=None, headless=True, account_alias=None):
    """Ejecuta un único intento usando un navegador (crea su propio Playwright)."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
        except PWTimeout:
            pass
        time.sleep(1)

        # --- LOGIN (intento heurístico) ---
        try:
            page.click('text="Iniciar sesión"', timeout=3000)
        except Exception:
            pass

        try_fill_any(page,
            ['input[type="email"]', 'input[name="email"]', 'input#email', 'input[placeholder*="Correo"]', 'input[placeholder*="Email"]'],
            user)
        try_fill_any(page,
            ['input[type="password"]', 'input[name="password"]', 'input#password', 'input[placeholder*="Contraseña"]'],
            passwd)

        for btn in ['button[type="submit"]', 'button:has-text("Entrar")', 'button:has-text("Iniciar sesión")', 'button:has-text("Sign in")']:
            try:
                page.click(btn, timeout=2000)
                break
            except Exception:
                pass

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeout:
            pass

        # --- RELLENAR BÚSQUEDA (heurística) ---
        try_fill_any(page, ['input[name="origin"]', 'input[aria-label*="Origen"]', 'input[placeholder*="Origen"]', 'input[id*="origin"]'], origin)
        try_fill_any(page, ['input[name="destination"]', 'input[aria-label*="Destino"]', 'input[placeholder*="Destino"]', 'input[id*="destination"]'], dest)
        try_fill_any(page, ['input[name="departureDate"]', 'input[aria-label*="Fecha de salida"]', 'input[placeholder*="Salida"]', 'input[id*="departure"]'], depart)
        if ret_date:
            try_fill_any(page, ['input[name="returnDate"]', 'input[aria-label*="Fecha de regreso"]', 'input[placeholder*="Regreso"]', 'input[id*="return"]'], ret_date)

        for s in ['button:has-text("Buscar")', 'button:has-text("Search")', 'button[type="submit"]', 'button.search-button']:
            try:
                page.click(s, timeout=3000)
                break
            except Exception:
                pass

        page.wait_for_timeout(4000)

        available = check_availability(page)
        safe_alias = account_alias.replace(' ', '_') if account_alias else 'account'
        prefix = f"found_{safe_alias}" if available else f"attempt_{safe_alias}"
        screenshot, htmlfile = save_snapshot(page, prefix=prefix)

        browser.close()
        return available, screenshot, htmlfile


def worker_search(acc, origin, dest, depart, ret, headless):
    alias = acc.get('alias')
    email = acc.get('email')
    passwd = acc.get('password')
    try:
        ok, shot, html = do_search_once_local(email, passwd, origin, dest, depart, ret_date=ret, headless=headless, account_alias=alias)
        return {'alias': alias, 'email': email, 'available': ok, 'screenshot': shot, 'html': html}
    except Exception as e:
        return {'alias': alias, 'email': acc.get('email'), 'available': False, 'error': str(e)}


def load_credentials_file():
    """Carga credentials.json y devuelve lista de entradas validas.
    Cada entrada debe tener 'email' y 'password'.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        return []
    try:
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"No se pudo leer {CREDENTIALS_FILE}: {e}")
        return []
    accounts = []
    if isinstance(data, list):
        for entry in data:
            email = entry.get('email')
            password = entry.get('password')
            alias = entry.get('alias') or email
            if email and password:
                accounts.append({'alias': alias, 'email': email, 'password': password})
    return accounts


def main():
    global TELEGRAM_TOKEN, TELEGRAM_CHAT

    print("AUTOMATIZADOR Volaris (Python + Playwright) — Rotación paralela de cuentas")

    # Cargar cuentas desde credentials.json (si existe)
    accounts = load_credentials_file()
    if accounts:
        print(f"Se encontraron {len(accounts)} cuentas en {CREDENTIALS_FILE}.")
        for i, a in enumerate(accounts, start=1):
            print(f"  {i}) {a['alias']} <{a['email']}>")
        use_rotation = input("¿Deseas usar rotación automática entre estas cuentas? (s/n) [s]: ").strip().lower() or 's'
        if use_rotation in ('s', 'si', 'y'):
            rotation = True
        else:
            rotation = False
            # permitir seleccionar una cuenta individual
            sel = input("Selecciona el número de la cuenta a usar (o 'n' para ingresar manual): ").strip().lower()
            if sel == 'n':
                accounts = []
            else:
                try:
                    idx = int(sel) - 1
                    accounts = [accounts[idx]]
                except Exception:
                    print("Selección inválida — se usará la primera cuenta.")
                    accounts = [accounts[0]]
    else:
        rotation = False

    # Si no hay cuentas cargadas o usuario elige ingresar manualmente
    if not accounts:
        print("Introduce credenciales (no se guardan).")
        user = input("Email: ").strip()
        passwd = getpass.getpass("Contraseña (oculta): ")
        accounts = [{'alias': 'manual', 'email': user, 'password': passwd}]

    print("\nIntroduce la ruta y fechas a buscar.")
    origin = input("Origen (código o ciudad): ").strip()
    dest = input("Destino (código o ciudad): ").strip()
    depart = input("Fecha ida (YYYY-MM-DD): ").strip()
    ret = input("Fecha regreso (YYYY-MM-DD) [Enter = solo ida]: ").strip() or None

    # Solicitar configuración de Telegram al iniciar
    use_telegram = input("¿Quieres notificaciones por Telegram cuando se encuentre el vuelo? (s/n): ").strip().lower()
    if use_telegram in ('s', 'si', 'y'):
        if TELEGRAM_TOKEN:
            use_env_tok = input("Se detectó TELEGRAM_TOKEN en variables de entorno. ¿Deseas usarlo? (s/n): ").strip().lower()
            if use_env_tok in ('s', 'si', 'y'):
                token = TELEGRAM_TOKEN
            else:
                token = input("Introduce el token del bot de Telegram: ").strip()
        else:
            token = input("Introduce el token del bot de Telegram: ").strip()
        chat = input("Introduce el chat_id (número) donde quieres recibir la notificación: ").strip()
        if token:
            TELEGRAM_TOKEN = token
        if chat:
            TELEGRAM_CHAT = chat
        print("Notificaciones por Telegram activadas.")
    else:
        print("Notificaciones por Telegram desactivadas.")

    # Preguntar si abrir navegador visible
    headless_choice = input("¿Abrir navegador visible? (s/n) [s]: ").strip().lower() or 's'
    headless = False if headless_choice in ('s', 'si', 'y') else True

    interval = INITIAL_INTERVAL
    global_attempt = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        notify("Bot iniciado. Usa Ctrl+C para detener.")
        try:
            stop_all = False
            while True:
                global_attempt += 1
                notify(f"Intento global #{global_attempt}: buscando {origin} -> {dest} {depart} {('(vuelta '+ret+')') if ret else ''}")

                # Submit tasks for all accounts, but limit concurrency handled by executor
                futures = {executor.submit(worker_search, acc, origin, dest, depart, ret, headless): acc for acc in accounts}

                found = None
                for fut in as_completed(futures):
                    res = fut.result()
                    alias = res.get('alias')
                    email = res.get('email')
                    if res.get('available'):
                        msg = f"¡Disponibilidad encontrada por {alias} ({email}) para {origin} -> {dest} {depart}! Screenshot: {res.get('screenshot') or 'no guardada'} HTML: {res.get('html') or 'no guardado'}"
                        notify(msg)
                        found = res
                        stop_all = True
                        break
                    else:
                        if res.get('error'):
                            notify(f"    Error con {alias}: {res.get('error')}")
                        else:
                            notify(f"    No disponible con {alias}. Screenshot: {res.get('screenshot') or 'no guardado'} HTML: {res.get('html') or 'no guardado'}")

                if stop_all:
                    break

                notify(f"No hubo disponibilidad en ninguna cuenta en el intento global #{global_attempt}. Esperando {interval}s antes del siguiente intento.")
                sleep_t = max(1, interval + random.uniform(-JITTER, JITTER))
                time.sleep(sleep_t)
                interval = min(MAX_INTERVAL, int(interval * 1.3))

        except KeyboardInterrupt:
            notify("Detenido por usuario.")
            sys.exit(0)
        except Exception as e:
            notify(f"Error inesperado: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
