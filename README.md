# poc-chatbot

PoC de um chatbot (**QuantumHound**, uma agência fictícia de viagem no tempo) construído por etapas. Cada etapa é uma branch, e cada branch tem um Pull Request em rascunho que mostra só o que mudou naquela etapa. Os PRs não são mergeados: a `main` fica apenas com o README inicial, e a evolução se acompanha pelos PRs e pelas tags.

| Etapa | Branch | O que muda |
|-------|--------|------------|
| 1 | `step-1-baseline` | Chatbot Streamlit com respostas fixas |
| 2 | `step-2-ollama` | Backend FastAPI que chama o Ollama (do Mac), com observabilidade no Datadog |
| 3 (esta) | `step-3` | Ollama em container Docker e backend via cliente OpenAI, com um bug proposital para investigar no Datadog |

Para ver o código de uma etapa: `git checkout <branch>`. Para ver o que mudou, abra o PR da etapa. Cada branch tem o README com as instruções da própria etapa.

## Arquitetura (etapa 3)

```
Navegador ──► chatbot (Streamlit :8501) ──GET /ask──► api (FastAPI :8000) ──► llm (Ollama, container locallama :11434)
                                                            │
                                                            └──► Datadog (LLM Observability, modo agentless)
```

- **chatbot:** interface de chat em Streamlit, em [chatbot/app/](chatbot/app/).
- **api:** backend FastAPI, em [backend_api/app/](backend_api/app/). Expõe `GET /ask?prompt=...` e `GET /health`.
- **llm:** Ollama em container (`ollama/ollama`), com o modelo guardado no volume `ollama_models`.
- **Datadog:** o backend roda sob `ddtrace-run` e envia direto à API do Datadog, sem Datadog Agent. Nesta etapa a chamada ao modelo **não** tem instrumentação explícita (veja "Problemas encontrados").

## O que mudou em relação à etapa 2

| Assunto | Etapa 2 | Etapa 3 |
|---------|---------|---------|
| Ollama | Instalado no Mac, acessado por `host.docker.internal` | Container `locallama` no compose, modelo no volume `ollama_models` |
| `LLM_BASE_URL` | `http://host.docker.internal` | `http://locallama` |
| Endpoint do backend | `POST /chat` (JSON) | `GET /ask?prompt=...` (texto) |
| Chamada ao modelo | `requests` direto na API nativa do Ollama (`/api/chat`) | Cliente `openai` na API compatível do Ollama (`/v1`), em [utils/llm.py](backend_api/app/utils/llm.py) |
| Configuração | Variáveis lidas em `app.py` | Classe `Config` em [config.py](backend_api/app/config.py) |
| Erro mostrado no chat | `Backend error: ...` | `API Error ...: See Datadog trace for details`, convidando a investigar no Datadog |
| Dockerfile do backend | Só instala dependências | Instala `procps` e `coreutils`, e define o `CMD` do `uvicorn` |
| Porta do Ollama no Mac | Usa a do Ollama local | `127.0.0.1:11435`, só na loopback, para não colidir com o Ollama local |
| Instrumentação do Datadog | `@llm` e `LLMObs.annotate` em `app.py` | Nenhuma explícita: só a auto-instrumentação do `ddtrace` |
| Nome do modelo | Vem do `LLM_MODEL` | Fixo no código, em `utils/llm.py` (bug proposital) |

## Passo a passo do que foi feito na etapa 3

1. **Ollama em Docker.** Voltou o serviço `llm` ao [docker-compose.yml](docker-compose.yml), com limite de 4GiB de memória e o volume `ollama_models`. O `backend_api` passou a depender dele (`depends_on`). O modelo é baixado dentro do container:

   ```bash
   docker exec locallama ollama pull llama3.2:1b
   ```

2. **Porta do Ollama só na loopback.** O Ollama não tem autenticação. Publicá-lo em `0.0.0.0` o deixaria acessível a qualquer máquina da rede. A porta ficou `127.0.0.1:11435:11434`. O `11435` evita o conflito com o Ollama local, que já usa `11434`. O backend não usa essa porta: ele fala com `locallama:11434` pela rede do Docker.
3. **Backend com cliente OpenAI.** O [utils/llm.py](backend_api/app/utils/llm.py) cria um cliente `openai` apontando para `{LLM_BASE_URL}:{LLM_PORT}/v1`, o endpoint compatível do Ollama. [app.py](backend_api/app/app.py) expõe `GET /ask` e `GET /health`.
4. **Chatbot chamando `/ask`.** [chat_requests.py](chatbot/app/chat_requests.py) faz `GET` em `/ask` e, se o status não for 200, mostra `API Error (Status N): See Datadog trace for details`.
5. **Bug proposital.** Em [utils/llm.py](backend_api/app/utils/llm.py) o modelo está escrito direto no código, com typo (`lama3.2:1b`), em vez de vir de `config.LLM_MODEL`. O Ollama responde 404, o backend devolve 500 e o chat mostra `API Error (Status 500): See Datadog trace for details`. O exercício é encontrar a causa pelo Datadog.

