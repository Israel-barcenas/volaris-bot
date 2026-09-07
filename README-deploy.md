## Despliegue y ejecución 24/7

Se han añadido herramientas para ejecutar el bot en paralelo y desplegarlo como un servicio systemd.

Archivos añadidos
- run_bot.sh — script de arranque que activa el virtualenv y ejecuta el bot con nohup.
- deploy/volaris-bot.service — unidad systemd de ejemplo. Ajusta rutas y variables antes de habilitar.

Instrucciones rápidas para desplegar en un VPS (asumimos ruta /home/Israel-barcenas/volaris-bot y usuario Israel-barcenas)

1) Clona el repo y crea virtualenv

   git clone https://github.com/Israel-barcenas/volaris-bot.git /home/Israel-barcenas/volaris-bot
   cd /home/Israel-barcenas/volaris-bot
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install

2) Prepara credentials.json (en la raíz del repo) — ejemplo:

[
  { "alias": "personal", "email": "miemail1@example.com", "password": "MiPass1" },
  { "alias": "work",     "email": "miemail2@example.com", "password": "MiPass2" }
]

3) Ajusta variables de entorno (recomendado en /etc/environment o systemd unit):
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID
- OPTIONAL: CREDENTIALS_FILE, INITIAL_INTERVAL, MAX_INTERVAL, JITTER, OUTPUT_DIR, CONCURRENCY

4) Hacer ejecutable el script de arranque

   chmod +x run_bot.sh

5) Copiar la unidad systemd y habilitar

   sudo cp deploy/volaris-bot.service /etc/systemd/system/volaris-bot.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now volaris-bot.service

6) Logs

   journalctl -u volaris-bot -f
   o revisa bot.log en la carpeta del repo si iniciaste con run_bot.sh

Notas
- La unidad systemd no incluye TELEGRAM_TOKEN ni TELEGRAM_CHAT_ID por seguridad; coloca esas variables en /etc/environment o añade Environment= en la unit (con cuidado).
- Ajusta User y WorkingDirectory en la unit para que correspondan a tu servidor.
- Por defecto la concurrencia (CONCURRENCY) es 3. Puedes cambiarlo exportando la variable de entorno antes de iniciar el servicio.

Ejemplo para ejecutar con concurrency=5 manualmente:

  export CONCURRENCY=5
  python bot_volaris.py

