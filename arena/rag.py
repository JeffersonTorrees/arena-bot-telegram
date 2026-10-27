"""Indexação e busca na base de conhecimento da Arena Vila Nova.

Etapas: carrega os .md, lê o front matter, descarta documentos obsoletos,
corta por seção (##), remove trechos com instruções embutidas e faz a busca
com BM25 sobre texto normalizado (minúsculas, sem acento, radical simples).
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent / "base-de-conhecimento" / "base-de-conhecimento"

# Precedência definida nas diretrizes: política > tabela de preços > demais > FAQ.
PRECEDENCIA = {"politica": 0, "comercial": 1, "institucional": 2, "regras": 2, "atendimento": 9}

# Frases típicas de prompt injection. Seções que as contenham não entram no índice.
PADROES_INJECAO = [
    r"ignor[ea]\w*\s+(as\s+|todas\s+as\s+)?(regras|instru)",
    r"instru[cç][aã]o\s+para\s+(o\s+)?assistente",
    r"assistentes?\s+virtua",
    r"esque[cç]a\s+(suas|as)\s+regras",
    r"ignore\s+(all|previous|the)",
    r"cupom",
]

STOPWORDS = set(
    "a o as os e de da do das dos em no na nos nas um uma uns umas para por pra pro com sem "
    "que se ao aos eu voce voces vcs me te meu minha seu sua isso esse essa este esta ja "
    "mais muito tem ter ha qual quais quanto quanta como onde quando the e ou mesmo "
    "posso pode podem da dar ser sao foi vai vou nao sim".split()
)

# Expansão de consulta: palavras do cliente -> vocabulário da base.
SINONIMOS = {
    "desmarcar": "cancelamento cancelar gratuito",
    "desmarco": "cancelamento cancelar gratuito",
    "nada": "gratuito custo",
    "gratis": "gratuito custo",
    "jogo": "reserva",
    "aqui": "telegram atendimento",
    "chover": "chuva",
    "chove": "chuva",
    "chuvoso": "chuva",
    "multa": "sinal comparecimento devolvido cobranca",
    "aparecer": "comparecimento comparecer",
    "faltar": "comparecimento falta",
    "abrem": "horario funcionamento",
    "abre": "horario funcionamento",
    "fecha": "horario funcionamento",
    "fecham": "horario funcionamento",
    "horas": "horario",
    "cabem": "capacidade pessoas",
    "cabe": "capacidade pessoas",
    "custa": "preco tabela valor",
    "custo": "preco tabela valor",
    "quanto": "preco valor",
    "trava": "chuteira calcado",
    "travas": "chuteira calcado",
    "pago": "pagamento",
    "pagar": "pagamento",
    "devolta": "devolvido",
    "reembolso": "devolvido",
    "telegram": "telegram atendimento",
    "chat": "telegram atendimento",
    "dinheiro": "dinheiro pagamento",
    "mensal": "mensalista",
    "aniversario": "eventos",
    "festa": "eventos aniversario",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def radical(palavra: str) -> str:
    # Radical grosseiro, suficiente para casar cancelar/cancelamento, reserva/reservas.
    return palavra[:6] if len(palavra) > 6 else palavra.rstrip("s")


def tokens(texto: str, expandir: bool = False) -> list[str]:
    palavras = [p for p in re.findall(r"[a-z0-9]+", normalizar(texto)) if p not in STOPWORDS]
    if expandir:
        palavras += [s for p in palavras for s in SINONIMOS.get(p, "").split()]
    return [radical(p) for p in palavras]


@dataclass
class Trecho:
    arquivo: str
    documento: str  # título do documento, ex.: "Política de reservas e cancelamento (versão 2.0)"
    secao: str
    texto: str
    area: str
    versao: str
    termos: Counter = field(default_factory=Counter)

    @property
    def fonte(self) -> str:
        return f"{self.documento} > {self.secao}"


def _front_matter(conteudo: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", conteudo, re.S)
    if not m:
        return {}, conteudo
    meta = dict(
        (k.strip(), v.strip()) for k, v in (linha.split(":", 1) for linha in m.group(1).splitlines() if ":" in linha)
    )
    return meta, conteudo[m.end():]


def _tem_injecao(texto: str) -> bool:
    t = normalizar(texto)
    return any(re.search(normalizar(p), t) for p in PADROES_INJECAO)


def carregar_trechos(base_dir: Path = BASE_DIR) -> list[Trecho]:
    trechos: list[Trecho] = []
    for caminho in sorted(base_dir.glob("*.md")):
        meta, corpo = _front_matter(caminho.read_text(encoding="utf-8"))
        if meta.get("status", "").lower() != "vigente":
            log.info("Ignorando %s (status=%s)", caminho.name, meta.get("status"))
            continue

        titulo = re.search(r"^#\s+(.+)$", corpo, re.M)
        documento = titulo.group(1).strip() if titulo else caminho.stem

        for bloco in re.split(r"^(?=##\s)", corpo, flags=re.M):
            m = re.match(r"##\s+(.+)\n", bloco)
            if not m:
                continue  # cabeçalho do documento antes da primeira seção
            secao, texto = m.group(1).strip(), bloco[m.end():].strip()
            if not texto:
                continue
            if _tem_injecao(secao + "\n" + texto):
                log.warning("Trecho descartado por conter instrução embutida: %s > %s", caminho.name, secao)
                continue
            trechos.append(
                Trecho(
                    arquivo=caminho.name,
                    documento=documento,
                    secao=secao,
                    texto=texto,
                    area=meta.get("area", ""),
                    versao=meta.get("versao", ""),
                    termos=Counter(tokens(f"{documento} {secao} {secao} {texto}")),
                )
            )
    return trechos


class Indice:
    def __init__(self, trechos: list[Trecho], k1: float = 1.5, b: float = 0.75):
        self.trechos = trechos
        self.k1, self.b = k1, b
        self.media = sum(sum(t.termos.values()) for t in trechos) / max(len(trechos), 1)
        df = Counter(termo for t in trechos for termo in t.termos)
        n = len(trechos)
        self.idf = {termo: math.log(1 + (n - f + 0.5) / (f + 0.5)) for termo, f in df.items()}

    def _bm25(self, consulta: list[str], t: Trecho) -> float:
        tam = sum(t.termos.values())
        score = 0.0
        for termo in set(consulta):
            f = t.termos.get(termo, 0)
            if f:
                score += self.idf[termo] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * tam / self.media))
        return score

    def buscar(self, pergunta: str, k: int = 5, minimo: float = 1.0) -> list[tuple[Trecho, float]]:
        consulta = tokens(pergunta, expandir=True)
        pontuados = [(t, self._bm25(consulta, t)) for t in self.trechos]
        melhores = sorted((p for p in pontuados if p[1] >= minimo), key=lambda p: -p[1])[:k]
        # Na ordem final, a fonte de maior precedência aparece primeiro.
        return sorted(melhores, key=lambda p: (PRECEDENCIA.get(p[0].area, 5), -p[1]))

    def secao(self, arquivo_prefixo: str, secao: str) -> Trecho | None:
        return next(
            (t for t in self.trechos if t.arquivo.startswith(arquivo_prefixo) and t.secao == secao), None
        )
