# GPT-2-Machado-de-Asssis
Modelo de linguagem similar ao GPT-2 com conteúdos do escritor Machado de Assis.

## Etapa 1 — Corpus (`data/machado/`)

Fonte: [Machado de Assis — Obra Completa](https://machado.mec.gov.br/obra-completa-lista) (MEC / Domínio Público / NUPILL-UFSC).

```bash
pip install -r requirements.txt
cd data/machado
python 01_baixar_obras.py   # catálogo (catalogo.csv) + download dos 116 PDFs em pdf/<categoria>/
python 02_extrair_texto.py  # texto limpo em txt/<categoria>/ e corpus completo em machado.txt
```

Limpeza aplicada: remoção do cabeçalho editorial ("Texto-fonte…"), dos sumários ("ÍNDICE") e
das notas dos organizadores; reunião das linhas quebradas pela diagramação usando a
geometria do PDF (versos são preservados); normalização Unicode NFC.

| categoria | obras | caracteres | palavras |
|---|---:|---:|---:|
| crônica | 24 | 3.110.008 | 539.156 |
| romance | 10 | 3.066.229 | 535.227 |
| conto | 7 | 1.728.628 | 299.561 |
| tradução | 3 | 1.078.460 | 185.146 |
| crítica | 45 | 945.872 | 161.994 |
| poesia | 7 | 650.564 | 115.534 |
| teatro | 10 | 368.026 | 64.128 |
| miscelânea | 10 | 67.604 | 11.626 |
| **total** | **116** | **≈11,0 M** | **≈1,91 M** |
