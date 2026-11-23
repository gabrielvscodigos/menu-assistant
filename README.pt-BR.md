# menu-assistant

[English](README.md) | **Português (Brasil)**

[![CI](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/gabrielvscodigos/menu-assistant/actions/workflows/ci.yml)

Um assistente de geração aumentada por recuperação (RAG) que ajuda as pessoas a escolher
o que comer a partir do cardápio de um restaurante.

Pergunte coisas como *"Gosto de lámen apimentado, o que mais eu curtiria aqui?"* e receba
sugestões fundamentadas nos ingredientes, no preparo, nas restrições alimentares e nos
alérgenos de cada prato.

> **Status:** funcionando de ponta a ponta: os cardápios são validados e indexados, a
> busca é filtrada e avaliada, e respostas fundamentadas de um LLM local (Ollama) estão
> disponíveis pela linha de comando e por uma API HTTP.

> A documentação técnica em [`docs/`](docs/) está em inglês.

## Princípios de design

- **Somente respostas fundamentadas.** O LLM responde exclusivamente com base nos dados
  recuperados do cardápio e cita os pratos que usou. Se algo não está no cardápio, ele
  diz isso.
- **Filtros de segurança determinísticos.** A filtragem de alérgenos e de restrições
  alimentares é feita com filtros de metadados no código, nunca delegada ao LLM.
  Ingredientes que a pessoa não quer ("sem cebola", "no cilantro") também são filtrados no
  código, pela lista de ingredientes de cada prato.
- **Aviso para confirmar com a equipe.** Toda resposta que envolve alérgenos ou
  restrições alimentares lembra o usuário de confirmar com a equipe do restaurante, no
  idioma da pergunta (inglês, português ou espanhol).
- **Acesso ao LLM independente de provedor.** A aplicação depende apenas da interface
  `LLMClient`; o código específico de provedor (hoje, um cliente Ollama local) fica em
  `llm/`.

## Stack

| Aspecto          | Escolha                                   |
| ---------------- | ----------------------------------------- |
| Linguagem        | Python 3.12, gerenciado com [uv]          |
| API              | FastAPI                                   |
| Banco vetorial   | ChromaDB (local, persistente)             |
| Embeddings       | sentence-transformers (multilíngue)       |
| LLM              | Modelo local via Ollama (`llama3.2`)      |
| Qualidade        | pytest, ruff, mypy (strict)               |

Como as peças se encaixam está descrito em [docs/architecture.md](docs/architecture.md)
(em inglês).

## Primeiros passos

Pré-requisito: [uv] instalado. O uv baixa o Python 3.12 automaticamente, se necessário.

```bash
git clone https://github.com/gabrielvscodigos/menu-assistant.git
cd menu-assistant
uv sync
```

Indexe o cardápio de exemplo no banco vetorial local:

```bash
uv run menu-ingest data/menu.json
```

A primeira execução baixa o modelo de embeddings (~1,1 GB) para o cache do Hugging Face.
Executar de novo é idempotente: os pratos são atualizados pelo id e os pratos que saíram
do cardápio são removidos do índice. Se o modelo de embeddings mudar, a ingestão
reconstrói o índice; a busca se recusa a usar um índice criado com outro modelo.

## Rodar com Docker

A stack inteira (API, Ollama, download do modelo e ingestão do cardápio) sobe com um
único comando. Só é preciso ter o [Docker](https://docs.docker.com/get-docker/):

```bash
docker compose up --build
```

Depois abra <http://localhost:8000/docs>. A primeira inicialização baixa o `llama3.2`
(~2 GB) e o modelo de embeddings (~1,1 GB) para volumes nomeados, então leva alguns
minutos; as próximas reaproveitam os downloads. Espere a linha
`Uvicorn running on http://0.0.0.0:8000` no log antes de acessar a API. Para usar outro
modelo do Ollama: `MENU_ASSISTANT_LLM_MODEL=qwen2.5:7b docker compose up`. Tudo roda na
CPU; `docker compose down -v` remove os volumes.

## Pedir sugestões

Com o cardápio indexado e o Ollama rodando:

```bash
uv run menu-ask "Quero uma sobremesa vegana"   # prato: sobremesa
uv run menu-ask "Tenho alergia a amendoim. Tem algum macarrão apimentado?"
uv run menu-ask "algo leve" --exclude soy --diet vegan
uv run menu-ask "tacos sem coentro"            # evita coentro (cilantro e coriander)
uv run menu-ask "um curry encorpado" --without onion --without garlic
uv run menu-ask "I like spicy ramen, what else here would I enjoy?"
```

Exemplo de saída:

```text
Eu recomendo o Mango Sticky Rice [mango-sticky-rice]: uma sobremesa tailandesa clássica
de arroz glutinoso com coco e manga, totalmente vegana.

Sources:
  - Mango Sticky Rice [mango-sticky-rice]
Restrictions applied: must be vegan
Course: dessert

Note: As informações sobre alérgenos e restrições alimentares vêm do cardápio e podem estar incompletas. Confirme com a equipe do restaurante antes de pedir.
```

O modelo responde no idioma da pergunta, e o aviso de segurança e a resposta de "nenhum
prato atende" também. Os rótulos da saída (`Sources`, `Note`) continuam em inglês.

Como uma resposta é produzida:

1. **As restrições são decididas no código.** As opções `--exclude` / `--diet` /
   `--without` são combinadas com restrições detectadas na pergunta ("sou alérgico a
   amendoim", "sou vegano", "sem glúten", "sem cebola"), usando padrões determinísticos em inglês, português e
   espanhol. Um tipo de prato pedido ("uma sobremesa vegana", "um prato principal") é
   detectado da mesma forma, ou definido com `--course`.
2. **A busca aplica as restrições como filtros exatos**, então pratos excluídos nunca
   chegam ao LLM. Se nada passar, uma resposta fixa de "nenhum prato encontrado" é
   devolvida sem chamar o LLM.
3. **O LLM escreve a resposta** usando apenas os pratos recuperados, citando-os como
   `[id-do-prato]`.
4. **A saída é verificada no código.** Citações de pratos que não foram recuperados são
   removidas, nomes de pratos citados são convertidos em ids, e itens de lista que não
   correspondem a um prato recuperado (sugestões inventadas como "Sorvete de coco") são
   descartados. Sempre que há alérgenos ou dietas envolvidos, o aviso para confirmar com
   a equipe é adicionado pelo código, não pelo LLM.

Limitação conhecida do modelo padrão de 3B: às vezes ele acrescenta sugestões que o
cardápio não sustenta (por exemplo, "peça pimenta extra") ou inventa preços, que o
cardápio não tem. A filtragem de segurança e de tipo de prato não é afetada, porque nunca
depende do LLM. Modelos maiores (`qwen2.5:7b`) seguem melhor as regras.

### Perguntas de continuação

`--chat` mantém a conversa; uma linha vazia ou `sair` encerra. Restrições ditas uma vez
continuam valendo nas perguntas seguintes:

```text
$ uv run menu-ask --chat "Tenho alergia a amendoim, tem algum macarrão apimentado?"
...
Restrictions applied: excludes peanuts

> e uma sobremesa?
...
Restrictions applied: excludes peanuts
Course: dessert
```

## Front end do chat

Um chat no navegador em que um garçom mascote responde, em inglês, português ou espanhol
(escolhido nos botões EN / PT / ES). Com a API rodando:

```bash
cd frontend
pnpm install
pnpm dev        # http://localhost:5173
```

É um app React + TypeScript; veja [frontend/README.md](frontend/README.md).

## API HTTP

```bash
uv run uvicorn menu_assistant.api.main:app --reload
```

A documentação interativa (Swagger UI) fica em <http://127.0.0.1:8000/docs>.

| Método | Caminho   | Descrição                                                              |
| ------ | --------- | ---------------------------------------------------------------------- |
| GET    | `/health` | `ok`, ou `degraded` com uma mensagem de como corrigir se o índice não estiver pronto ou o LLM estiver indisponível |
| POST   | `/ask`    | Sugestões fundamentadas para uma pergunta                              |

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tem macarrão apimentado?", "exclude_allergens": ["peanuts"]}'
```

```json
{
  "answer": "... Spicy Miso Ramen [spicy-miso-ramen] ...",
  "sources": [{"id": "spicy-miso-ramen", "name": "Spicy Miso Ramen", "course": "main",
               "allergens": ["eggs", "gluten", "sesame", "soy"], "dietary_flags": [], "score": 0.91}],
  "candidates": ["... todos os pratos que o LLM recebeu ..."],
  "applied_restrictions": {"exclude_allergens": ["peanuts"], "require_flags": [],
                           "exclude_ingredients": [], "course": null},
  "language": "pt",
  "notice": "As informações sobre alérgenos e restrições alimentares vêm do cardápio e podem estar incompletas. ..."
}
```

No PowerShell, use `curl.exe` e escape as aspas do JSON (`'{\"question\": \"...\"}'`), ou
use a página `/docs`.

Um `course` opcional (`starter`, `main`, `side`, `dessert`) substitui o tipo de prato
detectado na pergunta, e um `language` opcional (`en`, `pt`, `es`) define o idioma da
resposta e do aviso em vez de detectá-lo. `exclude_dishes` (ids de pratos) deixa pratos
de fora da busca, que é como um cliente pede "outras opções". Cada prato em `sources` e
`candidates` traz descrição e ingredientes, para o cliente poder mostrar cartões. Para uma pergunta de continuação, envie os turnos anteriores em
`history` (do mais antigo ao mais novo, até 20); o servidor não guarda estado, e as
restrições das perguntas anteriores continuam valendo:

```json
{
  "question": "e uma sobremesa?",
  "history": [
    {"role": "user", "content": "Tenho alergia a amendoim, tem algum macarrão apimentado?"},
    {"role": "assistant", "content": "... Spicy Miso Ramen [spicy-miso-ramen] ..."}
  ]
}
```

 Alérgenos, restrições ou tipos de prato desconhecidos são
rejeitados com `422`. Se o Ollama estiver inacessível, `/ask` retorna `503` com o motivo.

## Configuração

As configurações vêm de variáveis de ambiente ou de um arquivo `.env`. Copie
[`.env.example`](.env.example) para `.env` para mudar os valores padrão:

| Variável                                   | Padrão                           |
| ------------------------------------------ | -------------------------------- |
| `MENU_ASSISTANT_CHROMA_PATH`               | `.chroma`                        |
| `MENU_ASSISTANT_COLLECTION_NAME`           | `menu`                           |
| `MENU_ASSISTANT_EMBEDDING_MODEL`           | `intfloat/multilingual-e5-base`  |
| `MENU_ASSISTANT_EMBEDDING_QUERY_PREFIX`    | `query: `                        |
| `MENU_ASSISTANT_EMBEDDING_DOCUMENT_PREFIX` | `passage: `                      |
| `MENU_ASSISTANT_TAG_BOOST`                 | `0.05`                           |
| `MENU_ASSISTANT_LLM_PROVIDER`              | `ollama`                         |
| `MENU_ASSISTANT_LLM_MODEL`                 | `llama3.2`                       |
| `MENU_ASSISTANT_LLM_TEMPERATURE`           | `0.2`                            |
| `MENU_ASSISTANT_LLM_TIMEOUT_SECONDS`       | `120`                            |
| `MENU_ASSISTANT_OLLAMA_BASE_URL`           | `http://localhost:11434`         |

Os padrões da busca foram escolhidos por avaliação; veja
[docs/evaluation.md](docs/evaluation.md).

### LLM local (Ollama)

As respostas são geradas por um modelo local via [Ollama](https://ollama.com). Instale-o
e baixe o modelo padrão:

```bash
ollama pull llama3.2
```

Qualquer outro modelo do Ollama funciona definindo `MENU_ASSISTANT_LLM_MODEL` (modelos
maiores, como `qwen2.5:7b`, seguem as instruções de fundamentação com mais confiabilidade).

## Desenvolvimento

| Tarefa              | Comando                                               |
| ------------------- | ----------------------------------------------------- |
| Rodar os testes     | `uv run pytest`                                       |
| Cobertura de testes | `uv run pytest --cov` (o CI falha abaixo de 90%)      |
| Lint                | `uv run ruff check .`                                 |
| Formatação          | `uv run ruff format .`                                |
| Checagem de tipos   | `uv run mypy src tests`                               |
| Avaliar a busca     | `uv run menu-eval`                                    |
| Avaliar respostas   | `uv run menu-eval-answers`                            |
| Rodar a API         | `uv run uvicorn menu_assistant.api.main:app --reload` |

## Avaliação

A busca é medida em 49 consultas rotuladas à mão (preferências de sabor, filtros de
alérgenos, dietas e ingredientes, perguntas em português do Brasil e espanhol) com recall@5, MRR e uma
contagem de violações de filtro que precisa continuar em zero.

| Configuração                                       | recall@5  | MRR       | violações |
| -------------------------------------------------- | --------: | --------: | --------: |
| Base (MiniLM-L12, busca vetorial pura)             |     0.750 |     0.783 |         0 |
| multilingual-e5-base + bônus por tag (34 casos)    |     0.956 |     0.934 |         0 |
| + aliases de tags em português (44 casos)          |     0.989 |     0.966 |         0 |
| **Atual** (+ 5 casos de ingredientes evitados, 49) | **0.990** | **0.969** |         0 |

Os aliases em português (`apimentado` → `spicy`, `macarrão` → `noodles`) elevaram o
recall@5 das consultas multilíngues de 0.765 para 1.000.

As respostas geradas são verificadas à parte em 29 perguntas (com o Ollama rodando)
usando regras determinísticas, não um LLM como juiz. Os resultados abaixo foram medidos no
conjunto anterior de 28 perguntas, antes de os preços entrarem no cardápio:

| Verificação (llama3.2)                                 | Resultado |
| ------------------------------------------------------ | --------: |
| Casos que passam em todas as verificações              |       93% |
| Respostas que citam um prato excluído pela busca       |         0 |
| Aviso para a equipe presente exatamente quando esperado |     100% |
| Pedidos fora do cardápio reconhecidos ("não temos")    |       83% |
| Respostas brutas citando um id que o modelo não recebeu |   0–9%\* |
| Respostas com um prato listado que o modelo não recebeu |   0–9%\* |

\* entre execuções; removidos no código antes de o usuário vê-los. O modelo às vezes
também inventa preços, que o cardápio não tem.

Método, a grade completa de experimentos, os erros restantes e as ressalvas estão em
[docs/evaluation.md](docs/evaluation.md) (em inglês).

## Dados do cardápio

Os cardápios são arquivos JSON validados pelos modelos em
[`src/menu_assistant/models.py`](src/menu_assistant/models.py). Cada prato tem:

| Campo           | Descrição                                                          |
| --------------- | ------------------------------------------------------------------ |
| `id`            | Identificador estável (`spicy-miso-ramen`), usado no índice e nas citações |
| `name`          | Nome exibido                                                       |
| `course`        | `starter`, `main`, `side` ou `dessert`                             |
| `description`   | Descrição curta do prato                                           |
| `ingredients`   | Lista não vazia de ingredientes                                    |
| `preparation`   | Como o prato é preparado                                           |
| `price`         | `{"amount": "16.50", "currency": "USD"}`: decimal exato, uma moeda por cardápio |
| `translations`  | Opcional, por idioma (`pt`): nome, descrição, ingredientes, preparo e preço local (ex.: BRL) |
| `tags`          | Tags livres em minúsculas e em inglês (`spicy`, `japanese`, `noodles`, ...) |
| `dietary_flags` | `vegan`, `vegetarian`, `gluten_free`, `dairy_free`, `halal`        |
| `allergens`     | Os 14 principais alérgenos da UE (`gluten`, `peanuts`, `sesame`, ...) |

As traduções mudam só o que o cliente lê. Alérgenos, restrições, tags e a lista de
ingredientes em inglês ficam no prato e controlam todos os filtros, então uma tradução
nunca enfraquece um filtro. Quando a resposta é em português (escolhido ou detectado na
pergunta), o garçom e os cartões usam o nome, os ingredientes e o preço em R$ em
português; o cardápio de exemplo está todo traduzido. O espanhol ainda não tem tradução e
usa a versão em inglês (USD).

A validação rejeita campos desconhecidos, alérgenos ou restrições desconhecidos, ids
duplicados e contradições, como um prato `vegan` que lista `eggs` ou um prato
`gluten_free` que lista `gluten`.

[`data/menu.json`](data/menu.json) é um cardápio de exemplo **fictício**, em inglês, com
25 pratos de várias cozinhas, usado no desenvolvimento, nos testes e na avaliação.

## Estrutura do projeto

```
src/menu_assistant/
  models.py   modelos de domínio do cardápio (Dish, Menu, alérgenos, restrições)
  config.py   configurações via variáveis de ambiente / .env
  console.py  saída UTF-8 para as linhas de comando
  api/        app FastAPI e rotas
  ingest/     carga, validação e indexação do cardápio
  retrieval/  embeddings, banco vetorial, filtros, ranking com bônus por tag
  llm/        interface LLMClient e implementações de provedores
  rag/        detecção de restrições e de tipo de prato, prompt, respostas fundamentadas
  eval/       conjuntos de avaliação e métricas (busca e respostas)
data/         dados de cardápio de exemplo (fictícios)
tests/        espelha a estrutura de src/
docs/         notas de arquitetura e decisões (em inglês)
frontend/     front end do chat com o mascote (React + TypeScript, veja frontend/README.md)
```

As decisões de design e seus trade-offs estão registrados em
[docs/decisions.md](docs/decisions.md) (em inglês).

## Licença

Veja [LICENSE](LICENSE).

[uv]: https://docs.astral.sh/uv/
