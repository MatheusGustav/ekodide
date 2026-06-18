"""O portal web do Ekodide: uma paginazinha pro aparelho que NÃO tem Ekodide.

A ideia: o celular não instala nada — abre um link no navegador (o app que todo
aparelho já tem) e manda/baixa arquivo por aqui. Quem roda o `serve --web` (o PC,
em geral) é que serve esta página.

Honestidade: o navegador não sabe fazer o lacre (HMAC), então o portal é protegido
só por um PIN e NÃO cifra — use em rede de confiança. É uma porta mais fraca que a
de Ekodide-pra-Ekodide, por isso fica OPCIONAL (`--web`).

Este módulo é PURO: só monta texto (HTML). Quem lê/grava arquivo e confere o PIN é
o recebedor. Sem dependência — string e stdlib (`json`, `html`, `urllib.parse`).
"""
from __future__ import annotations

import json
from html import escape
from urllib.parse import quote

_ESTILO = """
 body{font-family:system-ui,-apple-system,sans-serif;max-width:560px;margin:2rem auto;
      padding:0 1rem;color:#1d1d1f;background:#fafafa}
 h1{font-size:1.4rem} h2{font-size:1rem;margin:.2rem 0}
 .cartao{background:#fff;border:1px solid #e6e6e6;border-radius:12px;padding:1rem;margin:1rem 0}
 button{background:#1f8a4c;color:#fff;border:0;border-radius:8px;padding:.6rem 1.1rem;font-size:1rem}
 input[type=file]{width:100%;margin:.4rem 0}
 input[type=text]{padding:.5rem;font-size:1rem;border:1px solid #ccc;border-radius:8px}
 .lista a{display:block;padding:.45rem 0;border-bottom:1px solid #eee;color:#1f8a4c;text-decoration:none}
 .aviso{color:#999;font-size:.82rem} #status{margin-top:.6rem;font-size:.9rem;color:#1f8a4c}
"""


def _moldura(corpo: str) -> str:
    return (
        '<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Ekodide</title><style>{_ESTILO}</style></head><body>{corpo}</body></html>"
    )


def pagina_pin() -> str:
    """Página simples pedindo o PIN (quando o link foi aberto sem ele)."""
    return _moldura(
        '<h1>Ekodide \U0001F99C</h1>'
        '<div class="cartao"><form method="get" action="/">'
        "<p>Digite o PIN que apareceu no outro aparelho:</p>"
        '<input type="text" name="k" autofocus autocapitalize="off" autocomplete="off"> '
        "<button>entrar</button></form></div>"
    )


def pagina(token: str, arquivos: list[str]) -> str:
    """Página principal: enviar arquivos pra cá e baixar os que já chegaram."""
    if arquivos:
        itens = "".join(
            f'<a href="/web/download?nome={quote(a)}&k={quote(token)}">⬇️ {escape(a)}</a>'
            for a in arquivos
        )
    else:
        itens = '<p class="aviso">nada recebido ainda.</p>'
    corpo = (
        '<h1>Ekodide \U0001F99C</h1>'
        '<div class="cartao"><h2>Enviar pra cá</h2>'
        '<input type="file" id="arq" multiple>'
        '<p><button onclick="enviar()">enviar</button></p>'
        '<div id="status"></div></div>'
        f'<div class="cartao"><h2>Baixar daqui</h2><div class="lista">{itens}</div></div>'
        '<p class="aviso">Protegido só por PIN, sem cadeado forte — use na sua rede de confiança.</p>'
        f"<script>const K={json.dumps(token)};"
        "async function enviar(){"
        "const f=document.getElementById('arq').files,s=document.getElementById('status');"
        "if(!f.length){s.textContent='escolha um arquivo';return;}"
        "for(const a of f){s.textContent='enviando '+a.name+'…';"
        "const r=await fetch('/web/upload?k='+encodeURIComponent(K)+'&nome='+encodeURIComponent(a.name),"
        "{method:'POST',body:a});"
        "if(!r.ok){s.textContent='falhou em '+a.name+' ('+r.status+')';return;}}"
        "s.textContent='pronto! recarregue a página pra ver na lista de baixar.';}"
        "</script>"
    )
    return _moldura(corpo)
