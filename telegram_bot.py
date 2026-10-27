"""Canal Telegram: conecta o cérebro (arena.cerebro) ao bot criado no @BotFather.

    set TELEGRAM_BOT_TOKEN=...   (nunca coloque o token no código)
    python telegram_bot.py
"""

import asyncio
import logging
import os
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from arena.cerebro import Assistente

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # evita logar a URL com o token
log = logging.getLogger("telegram_bot")

assistente = Assistente()
log.info("Usando %s", assistente.gerar.nome)

BOAS_VINDAS = (
    "Olá! Sou o assistente virtual da Arena Vila Nova. Posso tirar dúvidas sobre horários, quadras e preços, "
    "reservas e cancelamento, pagamento, regras de uso, plano mensalista e campeonatos. Como posso ajudar?"
)


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assistente.limpar(str(update.effective_chat.id))
    await update.message.reply_text(BOAS_VINDAS)


async def mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    resposta = await asyncio.to_thread(assistente.responder, update.message.text, str(update.effective_chat.id))
    await update.message.reply_text(resposta)


async def nao_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Por enquanto só consigo responder mensagens de texto. Como posso ajudar?")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Defina a variável de ambiente TELEGRAM_BOT_TOKEN com o token do @BotFather.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "ajuda"], iniciar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, nao_texto))
    log.info("Bot no ar. Ctrl+C para parar.")
    app.run_polling()


if __name__ == "__main__":
    main()
