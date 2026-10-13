# poc-chatbot

PoC de um chatbot (**QuantumHound**, uma agência fictícia de viagem no tempo) construído por etapas. Cada etapa é uma branch, e cada branch tem um Pull Request em rascunho que mostra só o que mudou naquela etapa. Os PRs não são mergeados: a `main` fica apenas com o README inicial, e a evolução se acompanha pelos PRs.

| Etapa | Branch | O que muda |
|-------|--------|------------|
| 1 | `step-1-baseline` | Chatbot Streamlit com respostas fixas |
| 2 | `step-2-ollama` | Backend FastAPI que chama o Ollama (do Mac), com observabilidade no Datadog |
| 3 | `step-3` | Ollama em container Docker e backend via cliente OpenAI, com um bug proposital para investigar |
| 4 (esta) | `step-4-rag` | System prompt configurável e bug do modelo corrigido. Base para o RAG, que ainda **não** foi implementado |

Para ver o código de uma etapa: `git checkout <branch>`. Para ver o que mudou, abra o PR da etapa. Cada branch tem o README com as instruções da própria etapa.

## Estado da etapa 4

A etapa 4 prepara o terreno para o RAG, mas **ainda não há RAG**. O código diz isso: em [utils/llm.py](backend_api/app/utils/llm.py), `ask_the_llm` é uma chamada direta ao LLM ("Not RAG-enabled, just a straightforward LLM call"). Não existe base de conhecimento, busca por similaridade nem embeddings. O que existe é um system prompt carregado de arquivo e o modelo vindo da configuração.

## Arquitetura

```
Navegador ──► chatbot (Streamlit :8501) ──GET /ask──► api (FastAPI :8000) ──► llm (Ollama, container locallama :11434)
                                                            │
                                                            └──► Datadog (LLM Observability, modo agentless)
```

- **chatbot:** interface de chat em Streamlit, em [chatbot/app/](chatbot/app/).
- **api:** backend FastAPI, em [backend_api/app/](backend_api/app/). Expõe `GET /ask?prompt=...` e `GET /health`.
- **llm:** Ollama em container (`ollama/ollama`), com o modelo guardado no volume `ollama_models`.
- **Datadog:** o backend roda sob `ddtrace-run` e envia direto à API do Datadog, sem Datadog Agent. [app.py](backend_api/app/app.py) tem dois marcadores `# add ddtrace ... here`, ainda sem código: não há instrumentação explícita do LLM Observability nesta etapa.

## O que mudou em relação à etapa 3

| Assunto | Etapa 3 | Etapa 4 |
|---------|---------|---------|
| Nome do modelo | Fixo no código com typo (`lama3.2:1b`), bug proposital | `config.LLM_MODEL`, que vem do `LLM_MODEL` do `.env` |
| Mensagens enviadas ao modelo | Só a do usuário | Mensagem de sistema (system prompt) + mensagem do usuário |
| System prompt | Não havia | Lido de arquivo por [utils/system_prompt.py](backend_api/app/utils/system_prompt.py), no caminho `config.SYSTEM_PROMPT_PATH` |
| Prompts disponíveis | Nenhum | [system-prompt.txt](backend_api/app/prompts/system-prompt.txt) (padrão, curto), [system-prompt-concise.txt](backend_api/app/prompts/system-prompt-concise.txt) e [system-prompt-verboso.txt](backend_api/app/prompts/system-prompt-verboso.txt) |
| `GET /health` | Texto `OK` | JSON `{"status": "ok"}` |
| Chatbot | Spinner "Considering your request..." | Spinner avisa que pode demorar um minuto, pois o modelo roda em CPU |
| Compose | `external: true` no volume `ollama_models` (falha: o volume não existe) | Volume gerenciado pelo compose. O `chatbot_app` recebe `FASTAPI_PORT` e `FASTAPI_BASE_URL` e depende do `backend_api`. O `llm` recebe `LLM_MODEL` |

## Passo a passo do que foi feito na etapa 4

