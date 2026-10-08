# poc-chatbot

PoC de um chatbot (**QuantumHound**, uma agência fictícia de viagem no tempo) construído por etapas. Cada etapa é uma branch, e cada branch tem um Pull Request em rascunho que mostra só o que mudou naquela etapa. Os PRs não são mergeados: a `main` fica apenas com este README, e a evolução se acompanha pelos PRs e pelas tags.

| Etapa | Branch | Tag | O que muda |
|-------|--------|-----|------------|
| 1 | `step-1-baseline` | `step-1` | Chatbot Streamlit com respostas fixas |
| 2 | `step-2-ollama` | `step-2` | Backend FastAPI que chama o Ollama local, com observabilidade no Datadog |

Para ver o código de uma etapa: `git checkout step-N` (ou `git checkout step-N-nome`). Para ver o que mudou, abra o PR da etapa.

## Arquitetura (etapa 2)

```
Navegador ──► chatbot (Streamlit :8501) ──► api (FastAPI :8000) ──► Ollama (no seu Mac, :11434)
                                                  │
                                                  └──► Datadog (LLM Observability, modo agentless)
```

- **chatbot:** interface de chat em Streamlit, em [chatbot/app/](chatbot/app/).
- **api:** backend FastAPI, em [backend_api/app/](backend_api/app/). Recebe o prompt, chama o Ollama e devolve a resposta.
- **Ollama:** roda **fora do Docker**, direto na sua máquina. Os containers o alcançam por `host.docker.internal`.
- **Datadog:** o backend roda sob `ddtrace-run` e envia traces de LLM direto à API do Datadog, sem Datadog Agent.

## Passo a passo do que foi feito

### Etapa 1: baseline (`step-1-baseline`)

1. Criado o app Streamlit em [chatbot/app/app.py](chatbot/app/app.py), com histórico de conversa guardado em `st.session_state`.
2. A função `generate_response` em [chatbot/app/chat_requests.py](chatbot/app/chat_requests.py) devolvia respostas fixas, escolhidas por palavras-chave (`hello`, `price`, `safe`, `how`, `where`). Nenhuma chamada de rede e nenhum LLM.
3. Criado o [Dockerfile](chatbot/app/Dockerfile) (`python:3.12-slim`) e o [docker-compose.yml](docker-compose.yml) para subir o chatbot.
4. O `.env` (que guarda chaves) fica fora do Git, pelo `.gitignore`.

### Etapa 2: backend com Ollama (`step-2-ollama`)

1. **Problema inicial:** o compose original usava as imagens `workshop-llm-obs-chatbot-base` e `workshop-llm-obs-backend-api-base`. Elas só existiam na máquina de quem montou o workshop, e o `docker compose up` falhava com `pull access denied`.
   **Solução:** troquei `image:` por `build:` nos dois serviços. Agora o Docker constrói as imagens a partir dos Dockerfiles do repositório.
2. **Ollama local no lugar do container.** Como o Ollama já estava instalado, removi o serviço `llm` e o volume `ollama_models` do compose. O backend usa `LLM_BASE_URL=http://host.docker.internal`.
3. **Backend FastAPI** em [backend_api/app/app.py](backend_api/app/app.py):
   - `POST /chat` recebe `{"prompt": "..."}` e devolve `{"success": true, "message": "..."}`.
   - `GET /health` devolve `{"status": "ok"}`.
   - A chamada ao Ollama usa `POST /api/chat`, com um prompt de sistema que mantém o personagem da QuantumHound.
   - A função que chama o modelo tem o decorator `@llm` do `ddtrace`, e `LLMObs.annotate` registra entrada e saída para o Datadog.
4. **Chatbot ligado ao backend.** `generate_response` agora faz `POST` em `{FASTAPI_BASE_URL}:{FASTAPI_PORT}/chat`. Se o backend falhar, devolve `{"success": false, "error": ...}`, que a interface já sabia exibir.
5. **Datadog (LLM Observability, agentless):** o serviço `backend_api` sobe com `ddtrace-run uvicorn ...` e as variáveis `DD_LLMOBS_ENABLED=1`, `DD_LLMOBS_ML_APP=quantumhound-chatbot`, `DD_LLMOBS_AGENTLESS_ENABLED=1`, `DD_API_KEY` e `DD_SITE`.
6. Adicionado o [.python-version](.python-version) (`3.12`), alinhado ao Dockerfile.

## Como rodar (etapa 2)

**Pré-requisitos:** Docker, Ollama rodando em `localhost:11434` e ao menos um modelo baixado (`ollama list`).

1. Crie um arquivo `.env` na raiz:

   ```env
   STREAMLIT_PORT=8501
   FASTAPI_PORT=8000
   FASTAPI_HOST=0.0.0.0

   # Ollama local
   LLM_PORT=11434
   LLM_MODEL=qwen2.5-coder:7b   # use um modelo que apareça em `ollama list`
   LLM_BASE_URL=http://host.docker.internal
   OPENAI_API_KEY=dummy         # exigida pelo compose, não é usada pelo Ollama

   # Datadog (opcional: sem chave, os traces não são enviados)
   DD_API_KEY=
   DD_SITE=datadoghq.com        # o site da sua conta Datadog
   DD_ENV=local
   ```

2. Suba os containers:

   ```bash
   docker compose up -d --build
   ```

3. Abra http://localhost:8501 e converse. Teste o backend direto:

   ```bash
   curl -X POST localhost:8000/chat -H 'content-type: application/json' -d '{"prompt":"hello"}'
   ```

4. Para ver os traces, abra **LLM Observability** no Datadog e procure a app `quantumhound-chatbot`.

## Problemas encontrados

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `pull access denied for workshop-llm-obs-...` | Imagens base não existem em nenhum registry | `build:` no compose |
| `no port specified: :<empty>` e avisos de variável não definida | Faltava o `.env` | Criar o `.env` acima |
| Chat não responde, ou só devolve texto padrão | Na etapa 1 o chat não usa LLM, só palavras-chave | Etapa 2 |
| `Span started with LLMObs disabled` nos logs do `api` | Compose sem as variáveis `DD_*` e sem `ddtrace-run` | Variáveis e `ddtrace-run` adicionados na etapa 2 |
| `external volume "ollama_models" not found` | Volume do Ollama containerizado, que não é mais usado | Volume removido do compose |

## Segurança

- O `.env` está no `.gitignore`. **Nunca commite `DD_API_KEY`.** O repositório é público.
- O modelo roda localmente. Nenhum prompt sai da sua máquina, a não ser os traces enviados ao Datadog quando há `DD_API_KEY`.

## Próximas etapas

Planejadas, ainda não implementadas. As etapas seguintes entram como novas branches `step-N-*`.
