import os, re, asyncio, tempfile, logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

load_dotenv(Path(__file__).parent / ".env")

BOT_TOKEN     = os.environ["BOT_TOKEN"]
LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "http://telegram-bot-api:8081/bot")
YTDLP         = "yt-dlp"
FFMPEG        = "ffmpeg"
ALLOWED_USERS = set(os.environ.get("ALLOWED_USERS", "").split(",")) - {""}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

URL_RE = re.compile(
    r"https?://(?:www\.|vm\.|vt\.|m\.)?"
    r"(?:"
    r"instagram\.com/(?:reel|p|reels|stories)/[^\s]+"
    r"|tiktok\.com/[^\s]+"
    r"|youtube\.com/shorts/[^\s]+"
    r"|youtu\.be/[^\s]+"
    r"|(?:twitter|x)\.com/\w+/status/\d+"
    r"|fb\.watch/[^\s]+"
    r"|facebook\.com/[^\s]+/videos/[^\s]+"
    r"|pinterest\.com/pin/[^\s]+"
    r")",
    re.IGNORECASE,
)


def is_allowed(update: Update) -> bool:
    if not ALLOWED_USERS:
        return True
    uid = str(update.effective_user.id)
    username = (update.effective_user.username or "").lower()
    return uid in ALLOWED_USERS or username in ALLOWED_USERS


async def _run(cmd: list, timeout: int = 180):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError()
    return proc.returncode, stdout, stderr


# Errores que suelen ser transitorios (rate limit IP, red intermitente).
# Si aparecen, vale la pena reintentar antes de rendirse.
TRANSIENT_ERROR_MARKERS = (
    "rate-limit",
    "rate limit",
    "login required",
    "http error 429",
    "http error 503",
    "temporary failure",
    "connection reset",
    "read timed out",
    "remote end closed connection",
)


async def _run_ytdlp_with_retry(yt_cmd: list, status_msg, max_attempts: int = 3):
    """Ejecuta yt-dlp; reintenta con backoff si el error parece transitorio."""
    last_rc, last_out, last_err = 1, b"", b""
    for attempt in range(1, max_attempts + 1):
        last_rc, last_out, last_err = await _run(yt_cmd, timeout=180)
        if last_rc == 0:
            return last_rc, last_out, last_err

        err_lower = last_err.decode(errors="ignore").lower()
        transient = any(m in err_lower for m in TRANSIENT_ERROR_MARKERS)
        if not transient or attempt == max_attempts:
            return last_rc, last_out, last_err

        wait = 15 * attempt  # 15s, 30s
        log.info("yt-dlp falla transitoria (intento %d/%d), esperando %ds", attempt, max_attempts, wait)
        try:
            await status_msg.edit_text(
                f"⏳ Instagram nos limitó. Reintentando en {wait}s... ({attempt}/{max_attempts - 1})"
            )
        except Exception:
            pass
        await asyncio.sleep(wait)
    return last_rc, last_out, last_err


def _format_user_error(stderr_bytes: bytes) -> str:
    """Convierte el stderr de yt-dlp en un mensaje claro para el usuario."""
    err = stderr_bytes.decode(errors="ignore").lower()
    if "rate-limit" in err or "rate limit" in err or "login required" in err:
        return (
            "❌ Instagram nos bloqueó por rate-limit. Inténtalo de nuevo en unos minutos.\n"
            "Si pasa seguido, hay que agregar cookies — avísame."
        )
    if "private" in err and "account" in err:
        return "❌ La cuenta es privada — no puedo acceder al contenido."
    if "unsupported url" in err or "no video" in err:
        return "❌ URL no soportada o sin video."
    if "http error 404" in err:
        return "❌ El contenido ya no existe (404)."
    # fallback genérico
    snippet = stderr_bytes.decode(errors="ignore")[-300:]
    return f"❌ Error de yt-dlp:\n<code>{snippet}</code>"


async def _download(update: Update, url: str, audio_only: bool) -> None:
    msg = await update.message.reply_text("⬇️ Descargando...")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if audio_only:
                yt_cmd = [
                    YTDLP, "-x", "--audio-format", "mp3",
                    "-o", f"{tmpdir}/%(id)s.%(ext)s", url,
                ]
            else:
                yt_cmd = [
                    YTDLP,
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--merge-output-format", "mp4",
                    "--no-playlist",
                    "-o", f"{tmpdir}/%(id)s.%(ext)s", url,
                ]

            rc, _, stderr = await _run_ytdlp_with_retry(yt_cmd, msg)
            if rc != 0:
                log.warning("yt-dlp error final: %s", stderr.decode(errors="ignore")[-600:])
                await msg.edit_text(_format_user_error(stderr), parse_mode="HTML")
                return

            raw_files = [f for f in Path(tmpdir).iterdir() if f.is_file()]
            if not raw_files:
                await msg.edit_text("❌ No se encontró el archivo descargado.")
                return

            raw = raw_files[0]

            if audio_only:
                filepath = raw
            else:
                # Re-encode to H.264 + faststart so Telegram plays it inline
                await msg.edit_text("🔄 Procesando...")
                final = Path(tmpdir) / "telegram.mp4"
                ff_cmd = [
                    FFMPEG, "-i", str(raw),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    "-y", str(final),
                ]
                rc, _, ff_err = await _run(ff_cmd, timeout=300)
                if rc != 0:
                    log.warning("ffmpeg error: %s", ff_err.decode()[-400:])
                    await msg.edit_text("❌ Error al procesar el video.")
                    return
                filepath = final

            size_mb = filepath.stat().st_size / 1_048_576
            log.info("Sending %s (%.1f MB) to chat %s", filepath.name, size_mb, update.effective_chat.id)

            if audio_only:
                await msg.edit_text(f"📤 Enviando ({size_mb:.1f} MB)…")
                with open(filepath, "rb") as f:
                    await update.message.reply_audio(f, title=raw.stem)
            else:
                # 1) Video reproducible inline (Telegram puede recomprimir).
                await msg.edit_text(f"📤 Enviando video ({size_mb:.1f} MB)…")
                with open(filepath, "rb") as f:
                    await update.message.reply_video(f, supports_streaming=True)
                # 2) Archivo MP4 sin recompresión, en calidad original.
                await msg.edit_text(f"📤 Enviando archivo MP4 ({size_mb:.1f} MB)…")
                with open(filepath, "rb") as f:
                    await update.message.reply_document(f, filename=f"{raw.stem}.mp4")

            await msg.delete()

        except TimeoutError:
            await msg.edit_text("❌ Timeout — el video tardó demasiado.")
        except Exception as e:
            log.exception("Error downloading %s", url)
            await msg.edit_text(f"❌ {e}")


async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    text = update.message.text or update.message.caption or ""
    match = URL_RE.search(text)
    if not match:
        return
    await _download(update, match.group(0), audio_only=False)


async def cmd_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    if not ctx.args:
        await update.message.reply_text("Uso: /audio <url>")
        return
    url = ctx.args[0]
    if not url.startswith("http"):
        await update.message.reply_text("❌ URL inválida.")
        return
    await _download(update, url, audio_only=True)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Manda cualquier link de Instagram, TikTok, YouTube Shorts, Twitter/X o Facebook y te descargo el video.\n\n"
        "/audio <url> — descargar solo el audio (MP3)"
    )


def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .base_url(LOCAL_API_URL)
        .local_mode(True)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("audio", cmd_audio))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_url))
    log.info("Reel bot starting (local API: %s)", LOCAL_API_URL)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
