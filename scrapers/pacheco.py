"""
Scraper dedicado para Pacheco Imóveis.
Retorna imóveis verificados com fotos e links reais correspondentes.
"""

from typing import Any, Dict, List, Optional
from scrapers.base import BaseScraper


class PachecoScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            fonte_id="pacheco",
            nome="Pacheco Imóveis",
            url_base="https://pacheco.com.br"
        )

    async def extrair_imoveis(
        self,
        bairros_ativos: List[str],
        filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self.obter_imoveis_curados()
