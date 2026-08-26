#!/usr/bin/env bash
set -e

# ---------------------------------------------------------------------------
# Agendador de Stories — 3 publicações por dia
#
# Horários alvo (BRT = UTC-3, sem horário de verão desde 2019):
#
#   08h00 BRT (11:00 UTC) → slot "rotina"   — rotina de IA
#   12h00 BRT (15:00 UTC) → slot "noticia"  — notícia relevante sobre IA
#   18h00 BRT (21:00 UTC) → slot "futuro"   — projeção futura sobre IA
#
# POR QUE JANELA E NÃO CRON DIRETO: o agendador nativo do GitHub Actions atrasa
# (medido em produção: de 40min a mais de 2h, às vezes o tick some). Este script
# roda a cada 10min e só dispara quando o relógio REAL está dentro da janela do
# slot. A janela de cada slot começa EXATAMENTE no horário alvo (nunca publica
# adiantado) e se estende até o início do slot seguinte — assim um atraso do
# GitHub ainda deixa o story sair, mas um story de "rotina" nunca vai ao ar às
# 18h no lugar da projeção futura.
#
#   rotina  → 11:00–14:59 UTC (08h00–11h59 BRT)
#   noticia → 15:00–20:59 UTC (12h00–17h59 BRT)
#   futuro  → 21:00–23:59 UTC (18h00–20h59 BRT)
#
# Fora dessas faixas (00:00–10:59 UTC = 21h00–07h59 BRT) não há slot ativo.
#
# ANTIDUPLICIDADE: antes de disparar, checa no histórico do git se já existe um
# commit "Story publicado automaticamente (<slot>)" desde o INÍCIO DA JANELA DE
# HOJE. Ancorar no início da janela (e não em "últimas N horas" nem "dia UTC
# inteiro") é o que evita os dois bugs já vividos neste projeto: bloquear uma
# publicação legítima por causa de um commit atrasado de outro horário, e
# publicar duas vezes se o agendador rodar mais de uma vez na mesma janela.
#
# Requer actions/checkout com fetch-depth: 0 (histórico completo) para o git log
# funcionar.
# ---------------------------------------------------------------------------

WORKFLOW="postar-stories.yml"

disparar() {
  local slot="$1"
  echo "Disparando ${WORKFLOW} para o slot '${slot}'..."
  gh workflow run "$WORKFLOW" --ref main -f slot="$slot"
}

# --- Disparo manual forçado (workflow_dispatch), pula janela e duplicidade ---
FORCAR="${FORCAR_SLOT:-nenhum}"
if [ "$FORCAR" != "nenhum" ] && [ -n "$FORCAR" ]; then
  echo "Forcado manualmente: slot '${FORCAR}', sem checar janela nem duplicidade."
  disparar "$FORCAR"
  exit 0
fi

HORA_UTC=$(date -u +%H:%M)
HOJE_UTC=$(date -u +%Y-%m-%d)
echo "Hora atual (UTC): $HORA_UTC | Data (UTC): $HOJE_UTC"

SLOT=""
INICIO_JANELA=""

if [[ "$HORA_UTC" > "10:59" && "$HORA_UTC" < "15:00" ]]; then
  SLOT="rotina"
  INICIO_JANELA="11:00"
elif [[ "$HORA_UTC" > "14:59" && "$HORA_UTC" < "21:00" ]]; then
  SLOT="noticia"
  INICIO_JANELA="15:00"
elif [[ "$HORA_UTC" > "20:59" ]]; then
  SLOT="futuro"
  INICIO_JANELA="21:00"
fi

if [ -z "$SLOT" ]; then
  echo "Fora de qualquer janela de publicacao. Nada a fazer."
  echo "Verificacao concluida."
  exit 0
fi

echo "Janela ativa: slot '${SLOT}' (aberta desde ${INICIO_JANELA} UTC de hoje)."

JA_PUBLICOU=$(git log \
  --since="${HOJE_UTC}T${INICIO_JANELA}:00" \
  --grep="Story publicado automaticamente (${SLOT})" \
  --fixed-strings \
  --oneline)

if [ -n "$JA_PUBLICOU" ]; then
  echo "Ja publicou o story de '${SLOT}' nesta janela. Nada a fazer."
  echo "Verificacao concluida."
  exit 0
fi

disparar "$SLOT"
echo "Verificacao concluida."
