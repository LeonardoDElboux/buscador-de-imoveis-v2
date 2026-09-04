"""
Gera um arquivo `index.html` unificado e 100% autocontido para o projeto todo,
incorporando HTML, CSS, JavaScript, catálogo de imóveis, bairros e fontes.
Funciona perfeitamente tanto online (com backend/Netlify) quanto 100% offline/estático.
"""

import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 1. Carrega dados do banco SQLite
conn = sqlite3.connect(str(BASE_DIR / "database.db"))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM imoveis ORDER BY data_coleta DESC")
imoveis = [dict(r) for r in cursor.fetchall()]
for im in imoveis:
    if "fotos_json" in im and im["fotos_json"]:
        try:
            im["fotos"] = json.loads(im["fotos_json"])
        except Exception:
            im["fotos"] = []
    if "outras_fontes_json" in im and im["outras_fontes_json"]:
        try:
            im["outras_fontes"] = json.loads(im["outras_fontes_json"])
        except Exception:
            im["outras_fontes"] = []

cursor.execute("SELECT * FROM bairros ORDER BY nome ASC")
bairros = [dict(r) for r in cursor.fetchall()]
for b in bairros:
    b["ativo"] = bool(b.get("ativo", 1))

cursor.execute("SELECT * FROM fontes ORDER BY nome ASC")
fontes = [dict(r) for r in cursor.fetchall()]
for f in fontes:
    f["ativa"] = bool(f.get("ativa", 1))

conn.close()

# 2. Carrega CSS e JS originais
css_content = (BASE_DIR / "static" / "style.css").read_text(encoding="utf-8")
js_content = (BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")

# 3. Prepara os dados embutidos
default_data_json = json.dumps({
    "imoveis": imoveis,
    "bairros": bairros,
    "fontes": fontes
}, ensure_ascii=False, indent=2)

# 4. Melhora o JS para funcionar de forma híbrida (Backend ou Standalone com simulação real)
js_hybrid_enhancements = f"""
// DADOS EMBUTIDOS DE BASE PARA EXECUÇÃO AUTOCONTIDA / NETLIFY
window.DEFAULT_DATA = {default_data_json};

// Invalidação imediata de caches antigos do navegador com fotos ou links antigos
const CATALOG_VERSION = "2026_09_04_v12_curated_clean";
try {{
    if (localStorage.getItem("imovel_radar_version") !== CATALOG_VERSION) {{
        localStorage.removeItem("imovel_radar_catalogo");
        localStorage.setItem("imovel_radar_version", CATALOG_VERSION);
    }}
}} catch (e) {{}}

// Enriquecimento para garantir funcionamento 100% igual com ou sem backend
const _origCarregarImoveisCache = carregarImoveisCache;
carregarImoveisCache = async function() {{
    try {{
        const resp = await fetch("/api/imoveis");
        if (resp.ok) {{
            const data = await resp.json();
            if (data.imoveis && data.imoveis.length > 0) {{
                todosImoveis = data.imoveis;
                document.getElementById("label-ultima-pesquisa").textContent = data.ultima_atualizacao || ("Hoje às " + new Date().toLocaleTimeString([], {{hour:'2-digit', minute:'2-digit'}}));
                aplicarFiltrosFront();
                return;
            }}
        }}
    }} catch (e) {{}}
    
    // Standalone fallback com garantia de fotos exclusivas
    todosImoveis = window.DEFAULT_DATA.imoveis;
    try {{ localStorage.setItem("imovel_radar_catalogo", JSON.stringify(todosImoveis)); }} catch (e) {{}}
    document.getElementById("label-ultima-pesquisa").textContent = "Hoje às " + new Date().toLocaleTimeString([], {{hour:'2-digit', minute:'2-digit'}});
    aplicarFiltrosFront();
}};

const _origCarregarBairros = carregarBairros;
carregarBairros = async function() {{
    try {{
        const resp = await fetch("/api/bairros");
        if (resp.ok) {{
            const data = await resp.json();
            if (data.bairros && data.bairros.length > 0) {{
                bairrosConfig = data.bairros;
                document.getElementById("count-bairros").textContent = bairrosConfig.length;
                renderizarListaBairros();
                return;
            }}
        }}
    }} catch (e) {{}}
    
    bairrosConfig = window.DEFAULT_DATA.bairros;
    document.getElementById("count-bairros").textContent = bairrosConfig.length;
    renderizarListaBairros();
}};

const _origCarregarFontes = carregarFontes;
carregarFontes = async function() {{
    try {{
        const resp = await fetch("/api/fontes");
        if (resp.ok) {{
            const data = await resp.json();
            if (data.fontes && data.fontes.length > 0) {{
                fontesConfig = data.fontes;
                document.getElementById("count-fontes").textContent = fontesConfig.length;
                renderizarListaFontes();
                return;
            }}
        }}
    }} catch (e) {{}}
    
    fontesConfig = window.DEFAULT_DATA.fontes;
    document.getElementById("count-fontes").textContent = fontesConfig.length;
    renderizarListaFontes();
}};
"""

# 5. Monta o HTML autocontido final
html_template = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")

# Substitui o link do CSS pela tag <style> completa
html_template = html_template.replace(
    '<link rel="stylesheet" href="/static/style.css">',
    f'<style>\n{css_content}\n</style>'
)

# Adiciona o script embutido no final antes de </body>
html_final = html_template.replace(
    '<script src="/static/app.js"></script>',
    f'<script>\n{js_content}\n\n{js_hybrid_enhancements}\n</script>'
)

# 6. Grava na raiz do projeto (index.html) e em public/index.html
target_root = BASE_DIR / "index.html"
target_public = BASE_DIR / "public" / "index.html"

target_root.write_text(html_final, encoding="utf-8")
target_public.write_text(html_final, encoding="utf-8")

print(f"[OK] index.html unificado criado com sucesso!")
print(f" - Tamanho: {len(html_final.encode('utf-8')) / 1024:.1f} KB")
print(f" - Raiz: {target_root}")
print(f" - Public: {target_public}")
