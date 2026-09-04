"""
Classe base abstrata para todos os scrapers de portais e imobiliárias.
Garante padronização estrita de esquema (Item 27 do PRD), timeouts, headers e tratamento de erros.
"""

import abc
import datetime
import logging
from typing import Any, Dict, List, Optional
import httpx

from services.normalizacao import (
    extrair_preco,
    extrair_area,
    extrair_inteiro,
    calcular_custo_total,
    detectar_pet,
    detectar_quintal,
    detectar_garagem_fechada,
    detectar_lavanderia,
    remover_acentos
)

logger = logging.getLogger("scrapers")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}


class BaseScraper(abc.ABC):
    def __init__(self, fonte_id: str, nome: str, url_base: str):
        self.fonte_id = fonte_id
        self.nome = nome
        self.url_base = url_base
        self.timeout = 15.0

    async def get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP assíncrono com headers realistas e follow_redirects."""
        return httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
            verify=False
        )

    @abc.abstractmethod
    async def extrair_imoveis(
        self,
        bairros_ativos: List[str],
        filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Método obrigatório implementado por cada scraper específico."""
        pass

    def obter_imoveis_curados(self) -> List[Dict[str, Any]]:
        """Retorna imóveis verificados do catálogo mestre para esta fonte."""
        import json
        from pathlib import Path
        catalog_path = Path(__file__).resolve().parent.parent / "master_curated_properties.json"
        if not catalog_path.exists():
            return []
        try:
            dados = json.loads(catalog_path.read_text(encoding="utf-8"))
            return [
                d for d in dados
                if d.get("id", "").startswith(self.fonte_id)
                or d.get("fonte", "").lower() in self.nome.lower()
                or self.nome.lower() in d.get("fonte", "").lower()
            ]
        except Exception:
            return []

    def criar_imovel_padronizado(
        self,
        titulo: str,
        bairro: str,
        url: str,
        aluguel: float,
        endereco: Optional[str] = None,
        condominio: Optional[float] = None,
        iptu: Optional[float] = None,
        quartos: Optional[int] = None,
        suites: Optional[int] = None,
        banheiros: Optional[int] = None,
        vagas: Optional[int] = None,
        area: Optional[float] = None,
        tipo: Optional[str] = None,
        descricao: str = "",
        fotos: Optional[List[str]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        pet: Optional[str] = None,
        quintal: Optional[str] = None,
        garagem_fechada: Optional[str] = None,
        lavanderia: Optional[bool] = None,
        data_coleta: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Valida e formata o anúncio para a estrutura canônica definida no Item 27 do PRD:
        Descarta anúncios de venda ou links inválidos.
        """
        if not url or not url.startswith("http"):
            return None

        # Rejeição estrita de venda: aluguel residencial não pode ser absurdo e termos de venda desclassificam
        texto_analise = remover_acentos(f"{titulo} {descricao}")
        if "venda" in texto_analise and "aluguel" not in texto_analise and "locacao" not in texto_analise:
            return None

        if aluguel is None or aluguel <= 0 or aluguel > 50000:
            return None

        # Detecção automática de características caso não fornecidas explicitamente
        if pet is None:
            pet = detectar_pet(texto_analise)

        if quintal is None:
            quintal = detectar_quintal(texto_analise)

        if garagem_fechada is None:
            garagem_fechada = detectar_garagem_fechada(texto_analise, vagas)

        if lavanderia is None:
            lavanderia = detectar_lavanderia(texto_analise)

        # Dedução de tipo se não informado
        if not tipo:
            if "sobrado" in texto_analise:
                tipo = "sobrado"
            elif "apartamento" in texto_analise or "apto" in texto_analise:
                tipo = "apartamento"
            elif "casa em condominio" in texto_analise:
                tipo = "casa em condomínio"
            elif "casa" in texto_analise:
                tipo = "casa"
            else:
                tipo = "imóvel residencial"

        fotos_limpas = [f for f in (fotos or []) if f and str(f).startswith("http")]

        custo_total = calcular_custo_total(aluguel, condominio, iptu)

        return {
            "id": f"{self.fonte_id}_{abs(hash(url)) % 10000000}",
            "titulo": titulo.strip(),
            "bairro": bairro.strip(),
            "endereco": endereco.strip() if endereco else None,
            "latitude": latitude,
            "longitude": longitude,
            "aluguel": round(float(aluguel), 2),
            "condominio": round(float(condominio), 2) if condominio is not None else None,
            "iptu": round(float(iptu), 2) if iptu is not None else None,
            "custo_total": custo_total,
            "quartos": quartos,
            "suites": suites,
            "banheiros": banheiros,
            "vagas": vagas,
            "area": round(float(area), 1) if area is not None else None,
            "tipo": tipo,
            "pet": pet,
            "quintal": quintal,
            "garagem_fechada": garagem_fechada,
            "lavanderia": lavanderia,
            "descricao": descricao.strip(),
            "fotos": fotos_limpas,
            "fonte": self.nome,
            "url": url.strip(),
            "outras_fontes": [],
            "observacao_localizacao": None,
            "indisponivel": False,
            "data_coleta": data_coleta or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
