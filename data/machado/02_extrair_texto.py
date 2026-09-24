"""
Etapa 2 — Extração e limpeza do texto dos PDFs (código próprio).

Lê catalogo.csv (gerado por 01_baixar_obras.py), extrai o texto de cada PDF
com PyMuPDF e aplica a limpeza:

  1. remove o cabeçalho editorial ("Texto-fonte: ... Publicado originalmente ...");
  2. remove sumários ("ÍNDICE" seguido da lista de títulos/capítulos);
  3. remove chamadas de nota ("[1]") e o corpo das notas quando são editoriais;
  4. desfaz a quebra de linha dos parágrafos em prosa, preservando versos
     (usa a posição de cada linha no PDF para saber se ela chegou à margem direita);
  5. normaliza Unicode (NFC), espaços e linhas em branco.

Saídas:
  txt/<categoria>/<obra>.txt   — um arquivo limpo por obra
  machado.txt                  — corpus completo (obras separadas por linha em branco dupla)

Uso:
    python 02_extrair_texto.py
"""

import csv
import re
import unicodedata
from pathlib import Path

import pymupdf

RAIZ = Path(__file__).parent
CATALOGO = RAIZ / "catalogo.csv"
DIR_TXT = RAIZ / "txt"
CORPUS = RAIZ / "machado.txt"

RE_FONTE = re.compile(r"^Textos?[- ]?(fonte|de refer[êe]ncia)\s*:", re.I)
RE_PUBLICADO = re.compile(r"^Publicad[oa]s? originalmente", re.I)
RE_NOTA = re.compile(r"^\[\d+\]")
RE_CHAMADA = re.compile(r"\s?\[\d+\]")
# Obras cujas notas de rodapé são dos organizadores da edição (não de Machado).
# Nas demais (Falenas, Americanas, O Almada, O jornal e o livro) as notas são do autor e são mantidas.
NOTAS_EDITORIAIS = {"1854_1939_dispersas", "1872_un_cuento_endemoniado_e_la_mujer_misteriosa_de_guilherme_malta"}


class Linha(str):
    """Linha de texto que sabe se continua na linha seguinte (quebra feita pela diagramação)."""

    continua = False

    def com_texto(self, texto: str) -> "Linha":
        nova = Linha(texto)
        nova.continua = self.continua
        return nova


def extrair_linhas(caminho: Path) -> list[Linha]:
    """Texto do PDF como lista de linhas, marcando as que foram quebradas pela diagramação.

    Usa a geometria do PDF: uma linha "continua" se termina na margem direita (prosa
    justificada) ou se a primeira palavra da linha seguinte não caberia nela. Versos
    terminam antes da margem e por isso não são unidos. Linhas em branco no início/fim
    de cada página são descartadas para que um parágrafo interrompido pela página seja reunido.
    """
    brutas = []  # (texto, x1, largura média de caractere, largura da página)
    with pymupdf.open(caminho) as doc:
        for pagina in doc:
            # O PDF às vezes divide uma linha visual em vários pedaços; eles são
            # reunidos quando estão na mesma altura e à direita do pedaço anterior.
            pedacos = []  # [texto, x0, y0, x1]
            for bloco in pagina.get_text("dict")["blocks"]:
                for l in bloco.get("lines", []):
                    texto = "".join(s["text"] for s in l["spans"])
                    x0, y0, x1, _ = l["bbox"]
                    ant = pedacos[-1] if pedacos else None
                    if ant and abs(y0 - ant[2]) < 2 and x0 >= ant[3] - 1:
                        sep = "" if ant[0].endswith(" ") or texto.startswith(" ") else " "
                        ant[0] += sep + texto
                        ant[3] = x1
                    else:
                        pedacos.append([texto, x0, y0, x1])
            ls = []
            for texto, x0, _, x1 in pedacos:
                texto = texto.rstrip()
                cw = (x1 - x0) / max(len(texto), 1)
                ls.append((texto, x1, cw, pagina.rect.width))
            while ls and not ls[0][0].strip():
                ls.pop(0)
            while ls and not ls[-1][0].strip():
                ls.pop()
            brutas += ls

    bordas = sorted(x1 for t, x1, _, _ in brutas if len(t.strip()) > 20)
    if not bordas:
        return [Linha(t) for t, *_ in brutas]
    largura_pag = max(w for *_, w in brutas)
    margem = max(bordas[int(0.95 * (len(bordas) - 1))], 0.75 * largura_pag)

    linhas = []
    for i, (texto, x1, cw, _) in enumerate(brutas):
        linha = Linha(texto)
        prox = brutas[i + 1][0].strip() if i + 1 < len(brutas) else ""
        if texto.strip() and prox:
            palavra = prox.split()[0]
            linha.continua = x1 >= margem - 3 or x1 + (len(palavra) + 1) * cw > margem
        linhas.append(linha)
    return linhas


