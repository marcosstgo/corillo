# Corillo Bot — Chat API

Backend del chat widget en `corillo.live/`. Corre en la Raspberry Pi como servicio systemd.

## Infraestructura

```
[Internet] → Caddy (servidor principal)
                └── /chat-api/* → reverse_proxy 192.168.8.167:3001
                                        └── Raspberry Pi 3B
                                            /home/marcos/corillo-bot/
                                            ├── venv/
                                            ├── server.py
                                            └── .env
```

> El bot corre en la Pi 3B en la red local (`192.168.8.167:3001`). Caddy hace el proxy desde el servidor principal.

## Stack

- **FastAPI** + **uvicorn** en puerto `3001`
- **Anthropic SDK** — modelo `claude-haiku-4-5-20251001`
- **httpx** — para consultar el estado en vivo de MediaMTX
- **python-dotenv** — carga `ANTHROPIC_API_KEY` desde `.env`

Caddy hace el proxy de `/chat-api/` → `localhost:3001`.

## Cómo funciona

1. El frontend hace `POST /chat-api/message` con `{ message: "..." }`
2. El bot consulta `/mediamtx-api/v3/paths/list` para saber quién está en vivo
3. Pasa el estado en vivo al system prompt de Claude
4. Devuelve `{ reply: "..." }`

> **Nota:** No hay historial de conversación — cada mensaje es independiente.

## Variables de entorno

Archivo `/home/marcos/corillo-bot/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Comando de arranque (lo maneja systemd)

```bash
uvicorn server:app --host 0.0.0.0 --port 3001
```

## Systemd service

Archivo: `/etc/systemd/system/corillo-bot.service`

```ini
[Unit]
Description=Corillo Bot Chat API
After=network.target

[Service]
User=marcos
WorkingDirectory=/home/marcos/corillo-bot
ExecStart=/home/marcos/corillo-bot/venv/bin/uvicorn server:app --host 0.0.0.0 --port 3001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Comandos útiles

```bash
# Ver estado
sudo systemctl status corillo-bot

# Ver logs en vivo
sudo journalctl -u corillo-bot -f

# Reiniciar
sudo systemctl restart corillo-bot

# Parar
sudo systemctl stop corillo-bot
```

## Notas

- El servicio arranca automáticamente al reiniciar el Pi.
- No hace falta tener Putty abierto para que funcione.
- Si se modifica `server.py`, hay que correr `sudo systemctl restart corillo-bot`.
