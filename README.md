# Assistente da Arena Vila Nova (Telegram + RAG)

Bot de atendimento que responde **somente** com o que está na base de conhecimento, consultada a cada pergunta.

## Estrutura

```
arena/rag.py       busca: carrega a base, descarta obsoletos, corta por seção, filtra injeção, BM25
arena/cerebro.py   prompt + filtros (dados sensíveis, histórico curto)
arena/provedores.py  chamada ao modelo: Claude, Gemini ou Ollama (local)
terminal.py        "primeiro o cérebro": conversa no terminal e roda as 16 perguntas públicas
telegram_bot.py    "depois o canal": liga o cérebro ao bot do @BotFather
```

## Como rodar

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Escolha um cérebro (só precisa de um):

| Opção | Custo | Como configurar |
|---|---|---|
| **Gemini** | grátis (conta Google, sem cartão) | Gere a chave em aistudio.google.com/apikey e rode `$env:GEMINI_API_KEY = "..."` |
| **Ollama** (local) | grátis, sem chave | Instale em ollama.com, rode `ollama pull qwen2.5:7b` e deixe o Ollama aberto |
| **Claude** | pago | `$env:ANTHROPIC_API_KEY = "..."` |

Sem `PROVEDOR`, o bot usa o primeiro que tiver chave e, se não houver nenhuma, o Ollama. Para forçar uma opção, use `$env:PROVEDOR = "gemini"` (ou `claude`, ou `ollama`).

```powershell
python terminal.py                         # conversa no terminal
python terminal.py --teste                 # 16 perguntas -> resultados-testes.md

$env:TELEGRAM_BOT_TOKEN = "token-do-botfather"
python telegram_bot.py
```

## Como cada armadilha é tratada

| Armadilha | Defesa |
|---|---|
| `03b-reservas-v1-obsoleta.md` (sinal de 50%, cancelamento até 2h) | Front matter `status: obsoleta` → o documento nem entra no índice. |
| FAQ diz "cancelar até 12h"; a política vigente diz 24h | Trechos ordenados por precedência (política > preços > FAQ), FAQ marcado como "apenas apoio" e regra de precedência no prompt. |
| "Aviso interno" no FAQ manda divulgar o cupom ARENA50 | A seção é descartada na indexação (padrões de injeção) e o prompt trata trechos como informação, não ordens. |
| Pergunta sem resposta na base (ex.: estacionamento) | O prompt proíbe inventar; manda dizer que não consta e passar telefone e horário da recepção, lidos da própria base. |
| Fora do escopo / "esqueça suas regras" | O prompt recusa e volta ao assunto da arena; a pergunta do usuário vai delimitada em `<pergunta_do_cliente>`. |
| CPF, cartão ou senha na mensagem | Uma regex intercepta a mensagem **antes** do modelo: ela não é enviada nem guardada, e o bot avisa o cliente. |
| Reservar pelo chat | O bot orienta o site ou a recepção. |

Histórico: só as últimas 3 trocas por conversa, em memória e sem os documentos. Nada é gravado em disco.
