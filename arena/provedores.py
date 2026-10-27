"""Provedores de LLM. Todos recebem (sistema, mensagens) e devolvem o texto da resposta.

Escolha com a variável PROVEDOR (claude, gemini ou ollama). Sem ela, usa o
primeiro que tiver chave configurada e, por último, o Ollama local.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable

Gerador = Callable[[str, list[dict]], str]

RECUSA = "Posso ajudar apenas com assuntos da Arena Vila Nova. Quer saber sobre horários, preços ou reservas?"


class ErroProvedor(Exception):
    pass


def claude() -> Gerador:
    import anthropic

    cliente = anthropic.Anthropic()
    modelo = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

    def gerar(sistema: str, mensagens: list[dict]) -> str:
        try:
            resposta = cliente.beta.messages.create(
                model=modelo,
                max_tokens=2048,
                system=sistema,
                messages=mensagens,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as e:
            raise ErroProvedor(str(e)) from e
        if resposta.stop_reason == "refusal":
            return RECUSA
        return "".join(b.text for b in resposta.content if b.type == "text")

    gerar.nome = f"claude ({modelo})"
    return gerar


def gemini() -> Gerador:
    from google import genai
    from google.genai import errors, types

    cliente = genai.Client()  # lê GEMINI_API_KEY
    modelo = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

    def gerar(sistema: str, mensagens: list[dict]) -> str:
        conteudo = [
            types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
            for m in mensagens
        ]
        try:
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=conteudo,
                config=types.GenerateContentConfig(system_instruction=sistema, max_output_tokens=2048),
            )
        except errors.APIError as e:
            raise ErroProvedor(str(e)) from e
        return resposta.text or ""

    gerar.nome = f"gemini ({modelo})"
    return gerar


def ollama() -> Gerador:
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat"
    modelo = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def gerar(sistema: str, mensagens: list[dict]) -> str:
        corpo = json.dumps(
            {
                "model": modelo,
                "messages": [{"role": "system", "content": sistema}] + mensagens,
                "stream": False,
                "options": {"temperature": 0.2},
            }
        ).encode()
        pedido = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=300) as r:
                return json.load(r)["message"]["content"]
        except (urllib.error.URLError, KeyError, TimeoutError) as e:
            raise ErroProvedor(f"Ollama indisponível em {url} ({e}). Ele está aberto e o modelo {modelo} foi baixado?") from e

    gerar.nome = f"ollama ({modelo})"
    return gerar


PROVEDORES = {"claude": claude, "gemini": gemini, "ollama": ollama}


def escolher() -> Gerador:
    nome = os.environ.get("PROVEDOR", "").lower()
    if not nome:
        nome = "claude" if os.environ.get("ANTHROPIC_API_KEY") else "gemini" if os.environ.get("GEMINI_API_KEY") else "ollama"
    if nome not in PROVEDORES:
        raise SystemExit(f"PROVEDOR inválido: {nome}. Use um de: {', '.join(PROVEDORES)}.")
    if nome == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("PROVEDOR=claude exige a variável ANTHROPIC_API_KEY.")
    if nome == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("PROVEDOR=gemini exige a variável GEMINI_API_KEY (grátis em aistudio.google.com/apikey).")
    return PROVEDORES[nome]()
