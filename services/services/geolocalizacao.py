"""
Serviço de geolocalização, validação de bairros e aplicação da regra especial da Vila Mangalot.
Calcula distância Haversine em relação ao Parque São Domingos.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from services.normalizacao import remover_acentos

# Coordenadas de referência do Parque São Domingos (Praça/Centro)
PARQUE_SAO_DOMINGOS_LAT = -23.5048
PARQUE_SAO_DOMINGOS_LON = -46.7352


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância em quilômetros entre dois pontos geográficos."""
    r = 6371.0  # Raio da Terra em km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(r * c, 2)


class GeoService:
    def __init__(self, config_bairros_path: Optional[str] = None):
        if not config_bairros_path:
            config_bairros_path = str(Path(__file__).parent.parent / "config" / "bairros.json")
        self.config_path = config_bairros_path
        self.bairros = self._carregar_bairros()

    def _carregar_bairros(self) -> List[Dict]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def recarregar_bairros(self) -> None:
        self.bairros = self._carregar_bairros()

    def normalizar_bairro(self, bairro_candidato: Optional[str]) -> Optional[str]:
        """Identifica o nome oficial do bairro com base em aliases cadastrados."""
        if not bairro_candidato:
            return None

        texto_limpo = remover_acentos(bairro_candidato)

        for b in self.bairros:
            nome_limpo = remover_acentos(b["nome"])
            if nome_limpo == texto_limpo or nome_limpo in texto_limpo or texto_limpo in nome_limpo:
                return b["nome"]
            for alias in b.get("aliases", []):
                alias_limpo = remover_acentos(alias)
                if alias_limpo == texto_limpo or alias_limpo in texto_limpo:
                    return b["nome"]

        return None

    def bairro_esta_ativo(self, nome_bairro: str) -> bool:
        """Verifica se o bairro está na lista ativa configurada pelo usuário."""
        for b in self.bairros:
            if b["nome"].lower() == nome_bairro.lower():
                return b.get("ativo", True)
        return False

    def validar_localizacao(
        self,
        bairro: Optional[str],
        endereco: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        distancia_max_mangalot_km: float = 2.0
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Valida se o imóvel está em um bairro aceito e aplica a regra especial da Vila Mangalot.
        
        Retorna:
        - (valido: bool, bairro_normalizado: str | None, observacao_localizacao: str | None)
        """
        bairro_oficial = self.normalizar_bairro(bairro)

        # Se não encontrou no bairro, tenta buscar indício de bairro no endereço
        if not bairro_oficial and endereco:
            bairro_oficial = self.normalizar_bairro(endereco)

        if not bairro_oficial:
            return False, None, "Bairro fora do escopo configurado"

        if not self.bairro_esta_ativo(bairro_oficial):
            return False, bairro_oficial, "Bairro desativado nas preferências"

        # Regra Especial: Vila Mangalot
        if bairro_oficial == "Vila Mangalot":
            if latitude is not None and longitude is not None:
                dist = calcular_distancia_haversine(
                    latitude, longitude,
                    PARQUE_SAO_DOMINGOS_LAT, PARQUE_SAO_DOMINGOS_LON
                )
                if dist <= distancia_max_mangalot_km:
                    return True, bairro_oficial, f"A {dist} km do Parque São Domingos"
                else:
                    return False, bairro_oficial, f"Excedeu distância máxima de {distancia_max_mangalot_km} km (está a {dist} km)"
            else:
                # Localização precisa não confirmada por ausência de coordenadas
                return True, bairro_oficial, "Localização precisa não confirmada."

        return True, bairro_oficial, None
