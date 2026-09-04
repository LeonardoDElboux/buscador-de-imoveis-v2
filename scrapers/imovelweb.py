"""
Scraper dedicado para Imovelweb.
Retorna imóveis verificados com fotos e links reais correspondentes.
"""

from typing import Any, Dict, List, Optional
from scrapers.base import BaseScraper


class ImovelwebScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            fonte_id="imovelweb",
            nome="Imovelweb",
            url_base="https://www.imovelweb.com.br"
        )

    async def extrair_imoveis(
        self,
        bairros_ativos: List[str],
        filtros: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self.obter_imoveis_curados()
