# poc-chatbot

PoC de um chatbot (**QuantumHound**, uma agência fictícia de viagem no tempo) construído por etapas. Cada etapa é uma branch, e cada branch tem um Pull Request em rascunho que mostra só o que mudou naquela etapa. Os PRs não são mergeados: a `main` fica apenas com o README inicial, e a evolução se acompanha pelos PRs.

| Etapa | Branch | O que muda |
|-------|--------|------------|
| 1 | `step-1-baseline` | Chatbot Streamlit com respostas fixas |
| 2 | `step-2-ollama` | Backend FastAPI que chama o Ollama (do Mac), com observabilidade no Datadog |
| 3 | `step-3` | Ollama em container Docker e backend via cliente OpenAI, com um bug proposital para investigar |
| 4 (esta) | `step-4-rag` | Pontapé inicial do RAG: system prompt configurável, bug do modelo corrigido e a **ingestão** da base de conhecimento (chunks, embeddings e ChromaDB). A busca e a injeção no prompt ficam para a próxima etapa |

Para ver o código de uma etapa: `git checkout <branch>`. Para ver o que mudou, abra o PR da etapa. Cada branch tem o README com as instruções da própria etapa.

## Estado da etapa 4

A etapa 4 é o pontapé inicial do RAG. Ela entrega a primeira metade: a **ingestão**. O [kb-service/](kb-service/) quebra os documentos de `kb-data/` em chunks, gera embeddings com o `nomic-embed-text` e os grava no ChromaDB. O [README do kb-service](kb-service/README.md) explica os conceitos (chunk, embedding, vetor) e o passo a passo.

A segunda metade, a **consulta**, ainda não existe. Em [utils/llm.py](backend_api/app/utils/llm.py), `ask_the_llm` continua sendo uma chamada direta ao LLM ("Not RAG-enabled, just a straightforward LLM call"): o backend não consulta o Chroma. Também há um system prompt carregado de arquivo e o modelo vindo da configuração.

### O que esta etapa cobre e o que não cobre

| Cobre | Não cobre |
|---|---|
| System prompt configurável, lido de arquivo (`SYSTEM_PROMPT_PATH`), com duas variantes para comparar | Busca no Chroma: nenhuma pergunta do chat gera consulta à base |
| Ingestão dos documentos de `kb-data/` (`.md`, `.txt` e `.json`) em chunks, com quebra fixa de 500 caracteres ou por sentenças | Injeção dos trechos recuperados no prompt do LLM |
| Embeddings com o `nomic-embed-text`, rodando no Ollama do container `text-embedder` | Integração do `backend_api` com o Chroma ou com o `kb_service` |
| Armazenamento dos vetores no ChromaDB, uma coleção por arquivo, persistido em `./chroma_data` | Ingestão incremental: cada execução apaga todas as coleções e recria tudo |
| Spans de LLM Observability na ingestão (workflow, embedding e tool), enviados ao Datadog em modo agentless | Input e output nos spans de embedding e tool (falta `LLMObs.annotate`) |
| Testes unitários da ingestão em [kb-service/test_ingest_documents.py](kb-service/test_ingest_documents.py) | Avaliação da qualidade da recuperação, ou ajuste do tamanho dos chunks |
| Suporte a proxy corporativo (`corp-ca.pem`) nos containers que acessam a internet | Ingestão automática: ela é manual, com `docker exec` (veja o README do kb-service) |

Resumindo: ao fim desta etapa, a base de conhecimento existe e está populada, mas o chatbot ainda não a usa.

## Arquitetura

```
Navegador ──► chatbot (Streamlit :8501) ──GET /ask──► api (FastAPI :8000) ──► llm (Ollama, container locallama :11434)
                                                            │
                                                            └──► Datadog (LLM Observability, modo agentless)

Ingestão (manual, fora do caminho do chat):
kb-data/ ──► kb_service ──► text_embedder (Ollama, nomic-embed-text) ──► vetores ──► ChromaDB (./chroma_data)
```

- **chatbot:** interface de chat em Streamlit, em [chatbot/app/](chatbot/app/).
- **api:** backend FastAPI, em [backend_api/app/](backend_api/app/). Expõe `GET /ask?prompt=...` e `GET /health`.
- **llm:** Ollama em container (`ollama/ollama`), com o modelo guardado no volume `ollama_models`.
- **text_embedder:** segundo Ollama, só para embeddings, com o modelo `nomic-embed-text:v1.5`. Compartilha o volume `ollama_models` com o `llm`.
- **vector_store:** servidor ChromaDB, com dados em `./chroma_data`. O `kb_service` grava nessa pasta com `PersistentClient`, sem passar por esse servidor, e o `backend_api` ainda não o consulta.
- **kb_service:** roda a ingestão em [kb-service/](kb-service/). O container fica parado em `tail -f /dev/null`, e o script é executado com `docker exec`.
- **Datadog:** o backend roda sob `ddtrace-run` e envia direto à API do Datadog, sem Datadog Agent. [app.py](backend_api/app/app.py) tem dois marcadores `# add ddtrace ... here`, ainda sem código: não há instrumentação explícita do LLM Observability nesta etapa.

