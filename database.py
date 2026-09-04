"""
Camada de persistência local SQLite usando aiosqlite.
Gerencia cache da última pesquisa, favoritos, bairros, fontes e configurações locais.
"""

import json
import os
import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import shutil
import tempfile

# Detecta se está rodando no ambiente Serverless da AWS Lambda / Netlify
if os.environ.get("NETLIFY") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = str(Path(tempfile.gettempdir()) / "database.db")
    seed_db = Path(__file__).parent / "database.db"
    if seed_db.exists() and not Path(DB_PATH).exists():
        try:
            shutil.copyfile(str(seed_db), DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = str(Path(__file__).parent / "database.db")

_DB_INITIALIZED = False


@asynccontextmanager
async def _raw_get_db():
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def ensure_db_initialized():
    global _DB_INITIALIZED
    if not _DB_INITIALIZED:
        _DB_INITIALIZED = True
        await init_db()


@asynccontextmanager
async def get_db():
    """Gerenciador de contexto assíncrono para conexão com o banco SQLite."""
    await ensure_db_initialized()
    async with _raw_get_db() as conn:
        yield conn


async def init_db() -> None:
    """Inicializa as tabelas do banco de dados se não existirem."""
    async with _raw_get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS imoveis (
                id TEXT PRIMARY KEY,
                titulo TEXT,
                bairro TEXT,
                endereco TEXT,
                latitude REAL,
                longitude REAL,
                aluguel REAL,
                condominio REAL,
                iptu REAL,
                custo_total REAL,
                quartos INTEGER,
                suites INTEGER,
                banheiros INTEGER,
                vagas INTEGER,
                area REAL,
                tipo TEXT,
                pet TEXT,
                quintal TEXT,
                garagem_fechada TEXT,
                lavanderia INTEGER,
                descricao TEXT,
                fotos_json TEXT,
                fonte TEXT,
                url TEXT UNIQUE,
                outras_fontes_json TEXT,
                observacao_localizacao TEXT,
                indisponivel INTEGER DEFAULT 0,
                data_coleta TEXT,
                data_atualizacao TEXT
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS favoritos (
                url TEXT PRIMARY KEY,
                imovel_id TEXT,
                dados_json TEXT,
                data_favoritado TEXT,
                indisponivel INTEGER DEFAULT 0
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bairros (
                nome TEXT PRIMARY KEY,
                ativo INTEGER DEFAULT 1,
                aliases_json TEXT,
                regra_especial_json TEXT
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS fontes (
                id TEXT PRIMARY KEY,
                nome TEXT,
                url TEXT,
                scraper TEXT,
                ativa INTEGER DEFAULT 1,
                status TEXT,
                ultima_tentativa TEXT,
                imoveis_encontrados INTEGER DEFAULT 0
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor_json TEXT
            );
        """)

        await db.commit()

        # Seed inicial de bairros e fontes se estiverem vazios
        cursor = await db.execute("SELECT COUNT(*) as count FROM bairros")
        row = await cursor.fetchone()
        if row and row["count"] == 0:
            bairros_path = Path(__file__).parent / "config" / "bairros.json"
            if bairros_path.exists():
                with open(bairros_path, "r", encoding="utf-8") as f:
                    bairros_data = json.load(f)
                    for b in bairros_data:
                        await db.execute(
                            "INSERT OR REPLACE INTO bairros (nome, ativo, aliases_json, regra_especial_json) VALUES (?, ?, ?, ?)",
                            (
                                b["nome"],
                                1 if b.get("ativo", True) else 0,
                                json.dumps(b.get("aliases", []), ensure_ascii=False),
                                json.dumps(b.get("regra_especial"), ensure_ascii=False) if b.get("regra_especial") else None
                            )
                        )

        fontes_path = Path(__file__).parent / "config" / "fontes.json"
        if fontes_path.exists():
            with open(fontes_path, "r", encoding="utf-8") as f:
                fontes_data = json.load(f)
                for s in fontes_data:
                    await db.execute(
                        """INSERT INTO fontes (id, nome, url, scraper, ativa, status, ultima_tentativa, imoveis_encontrados)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET
                               nome=excluded.nome,
                               url=excluded.url,
                               scraper=excluded.scraper;""",
                        (
                            s["id"],
                            s["nome"],
                            s["url"],
                            s.get("scraper", "generic_agency"),
                            1 if s.get("ativa", True) else 0,
                            s.get("status", "funcionando"),
                            s.get("ultima_tentativa"),
                            s.get("imoveis_encontrados", 0)
                        )
                    )

        await db.commit()


async def salvar_imoveis_pesquisa(imoveis: List[Dict[str, Any]]) -> None:
    """Salva os imóveis encontrados no cache da pesquisa."""
    async with get_db() as db:
        for im in imoveis:
            url = im.get("url")
            if not url:
                continue

            fotos_json = json.dumps(im.get("fotos") or [], ensure_ascii=False)
            outras_fontes_json = json.dumps(im.get("outras_fontes") or [], ensure_ascii=False)

            await db.execute("""
                INSERT INTO imoveis (
                    id, titulo, bairro, endereco, latitude, longitude,
                    aluguel, condominio, iptu, custo_total, quartos, suites,
                    banheiros, vagas, area, tipo, pet, quintal, garagem_fechada,
                    lavanderia, descricao, fotos_json, fonte, url,
                    outras_fontes_json, observacao_localizacao, indisponivel,
                    data_coleta, data_atualizacao
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, datetime('now')
                )
                ON CONFLICT(url) DO UPDATE SET
                    titulo=excluded.titulo,
                    bairro=excluded.bairro,
                    aluguel=excluded.aluguel,
                    condominio=excluded.condominio,
                    iptu=excluded.iptu,
                    custo_total=excluded.custo_total,
                    quartos=excluded.quartos,
                    suites=excluded.suites,
                    banheiros=excluded.banheiros,
                    vagas=excluded.vagas,
                    area=excluded.area,
                    pet=excluded.pet,
                    quintal=excluded.quintal,
                    garagem_fechada=excluded.garagem_fechada,
                    lavanderia=excluded.lavanderia,
                    descricao=excluded.descricao,
                    fotos_json=excluded.fotos_json,
                    outras_fontes_json=excluded.outras_fontes_json,
                    observacao_localizacao=excluded.observacao_localizacao,
                    data_atualizacao=datetime('now');
            """, (
                im.get("id") or url,
                im.get("titulo"),
                im.get("bairro"),
                im.get("endereco"),
                im.get("latitude"),
                im.get("longitude"),
                im.get("aluguel"),
                im.get("condominio"),
                im.get("iptu"),
                im.get("custo_total"),
                im.get("quartos"),
                im.get("suites"),
                im.get("banheiros"),
                im.get("vagas"),
                im.get("area"),
                im.get("tipo"),
                im.get("pet"),
                im.get("quintal"),
                im.get("garagem_fechada"),
                1 if im.get("lavanderia") else 0,
                im.get("descricao"),
                fotos_json,
                im.get("fonte"),
                url,
                outras_fontes_json,
                im.get("observacao_localizacao"),
                0,
                im.get("data_coleta")
            ))
        await db.commit()


async def listar_imoveis_cache() -> List[Dict[str, Any]]:
    """Carrega todos os imóveis armazenados no banco local."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM imoveis WHERE indisponivel = 0 ORDER BY data_coleta DESC")
        rows = await cursor.fetchall()

        resultado = []
        for r in rows:
            im = dict(r)
            im["fotos"] = json.loads(im["fotos_json"]) if im.get("fotos_json") else []
            im["outras_fontes"] = json.loads(im["outras_fontes_json"]) if im.get("outras_fontes_json") else []
            im["lavanderia"] = bool(im["lavanderia"])
            resultado.append(im)
        return resultado


async def alternar_favorito(imovel_dados: Dict[str, Any]) -> bool:
    """Adiciona ou remove um imóvel dos favoritos. Retorna True se favoritado, False se removido."""
    url = imovel_dados.get("url")
    if not url:
        return False

    async with get_db() as db:
        cursor = await db.execute("SELECT url FROM favoritos WHERE url = ?", (url,))
        row = await cursor.fetchone()

        if row:
            # Já está favoritado: remover
            await db.execute("DELETE FROM favoritos WHERE url = ?", (url,))
            await db.commit()
            return False
        else:
            # Adicionar aos favoritos
            await db.execute(
                "INSERT INTO favoritos (url, imovel_id, dados_json, data_favoritado, indisponivel) VALUES (?, ?, ?, datetime('now'), 0)",
                (url, imovel_dados.get("id") or url, json.dumps(imovel_dados, ensure_ascii=False))
            )
            await db.commit()
            return True


async def listar_favoritos() -> List[Dict[str, Any]]:
    """Retorna lista de todos os imóveis favoritados."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM favoritos ORDER BY data_favoritado DESC")
        rows = await cursor.fetchall()

        favs = []
        for r in rows:
            dados = json.loads(r["dados_json"])
            dados["favoritado"] = True
            dados["indisponivel"] = bool(r["indisponivel"])
            favs.append(dados)
        return favs


async def listar_bairros_db() -> List[Dict[str, Any]]:
    """Retorna a lista de bairros cadastrados."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM bairros ORDER BY nome ASC")
        rows = await cursor.fetchall()
        return [
            {
                "nome": r["nome"],
                "ativo": bool(r["ativo"]),
                "aliases": json.loads(r["aliases_json"]) if r["aliases_json"] else [],
                "regra_especial": json.loads(r["regra_especial_json"]) if r["regra_especial_json"] else None
            }
            for r in rows
        ]


async def atualizar_bairro_status(nome: str, ativo: bool) -> None:
    """Ativa ou desativa um bairro."""
    async with get_db() as db:
        await db.execute("UPDATE bairros SET ativo = ? WHERE nome = ?", (1 if ativo else 0, nome))
        await db.commit()


async def adicionar_bairro_db(nome: str) -> None:
    """Adiciona um novo bairro ao sistema."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO bairros (nome, ativo, aliases_json) VALUES (?, 1, ?)",
            (nome, json.dumps([nome.lower()], ensure_ascii=False))
        )
        await db.commit()


async def listar_fontes_db() -> List[Dict[str, Any]]:
    """Lista todas as fontes cadastradas."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM fontes ORDER BY nome ASC")
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "nome": r["nome"],
                "url": r["url"],
                "scraper": r["scraper"],
                "ativa": bool(r["ativa"]),
                "status": r["status"],
                "ultima_tentativa": r["ultima_tentativa"],
                "imoveis_encontrados": r["imoveis_encontrados"]
            }
            for r in rows
        ]


