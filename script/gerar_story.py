#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de Stories "orgânicos" — Agente de Instagram Stories
(agencyaibrazil/agente-instagram-stories).

Diferente do factory/design_system.py do feed (que tem um sistema fixo de 4
paletas de cor): aqui não existe paleta fixa nem layout padronizado. Cada
story sorteia um visual próprio — foto real de fundo (quando fizer sentido
pro tema) ou um degradê contínuo com matiz aleatória (nunca uma de 4 opções
fixas) — pra fugir do "engessado" e parecer mais natural/humano, como pediu
o Rafael em 26/08/2026.

Self-contido de propósito: não depende do hub (agencyai-content-hub) estar
clonado ao lado, porque este script roda dentro do repo de Stories, numa
execução agendada separada. Usa as mesmas fontes do sistema (Poppins, já
instaladas no ambiente) e uma cópia local de 2 assets de marca em brand/.

Saída sempre em JPEG (a API de Stories da Meta não aceita PNG) — 1080x1920,
zona de segurança de 250px respeitada (todo conteúdo entre y=250 e y=1670).

Uso:
    python3 gerar_story.py --content-json conteudo.json --out-dir ./saida

Schema do JSON de conteúdo:
{
  "stories": [
    {
      "slot": "rotina" | "noticia" | "futuro",
      "slug": "tres-prompts-que-uso-todo-dia",
      "tag": "ROTINA DE IA",                  # rótulo curto opcional
      "headline": "Frase de impacto, pode ter **destaque**.",
      "sub": "Complemento menor opcional.",
      "photo": "/caminho/local/foto.jpg"      # opcional; sem isso, degradê
    }
  ]
}
"""
import os, sys, re, json, random, hashlib, argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))

W, H = 1080, 1920
SAFE_TOP = 250
SAFE_BOTTOM = 250
MARGIN = 80

WHITE = (255, 255, 255)
NEAR_BLACK = (18, 16, 24)

FONT_DIR = "/usr/share/fonts/truetype/google-fonts/"
def F(weight, size):
    return ImageFont.truetype(f"{FONT_DIR}Poppins-{weight}.ttf", size)

ASSETS = os.environ.get("STORIES_ASSETS_DIR", os.path.join(HERE, "..", "brand") + "/")
if not ASSETS.endswith("/"):
    ASSETS += "/"
ICON_WHITE = ASSETS + "03_icone_branco_sem_fundo.png"

OUT = os.environ.get("STORIES_OUT_DIR", "./saida")

# ----------------------------------------------------------------------------
# util: hash determinístico (mesmo slug -> mesmo visual, sem repetir padrão
# fixo entre slugs diferentes)
# ----------------------------------------------------------------------------
def _h(s, salt=""):
    return int(hashlib.md5((str(s) + salt).encode("utf-8")).hexdigest(), 16)

def hsl_to_rgb(h, s, l):
    import colorsys
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

# ----------------------------------------------------------------------------
# quebra de texto / destaque **palavra** — mesma lógica do feed, copiada aqui
# de propósito pra este script não depender de outro repo estar clonado.
# ----------------------------------------------------------------------------
_ABREV = {"sr", "sra", "dr", "dra", "srta", "prof", "etc", "vs"}

def _ends_with_abbrev(sentence):
    last_word = sentence.split(" ")[-1] if sentence else ""
    last_word = re.sub(r'\.$', '', last_word).lower()
    return last_word in _ABREV

def _split_sentences(text):
    text = text.strip()
    if not text:
        return []
    tokens = re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-Ú"“\'0-9])', text)
    sentences = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        if sentences and _ends_with_abbrev(sentences[-1]):
            sentences[-1] = sentences[-1] + " " + t
        else:
            sentences.append(t)
    return sentences

def wrap_text(text, font, max_width, draw):
    lines = []
    for sentence in _split_sentences(text):
        words = sentence.split()
        cur = ""
        for w_ in words:
            trial = (cur + " " + w_).strip()
            if draw.textlength(trial, font=font) <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w_
        if cur:
            lines.append(cur)
    return lines

def parse_highlight(text):
    parts = text.split("**")
    words, accents = [], []
    for i, part in enumerate(parts):
        is_accent = (i % 2 == 1)
        for w in part.split():
            words.append(w)
            accents.append(is_accent)
    merged_words, merged_accents = [], []
    for w, a in zip(words, accents):
        if merged_words and re.fullmatch(r'[.,!?;:…]+', w):
            merged_words[-1] += w
        else:
            merged_words.append(w)
            merged_accents.append(a)
    return merged_words, merged_accents

def draw_centered_multiline_rich(draw, cx, top_y, text, font, base_fill, accent_fill, max_width, line_spacing=1.28):
    words, accents = parse_highlight(text)
    plain = " ".join(words)
    lines = wrap_text(plain, font, max_width, draw)
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * line_spacing)
    space_w = draw.textlength(" ", font=font)
    y = top_y
    idx = 0
    for line in lines:
        line_words = line.split()
        widths = [draw.textlength(w, font=font) for w in line_words]
        total_w = sum(widths) + space_w * max(0, len(line_words) - 1)
        x = cx - total_w / 2
        for j, w in enumerate(line_words):
            fill = accent_fill if accents[idx] else base_fill
            draw.text((x, y), w, font=font, fill=fill)
            x += widths[j] + space_w
            idx += 1
        y += line_h
    return y

def draw_centered_multiline(draw, cx, top_y, text, font, fill, max_width, line_spacing=1.28):
    lines = wrap_text(text, font, max_width, draw)
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * line_spacing)
    y = top_y
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text((cx - lw / 2, y), line, font=font, fill=fill)
        y += line_h
    return y

def block_height(text, font, max_width, draw, line_spacing=1.28):
    lines = wrap_text(text, font, max_width, draw)
    ascent, descent = font.getmetrics()
    return max(1, len(lines)) * int((ascent + descent) * line_spacing)

def measure_pill(text, font, pad_x=22, pad_y=13):
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    tw = d.textlength(text, font=font)
    a, de = font.getmetrics()
    th = a + de
    return tw + pad_x * 2, th + pad_y * 2

def draw_pill(draw, xy, text, font, fg, bg, pad_x=22, pad_y=13):
    x, y = xy
    w_, h_ = measure_pill(text, font, pad_x, pad_y)
    draw.rounded_rectangle([x, y, x + w_, y + h_], radius=h_ / 2, fill=bg)
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=fg)
    return w_, h_

def add_dots(base_rgba, seed=1, count=90, color=(255, 255, 255, 20), rmin=1, rmax=3):
    rnd = random.Random(seed)
    dots = Image.new("RGBA", base_rgba.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for _ in range(count):
        x = rnd.randint(0, base_rgba.width)
        y = rnd.randint(0, base_rgba.height)
        r = rnd.randint(rmin, rmax)
        dd.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return Image.alpha_composite(base_rgba, dots)

def paste_logo(canvas_rgba, path, target_w, xy, anchor="topleft"):
    logo = Image.open(path).convert("RGBA")
    ratio = target_w / logo.width
    logo = logo.resize((target_w, max(1, int(logo.height * ratio))), Image.LANCZOS)
    x, y = xy
    if anchor == "center":
        x -= logo.width / 2
    canvas_rgba.alpha_composite(logo, (int(x), int(y)))
    return logo.width, logo.height

# ----------------------------------------------------------------------------
# FUNDO — sem paleta fixa
# ----------------------------------------------------------------------------
def background_gradient(slug, seed):
    """Degradê contínuo: matiz sorteada livremente a partir do hash do slug
    (não é uma de 4 opções fixas), sempre saturação/luminosidade em faixa que
    garante contraste bom com texto branco. Direção do degradê (vertical vs
    diagonal-ish via 2 camadas) também varia por slug."""
    hue = (_h(slug, "hue") % 1000) / 1000.0
    variant = _h(slug, "dir") % 3

    top = hsl_to_rgb(hue, 0.55, 0.16)
    deep = hsl_to_rgb((hue + 0.06) % 1.0, 0.6, 0.06)

    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        t = y / (H - 1)
        c = lerp(top, deep, t)
        for x in range(0, W, 4):  # passo 4 = mais rápido, imperceptível
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = c
    bg = bg.convert("RGBA")

    # glow suave de destaque, posição variando por slug
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    accent = hsl_to_rgb((hue + 0.5) % 1.0, 0.65, 0.55)
    positions = [(0.8, 0.15), (0.15, 0.85), (0.5, 0.05)]
    gx, gy = positions[variant]
    cx, cy, r = int(W * gx), int(H * gy), int(H * 0.22)
    gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent + (55,))
    glow = glow.filter(ImageFilter.GaussianBlur(r // 2))
    bg = Image.alpha_composite(bg, glow)

    bg = add_dots(bg, seed=seed)
    return bg, accent

def background_photo(photo_path, slug):
    """Foto real cobrindo o canvas inteiro (cover-fit) + scrim escuro
    gradual na base (onde o texto normalmente fica) pra manter legibilidade
    sem esconder a foto — visual de story nativo, não de arte gráfica."""
    photo = Image.open(photo_path).convert("RGB")
    photo = ImageOps.fit(photo, (W, H), method=Image.LANCZOS, centering=(0.5, 0.35))
    bg = photo.convert("RGBA")

    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    fade_start = int(H * 0.42)
    for y in range(fade_start, H):
        t = (y - fade_start) / (H - fade_start)
        a = int(215 * (t ** 1.4))
        sd.line([(0, y), (W, y)], fill=(8, 6, 14, a))
    # leve escurecida no topo também, pra tag/legibilidade
    for y in range(0, 200):
        a = int(120 * (1 - y / 200))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    bg = Image.alpha_composite(bg, scrim)

    hue = (_h(slug, "hue") % 1000) / 1000.0
    accent = hsl_to_rgb((hue + 0.5) % 1.0, 0.7, 0.62)
    return bg, accent

# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
SLOT_LABELS = {
    "rotina": "ROTINA DE IA",
    "noticia": "NOTÍCIA",
    "futuro": "DAQUI A POUCO",
}

def render_story(item):
    slot = item["slot"]
    slug = item["slug"]
    seed = _h(slug, "seed") % 100000
    photo_path = item.get("photo")

    if photo_path and os.path.exists(photo_path):
        canvas, accent = background_photo(photo_path, slug)
    else:
        canvas, accent = background_gradient(slug, seed)

    draw = ImageDraw.Draw(canvas, "RGBA")

    safe_top = SAFE_TOP + 40
    safe_bottom = H - SAFE_BOTTOM - 40

    tag = item.get("tag") or SLOT_LABELS.get(slot, "")
    tag_font = F("Medium", 24)
    tw, th = measure_pill(tag, tag_font) if tag else (0, 0)
    if tag:
        draw_pill(draw, (MARGIN, safe_top), tag, tag_font, NEAR_BLACK, WHITE)

    content_top = safe_top + (th + 46 if tag else 0)
    footer_y = safe_bottom - 90
    content_bottom = footer_y - 50

    headline = item.get("headline", "")
    sub = item.get("sub", "")

    hf = F("Bold", 66)
    sf = F("Regular", 34)
    hh = block_height(headline.replace("**", ""), hf, 900, draw, 1.2)
    sh = block_height(sub, sf, 820, draw, 1.32) if sub else 0
    block_total = hh + (36 + sh if sub else 0)
    start_y = content_top + max(0, (content_bottom - content_top - block_total) / 2)

    y = draw_centered_multiline_rich(draw, W / 2, start_y, headline, hf, WHITE, accent, 900, 1.2)
    if sub:
        draw_centered_multiline(draw, W / 2, y + 36, sub, sf, (232, 230, 240), 820, 1.32)

    # marca discreta (só o ícone, não a logo inteira — mais natural, menos "anúncio")
    paste_logo(canvas, ICON_WHITE, 42, (W / 2, footer_y), anchor="center")

    out_dir = os.path.join(OUT, slot)
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f"story-{item['id']:02d}-{slug}.jpg")
    canvas.convert("RGB").save(dest, "JPEG", quality=92)
    print("OK:", dest)
    return dest

def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--content-json", required=True)
    ap.add_argument("--out-dir", default=OUT)
    args = ap.parse_args()
    OUT = args.out_dir
    os.makedirs(OUT, exist_ok=True)

    with open(args.content_json, encoding="utf-8") as f:
        spec = json.load(f)

    for item in spec.get("stories", []):
        render_story(item)

if __name__ == "__main__":
    main()
