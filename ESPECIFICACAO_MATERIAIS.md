# Especificação de Materiais — Agente de Instagram (Stories)

Este documento é o contrato entre **quem gera os stories** e **quem publica**.
O agente de publicação deste repositório não gera conteúdo: ele só olha as
pastas abaixo, pega o próximo arquivo e publica no horário certo.

Se você é o agente (ou a pessoa) que abastece as pastas, **é este arquivo que
você precisa seguir**. Qualquer coisa fora da especificação é ignorada em
silêncio pelo publicador.

---

## 1. Onde colocar cada material

Três pastas, uma por horário do dia. O tema de cada uma é fixo:

| Pasta | Horário de publicação | Tema |
|---|---|---|
| `pendentes/stories/rotina/` | **08h00** (Brasília) | Rotina de IA — o dia a dia de usar IA no trabalho: um hábito, um atalho, um erro comum, um "como eu faço isso aqui". |
| `pendentes/stories/noticia/` | **12h00** (Brasília) | Notícia relevante sobre IA — algo que aconteceu de verdade e importa pra quem trabalha com isso. |
| `pendentes/stories/futuro/` | **18h00** (Brasília) | Projeção futura sobre IA — pra onde a coisa está indo, o que muda daqui a 6 meses / 2 anos, consequência prática. |

**Um arquivo = um story.** Não existe pasta por story, nem arquivo de legenda:
a API de Stories da Meta não aceita legenda. Todo o texto precisa estar
desenhado dentro da própria imagem ou do próprio vídeo.

### Ritmo de abastecimento

As pastas são abastecidas **no mesmo dia da publicação, algumas horas antes**.
Consequências práticas disso, que o agente gerador precisa respeitar:

- O material de `noticia/` precisa estar na pasta **antes das 12h00 BRT**, e o
  ideal é subir os três de uma vez de manhã cedo.
- Se a pasta estiver vazia no horário, **aquele slot é simplesmente pulado** —
  o agente não publica story de outra pasta no lugar. Nada quebra, mas o
  horário passa em branco.
- A janela de tolerância de cada slot vai até o horário do slot seguinte
  (detalhe na seção 5), então um material que chega atrasado ainda pode sair —
  mas dentro do dia, e só naquele slot.

---

## 2. Nome do arquivo

```
story-NN-slug-curto.jpg
```

- `NN` = número sequencial de dois dígitos dentro da pasta (`01`, `02`, ...).
  **O publicador pega sempre o primeiro em ordem alfabética**, então a
  numeração é o que define a fila.
- `slug-curto` = descrição em minúsculas, sem acento, separada por hífen.
- Sem espaços, sem maiúsculas, sem acento no nome do arquivo.

Exemplos válidos:

```
pendentes/stories/rotina/story-01-tres-prompts-que-uso-todo-dia.jpg
pendentes/stories/noticia/story-01-meta-libera-api-de-agentes.jpg
pendentes/stories/futuro/story-01-atendimento-em-2027.mp4
```

Se o mesmo nome já existir em `publicados/`, o publicador acrescenta um sufixo
(`-2`, `-3`) em vez de sobrescrever — dá pra reusar nomes entre dias sem medo,
mas nomes únicos facilitam auditar depois.

---

## 3. Especificação técnica — imagem

Fonte: documentação oficial da Meta (IG User Media Endpoint Reference).

| Item | Valor |
|---|---|
| Formato | **JPEG apenas** (`.jpg` / `.jpeg`) — PNG **não** é aceito pela API |
| Dimensão | 1080 x 1920 px |
| Proporção | 9:16 (recomendada pela Meta para não cortar nem deixar barra) |
| Tamanho do arquivo | até **8 MB** |
| Espaço de cor | sRGB |

> **Atenção:** o `factory/design_system.py` do hub gera os stories em **PNG**.
> É obrigatório converter para JPEG antes de colocar na pasta — o container da
> Meta falha com PNG. Conversão simples:
> ```bash
> python3 -c "from PIL import Image; Image.open('story.png').convert('RGB').save('story.jpg','JPEG',quality=92)"
> ```

### Zona de segurança

Os 250 px do topo e os 250 px da base ficam cobertos pela interface do
Instagram (barra do perfil em cima, caixa de resposta embaixo). Todo texto,
logo e elemento importante precisa estar dentro dos 1420 px centrais. O
`design_system.py` já desenha respeitando isso.

---

## 4. Especificação técnica — vídeo

| Item | Valor |
|---|---|
| Container | `.mp4` ou `.mov` |
| Codec | H.264 ou HEVC (vídeo), AAC (áudio) |
| Duração | **3 a 60 segundos** |
| Taxa de quadros | 23 a 60 fps |
| Resolução | até 1920 px de largura; use 1080x1920 |
| Proporção | 9:16 recomendada |
| Tamanho do arquivo | até 100 MB pela Meta — **mas mantenha abaixo de 90 MB**, porque o GitHub bloqueia arquivos de 100 MB no git comum, sem Git LFS |

---

## 5. O que a API **não** permite (e por isso não é automatizável)

A documentação da Meta é explícita: *"Publishing stickers (i.e., link, poll,
location) is not supported"*. Ou seja, **nenhum destes sai por automação**:

- adesivo de link ("arrasta pra cima" / link sticker)
- enquete, caixa de pergunta, quiz, contagem regressiva, controle deslizante
- adesivo de localização, hashtag, GIF, música
- menção com adesivo visível

O único elemento interativo suportado é **menção a usuário sem adesivo**
(parâmetro `user_tags`) — não usado por padrão neste agente.

**Consequência prática para quem gera o conteúdo:** se um story depende de
link ou enquete pra funcionar, ele não serve pra este agente — vira publicação
manual pelo app. Todo o resto (texto, CTA visual do tipo "me chama no direct",
setas, marca) precisa estar desenhado dentro da própria arte.

---

## 6. Checklist antes de subir para o repositório

- [ ] Arquivo está na pasta do slot certo (`rotina` / `noticia` / `futuro`)
- [ ] Nome no padrão `story-NN-slug.jpg` (sem acento, sem espaço, minúsculas)
- [ ] Imagem em **JPEG** (não PNG), 1080x1920, abaixo de 8 MB
- [ ] Vídeo entre 3 e 60 s, abaixo de 90 MB
- [ ] Texto dentro da zona de segurança (250 px livres em cima e embaixo)
- [ ] Nada que dependa de adesivo de link, enquete ou música
- [ ] Escrita humanizada, seguindo a seção 12 das
      `Diretrizes_Conteudo_Instagram_2026_Correcoes.md` (sem travessão, sem
      sotaque de IA)
- [ ] Commit e push feitos **antes** do horário do slot
