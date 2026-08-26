# RUNBOOK — Geração diária de conteúdo (Agente de Instagram Stories)

Este arquivo é o roteiro que as 3 tarefas agendadas diárias seguem (05h, 09h
e 15h BRT). Escrito pra ser executado por um agente Claude com acesso a
shell (bash), Read/Write, WebSearch e Chrome (`mcp__claude-in-chrome__*`),
**sem memória da sessão anterior** — por isso é bem explícito.

## Objetivo

Gerar **1 story novo** pra um dos 3 slots (`rotina`, `noticia`, `futuro`) e
colocar em `pendentes/stories/<slot>/` do repositório
`agencyaibrazil/agente-instagram-stories`, ANTES do horário de publicação
daquele slot. Este repositório **não gera conteúdo sozinho** (ver
`ESPECIFICACAO_MATERIAIS.md` na raiz dele) — é este runbook que preenche
essa lacuna.

| Geração (este runbook) | Publicação (agendador do repo, já existe) | Slot | Tema |
|---|---|---|---|
| **05h00 BRT** | 08h00 BRT | `rotina` | Rotina de IA — hábito, atalho, erro comum, "como eu faço isso aqui" |
| **09h00 BRT** | 12h00 BRT | `noticia` | Notícia relevante sobre IA — algo que aconteceu de verdade hoje |
| **15h00 BRT** | 18h00 BRT | `futuro` | Projeção futura sobre IA — pra onde a coisa está indo |

3h de folga entre geração e publicação em todos os slots — dá margem mesmo
se alguma etapa (busca de foto, WebSearch) demorar mais que o normal.

**Enquetes/links não fazem parte deste fluxo** (decisão do Rafael,
26/08/2026): a API de Stories da Meta não publica adesivo de enquete/link de
jeito nenhum, então esse formato nunca entra na geração automática — se o
Rafael quiser uma enquete, ele publica manualmente pelo app.

## 0. Pré-requisito: qual slot rodar

Cada uma das 3 tarefas agendadas passa o slot certo no prompt (`rotina`,
`noticia` ou `futuro`). Rode a seção 1-6 abaixo só pra esse slot.

## 1. Token de acesso

Leia o token de dentro de (caminho monta conforme a sessão atual, ver seção
"Shell access" do prompt de sistema — não hardcode um `/sessions/<id>/...`
antigo):

```
Agentes para Vender/Agente de Instagram - Stories/Acesso_GitHub_agente-instagram-stories.md
```

## 2. Clonar o repositório (usar /tmp, não a pasta `outputs` montada)

```bash
git clone https://x-access-token:<TOKEN>@github.com/agencyaibrazil/agente-instagram-stories.git /tmp/stories
```

**Gotcha conhecido:** clonar/commitar dentro de `outputs` montada pode falhar
com `unable to unlink ... Operation not permitted` — sempre trabalhe em
`/tmp`.

## 3. Descobrir o próximo número de arquivo

```bash
cd /tmp/stories
ls pendentes/stories/<slot>/*.jpg publicados/stories/<slot>/*.jpg 2>/dev/null \
  | sed -E 's/.*story-([0-9]+)-.*/\1/' | sort -n | tail -1
# some 1 a esse número; se vazio, comece em 01
```

Olhar as duas pastas (pendentes E publicados) evita colidir número com um
story que já foi ao ar.

## 4. Decidir o tema do dia (varia por slot)

**Antes de escrever, veja os últimos itens já publicados** em
`publicados/stories/<slot>/` (nome do arquivo já entrega o ângulo) pra não
repetir o mesmo ângulo dia após dia — pode repetir tema amplo, mas com
ângulo novo, mesma regra já usada nos posts do feed.

### `rotina`
Um hábito, atalho, erro comum ou "como eu faço isso aqui" no uso do dia a
dia de IA no trabalho. Não precisa de pesquisa em tempo real — pode nascer
de conhecimento geral + as
[[reference-50-fontes-ia-confiaveis|50 fontes confiáveis]] como inspiração
de ângulo. Tom pessoal, direto, como se fosse alguém contando um truque
rápido — não uma dica genérica de blog.

### `noticia`
**Precisa ser algo que aconteceu de verdade, hoje ou nos últimos dias.**
Rode `WebSearch` com algo como `"AI news today <data de hoje>"` (a data
real, não um exemplo fixo), leia os resultados, e escolha **1 item**
relevante pra quem trabalha com agentes de IA/negócio — prefira histórias
com narrativa clara (algo que muda, termina, começa) a anúncios técnicos
secos. Escreva headline + sub explicando por que importa, sem jargão. Nunca
invente ou especule — se não achar nada de fato relevante no dia, escolha o
item mais consequente disponível, mesmo que técnico.

### `futuro`
Projeção: pra onde a IA está indo, o que muda daqui a 6 meses / 2 anos,
consequência prática pra quem usa no trabalho. Pode se inspirar em
tendências vistas em `noticia` de dias anteriores, mas o ângulo aqui é
sempre prospectivo, não descritivo do presente.

### Escrita
Sempre seguindo a escrita humanizada (seção 12 de
`Diretrizes_Conteudo_Instagram_2026_Correcoes.md`): nunca usar travessão,
variar ritmo de frase, sem jargão vazio, ler antes de aprovar. Headline
curta (1-2 linhas), sub opcional complementando — nunca repetindo a
headline.