def remover_cabecalho(linhas: list[Linha]) -> list[Linha]:
    for i, l in enumerate(linhas[:40]):
        if RE_FONTE.match(l.strip()):
            fim = i
            # O bloco termina na linha "Publicado originalmente..." (se houver, até 3 parágrafos
            # adiante) ou, caso contrário, no fim do parágrafo da referência.
            for j in range(i, min(i + 20, len(linhas))):
                if RE_PUBLICADO.match(linhas[j].strip()):
                    fim = j
                    while fim + 1 < len(linhas) and linhas[fim + 1].strip():
                        fim += 1
                    break
            else:
                while fim + 1 < len(linhas) and linhas[fim + 1].strip():
                    fim += 1
            return linhas[fim + 1 :]
    return linhas


def remover_indices(linhas: list[Linha]) -> list[Linha]:
    """Remove "ÍNDICE" + entradas. A lista termina quando uma entrada reaparece
    (início do conteúdo) ou quando surge uma linha longa (texto corrido)."""
    saida, i = [], 0
    while i < len(linhas):
        if linhas[i].strip().upper() != "ÍNDICE":
            saida.append(linhas[i])
            i += 1
            continue
        j = i + 1
        entradas = set()
        while j < len(linhas):
            l = linhas[j].strip()
            if not l:
                j += 1
                continue
            if len(l) > 60 or l in entradas:
                break
            entradas.add(l)
            j += 1
        if j - i > 400:  # salvaguarda: não parece um sumário, mantém o texto
            saida.append(linhas[i])
            i += 1
        else:
            i = j
    return saida


def remover_notas(linhas: list[Linha], editoriais: bool) -> list[Linha]:
    """Remove as chamadas "[n]"; se as notas forem editoriais, remove também o corpo delas."""
    saida, em_nota = [], False
    for l in linhas:
        if editoriais and RE_NOTA.match(l.strip()):
            em_nota = True
        elif not l.strip():
            em_nota = False
        if not em_nota:
            saida.append(l.com_texto(RE_CHAMADA.sub("", l)) if isinstance(l, Linha) else l)
    return saida


def reunir_paragrafos(linhas: list[Linha]) -> str:
    """Une as linhas quebradas pela diagramação (ver extrair_linhas); preserva as demais."""
    paragrafos, atual = [], ""
    for l in linhas:
        s = " ".join(l.split())
        if not s:
            if atual:
                paragrafos.append(atual)
                atual = ""
            paragrafos.append("")
            continue
        if not atual:
            atual = s
        elif atual.endswith("-") and not atual.endswith(" -"):
            atual += s  # hífen real (ênclise: "impedir-lho"), une sem espaço
        else:
            atual += " " + s
        if not getattr(l, "continua", False):
            paragrafos.append(atual)
            atual = ""
    if atual:
        paragrafos.append(atual)

    texto = "\n".join(paragrafos)
    # Linhas em branco entre versos/parágrafos: no máximo uma.
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto)
    texto = texto.replace(" ", " ").replace("­", "").replace("\t", " ")
    texto = re.sub(r"[​-‏﻿]", "", texto)
    texto = re.sub(r" {2,}", " ", texto)
    return texto


def limpar(caminho: Path) -> str:
    linhas = extrair_linhas(caminho)
    linhas = remover_cabecalho(linhas)
    linhas = remover_indices(linhas)
    linhas = remover_notas(linhas, caminho.stem in NOTAS_EDITORIAIS)
    return normalizar(reunir_paragrafos(linhas))


def main():
    with open(CATALOGO, encoding="utf-8") as f:
        obras = list(csv.DictReader(f))

    textos = []
    for o in obras:
        pdf = RAIZ / o["arquivo"]
        texto = limpar(pdf)
        destino = DIR_TXT / pdf.relative_to(RAIZ / "pdf").with_suffix(".txt")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto + "\n", encoding="utf-8")
        textos.append(texto)
        print(f"{len(texto):>9,} chars  {o['categoria']:<10} {o['titulo']}")

    corpus = "\n\n\n".join(textos) + "\n"
    CORPUS.write_text(corpus, encoding="utf-8")
    print(f"\nCorpus: {CORPUS} — {len(corpus):,} caracteres, "
          f"{len(corpus.split()):,} palavras, {len(set(corpus))} caracteres distintos")


if __name__ == "__main__":
    main()
