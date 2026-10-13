# KB Service

This service handles document ingestion for the QuantumHound RAG application.

## Conceitos

Esta seção explica os termos usados no restante do README. Quem já conhece RAG pode pular para a ingestão.

### O problema: o LLM não conhece os seus documentos

Um LLM só sabe o que aprendeu no treinamento e o que vem no prompt. Ele não sabe as políticas de viagem, os pacotes e o FAQ da QuantumHound. Colar todos os documentos no prompt a cada pergunta não funciona bem: o prompt tem tamanho máximo, fica caro e lento, e o modelo se perde em muito texto irrelevante.

**RAG** (*Retrieval-Augmented Generation*, geração aumentada por recuperação) resolve isso em duas fases:

1. **Ingestão (offline, feita uma vez):** os documentos são preparados e guardados numa base que permite busca por significado. É o que este serviço faz.
2. **Consulta (a cada pergunta):** o sistema busca na base só os trechos relevantes para a pergunta e os coloca no prompt, junto com a pergunta. O LLM responde com base nesses trechos. **Esta etapa ainda não está implementada.**

### Chunk

Chunk é um trecho de um documento. Documentos inteiros são grandes demais para uma busca precisa: um arquivo de 4 KB sobre vários assuntos teria um único "significado médio", que não se parece com nenhuma pergunta específica. Por isso cada arquivo é cortado em pedaços pequenos, e cada pedaço é tratado como uma unidade.

Neste projeto existem duas estratégias, escolhidas por `CHUNKING_STRATEGY`:

| Estratégia | Como corta | Vantagem | Desvantagem |
|---|---|---|---|
| `fixed` (padrão) | A cada 500 caracteres, sem olhar o conteúdo | Simples e previsível | Pode cortar no meio de uma frase ou palavra |
| outro valor (por exemplo `sentence`) | Respeita o fim das frases, com sobreposição entre chunks | Cada chunk fica legível e mantém contexto | Chunks de tamanhos diferentes |

O tamanho do chunk afeta a qualidade da resposta: chunks pequenos demais perdem contexto, e grandes demais diluem o significado.

### Embedding e vetor

Um **embedding** é a representação de um texto como uma lista de números, chamada de **vetor**. Um modelo de embedding lê o texto e devolve esse vetor. Neste projeto, cada vetor tem **768 números** (768 dimensões).

O que importa é a propriedade do vetor: **textos com significado parecido geram vetores próximos**, mesmo com palavras diferentes. "Posso cancelar minha viagem?" e "política de reembolso" ficam perto um do outro. "Receita de bolo" fica longe. Assim dá para buscar por significado, o que uma busca por palavra-chave (`grep`, `LIKE`) não faz.

A proximidade entre dois vetores é medida por uma distância. O Chroma usa aqui a distância euclidiana ao quadrado (`l2`), que é o padrão das coleções. Quanto menor a distância, mais parecidos os textos.

Um vetor sozinho não é legível por humanos. Por isso a base guarda o **texto original do chunk junto com o vetor**: a busca acontece pelo vetor, e o que vai para o prompt é o texto.

### nomic-embed-text

`nomic-embed-text` é o **modelo de embedding** usado: um modelo pequeno e open source, da Nomic AI, que transforma texto em vetores de 768 dimensões. Ele é diferente do `llama3.2`, que é um modelo de **geração** de texto:

| | Modelo de embedding (`nomic-embed-text`) | Modelo de geração (`llama3.2`) |
|---|---|---|
| Entrada | Texto | Prompt |
| Saída | Vetor de números | Texto |
| Uso no RAG | Busca: indexar e consultar | Resposta final ao usuário |
| Tamanho | Pequeno (centenas de MB) | Bem maior |

Ele roda no Ollama, no container `text-embedder`, e é chamado pela API `/v1/embeddings`, compatível com a da OpenAI. Por isso o código usa o cliente `openai` apontando para o Ollama.

Pontos de atenção:

- **Prefixos obrigatórios.** O modelo foi treinado para receber `search_document: ` antes de textos que serão guardados e `search_query: ` antes de perguntas. [utils.py](utils.py) já faz isso em `create_embeddings`. Na consulta, use `search_query`. Misturar os prefixos piora os resultados.
- **O mesmo modelo na ingestão e na consulta.** Vetores de modelos diferentes não são comparáveis. Se trocar o `EMBED_MODEL`, é preciso reingerir todos os documentos.
- O `v1.5` na tag é a versão do modelo.

### ChromaDB e coleções

**ChromaDB** é um banco de dados de vetores, open source. Ele guarda os vetores, os textos e metadados, e responde à pergunta "quais são os N chunks mais próximos deste vetor?" de forma eficiente, mesmo com muitos registros (usa um índice HNSW).

