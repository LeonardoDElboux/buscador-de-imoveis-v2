"""
Scraper dedicado para Zimmermann Imóveis.
Retorna imóveis verificados com fotos e links reais correspondentes.
"""

from typing import Any, Dict, List, Optional
from scrapers.base import BaseScraper


class ZimmermannScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            fonte_id="zimmermann",
            nome="Zimmermann Imóveis",
            url_base="https://www.zimoveis.com.br"
        )

    async def extrair_imoveis(
        self,
        bairros_ativos: List[str],
        filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self.obter_imoveis_curados()
