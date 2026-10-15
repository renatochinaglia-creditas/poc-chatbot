# poc-chatbot

PoC de um chatbot (**QuantumHound**, uma agência fictícia de viagem no tempo) construído por etapas. Cada etapa é uma branch, e cada branch tem um Pull Request em rascunho que mostra só o que mudou naquela etapa. Os PRs não são mergeados: a `main` fica apenas com o README inicial, e a evolução se acompanha pelos PRs.

| Etapa | Branch | O que muda |
|-------|--------|------------|
| 1 | `step-1-baseline` | Chatbot Streamlit com respostas fixas |
| 2 | `step-2-ollama` | Backend FastAPI que chama o Ollama (do Mac), com observabilidade no Datadog |
| 3 | `step-3` | Ollama em container Docker e backend via cliente OpenAI, com um bug proposital para investigar |
| 4 | `step-4-rag` | Pontapé inicial do RAG: system prompt configurável, bug do modelo corrigido e a **ingestão** da base de conhecimento (chunks, embeddings e ChromaDB). A busca e a injeção no prompt ficam para a próxima etapa |
| 5 (esta) | `step-5-workflow-rag` | Fim do RAG: o backend categoriza a pergunta, busca os chunks no ChromaDB e injeta o contexto no prompt, com spans de LLM Observability em cada passo |

Para ver o código de uma etapa: `git checkout <branch>`. Para ver o que mudou, abra o PR da etapa. Cada branch tem o README com as instruções da própria etapa.

## Estado da etapa 5

A etapa 5 completa o RAG. A etapa 4 entregou a **ingestão** (veja o [README do kb-service](kb-service/README.md) para os conceitos e o passo a passo). Agora o endpoint `GET /ask` chama `ask_the_llm_with_rag`, em [utils/llm.py](backend_api/app/utils/llm.py), que consulta a base antes de responder.

### Como o workflow funciona

Cada pergunta passa por cinco passos, todos no mesmo trace do Datadog:

| # | Passo | Função | Span |
|---|-------|--------|------|
| 1 | Pergunta | `ask_the_llm_with_rag` | workflow (raiz) |
| 2 | Escolhe a coleção: o LLM classifica a pergunta em uma de 7 categorias (`faq`, `legal`, `sales`, `technology`, `travel_experience`, `travel_packages`, `travel_policies`) | `categorize_query` | llm |
| 3 | Transforma a pergunta em vetor, com o prefixo `search_query:` | `create_embeddings` | embedding |
| 4 | Busca no Chroma os 3 chunks mais próximos, na coleção escolhida | `find_similar_documents` em [vector_store.py](backend_api/app/utils/vector_store.py) | retrieval |
| 5 | Monta o prompt com o contexto e chama o LLM | `ask_the_llm` | llm |

O Chroma é lido direto de `./chroma_data` (`PersistentClient`), a mesma pasta em que o `kb_service` grava. O `vector_store` não é usado.

### O que esta etapa cobre e o que não cobre

| Cobre | Não cobre |
|---|---|
| Consulta completa: categoriza, gera o embedding, busca no Chroma e responde com o contexto | Limiar de distância: perguntas sem conteúdo (como "ola") recuperam 3 chunks quaisquer |
| Spans de LLM Observability do workflow, llm, embedding e retrieval | Tratar saudações antes da busca |
| `backend_api` com `chromadb`, `EMBED_*` e acesso a `./chroma_data` | Corrigir o chunking `fixed`, que corta o JSON no meio (use `CHUNKING_STRATEGY` diferente de `fixed` e reingira) |
| `corp-ca.pem` também no `backend_api`, para o envio ao Datadog | Evitar o span duplicado da chamada ao LLM (veja "Problemas encontrados") |
| | Avaliar a qualidade das respostas ou trocar o modelo de 1B |

Limitações que valem saber:

- O prompt do RAG está **fixo em `ask_the_llm_with_rag`**. O `SYSTEM_PROMPT_PATH` e os arquivos em `prompts/` só valem para chamadas diretas a `ask_the_llm` sem `system_prompt`, que o `/ask` não faz mais.
- O contexto entra no prompt como o `repr` da lista de chunks, com aspas e escapes.
- O categorizador (`llama3.2:1b`) pode devolver uma categoria inválida. Nesse caso `categorize_query` lança `ValueError` e o `/ask` responde 500.

## Arquitetura

```
Navegador ──► chatbot (Streamlit :8501) ──GET /ask──► api (FastAPI :8000) ──► llm (Ollama, container locallama :11434)
                                                            │
                                                            ├──► text_embedder (Ollama, embedding da pergunta)
                                                            ├──► ChromaDB (./chroma_data, leitura dos chunks)
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
- **Datadog:** o backend roda sob `ddtrace-run` e envia direto à API do Datadog, sem Datadog Agent. [app.py](backend_api/app/app.py) chama `LLMObs.enable`, e as funções do workflow usam os decorators `@workflow`, `@llm`, `@embedding` e `@retrieval`.

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
| `Connection refused` ao chamar `api:8000` | O container `api` caiu na subida. Nesta etapa já aconteceu por `EMBED_BASE_URL` e `EMBED_PORT` não repassadas pelo compose, e por falta do `chromadb` na imagem | `docker logs api`, e `docker compose up -d --build backend_api` |
| `SSLCertVerificationError`, ou `ollama pull` falhando | Proxy da empresa intercepta o HTTPS | Montar `corp-ca.pem` e usar `SSL_CERT_FILE` e `REQUESTS_CA_BUNDLE` |
| `failed to send, dropping N traces to http://localhost:8126` nos logs | O APM (aba Traces) precisa de um Datadog Agent, que não existe aqui | Ignorar: o LLM Observability em modo agentless não depende dele |
| Dois spans de LLM iguais no mesmo trace (`ask_the_llm` e `OpenAI.createChatCompletion`) | O `@llm` manual e a integração automática do `ddtrace` com o cliente `openai` registram a mesma chamada, um dentro do outro | Remover o `@llm` e o `LLMObs.annotate` de `ask_the_llm` e `categorize_query`, ou ligar `LLMObs.enable(..., integrations_enabled=False)`. Ainda não corrigido |
| Nada no Datadog, ou `CERTIFICATE_VERIFY_FAILED` | O `backend_api` ou o `kb_service` sem `SSL_CERT_FILE` e `REQUESTS_CA_BUNDLE` atrás do proxy da empresa | Manter as duas variáveis e o mount do `corp-ca.pem`, e recriar o container |
| Só a versão antiga aparece no gráfico de versões do Datadog | Gráfico de média de `total_tokens` só inclui spans que têm tokens, e a raiz agora é um workflow, sem tokens | Trocar a medida para Count, ou filtrar `@span.kind:llm` |

## Segurança

- O `.env` e o `corp-ca.pem` estão no `.gitignore`. **Nunca commite `DD_API_KEY`.** O repositório é público.
- O Ollama não tem autenticação: por isso a porta publicada fica só na loopback (`127.0.0.1:11435`).
- Não use `DD_TRACE_DEBUG=true` com a chave real: o modo debug imprime o cabeçalho `dd-api-key` completo nos logs.
- O modelo roda localmente. Nenhum prompt sai da sua máquina, a não ser os spans enviados ao Datadog quando há `DD_API_KEY`.

## Próximas etapas

Melhorar a qualidade da recuperação: limiar de distância e tratamento de perguntas sem conteúdo, chunking que preserve a estrutura, contexto formatado no prompt, remoção do span duplicado e um modelo de geração maior.
