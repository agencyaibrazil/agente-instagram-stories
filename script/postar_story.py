#!/usr/bin/env python3
"""
Agente de Instagram — Publicação de Stories (Agency AI Brazil)

Uso:

    python postar_story.py --slot rotina
    python postar_story.py --slot noticia
    python postar_story.py --slot futuro

Cada "slot" é um horário fixo do dia com um tema próprio (ver README.md):

    rotina   → 08h00 BRT — rotina de IA
    noticia  → 12h00 BRT — notícia relevante sobre IA
    futuro   → 18h00 BRT — projeção futura sobre IA

O script lê `pendentes/stories/<slot>/`, pega o PRIMEIRO arquivo em ordem
alfabética (imagem .jpg/.jpeg ou vídeo .mp4/.mov), publica como Story via
Instagram Graph API oficial da Meta e move o arquivo para
`publicados/stories/<slot>/`.

`image_url` / `video_url` apontam para raw.githubusercontent.com dos próprios
arquivos deste repositório — por isso o repositório PRECISA ser público. Se ele
virar privado, a Meta não consegue baixar o arquivo e a publicação falha (isso
já aconteceu de verdade no agente de posts, em 26/08/2026).

O que este script NÃO faz (limitação da própria API da Meta, não do código):
adesivos de link, enquete, pergunta, localização, GIF, música ou contagem
regressiva. A documentação da Meta é explícita: "Publishing stickers (i.e.,
link, poll, location) is not supported". Menção a usuário SEM adesivo é o único
elemento interativo suportado (parâmetro user_tags) — não usado aqui por
padrão. Se um story específico precisar de link ou enquete, é publicação manual
pelo app.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

SLOTS = ("rotina", "noticia", "futuro")

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
EXTENSOES_VALIDAS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# Limites da Meta para Stories (fonte: IG User Media Endpoint Reference).
# Aviso não bloqueante — o script publica assim mesmo e deixa a Meta decidir,
# mas registra no log para facilitar o diagnóstico se der erro.
LIMITE_IMAGEM_MB = 8
LIMITE_VIDEO_MB = 100

REPO_ROOT = Path(__file__).resolve().parent.parent
PENDENTES_DIR = REPO_ROOT / "pendentes" / "stories"
PUBLICADOS_DIR = REPO_ROOT / "publicados" / "stories"


def log(msg: str) -> None:
    print(f"[agente-instagram-stories] {msg}", flush=True)


def erro_fatal(msg: str) -> None:
    print(f"[agente-instagram-stories] ERRO: {msg}", flush=True)
    sys.exit(1)


def carregar_configuracao() -> dict:
    access_token = os.environ.get("IG_ACCESS_TOKEN")
    ig_user_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")

    if not access_token or not ig_user_id:
        erro_fatal(
            "Faltam variáveis de ambiente IG_ACCESS_TOKEN e/ou IG_BUSINESS_ACCOUNT_ID "
            "(devem vir dos GitHub Secrets)."
        )

    github_repository = os.environ.get("GITHUB_REPOSITORY")  # ex.: sua-conta/seu-repo
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    if not github_repository:
        erro_fatal(
            "Variável GITHUB_REPOSITORY não encontrada "
            "(esperada quando rodando no GitHub Actions)."
        )

    return {
        "access_token": access_token,
        "ig_user_id": ig_user_id,
        "github_repository": github_repository,
        "branch": branch,
    }


def montar_url_publica(caminho: Path, config: dict) -> str:
    caminho_relativo = caminho.relative_to(REPO_ROOT).as_posix()
    return (
        f"https://raw.githubusercontent.com/{config['github_repository']}"
        f"/{config['branch']}/{caminho_relativo}"
    )


# ---------------------------------------------------------------------------


def encontrar_proximo_story(slot: str) -> Path | None:
    pasta = PENDENTES_DIR / slot
    if not pasta.exists():
        log(f"Pasta '{pasta.relative_to(REPO_ROOT)}' não existe.")
        return None

    candidatos = sorted(
        p
        for p in pasta.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in EXTENSOES_VALIDAS
    )

    if not candidatos:
        return None

    escolhido = candidatos[0]
    tamanho_mb = escolhido.stat().st_size / (1024 * 1024)
    limite = (
        LIMITE_IMAGEM_MB if escolhido.suffix.lower() in IMAGE_EXTENSIONS else LIMITE_VIDEO_MB
    )
    if tamanho_mb > limite:
        log(
            f"Aviso: '{escolhido.name}' tem {tamanho_mb:.1f}MB, acima do limite de "
            f"{limite}MB da Meta para este tipo de mídia. Tentando publicar mesmo assim."
        )

    return escolhido


def criar_container_de_story(arquivo: Path, config: dict) -> str:
    url_publica = montar_url_publica(arquivo, config)
    log(f"URL pública da mídia: {url_publica}")

    dados_form = {
        "media_type": "STORIES",
        "access_token": config["access_token"],
    }
    if arquivo.suffix.lower() in IMAGE_EXTENSIONS:
        dados_form["image_url"] = url_publica
    else:
        dados_form["video_url"] = url_publica

    url = f"{GRAPH_API_BASE}/{config['ig_user_id']}/media"
    resp = requests.post(url, data=dados_form, timeout=60)
    dados = resp.json()
    if resp.status_code != 200 or "id" not in dados:
        erro_fatal(f"Falha ao criar container do Story: {dados}")
    return dados["id"]


def aguardar_container_pronto(
    creation_id: str, config: dict, tentativas: int, intervalo_s: int
) -> None:
    url = f"{GRAPH_API_BASE}/{creation_id}"
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(
            url,
            params={"fields": "status_code", "access_token": config["access_token"]},
            timeout=30,
        )
        dados = resp.json()
        status = dados.get("status_code")
        log(f"Status do container {creation_id} ({tentativa}/{tentativas}): {status}")
        if status == "FINISHED":
            return
        if status == "ERROR":
            erro_fatal(f"Container do Story falhou no processamento: {dados}")
        if status == "EXPIRED":
            erro_fatal(f"Container do Story expirou antes de terminar de processar: {dados}")
        time.sleep(intervalo_s)
    erro_fatal(
        f"Container {creation_id} não ficou pronto (status FINISHED) dentro do tempo esperado."
    )


def publicar_container(creation_id: str, config: dict) -> str:
    url = f"{GRAPH_API_BASE}/{config['ig_user_id']}/media_publish"
    resp = requests.post(
        url,
        data={"creation_id": creation_id, "access_token": config["access_token"]},
        timeout=60,
    )
    dados = resp.json()
    if resp.status_code != 200 or "id" not in dados:
        erro_fatal(f"Falha ao publicar o Story: {dados}")
    return dados["id"]


def mover_para_publicados(arquivo: Path, slot: str) -> None:
    destino_dir = PUBLICADOS_DIR / slot
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / arquivo.name

    # Se já existir um arquivo com o mesmo nome (o agente que abastece pode
    # reutilizar nomes entre dias), acrescenta um sufixo numérico em vez de
    # sobrescrever o histórico.
    if destino.exists():
        contador = 2
        while True:
            candidato = destino_dir / f"{arquivo.stem}-{contador}{arquivo.suffix}"
            if not candidato.exists():
                destino = candidato
                break
            contador += 1

    arquivo.rename(destino)
    log(f"Movido: {arquivo.relative_to(REPO_ROOT)} -> {destino.relative_to(REPO_ROOT)}")


def commit_e_push(mensagem: str) -> None:
    comandos = [
        ["git", "config", "user.name", "agente-instagram-stories"],
        [
            "git",
            "config",
            "user.email",
            "agente-instagram-stories@users.noreply.github.com",
        ],
        ["git", "add", "pendentes", "publicados"],
        ["git", "commit", "-m", mensagem],
        ["git", "push"],
    ]
    for cmd in comandos:
        resultado = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if resultado.returncode != 0:
            if "nothing to commit" in resultado.stdout + resultado.stderr:
                log("Nada para commitar (inesperado, mas seguindo em frente).")
                continue
            erro_fatal(
                f"Comando git falhou: {' '.join(cmd)}\n{resultado.stdout}\n{resultado.stderr}"
            )


def executar_publicacao(slot: str, config: dict) -> None:
    arquivo = encontrar_proximo_story(slot)
    if arquivo is None:
        # Comportamento definido com o Rafael: pasta vazia = slot pulado, sem
        # publicar nada de outra pasta (mantém a coerência tema/horário).
        log(
            f"Nenhum story pendente em pendentes/stories/{slot}/. "
            f"Slot '{slot}' pulado, nada a fazer."
        )
        return

    log(f"Próximo story do slot '{slot}': {arquivo.name}")

    eh_video = arquivo.suffix.lower() in VIDEO_EXTENSIONS
    creation_id = criar_container_de_story(arquivo, config)
    log(f"Container de Story criado: {creation_id}")

    # Vídeo demora para processar (Meta recomenda checar por até ~5min);
    # imagem costuma ficar pronta em segundos.
    if eh_video:
        aguardar_container_pronto(creation_id, config, tentativas=10, intervalo_s=30)
    else:
        aguardar_container_pronto(creation_id, config, tentativas=6, intervalo_s=5)

    media_id = publicar_container(creation_id, config)
    log(f"Story publicado com sucesso. ID: {media_id}")

    mover_para_publicados(arquivo, slot)
    commit_e_push(
        f"Story publicado automaticamente ({slot}): move arquivo de "
        f"pendentes/stories/{slot}/ para publicados/stories/{slot}/"
    )

    log("Concluído.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica um Story no Instagram.")
    parser.add_argument("--slot", required=True, choices=SLOTS)
    args = parser.parse_args()

    config = carregar_configuracao()
    executar_publicacao(args.slot, config)


if __name__ == "__main__":
    main()