## O que mudou em relação à etapa 3

| Assunto | Etapa 3 | Etapa 4 |
|---------|---------|---------|
| Nome do modelo | Fixo no código com typo (`lama3.2:1b`), bug proposital | `config.LLM_MODEL`, que vem do `LLM_MODEL` do `.env` |
| Mensagens enviadas ao modelo | Só a do usuário | Mensagem de sistema (system prompt) + mensagem do usuário |
| System prompt | Não havia | Lido de arquivo por [utils/system_prompt.py](backend_api/app/utils/system_prompt.py), no caminho `config.SYSTEM_PROMPT_PATH` |
| Prompts disponíveis | Nenhum | [system-prompt-concise.txt](backend_api/app/prompts/system-prompt-concise.txt) (padrão), [system-prompt.txt](backend_api/app/prompts/system-prompt.txt) (curto) e [system-prompt-verboso.txt](backend_api/app/prompts/system-prompt-verboso.txt) |
| `GET /health` | Texto `OK` | JSON `{"status": "ok"}` |
| Chatbot | Spinner "Considering your request..." | Spinner avisa que pode demorar um minuto, pois o modelo roda em CPU |
| Compose | `external: true` no volume `ollama_models` (falha: o volume não existe) | Volume gerenciado pelo compose. O `chatbot_app` recebe `FASTAPI_PORT` e `FASTAPI_BASE_URL` e depende do `backend_api`. O `llm` recebe `LLM_MODEL` |

## Passo a passo do que foi feito na etapa 4

1. **Corrigido o modelo fixo.** `ask_the_llm` passou a usar `config.LLM_MODEL`. Agora trocar o modelo no `.env` tem efeito.
2. **System prompt em arquivo.** [system_prompt.py](backend_api/app/utils/system_prompt.py) lê o arquivo apontado por `config.SYSTEM_PROMPT_PATH`, e `ask_the_llm` envia o texto como mensagem de sistema. O caminho está fixo em [config.py](backend_api/app/config.py) e hoje aponta para `./prompts/system-prompt-concise.txt`. O prompt define o personagem: um concierge de viagem no tempo da QuantumHound.
3. **Três variantes do prompt**, de tamanhos bem diferentes (de 288 B a 9,6 KB), para comparar. Para trocar de prompt, edite `SYSTEM_PROMPT_PATH` em `config.py`. O valor é fixo no código: a variável de ambiente `SYSTEM_PROMPT_PATH` não é lida.
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

   # Embeddings e vetores (etapa 4)
   OLLAMA_DEFAULT_PORT=11434    # porta interna do Ollama nos containers
   EMBED_PORT=11436             # porta no Mac do container text-embedder
   EMBED_MODEL=nomic-embed-text:v1.5
   CHROMADB_PORT=8001           # porta no Mac do Chroma (a 8000 é da api)

   # Datadog (opcional: sem chave, os traces não são enviados)
   DD_API_KEY=
   DD_SITE=datadoghq.com        # o site da sua conta Datadog
   DD_ENV=local
   ```

2. Gere o `corp-ca.pem` com os certificados do seu Mac. O compose o monta no `backend_api` e no `kb_service` (envio ao Datadog) e no `llm` e no `text_embedder` (download dos modelos), para funcionar atrás de proxy corporativo que intercepta o HTTPS. O arquivo é local e está no `.gitignore`. Gere-o **antes** do `docker compose up`: se não existir, o Docker cria uma pasta com esse nome.

   ```bash
   security find-certificate -a -p /Library/Keychains/System.keychain /System/Library/Keychains/SystemRootCertificates.keychain > corp-ca.pem
   ```

3. Suba os containers e baixe o modelo:

   ```bash
   docker compose up -d --build
   docker exec locallama ollama pull llama3.2:1b
   ```

4. Baixe o modelo de embedding e rode a ingestão (veja [kb-service/README.md](kb-service/README.md) para o que cada comando faz):

   ```bash
   docker exec text-embedder ollama pull nomic-embed-text:v1.5
   docker exec kb-service python ingest_documents.py
   ```

5. Abra http://localhost:8501 e converse. Teste o backend direto (a primeira resposta pode levar um tempo):

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

Completar o RAG com a consulta: transformar a pergunta em embedding (com o prefixo `search_query:`), buscar no Chroma os chunks mais próximos e injetá-los no prompt do LLM.