- **Coleção:** agrupamento de registros, parecido com uma tabela. Aqui existe uma coleção por arquivo da base (`faq`, `travel_policies`, `travel_packages` e assim por diante). O nome vem do nome do arquivo, o *topic*.
- **Registro:** um chunk, com UUID, texto e vetor.
- **Persistência:** os dados ficam em `./chroma_data`, no host.
- **Dois modos:** o Chroma pode rodar embutido no processo Python (`PersistentClient`, usado hoje pelo `kb_service`) ou como servidor HTTP (container `vector_store`).

### Resumo do fluxo

```text
documento ──> chunks ──> modelo de embedding ──> vetores ──> ChromaDB
 (kb-data)   (500 chars)  (nomic-embed-text)     (768 nºs)   (uma coleção por arquivo)
```

Na consulta, a pergunta passa pelo mesmo modelo de embedding. O Chroma devolve os chunks com vetores mais próximos, e esses textos entram no prompt do LLM.

## Ingestão dos documentos (embeddings)

A ingestão lê os arquivos de [kb-data/](kb-data/), quebra cada um em trechos (chunks), transforma cada trecho em um vetor (embedding) e grava os vetores no Chroma. Três containers participam:

| Container | Serviço no compose | Papel |
|---|---|---|
| `text-embedder` | `text_embedder` | Ollama dedicado a embeddings. Serve o modelo `nomic-embed-text:v1.5` pela API compatível com OpenAI (`/v1/embeddings`). |
| `vector-store` | `vector_store` | Chroma, o banco de vetores. |
| `kb-service` | `kb_service` | Roda o script `ingest_documents.py`. Fica parado com `tail -f /dev/null` e o script é executado sob demanda com `docker exec`. |

O `text_embedder` e o `llm` são dois Ollama separados, mas compartilham o volume `ollama_models`.

### Passo a passo

Antes de começar, o `corp-ca.pem` precisa existir na raiz do projeto (veja o README principal). Ele é montado no `text_embedder`, para o `ollama pull` funcionar atrás do proxy da empresa, e no `kb_service`, para o envio dos spans ao Datadog (`SSL_CERT_FILE` e `REQUESTS_CA_BUNDLE`).

**1. Subir os serviços**

```bash
docker compose up -d text_embedder vector_store kb_service
```

Cria e inicia os três containers em segundo plano (`-d`). O compose respeita o `depends_on`, então o `kb_service` só sobe depois dos outros dois. O `kb_service` é construído a partir do [Dockerfile](Dockerfile), que instala o [requirements.txt](requirements.txt). A pasta `kb-service/` também é montada em `/app`, então mudanças nos arquivos `.py` valem sem rebuild.

**2. Baixar o modelo de embedding**

```bash
docker exec text-embedder ollama pull nomic-embed-text:v1.5
```

O `docker exec` executa um comando dentro de um container que já está rodando. Aqui, ele pede ao Ollama do `text-embedder` que baixe o modelo para o volume `ollama_models`. Só é preciso na primeira vez. O nome do modelo vem de `EMBED_MODEL` no `.env`. Sem esse passo, a ingestão falha com `model not found`.

Se aparecer `x509: certificate signed by unknown authority`, o proxy da empresa está interceptando o HTTPS. Confira se o `corp-ca.pem` existe e se o serviço `text_embedder` o monta em `/etc/ssl/certs/ca-certificates.crt`. Depois recrie o container com `docker compose up -d --force-recreate text_embedder`.

**3. Rodar a ingestão**

```bash
docker exec kb-service python ingest_documents.py
```

Executa o script dentro do `kb-service`. Ele faz, nesta ordem:

1. **Limpa o Chroma.** `clear_collections()` apaga todas as coleções existentes. Cada execução recomeça do zero e não duplica dados, mas qualquer coisa gravada antes se perde.
2. **Carrega e quebra os documentos.** `load_data_for_kb()` percorre `KB_DATA_DIR` e processa arquivos `.md`, `.txt` e `.json`. O padrão é quebrar em blocos de 500 caracteres (`CHUNKING_STRATEGY=fixed`). Qualquer outro valor usa quebra por sentenças, com sobreposição.
3. **Gera o embedding de cada chunk.** `create_embeddings()` chama o `text_embedder` e manda o texto com o prefixo `search_document:`. Esse prefixo é exigido pelo `nomic-embed-text` para indexação. Nas buscas, o prefixo deve ser `search_query:`.
4. **Grava no Chroma.** `add_document()` guarda o chunk, o vetor e um UUID. Existe **uma coleção por arquivo**, e o nome vem do arquivo: `travel-policies.md` vira `travel_policies`.

