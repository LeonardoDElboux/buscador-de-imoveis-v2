"""
Script de compilação e empacotamento estático para publicação no Netlify.
Cria o diretório `public/` com o frontend otimizado para o Edge CDN.
"""

import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


def build():
    print("[1/3] Limpando e preparando diretório public/...")
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DIR / "static").mkdir(parents=True, exist_ok=True)

    print("[2/3] Copiando index.html unificado e assets estáticos...")
    import subprocess
    subprocess.run([sys.executable, str(BASE_DIR / "generate_single_index_html.py")], check=True)
    shutil.copyfile(BASE_DIR / "index.html", PUBLIC_DIR / "index.html")
    shutil.copyfile(STATIC_DIR / "style.css", PUBLIC_DIR / "static" / "style.css")
    shutil.copyfile(STATIC_DIR / "app.js", PUBLIC_DIR / "static" / "app.js")

    print("[3/3] Gerando arquivo _redirects para o Netlify...")
    redirects_content = """# Roteamento de API para Serverless Function
/api/*  /.netlify/functions/api/:splat  200

# Roteamento SPA
/*  /index.html  200
"""
    (PUBLIC_DIR / "_redirects").write_text(redirects_content, encoding="utf-8")

    print(f"[OK] Build do Netlify concluído com sucesso em: {PUBLIC_DIR}")


if __name__ == "__main__":
    build()
