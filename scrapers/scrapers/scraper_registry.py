"""
Orquestrador central de scrapers com concorrência segura, isolamento estrito de falhas
e geração de eventos de progresso em tempo real para a interface (SSE).
"""

import asyncio
import datetime
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from scrapers.base import BaseScraper
from scrapers.garoni import GaroniScraper
from scrapers.gimenez import GimenezScraper
from scrapers.olx import OlxScraper
from scrapers.lopes import LopesScraper
from scrapers.vivareal import VivaRealScraper
from scrapers.zapimoveis import ZapImoveisScraper
from scrapers.quintoandar import QuintoAndarScraper
from scrapers.imovelweb import ImovelwebScraper
from scrapers.marcelo import MarceloScraper
from scrapers.zimmermann import ZimmermannScraper
from scrapers.pacheco import PachecoScraper
from scrapers.marques_dias import MarquesDiasScraper
from scrapers.caramelo import CarameloScraper
from scrapers.carrera import CarreraScraper
from scrapers.lobelo import LobeloScraper
from scrapers.confia import ConfiaScraper
from scrapers.gamba import GambaScraper
from scrapers.montenegro import MontenegroScraper
from scrapers.generic_agency import GenericAgencyScraper

from services.geolocalizacao import GeoService
from services.deduplicacao import deduplicar_imoveis
from services.filtros import aplicar_filtros_e_ordenacao
import database

logger = logging.getLogger("scrapers.registry")


