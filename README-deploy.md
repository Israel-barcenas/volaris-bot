## Despliegue y ejecución 24/7

Se han añadido herramientas para ejecutar el bot en paralelo y desplegarlo como un servicio systemd.

Archivos añadidos
- run_bot.sh — script de arranque que activa el virtualenv y lanza el bot en background.
- deploy/volaris-bot.service — unidad systemd de ejemplo. Ajusta rutas y variables antes de habilitar.
- deploy/volaris-bot.env.example — plantilla de variables de entorno sensibles (NO subir al repo).

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

3) Variables de entorno sensibles: crea /etc/volaris-bot.env a partir de la plantilla

   sudo cp deploy/volaris-bot.env.example /etc/volaris-bot.env
   sudo chown root:root /etc/volaris-bot.env
   sudo chmod 600 /etc/volaris-bot.env
   # Edita el archivo y coloca tus valores reales (TELEGRAM_TOKEN y TELEGRAM_CHAT_ID al menos)
   sudo nano /etc/volaris-bot.env

El servicio systemd está configurado para leer /etc/volaris-bot.env y cargar esas variables al iniciar.

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
- No incluyas /etc/volaris-bot.env en el repositorio ni en backups accesibles. Manténlo con permisos 600.
- Ajusta User y WorkingDirectory en la unit para que correspondan a tu servidor si es necesario.
- Por defecto la concurrencia (CONCURRENCY) es 3. Puedes cambiarlo exportando la variable de entorno antes de iniciar el servicio.

Ejemplo para ejecutar con concurrency=5 manualmente:

  export CONCURRENCY=5
  python bot_volaris.py

