"""
Aplicação principal FastAPI - Buscador de Imóveis (Tentativa 2).
Servidor web local e API REST/SSE para pesquisa em tempo real, favoritos, bairros e fontes.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, Request, Body, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import database
from scrapers.scraper_registry import ScraperRegistry
from services.filtros import aplicar_filtros_e_ordenacao


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa banco de dados SQLite local na subida do servidor
    await database.init_db()
    yield


app = FastAPI(
    title="Buscador de Imóveis",
    description="Monitor e Centralizador Local de Imóveis para Locação",
    version="2.0.0",
    lifespan=lifespan
)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

registry = ScraperRegistry()


@app.get("/", response_class=FileResponse)
async def home():
    """Página principal do Buscador de Imóveis."""
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


@app.get("/health")
async def health_check():
    """Health check do servidor."""
    return {"status": "ok", "app": "Buscador de Imóveis v2"}


@app.get("/api/imoveis")
async def listar_imoveis(
    aluguel_max: Optional[float] = None,
    custo_total_max: Optional[float] = None,
    min_quartos: Optional[int] = None,
    max_quartos: Optional[int] = None,
    min_suites: Optional[int] = None,
    min_banheiros: Optional[int] = None,
    min_vagas: Optional[int] = None,
    area_min: Optional[float] = None,
    pet: Optional[str] = None,
    possui_quintal: Optional[bool] = None,
    garagem_fechada: Optional[bool] = None,
    lavanderia: Optional[bool] = None,
    exigir_escritorio: Optional[bool] = None,
    bairros: Optional[str] = None,
    ordenar_por: str = "recentes"
):
    """
    Retorna os imóveis em cache aplicando filtros dinâmicos em tempo real sem re-scraping (Item 35).
    """
    imoveis = await database.listar_imoveis_cache()

    filtros = {
        "aluguel_max": aluguel_max,
        "custo_total_max": custo_total_max,
        "min_quartos": min_quartos,
        "max_quartos": max_quartos,
        "min_suites": min_suites,
        "min_banheiros": min_banheiros,
        "min_vagas": min_vagas,
        "area_min": area_min,
        "pet": pet,
        "possui_quintal": possui_quintal,
        "garagem_fechada": garagem_fechada,
        "lavanderia": lavanderia,
        "exigir_escritorio": exigir_escritorio,
        "bairros": [b.strip() for b in bairros.split(",")] if bairros else None,
        "ordenar_por": ordenar_por
    }

    resultado = aplicar_filtros_e_ordenacao(imoveis, filtros, ordenar_por=ordenar_por)

    # Identifica quais já estão nos favoritos
    favs = await database.listar_favoritos()
    fav_urls = {f["url"] for f in favs}
    for im in resultado:
        im["favoritado"] = im.get("url") in fav_urls

    ultima_atualizacao = await database.obter_configuracao("ultima_pesquisa", "Nenhuma pesquisa recente")

    return {
        "total": len(resultado),
        "total_bruto_cache": len(imoveis),
        "ultima_atualizacao": ultima_atualizacao,
        "imoveis": resultado
    }


@app.get("/api/pesquisar/stream")
async def stream_pesquisa(filtros_json: Optional[str] = None):
    """
    Endpoint SSE (Server-Sent Events) para transmissão em tempo real do progresso da busca (Itens 24, 25 e 26).
    """
    filtros = json.loads(filtros_json) if filtros_json else {}

    async def event_generator():
        async for evento in registry.executar_pesquisa_com_progresso(filtros):
            data_str = json.dumps(evento, ensure_ascii=False)
            yield f"data: {data_str}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/pesquisar")
async def disparar_pesquisa(filtros: Dict[str, Any] = Body(default={})):
    """Execução direta síncrona/assíncrona da pesquisa."""
    resultado_final = None
    async for evento in registry.executar_pesquisa_com_progresso(filtros):
        if evento.get("tipo") == "concluido":
            resultado_final = evento
    return resultado_final or {"status": "concluido"}


@app.get("/api/favoritos")
async def listar_favoritos():
    """Retorna a lista de imóveis favoritados pelo usuário (Item 32)."""
    favs = await database.listar_favoritos()
    return {"total": len(favs), "favoritos": favs}


@app.post("/api/favoritos/toggle")
async def alternar_favorito(payload: Dict[str, Any] = Body(...)):
    """Adiciona ou remove um imóvel dos favoritos."""
    imovel = payload.get("imovel")
    if not imovel or not imovel.get("url"):
        raise HTTPException(status_code=400, detail="Imóvel inválido")
    is_favorito = await database.alternar_favorito(imovel)
    return {"favoritado": is_favorito}


@app.get("/api/bairros")
async def listar_bairros():
    """Lista todos os bairros e seus status (Item 11)."""
    bairros = await database.listar_bairros_db()
    return {"bairros": bairros}


@app.post("/api/bairros")
async def adicionar_bairro(payload: Dict[str, Any] = Body(...)):
    """Cadastra um novo bairro dinamicamente pela interface."""
    nome = payload.get("nome", "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome do bairro é obrigatório")
    await database.adicionar_bairro_db(nome)
    registry.geo_service.recarregar_bairros()
    return {"status": "ok", "nome": nome}


@app.put("/api/bairros/{nome}/toggle")
async def alternar_status_bairro(nome: str, payload: Dict[str, Any] = Body(...)):
    """Ativa ou desativa a busca em um bairro."""
    ativo = payload.get("ativo", True)
    await database.atualizar_bairro_status(nome, ativo)
    registry.geo_service.recarregar_bairros()
    return {"status": "ok", "nome": nome, "ativo": ativo}


@app.get("/api/fontes")
async def listar_fontes():
    """Lista todas as fontes de scraping cadastradas (Item 39)."""
    fontes = await database.listar_fontes_db()
    return {"fontes": fontes}


@app.post("/api/fontes")
async def adicionar_fonte(payload: Dict[str, Any] = Body(...)):
    """Permite ao usuário cadastrar uma nova imobiliária manualmente (Item 7)."""
    nome = payload.get("nome", "").strip()
    url = payload.get("url", "").strip()
    if not nome or not url:
        raise HTTPException(status_code=400, detail="Nome e URL da imobiliária são obrigatórios")
    fonte_id = await database.adicionar_fonte_db(nome, url)
    return {"status": "ok", "id": fonte_id, "nome": nome}


@app.get("/api/configuracoes")
async def obter_configuracoes():
    """Retorna as configurações salvas de filtros e preferências."""
    filtros = await database.obter_configuracao("filtros_usuario", {})
    ultima_pesquisa = await database.obter_configuracao("ultima_pesquisa", None)
    return {"filtros": filtros, "ultima_pesquisa": ultima_pesquisa}


@app.post("/api/configuracoes")
async def salvar_configuracoes(payload: Dict[str, Any] = Body(...)):
    """Salva as configurações da interface no SQLite local (Item 40)."""
    await database.salvar_configuracao("filtros_usuario", payload)
    return {"status": "ok"}