async def adicionar_fonte_db(nome: str, url: str) -> str:
    """Adiciona uma nova imobiliária/fonte de busca."""
    import re
    fonte_id = re.sub(r"[^a-zA-Z0-9_]", "", nome.lower().replace(" ", "_"))
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO fontes (id, nome, url, scraper, ativa, status, ultima_tentativa, imoveis_encontrados) VALUES (?, ?, ?, 'generic_agency', 1, 'funcionando', NULL, 0)",
            (fonte_id, nome, url)
        )
        await db.commit()
    return fonte_id


async def atualizar_status_fonte(fonte_id: str, status: str, total_encontrados: int) -> None:
    """Atualiza o status de uma fonte após tentativa de busca."""
    async with get_db() as db:
        await db.execute(
            "UPDATE fontes SET status = ?, ultima_tentativa = datetime('now'), imoveis_encontrados = ? WHERE id = ?",
            (status, total_encontrados, fonte_id)
        )
        await db.commit()


async def salvar_configuracao(chave: str, valor: Any) -> None:
    """Salva configurações da UI no SQLite."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor_json) VALUES (?, ?)",
            (chave, json.dumps(valor, ensure_ascii=False))
        )
        await db.commit()


async def obter_configuracao(chave: str, default: Any = None) -> Any:
    """Obtém configuração salva."""
    async with get_db() as db:
        cursor = await db.execute("SELECT valor_json FROM configuracoes WHERE chave = ?", (chave,))
        row = await cursor.fetchone()
        if row and row["valor_json"]:
            return json.loads(row["valor_json"])
        return default
