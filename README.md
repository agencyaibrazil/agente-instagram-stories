# Agente de Instagram — Stories

Publica **3 stories por dia** no Instagram, sozinho, hospedado 100% no GitHub
Actions (não depende de computador ligado). Mesma arquitetura do
`agente-instagram-vivo` (posts e carrosséis) e do `agente-instagram-reels`,
adaptada ao formato Stories.

| Horário (Brasília) | Pasta de origem | Tema |
|---|---|---|
| **08h00** | `pendentes/stories/rotina/` | Rotina de IA |
| **12h00** | `pendentes/stories/noticia/` | Notícia relevante sobre IA |
| **18h00** | `pendentes/stories/futuro/` | Projeção futura sobre IA |

Depois de publicar, o arquivo é movido para `publicados/stories/<slot>/` com um
commit automático — é isso que dá o histórico e evita republicar o mesmo item.

---

## 1. Habilidades do agente

1. **Entra na pasta certa do repositório conforme o horário.** Cada slot do dia
   tem sua própria pasta e seu próprio tema; o agente nunca mistura.
2. **Publica no horário certo, 3x ao dia**, via API oficial da Meta
   (`media_type=STORIES`).
3. **Aceita imagem e vídeo.** JPEG 1080x1920 ou MP4/MOV de 3 a 60 s.
4. **Pula o slot em silêncio se a pasta estiver vazia** — não publica story de
   outro tema no lugar, não quebra, e tenta de novo no dia seguinte.
5. **Nunca publica duas vezes o mesmo slot no mesmo dia**, mesmo que a
   verificação rode várias vezes dentro da janela.
6. **Arquiva o que foi ao ar** movendo para `publicados/` com commit
   automático.

O agente **não gera conteúdo**. Quem abastece as pastas é outro agente, no
mesmo dia da publicação, algumas horas antes — o contrato entre os dois está em
[`ESPECIFICACAO_MATERIAIS.md`](ESPECIFICACAO_MATERIAIS.md).

Desde 26/08/2026, esse "outro agente" é automatizado: 3 tarefas agendadas do
Cowork (05h/09h/15h BRT, uma por slot) seguem
[`RUNBOOK_GERACAO.md`](RUNBOOK_GERACAO.md) pra escrever, renderizar e enviar
o próximo story de cada tema — sempre com 3h de folga antes do horário de
publicação. Enquetes e vídeo ficam fora desse fluxo por enquanto (limitação
real da API / decisão do Rafael, ver histórico no fim do RUNBOOK).

---

## 2. Estrutura de arquivos

```
.
├── .github/workflows/
│   ├── agendador.yml          # roda a cada 10min, decide se está na hora
│   └── postar-stories.yml     # publica de fato (disparado pelo agendador)
├── script/
│   ├── agendador.sh           # janelas dos 3 slots + antiduplicidade
│   ├── postar_story.py        # publicação via Graph API + arquivamento
│   └── requirements.txt
├── pendentes/stories/
│   ├── rotina/                # 08h — abastecida por outro agente
│   ├── noticia/               # 12h
│   └── futuro/                # 18h
├── publicados/stories/
│   ├── rotina/  noticia/  futuro/
├── ESPECIFICACAO_MATERIAIS.md # contrato com quem gera os stories
└── README.md
```

---

## 3. Setup

### 3.1 O repositório precisa ser PÚBLICO

A Meta baixa a mídia por URL. O agente usa
`raw.githubusercontent.com/<conta>/<repo>/main/pendentes/stories/...`, o que só
funciona em repositório público.

> **Isso já deu problema de verdade.** Em 26/08/2026 o repo do agente de posts
> virou privado e as publicações começaram a falhar em silêncio, porque a Meta
> não conseguia buscar a imagem. Se o agente parar de publicar do nada, esta é a
> primeira coisa a conferir.

**Trade-off aceito:** qualquer arquivo em `pendentes/` fica acessível por link
direto antes de ir ao ar. Não é indexado, mas não é sigiloso.

### 3.2 Secrets

Em **Settings → Secrets and variables → Actions**, cadastrar:

| Secret | O que é |
|---|---|
| `IG_ACCESS_TOKEN` | Token de longa duração da Meta (mesmo já usado nos outros agentes, se for a mesma conta do Instagram) |
| `IG_BUSINESS_ACCOUNT_ID` | ID da conta Instagram Business |

**Permissões necessárias no token:** `instagram_basic`,
`instagram_content_publish`, `pages_read_engagement`.

> O token de longa duração da Meta **expira a cada ~60 dias**. Sem renovar, o
> agente para de publicar e ninguém é avisado automaticamente. Quando ele
> expira, o erro que aparece no log é `OAuthException` código 190.

### 3.3 Ajustar horários

Todos os horários vivem em **`script/agendador.sh`**, em UTC. Não há horário
nenhum nos arquivos de workflow — não adianta mexer lá.

