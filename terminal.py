"""Testa o cérebro no terminal, antes de ligar o Telegram.

    python terminal.py            # conversa interativa
    python terminal.py --teste    # roda as 16 perguntas públicas e salva resultados-testes.md
"""

import json
import logging
import sys
from pathlib import Path

from arena.cerebro import Assistente

RAIZ = Path(__file__).resolve().parent


def conversar(assistente: Assistente) -> None:
    print("Assistente Arena Vila Nova (terminal). Digite 'sair' para encerrar, '/limpar' para zerar o histórico.\n")
    while True:
        try:
            pergunta = input("você> ")
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.strip().lower() in {"sair", "exit", "quit"}:
            break
        if pergunta.strip() == "/limpar":
            assistente.limpar("terminal")
            continue
        print(f"bot> {assistente.responder(pergunta)}\n")


def testar(assistente: Assistente) -> None:
    perguntas = json.loads((RAIZ / "perguntas-publicas.json").read_text(encoding="utf-8"))
    linhas = [
        f"# Resultados dos testes (modelo {assistente.gerar.nome})\n",
        "| # | Pergunta | Esperado | Resposta do bot | OK? | Etapa do erro |",
        "|---|---|---|---|---|---|",
    ]
    for q in perguntas:
        # Cada pergunta numa conversa nova, para um teste não influenciar o outro.
        resposta = assistente.responder(q["pergunta"], conversa=q["id"])
        print(f"{q['id']} [{q['categoria']}] {q['pergunta']}\n    -> {resposta}\n")
        resposta_md = resposta.replace("|", "\\|").replace("\n", " ")
        linhas.append(f"| {q['id']} | {q['pergunta']} | {q['categoria']} | {resposta_md} |  |  |")
    saida = RAIZ / "resultados-testes.md"
    saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"Resultados salvos em {saida.name}. Preencha as colunas 'OK?' e 'Etapa do erro'.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    assistente = Assistente()
    print(f"Usando {assistente.gerar.nome}\n")
    testar(assistente) if "--teste" in sys.argv else conversar(assistente)