class ScraperRegistry:
    def __init__(self):
        self.geo_service = GeoService()

    def instanciar_scraper(self, fonte_dict: Dict[str, Any]) -> BaseScraper:
        """Cria o objeto scraper correspondente à fonte configurada."""
        f_id = fonte_dict.get("id", "generica")
        nome = fonte_dict.get("nome", "Imobiliária")
        url = fonte_dict.get("url", "")
        tipo = fonte_dict.get("scraper", "generic_agency")

        if tipo == "garoni":
            return GaroniScraper()
        elif tipo == "gimenez":
            return GimenezScraper()
        elif tipo == "olx":
            return OlxScraper()
        elif tipo == "lopes":
            return LopesScraper()
        elif tipo == "vivareal":
            return VivaRealScraper()
        elif tipo == "zapimoveis":
            return ZapImoveisScraper()
        elif tipo == "quintoandar":
            return QuintoAndarScraper()
        elif tipo == "imovelweb":
            return ImovelwebScraper()
        elif tipo == "marcelo":
            return MarceloScraper()
        elif tipo == "zimmermann":
            return ZimmermannScraper()
        elif tipo == "pacheco":
            return PachecoScraper()
        elif tipo == "marques_dias":
            return MarquesDiasScraper()
        elif tipo == "caramelo":
            return CarameloScraper()
        elif tipo == "carrera":
            return CarreraScraper()
        elif tipo == "lobelo":
            return LobeloScraper()
        elif tipo == "confia":
            return ConfiaScraper()
        elif tipo == "gamba":
            return GambaScraper()
        elif tipo == "montenegro":
            return MontenegroScraper()
        else:
            return GenericAgencyScraper(fonte_id=f_id, nome=nome, url_base=url)

    async def executar_pesquisa_com_progresso(
        self,
        filtros: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executa as 10 etapas da pesquisa descritas no Item 24 do PRD e transmite
        o progresso em tempo real (Item 25 do PRD).
        """
        filtros = filtros or {}

        # Etapa 1: Carregar filtros e bairros ativos
        yield {
            "etapa": 1,
            "mensagem": "Carregando filtros e preferências de busca...",
            "tipo": "progresso"
        }
        bairros_db = await database.listar_bairros_db()
        bairros_ativos = [b["nome"] for b in bairros_db if b.get("ativo", True)]
        if not bairros_ativos:
            bairros_ativos = ["Parque São Domingos", "Lapa", "Perdizes", "Vila Romana"]

        # Etapa 2: Identificar fontes ativas
        yield {
            "etapa": 2,
            "mensagem": "Identificando fontes e imobiliárias ativas...",
            "tipo": "progresso"
        }
        fontes_db = await database.listar_fontes_db()
        fontes_ativas = [f for f in fontes_db if f.get("ativa", True)]
        total_fontes = len(fontes_ativas)

        yield {
            "etapa": 2,
            "mensagem": f"{total_fontes} fontes ativas selecionadas para consulta.",
            "total_fontes": total_fontes,
            "tipo": "progresso"
        }

        # Etapas 3 e 4: Consultar fontes e extrair anúncios
        todos_anuncios: List[Dict[str, Any]] = []
        fontes_sucesso = 0
        fontes_erro = 0
        consultadas = 0

        # Semáforo de concorrência responsável (Item 43 do PRD)
        semaforo = asyncio.Semaphore(3)

        for fonte in fontes_ativas:
            consultadas += 1
            nome_fonte = fonte.get("nome", "Fonte")
            fonte_id = fonte.get("id")

            yield {
                "etapa": 3,
                "mensagem": f"Consultando {nome_fonte} ({consultadas}/{total_fontes})...",
                "fonte_atual": nome_fonte,
                "consultadas": consultadas,
                "total_fontes": total_fontes,
                "tipo": "progresso_fonte",
                "status_fonte": "pesquisando"
            }

            scraper = self.instanciar_scraper(fonte)
            try:
                async with semaforo:
                    # Delay leve de scraping responsável
                    await asyncio.sleep(0.3)
                    imoveis_fonte = await asyncio.wait_for(
                        scraper.extrair_imoveis(bairros_ativos, filtros),
                        timeout=18.0
                    )

                fontes_sucesso += 1
                todos_anuncios.extend(imoveis_fonte)
                await database.atualizar_status_fonte(fonte_id, "funcionando", len(imoveis_fonte))

                yield {
                    "etapa": 4,
                    "mensagem": f"{nome_fonte} ✓ ({len(imoveis_fonte)} anúncios encontrados)",
                    "fonte_atual": nome_fonte,
                    "consultadas": consultadas,
                    "total_fontes": total_fontes,
                    "tipo": "progresso_fonte",
                    "status_fonte": "sucesso",
                    "anuncios_fonte": len(imoveis_fonte)
                }

            except Exception as exc:
                fontes_erro += 1
                logger.warning(f"Erro ao consultar {nome_fonte}: {exc}")
                await database.atualizar_status_fonte(fonte_id, "erro", 0)

                yield {
                    "etapa": 4,
                    "mensagem": f"{nome_fonte} ✗ (Erro ao pesquisar)",
                    "fonte_atual": nome_fonte,
                    "consultadas": consultadas,
                    "total_fontes": total_fontes,
                    "tipo": "progresso_fonte",
                    "status_fonte": "erro",
                    "anuncios_fonte": 0
                }

        total_anuncios_brutos = len(todos_anuncios)

        # Etapa 5: Padronizar os dados (já realizada na extração canônica)
        yield {
            "etapa": 5,
            "mensagem": f"Padronizando dados de {total_anuncios_brutos} anúncios...",
            "tipo": "progresso"
        }

        # Etapa 6: Aplicar bairros e regra especial da Vila Mangalot (Item 10 do PRD)
        yield {
            "etapa": 6,
            "mensagem": "Validando geolocalização e regras de bairro...",
            "tipo": "progresso"
        }
        anuncios_bairro_valido = []
        for im in todos_anuncios:
            valido, bairro_oficial, obs_loc = self.geo_service.validar_localizacao(
                bairro=im.get("bairro"),
                endereco=im.get("endereco"),
                latitude=im.get("latitude"),
                longitude=im.get("longitude")
            )
            if valido and bairro_oficial:
                im["bairro"] = bairro_oficial
                im["observacao_localizacao"] = obs_loc
                anuncios_bairro_valido.append(im)

        total_apos_bairros = len(anuncios_bairro_valido)

        # Etapa 7: Aplicar filtros do imóvel (Item 12 a 23 do PRD)
        yield {
            "etapa": 7,
            "mensagem": f"Aplicando filtros do usuário sobre {total_apos_bairros} anúncios...",
            "tipo": "progresso"
        }
        anuncios_filtrados = [im for im in anuncios_bairro_valido if self._passa_filtros(im, filtros)]
        total_apos_filtros = len(anuncios_filtrados)

        # Etapa 8: Remover duplicados (Item 28 do PRD)
        yield {
            "etapa": 8,
            "mensagem": "Eliminando anúncios duplicados entre portais e imobiliárias...",
            "tipo": "progresso"
        }
        imoveis_unicos = deduplicar_imoveis(anuncios_filtrados)
        total_unicos = len(imoveis_unicos)

        # Ordenação padrão recomendada: mais recentes (Item 34 do PRD)
        imoveis_finais = aplicar_filtros_e_ordenacao(
            imoveis_unicos,
            filtros,
            ordenar_por=filtros.get("ordenar_por", "recentes")
        )

        # Etapa 9: Salvar resultados temporariamente no cache SQLite (Item 37 do PRD)
        yield {
            "etapa": 9,
            "mensagem": "Salvando resultados em cache local...",
            "tipo": "progresso"
        }
        await database.salvar_imoveis_pesquisa(imoveis_finais)
        agora_str = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M")
        await database.salvar_configuracao("ultima_pesquisa", agora_str)

        # Etapa 10: Exibir imóveis (Item 26 do PRD)
        yield {
            "etapa": 10,
            "mensagem": "Pesquisa concluída!",
            "tipo": "concluido",
            "resumo": {
                "fontes_sucesso": fontes_sucesso,
                "fontes_erro": fontes_erro,
                "total_encontrados": total_anuncios_brutos,
                "total_apos_bairros": total_apos_bairros,
                "total_apos_filtros": total_apos_filtros,
                "total_unicos": total_unicos,
                "ultima_atualizacao": agora_str
            },
            "imoveis": imoveis_finais
        }

    def _passa_filtros(self, imovel: Dict[str, Any], filtros: Dict[str, Any]) -> bool:
        from services.filtros import filtrar_imovel
        return filtrar_imovel(imovel, filtros)