### 3.4 Como funciona o agendamento

O `schedule:` nativo do GitHub Actions com cron esparso (1x/dia) **não é
confiável** — medido em produção neste projeto: atrasos de 40 min a mais de 2 h,
e às vezes o disparo simplesmente não acontece. Por isso:

- `agendador.yml` roda a cada 10 minutos (cron frequente é bem mais confiável).
- `script/agendador.sh` olha o **relógio real** e decide se está dentro da
  janela de algum slot:

| Slot | Alvo | Janela útil (UTC) | Janela útil (BRT) |
|---|---|---|---|
| `rotina` | 08h00 BRT | 11:00–14:59 | 08h00–11h59 |
| `noticia` | 12h00 BRT | 15:00–20:59 | 12h00–17h59 |
| `futuro` | 18h00 BRT | 21:00–23:59 | 18h00–20h59 |

A janela **começa exatamente no horário alvo** (nunca publica adiantado) e vai
até o início do slot seguinte. Assim um atraso do GitHub ainda deixa o story
sair, mas um story de rotina nunca vai ao ar às 18h no lugar da projeção
futura.

- **Antiduplicidade:** antes de disparar, o script procura no `git log` um
  commit `Story publicado automaticamente (<slot>)` desde o **início da janela
  de hoje**. Ancorar no início da janela — e não em "últimas N horas" nem "dia
  UTC inteiro" — é o que evita os dois bugs já vividos neste projeto: bloquear
  uma publicação legítima por causa de um commit atrasado de outro horário, e
  publicar duas vezes se o agendador rodar mais de uma vez na mesma janela.
- Por isso o checkout do agendador usa `fetch-depth: 0` (histórico completo).
- **Pasta vazia = nenhum disparo.** O agendador confere se existe arquivo de
  mídia na pasta do slot antes de acionar a publicação. Sem isso ele dispararia
  o workflow de publicação a cada 10 minutos contra uma pasta vazia, enchendo o
  histórico do Actions de execuções inúteis.

### 3.5 Testar

**Camada 1 — o agendador roda limpo (não publica nada):** Actions → *Agendador
de Postagem de Stories* → *Run workflow* → `forcar_slot: nenhum`. O log deve
mostrar a hora UTC e a decisão de janela, sem disparar publicação (a menos que
esteja de fato dentro de uma janela com material pendente).

**Camada 2 — publicação real:** Actions → *Postar Story no Instagram* → *Run
workflow* → escolher o slot. **Isso publica de verdade** e consome um item de
`pendentes/`.

---

## 4. O que a API não permite

Nenhum destes é automatizável, por limitação da Meta (não do código):

- adesivo de link, enquete, pergunta, quiz, contagem regressiva, slider
- adesivo de localização, hashtag, GIF, música
- menção com adesivo visível

A documentação da Meta é explícita: *"Publishing stickers (i.e., link, poll,
location) is not supported"*. Menção a usuário **sem** adesivo (`user_tags`) é
a única exceção, e não é usada aqui por padrão.

Story que dependa de link ou enquete precisa ser publicado manualmente pelo
app. Todo o resto tem que estar desenhado dentro da própria arte.

Outra limitação a considerar: **PNG não é aceito**, só JPEG. O
`design_system.py` gera PNG — converter antes é obrigatório.

---

## 5. Lições aprendidas (herdadas dos agentes irmãos)

Estas custaram dias de depuração nos outros dois agentes. Já estão aplicadas
aqui, então **não desfaça**:

1. **Não use `schedule:` com cron esparso no workflow de publicação.** O
   agendador de verificação frequente existe exatamente por isso.
2. **Não coloque hora de fechamento apertada na janela.** A causa raiz de dias
   inteiros sem publicar no agente de posts foi uma janela de 40 min: nenhum
   tick do GitHub caía dentro dela. Aqui cada janela tem 3 a 6 horas.
3. **Ancore o corte de duplicidade no início da janela**, não em "últimas 20h".
   A versão com janela rolante bloqueou uma publicação legítima por causa de um
   commit atrasado da madrugada.
4. **Repo público, sempre.** Repo privado = Meta não consegue baixar a mídia =
   falha silenciosa.
5. **PAT precisa de escopo `Workflows`** pra editar qualquer coisa dentro de
   `.github/workflows/`. Sem isso o GitHub recusa o push com
   `refusing to allow a Personal Access Token ... without workflow scope` — nesse
   caso, subir esses arquivos pelo editor web.
6. **Teste manualmente antes de confiar no cron.** Sempre.
7. **Token da Meta expira a cada ~60 dias.** Erro `OAuthException` 190 no log é
   isso. Vale conferir também se o valor colado no secret é só o token, não o
   JSON inteiro da resposta do `fb_exchange_token` — esse erro exato já
   aconteceu no agente de Reels.