Se der certo, a saída mostra uma linha `Added document <id> to collection '<topico>'` por chunk, e termina com `Document ingestion complete!`. Os vetores ficam em `./chroma_data` no host, então sobrevivem a `docker compose down`.

### Observabilidade no Datadog

O [ingest_documents.py](ingest_documents.py) liga o LLM Observability em modo agentless (`LLMObs.enable`) e decora as funções com `@workflow`, `@tool` e `@embedding`. Depois da ingestão, procure em **LLM Observability → Traces** o ml_app `quantumhound-chatbot`, no ambiente definido por `DD_ENV`. Cada chunk gera um span `process_document` (workflow) com `create_document_embeddings` (embedding) e `store_document` (tool) dentro. Os spans levam alguns minutos para aparecer.

Os spans de embedding e tool aparecem **sem input e output**: os decorators não anotam nada sozinhos, e falta um `LLMObs.annotate` em cada função.

Se não aparecer nada, verifique nesta ordem:

1. A ingestão terminou com `Document ingestion complete!`? Se ela quebra antes de processar os chunks, nenhum span é gerado.
2. `docker exec kb-service sh -c 'echo $SSL_CERT_FILE; ls /etc/ssl/corp-ca.pem'` mostra o certificado? Sem ele, o proxy da empresa bloqueia o envio ao Datadog.
3. `DD_API_KEY` e `DD_SITE` estão definidos no `.env`?

### Variáveis de ambiente

Todas são definidas no serviço `kb_service` do [docker-compose.yml](../docker-compose.yml). Os valores padrão estão em [utils.py](utils.py).

| Variável | Padrão no compose | Função |
|---|---|---|
| `KB_DATA_DIR` | `./kb-data` | Pasta com os documentos. Sem essa variável, o código procura `./kb_data` (com underscore) e falha com `FileNotFoundError`. |
| `EMBED_BASE_URL` e `EMBED_PORT` | `http://text-embedder` e `11434` | Endereço do Ollama de embeddings **dentro da rede do compose**. A porta do Mac (`EMBED_PORT` do `.env`) não vale aqui. |
| `EMBED_MODEL` | `nomic-embed-text:v1.5` | Modelo usado nos embeddings. Precisa ter sido baixado no passo 2. |
| `CHROMADB_HOST` e `CHROMADB_PORT` | `vector-store` e `8000` | Endereço do Chroma dentro da rede do compose. |
| `CHROMA_DATA_DIR` | `/chroma/data` | Pasta de persistência do Chroma, ligada a `./chroma_data`. |
| `CHUNKING_STRATEGY` | `fixed` (padrão do código) | `fixed` ou qualquer outro valor para quebra por sentenças. |

### Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| `x509: certificate signed by unknown authority` no `ollama pull` | Proxy da empresa intercepta o HTTPS e o `text_embedder` não confia no certificado | Montar o `corp-ca.pem` no `text_embedder` e recriá-lo com `--force-recreate` |
| `FileNotFoundError: './kb_data'` | A pasta se chama `kb-data`, mas o padrão do código é `kb_data` | Definir `KB_DATA_DIR=./kb-data` no compose e recriar o `kb_service` |
| `model ... not found` ao gerar embeddings | O modelo não foi baixado no `text-embedder` | Repetir o passo 2 |
| `TypeError: argument 'name': 'Collection' object cannot be converted to 'PyString'` em `clear_collections` | O `chromadb` 1.x devolve objetos `Collection` em `list_collections()`, e o código passava o objeto no lugar do nome | Usar `collection.name` ao chamar `delete_collection` (já corrigido em `utils.py`) |
| Nada aparece no Datadog | A ingestão quebrou antes de gerar spans, ou o `kb_service` não confia no certificado do proxy | Ver a seção "Observabilidade no Datadog" |
| Mudança no `docker-compose.yml` não surte efeito | O container antigo continua com a configuração antiga | `docker compose up -d --force-recreate <servico>` |

## Testing

The service includes comprehensive unit tests for the document ingestion workflow. To run the tests:

1. Make sure you have pytest installed:
   ```
   pip install pytest
   ```

2. Run the tests from the kb-service directory:
   ```
   cd kb-service
   pytest test_ingest_documents.py -v
   ```

The tests cover the following scenarios:

### Document Embedding Tests
- Successful document embedding creation
- Error handling for embedding failures
- Proper metadata handling for both success and error cases

### Document Storage Tests
- Successful document storage
- Error handling for storage failures
- Proper response message formatting

### Complete Workflow Tests
- End-to-end document ingestion process
- Error handling at different stages of the workflow
- Proper handling of multiple documents
- Integration with mock ChromaDB for vector storage

The test suite uses pytest fixtures to:
- Set up mock environment variables
- Provide test document data
- Mock external dependencies (ChromaDB, embedding service)

## Components

- `ingest_documents.py`