## 5. Decidir se usa foto real (opcional, critério de sempre)

**Só quando o tema for concreto/de cenário** (ex.: "assim que a equipe usa
isso no escritório", uma notícia sobre um produto/empresa específica com
imagem óbvia). Temas abstratos (a maioria de `rotina` e `futuro`) ficam sem
foto — vira um degradê procedural (o próprio `gerar_story.py` já cuida
disso sozinho se o campo `photo` não for informado).

Se decidir usar foto:

1. Buscar no Unsplash via `mcp__workspace__web_fetch` (ex.:
   `https://unsplash.com/s/photos/<termo-em-ingles>`), escolher uma foto
   real e relevante (não genérica demais).
2. Montar a URL de crop: `https://images.unsplash.com/photo-XXXX?w=1080&h=520&fit=crop&auto=format&q=80`.
3. Carregar as tools do Chrome se ainda não estiverem
   (`ToolSearch` com `select:mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__tabs_close_mcp`).
4. `tabs_create_mcp` → `navigate` pra URL do passo 2 → `computer` ação
   `zoom` com `region: [143, 12, 1223, 532]` e `save_to_disk: true` (esse
   region é o que alinha certinho com uma imagem 1080x520 dentro do
   viewport de 1366x543 — não mude os números).
5. O arquivo salvo aparece em `outputs/screenshot-*.png` — copie pra
   `/tmp/photos/<slug-descritivo>.jpg` antes de usar no JSON.
6. Feche a aba (`tabs_close_mcp`) depois de terminar.

**Por que esse método:** o ambiente não tem acesso de rede direto (bash) a
bancos de imagem (proxy allowlist bloqueia), e `web_fetch` não baixa bytes
binários de imagem — só a captura de tela em resolução exata via Chrome
funciona. Detalhes completos na memória do projeto
(`project_instagram_content_hub.md`, atualização de 26/08/2026 Fase C).

## 6. Renderizar e publicar

```bash
cat > /tmp/stories/conteudo.json << 'EOF'
{
  "stories": [
    {"id": <NN>, "slot": "<slot>", "slug": "<slug-curto-sem-acento>",
     "tag": "ROTINA DE IA | NOTÍCIA | DAQUI A POUCO",
     "headline": "Frase de impacto, pode ter **destaque**.",
     "sub": "Complemento opcional.",
     "photo": "/tmp/photos/foto.jpg"}
  ]
}
EOF
cd /tmp/stories/script
export STORIES_ASSETS_DIR="/tmp/stories/brand/"
python3 gerar_story.py --content-json /tmp/stories/conteudo.json --out-dir /tmp/stories/saida
```

Revise o JPG gerado (`Read` no arquivo) antes de publicar — texto legível,
zona de segurança respeitada, sem defeito visual. Se algo sair errado,
ajuste o JSON e rode de novo — nunca suba um render com defeito.

```bash
mkdir -p /tmp/stories/pendentes/stories/<slot>
cp /tmp/stories/saida/<slot>/story-<NN>-<slug>.jpg /tmp/stories/pendentes/stories/<slot>/

cd /tmp/stories
git add pendentes/stories/<slot>
git -c user.name="Agency AI Brazil" -c user.email="agentedeiavivo@gmail.com" \
  commit -m "Novo story gerado (<slot>): <slug>"
git push origin main
```

Se `git push` falhar por não-fast-forward, `git fetch` + `git merge` antes
de tentar de novo. **Nunca use force-push.**

## 7. Sincronizar espelho local (opcional, mas recomendado)

Copie o mesmo arquivo pra
`Agentes para Vender/Agente de Instagram - Stories/pendentes/stories/<slot>/`
— é só acervo de referência, não trava o passo 6 se der problema aqui.

## 8. Registrar e encerrar

Termine com um resumo curto (slot, arquivo gerado, se usou foto ou
degradê, se usou WebSearch) — fica no log da tarefa agendada. Se algo
bloquear o processo (token revogado, push rejeitado, WebSearch sem
resultado nenhum), **não force nada silenciosamente** — registre o problema
claramente pra aparecer pro Rafael. Nesse caso, é melhor não gerar nada do
que gerar algo fora do padrão — o agendador de publicação já pula o slot em
silêncio se a pasta estiver vazia, então um dia sem geração não quebra
nada, só perde aquele story.

## Histórico de decisões

- 26/08/2026: criado junto com `script/gerar_story.py` (fundo sem paleta
  fixa — degradê procedural com matiz aleatória por slug, ou foto real
  full-bleed quando o tema pedir). Rafael pediu explicitamente "sem nada
  engessado de paleta de cores ou padrão" pra Stories, diferente do sistema
  de 4 paletas fixas usado no feed (`design_system.py`). Horários de
  geração (05h/09h/15h BRT) escolhidos pelo Rafael, alinhados 3h antes de
  cada horário de publicação já existente no repositório (08h/12h/18h BRT,
  não alterado). Enquetes ficaram fora do escopo automatizado por decisão
  dele (limitação real da API da Meta, não dá pra automatizar de jeito
  nenhum). Vídeo também ficou fora do escopo inicial (decisão dele) — sem
  ferramenta de geração de vídeo disponível hoje; pode ser adicionado no
  futuro seguindo a mesma lógica de busca de foto (banco gratuito +
  captura via navegador), só que seria mais lento por item.
