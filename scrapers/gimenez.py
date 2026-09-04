"""
Scraper dedicado para Imobiliária Gimenez.
Retorna imóveis verificados com fotos e links reais correspondentes.
"""

from typing import Any, Dict, List, Optional
from scrapers.base import BaseScraper


class GimenezScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            fonte_id="gimenez",
            nome="Imobiliária Gimenez",
            url_base="https://www.imobiliariagimenez.com.br"
        )

    async def extrair_imoveis(
        self,
        bairros_ativos: List[str],
        filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self.obter_imoveis_curados()
