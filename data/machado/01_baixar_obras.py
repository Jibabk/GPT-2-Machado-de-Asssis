"""
Etapa 1 — Coleta das obras de Machado de Assis (código próprio).

Fonte: portal "Machado de Assis — Obra Completa" (MEC / Domínio Público / NUPILL-UFSC)
       https://machado.mec.gov.br/obra-completa-lista

O script percorre cada categoria do portal (Romance, Conto, Poesia, ...),
coleta título, ano e link de download de cada obra, grava um catálogo
(catalogo.csv) e baixa os PDFs para pdf/<categoria>/.

Uso:
    python 01_baixar_obras.py
"""

import csv
import re
import time
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://machado.mec.gov.br"
# Um User-Agent de navegador é necessário: o Cloudflare do portal bloqueia o UA padrão.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
}
CATEGORIAS = {
    23: "romance",
    24: "conto",
    25: "poesia",
    26: "cronica",
    27: "teatro",
    28: "critica",
    29: "traducao",
    30: "miscelanea",
}
POR_PAGINA = 12
PAUSA = 1.0  # segundos entre requisições, para não sobrecarregar o servidor

RAIZ = Path(__file__).parent
DIR_PDF = RAIZ / "pdf"
CATALOGO = RAIZ / "catalogo.csv"

sessao = requests.Session()
sessao.headers.update(HEADERS)


def slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")[:80]


def obter_html(url: str) -> BeautifulSoup:
    r = sessao.get(url, timeout=60)
    r.raise_for_status()
    if "Just a moment" in r.text[:2000]:
        raise RuntimeError(f"Bloqueado pelo Cloudflare: {url}")
    r.encoding = r.apparent_encoding  # o portal serve ISO-8859-1 sem declarar corretamente
    return BeautifulSoup(r.text, "html.parser")


def listar_categoria(cat_id: int, nome: str) -> list[dict]:
    obras, start = [], 0
    while True:
        url = (
            f"{BASE}/index.php?option=com_k2&view=itemlist&layout=category"
            f"&task=category&id={cat_id}&order=year&Itemid=668&start={start}"
        )
        soup = obter_html(url)
        itens = soup.select("div.resultadoBusca div.item")
        for item in itens:
            titulo = item.select_one(".titulo")
            ano = item.select_one(".detalhe.ano")
            link = item.select_one(".download a[href*='item/download']")
            if not (titulo and link):
                continue
            obras.append(
                {
                    "categoria": nome,
                    "titulo": " ".join(titulo.get_text().split()),
                    "ano": " ".join(ano.get_text().split()) if ano else "",
                    "url": BASE + link["href"],
                }
            )
        print(f"  {nome} start={start}: {len(itens)} itens")
        if len(itens) < POR_PAGINA:
            return obras
        start += POR_PAGINA
        time.sleep(PAUSA)


def baixar(obra: dict) -> Path:
    destino = DIR_PDF / obra["categoria"] / f"{slug(obra['ano'])}_{slug(obra['titulo'])}.pdf"
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = sessao.get(obra["url"], timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"Resposta não é PDF: {obra['url']}")
    destino.write_bytes(r.content)
    time.sleep(PAUSA)
    return destino


def main():
    obras = []
    for cat_id, nome in CATEGORIAS.items():
        print(f"Categoria {nome}")
        obras += listar_categoria(cat_id, nome)
        time.sleep(PAUSA)

    # Uma mesma obra pode aparecer em mais de uma categoria: mantém a primeira.
    vistos, unicas = set(), []
    for o in obras:
        if o["url"] not in vistos:
            vistos.add(o["url"])
            unicas.append(o)
    print(f"\n{len(obras)} entradas, {len(unicas)} obras únicas")

    for i, o in enumerate(unicas, 1):
        caminho = baixar(o)
        o["arquivo"] = caminho.relative_to(RAIZ).as_posix()
        print(f"[{i}/{len(unicas)}] {o['categoria']}: {o['titulo']} ({o['ano']})")

    with open(CATALOGO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["categoria", "titulo", "ano", "url", "arquivo"])
        w.writeheader()
        w.writerows(unicas)
    print(f"\nCatálogo salvo em {CATALOGO}")


if __name__ == "__main__":
    main()
