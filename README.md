# poc-chatbot

PoC de um chatbot (**QuantumHound**, uma agência fictícia de viagem no tempo) construído por etapas. Cada etapa é uma branch, e cada branch tem um Pull Request em rascunho que mostra só o que mudou naquela etapa. Os PRs não são mergeados: a `main` fica apenas com o README inicial, e a evolução se acompanha pelos PRs e pelas tags.

| Etapa | Branch | Tag | O que muda |
|-------|--------|-----|------------|
| 1 (esta) | `step-1-baseline` | `step-1` | Chatbot Streamlit com respostas fixas |
| 2 | `step-2-ollama` | `step-2` | Backend FastAPI que chama o Ollama local, com observabilidade no Datadog |

Para ver o código de uma etapa: `git checkout step-N` (ou `git checkout step-N-nome`). Para ver o que mudou, abra o PR da etapa.

## Etapa 1: baseline

Interface de chat em Streamlit. **Não há LLM nem backend**: as respostas são fixas e escolhidas por palavras-chave na mensagem.

```
Navegador ──► chatbot (Streamlit :8501)
```

### O que foi feito

1. Criado o app Streamlit em [chatbot/app/app.py](chatbot/app/app.py), com título, ícone e histórico de conversa guardado em `st.session_state`.
2. Criada a função `generate_response` em [chatbot/app/chat_requests.py](chatbot/app/chat_requests.py). Ela converte o prompt para minúsculas e devolve uma resposta fixa conforme a palavra-chave encontrada:

   | Palavras-chave | Assunto da resposta |
   |----------------|---------------------|
   | `hello`, `hi`, `hey` | Saudação |
   | `cost`, `price`, `expensive` | Preços dos pacotes |
   | `safe`, `safety`, `dangerous` | Segurança |
   | `how`, `work`, `technology` | Como funciona a tecnologia |
   | `where`, `destination`, `visit` | Destinos |
   | (nenhuma) | Mensagem padrão convidando a perguntar |

   A função devolve `{"success": True, "message": ...}`, formato que a interface já sabe exibir.
3. Criado o [Dockerfile](chatbot/app/Dockerfile) (`python:3.12-slim`, dependências em [requirements.txt](chatbot/app/requirements.txt): `streamlit` e `requests`).
4. Criado o [docker-compose.yml](docker-compose.yml) com o serviço `chatbot_app`. O código em `chatbot/app` é montado como volume, então alterações no código aparecem sem reconstruir a imagem.
5. O [.gitignore](.gitignore) mantém o `.env` fora do Git.

### Como rodar

**Pré-requisito:** Docker.

1. Crie um arquivo `.env` na raiz:

   ```env
   STREAMLIT_PORT=8501
   ```

   Sem esse arquivo, o `docker compose` avisa `The "STREAMLIT_PORT" variable is not set` e falha com `no port specified`.

2. Construa a imagem. O compose desta etapa usa a imagem local `workshop-llm-obs-chatbot-base:latest`, que não existe em nenhum registry:

   ```bash
   docker build -t workshop-llm-obs-chatbot-base:latest ./chatbot/app
   ```

3. Suba o chatbot:

   ```bash
   docker compose up -d
   ```

4. Abra http://localhost:8501 e teste com `hello`, `price`, `safe`, `how` ou `where`. Qualquer outra mensagem recebe a resposta padrão.

### Problemas conhecidos

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `pull access denied for workshop-llm-obs-chatbot-base` | A imagem é local e ainda não foi construída | Passo 2 de "Como rodar" |
| `no port specified: :<empty>` | Faltou o `.env` | Passo 1 de "Como rodar" |
| O chat sempre devolve o mesmo texto | Nenhuma palavra-chave foi reconhecida (não há LLM nesta etapa) | Use as palavras da tabela. O LLM vem na etapa 2 |

## Segurança

O `.env` está no `.gitignore`. O repositório é público: nunca commite chaves.

## Próxima etapa

A etapa 2 troca as respostas fixas por um backend FastAPI que conversa com o Ollama local e envia traces ao Datadog (branch `step-2-ollama`).