## Como rodar (etapa 3)

**Pré-requisito:** Docker.

1. Crie um arquivo `.env` na raiz:

   ```env
   STREAMLIT_PORT=8501
   FASTAPI_PORT=8000
   FASTAPI_HOST=0.0.0.0

   # Ollama em container
   LLM_PORT=11434
   LLM_MODEL=llama3.2:1b
   LLM_BASE_URL=http://locallama
   OPENAI_API_KEY=dummy         # exigida pelo cliente openai, o Ollama não a valida

   # Datadog (opcional: sem chave, os traces não são enviados)
   DD_API_KEY=
   DD_SITE=datadoghq.com        # o site da sua conta Datadog
   DD_ENV=local
   ```

2. Gere o `corp-ca.pem` com os certificados do seu Mac. O compose o monta no `backend_api` (envio ao Datadog) e no `llm` (download do modelo), para funcionar atrás de proxy corporativo que intercepta o HTTPS. O arquivo é local e está no `.gitignore`. Gere-o **antes** do `docker compose up`: se não existir, o Docker cria uma pasta com esse nome.

   ```bash
   security find-certificate -a -p /Library/Keychains/System.keychain /System/Library/Keychains/SystemRootCertificates.keychain > corp-ca.pem
   ```

3. Suba os containers e baixe o modelo:

   ```bash
   docker compose up -d --build
   docker exec locallama ollama pull llama3.2:1b
   ```

4. Abra http://localhost:8501 e converse. Teste o backend direto:

   ```bash
   curl "localhost:8000/ask?prompt=ola"
   ```

5. Para ver os traces, abra **LLM Observability** no Datadog, na conta a que a `DD_API_KEY` pertence, e procure a app `quantumhound-chatbot` (período "Past 4 hours", filtro `env` igual ao seu `DD_ENV`).

## Problemas encontrados

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `Connection refused` ao chamar `api:8000` | O container `api` caía na subida: `ModuleNotFoundError: No module named 'openai'` | Adicionar `openai` e `pydantic-settings` ao [requirements.txt](backend_api/app/requirements.txt) e reconstruir (`docker compose up -d --build backend_api`) |
| `Internal Server Error` (500) e `model '...' not found` nos logs | O nome do modelo não existe no Ollama. Pode ser typo (`lama` em vez de `llama`) ou modelo não baixado | Conferir com `docker exec locallama ollama list` e usar o nome exato |
| Mudar `LLM_MODEL` no `config.py` ou no `.env` não surte efeito | O nome do modelo está fixo em `utils/llm.py`, e não vem de `config.LLM_MODEL` | Usar `config.LLM_MODEL` na chamada |
| `ports are not available: ... 127.0.0.1:11434: address already in use` | O Ollama local do Mac já usa a 11434 | Publicar o container em outra porta (`11435`) |
| `SSLCertVerificationError` nos logs, ou `ollama pull` falhando | Proxy da empresa intercepta o HTTPS | Montar `corp-ca.pem` e usar `SSL_CERT_FILE` e `REQUESTS_CA_BUNDLE` |
| A chamada ao modelo não aparece como span de LLM no LLM Observability, mesmo com chave e rede válidas | Nos testes, o `ddtrace` não gerou o span de LLM para o cliente `openai` apontando para o Ollama (`base_url` que não é da OpenAI). Um span manual foi enviado normalmente | Instrumentar `ask_the_llm` com `@llm(model_provider="ollama")` e `LLMObs.annotate`, como na etapa 2 |
| `failed to send, dropping N traces to http://localhost:8126` nos logs | O APM (aba Traces) precisa de um Datadog Agent, que não existe aqui | Ignorar: o LLM Observability em modo agentless não depende dele |
| Não vejo os dados no Datadog | Conta ou site errados, ou período curto | Usar a conta da `DD_API_KEY`, o `DD_SITE` dela e ampliar o período |

## Segurança

- O `.env` e o `corp-ca.pem` estão no `.gitignore`. **Nunca commite `DD_API_KEY`.** O repositório é público.
- O Ollama não tem autenticação: por isso a porta fica só na loopback.
- Não use `DD_TRACE_DEBUG=true` com a chave real: o modo debug imprime o cabeçalho `dd-api-key` completo nos logs.
- O modelo roda localmente. Nenhum prompt sai da sua máquina, a não ser os spans enviados ao Datadog quando há `DD_API_KEY`.

## Próximas etapas

Planejadas, ainda não implementadas. As etapas seguintes entram como novas branches.