1. **Corrigido o modelo fixo.** `ask_the_llm` passou a usar `config.LLM_MODEL`. Agora trocar o modelo no `.env` tem efeito.
2. **System prompt em arquivo.** [system_prompt.py](backend_api/app/utils/system_prompt.py) lê o arquivo apontado por `config.SYSTEM_PROMPT_PATH`, e `ask_the_llm` envia o texto como mensagem de sistema. O padrão é `prompts/system-prompt.txt`, definido em [config.py](backend_api/app/config.py). O prompt define o personagem: um concierge de viagem no tempo da QuantumHound.
3. **Duas variantes do prompt**, de tamanhos bem diferentes (cerca de 1,4 KB e 9,6 KB), para comparar. Para usar uma delas, mude o default em `config.py`. O compose ainda **não** repassa `SYSTEM_PROMPT_PATH` ao container, então definir a variável no `.env` não basta: adicione-a ao `environment` do `backend_api` no [docker-compose.yml](docker-compose.yml).
4. **Compose:** volume `ollama_models` gerenciado pelo compose (sem `external`), e variáveis que faltavam no `chatbot_app` e no `llm`.
5. **Healthcheck em JSON** e spinner mais honesto no chatbot.

## Como rodar

**Pré-requisito:** Docker.

1. Crie um arquivo `.env` na raiz:

   ```env
   STREAMLIT_PORT=8501
   FASTAPI_PORT=8000
   FASTAPI_HOST=0.0.0.0

   # Ollama em container
   LLM_PORT=11434
   LLM_MODEL=llama3.2:1b        # precisa existir no Ollama do container
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

4. Abra http://localhost:8501 e converse. Teste o backend direto (a primeira resposta pode levar um tempo):

   ```bash
   curl "localhost:8000/ask?prompt=ola"
   ```

## Problemas encontrados

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `external volume "ollama_models" not found` ao subir | O compose esperava um volume criado à mão (`external: true`) | Volume gerenciado pelo compose, como nesta etapa. Se vier de outra branch, remova `external` e `name` do volume |
| `FileNotFoundError: [Errno 2] No such file or directory: ''` em `system_prompt.py` | `config.SYSTEM_PROMPT_PATH` vazio. O `Config` devolve `""` para campos que não existem | Definir o campo em `config.py`, como nesta etapa |
| `model '...' not found` (404 do Ollama) e 500 no chat | O modelo do `LLM_MODEL` não existe no Ollama **do container**. O Ollama do Mac tem outros modelos | `docker exec locallama ollama list` e usar um nome exato, ou `ollama pull` |
| `Connection refused` ao chamar `api:8000` | O container `api` caiu na subida (por exemplo, dependência faltando) | `docker logs api` |
| `SSLCertVerificationError`, ou `ollama pull` falhando | Proxy da empresa intercepta o HTTPS | Montar `corp-ca.pem` e usar `SSL_CERT_FILE` e `REQUESTS_CA_BUNDLE` |
| `failed to send, dropping N traces to http://localhost:8126` nos logs | O APM (aba Traces) precisa de um Datadog Agent, que não existe aqui | Ignorar: o LLM Observability em modo agentless não depende dele |
| A chamada ao modelo não aparece como span de LLM no LLM Observability | Nos testes, o `ddtrace` não gerou o span para o cliente `openai` apontando para o Ollama (`base_url` que não é da OpenAI). Um span manual foi enviado normalmente | Instrumentar `ask_the_llm` com `@llm(model_provider="ollama")` e `LLMObs.annotate`. É o que os marcadores `# add ddtrace ... here` em `app.py` deixam em aberto |

## Segurança

- O `.env` e o `corp-ca.pem` estão no `.gitignore`. **Nunca commite `DD_API_KEY`.** O repositório é público.
- O Ollama não tem autenticação: por isso a porta publicada fica só na loopback (`127.0.0.1:11435`).
- Não use `DD_TRACE_DEBUG=true` com a chave real: o modo debug imprime o cabeçalho `dd-api-key` completo nos logs.
- O modelo roda localmente. Nenhum prompt sai da sua máquina, a não ser os spans enviados ao Datadog quando há `DD_API_KEY`.

## Próximas etapas

O RAG propriamente dito: uma base de conhecimento, busca de trechos relevantes e a injeção deles no prompt. Ainda não implementado.
