"""
Serviço de normalização e extração de dados de anúncios imobiliários brasileiros.
Trata formatações de valores, áreas, quartos, suítes, vagas, pets, quintal, garagem, etc.
Sem nunca inventar informações: campos ausentes retornam None.
"""

import re
import unicodedata
from typing import Optional, Tuple


def remover_acentos(texto: Optional[str]) -> str:
    """Remove acentos e converte para minúsculas para comparações insensíveis."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return sem_acentos.lower().strip()


def extrair_preco(valor_str: Optional[any]) -> Optional[float]:
    """
    Converte strings monetárias brasileiras para float.
    Exemplos: 'R$ 3.750,00' -> 3750.0; '3.500' -> 3500.0; 'Isento' -> 0.0.
    """
    if valor_str is None:
        return None
    if isinstance(valor_str, (int, float)):
        return float(valor_str)

    texto = str(valor_str).strip()
    texto_limpo = remover_acentos(texto)

    if any(palavra in texto_limpo for palavra in ["isento", "gratis", "incluso", "sem custo", "nao informado"]):
        return 0.0

    # Procura valores numéricos como 3.750,00 ou 3750.00 ou 3750
    # Remove R$, espaços
    match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?|\d+(?:\.\d{1,2})?)", texto)
    if not match:
        return None

    raw_num = match.group(1)
    if "." in raw_num and "," in raw_num:
        # Padrão brasileiro 3.750,50
        raw_num = raw_num.replace(".", "").replace(",", ".")
    elif "," in raw_num:
        # Padrão 3750,50
        raw_num = raw_num.replace(",", ".")
    elif "." in raw_num and len(raw_num.split(".")[-1]) == 3:
        # Padrão de milhar sem centavos 3.750
        raw_num = raw_num.replace(".", "")

    try:
        val = float(raw_num)
        return val if val >= 0 else None
    except ValueError:
        return None


def extrair_area(area_str: Optional[any]) -> Optional[float]:
    """Converte áreas (ex: '120 m²', '120m2', 120) para float."""
    if area_str is None:
        return None
    if isinstance(area_str, (int, float)):
        return float(area_str)

    match = re.search(r"(\d+(?:[.,]\d+)?)", str(area_str).replace(" ", ""))
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def extrair_inteiro(texto: Optional[any], padrao_regex: Optional[str] = None) -> Optional[int]:
    """Extrai número inteiro de contagens (quartos, banheiros, vagas, suítes)."""
    if texto is None:
        return None
    if isinstance(texto, int):
        return texto
    if isinstance(texto, float):
        return int(texto)

    s = str(texto).strip().lower()
    if padrao_regex:
        match = re.search(padrao_regex, s, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                return None

    match = re.search(r"\b(\d+)\b", s)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def calcular_custo_total(aluguel: Optional[float], condominio: Optional[float], iptu: Optional[float]) -> Optional[float]:
    """Calcula o custo mensal total estimado: Aluguel + Condomínio + IPTU."""
    if aluguel is None:
        return None
    total = float(aluguel)
    if condominio is not None and condominio > 0:
        total += float(condominio)
    if iptu is not None and iptu > 0:
        total += float(iptu)
    return round(total, 2)


def detectar_pet(texto_completo: str) -> Optional[str]:
    """
    Retorna:
    - 'Sim' se aceita animais
    - 'Não' se proíbe animais
    - 'Não informado' se não constar no anúncio
    """
    txt = remover_acentos(texto_completo)
    if not txt:
        return "Não informado"

    if re.search(r"\b(nao aceita (?:pet|animais|cachorro|gato)|proibido (?:animais|pet|caes)|sem animais)\b", txt):
        return "Não"

    if re.search(r"\b(aceita (?:pet|animais|cachorro|gato|bichos?)|pet friendly|permite (?:animais|pet)|com pet)\b", txt):
        return "Sim"

    return "Não informado"


def detectar_quintal(texto_completo: str) -> Optional[str]:
    """
    Retorna:
    - 'Privativo' se quintal privativo/exclusivo
    - 'Fechado/murado' se murado/fechado
    - 'Sim' se possui quintal genérico
    - None se não mencionado ou explicitamente sem quintal
    """
    txt = remover_acentos(texto_completo)
    if not txt:
        return None

    if re.search(r"\b(sem quintal|nao possui quintal|nao tem quintal|dispensa quintal)\b", txt):
        return None

    if re.search(r"\b(quintal privativo|quintal exclusivo|area externa privativa)\b", txt):
        return "Privativo"

    if re.search(r"\b(quintal fechado|quintal murado|todo murado|quintal amplo murado)\b", txt):
        return "Fechado/murado"

    if re.search(r"\b(quintal|amplo quintal|area externa)\b", txt):
        return "Sim"

    return None


def detectar_garagem_fechada(texto_completo: str, vagas: Optional[int]) -> Optional[str]:
    """
    Retorna:
    - 'Sim' se garagem fechada/coberta confirmada
    - 'Não' se garagem descoberta/sem vaga
    - 'Tipo de garagem não confirmado' se tem vaga mas não detalha se é fechada
    """
    if vagas is not None and vagas == 0:
        return "Não"

    txt = remover_acentos(texto_completo)
    if not txt:
        return "Tipo de garagem não confirmado" if (vagas and vagas > 0) else None

    if re.search(r"\b(garagem fechada|vaga fechada|garagem coberta|vaga coberta|portao automatico|portao eletronico)\b", txt):
        return "Sim"

    if re.search(r"\b(garagem descoberta|vaga descoberta|vaga aberta)\b", txt):
        return "Não"

    if vagas and vagas > 0:
        return "Tipo de garagem não confirmado"

    return None


def detectar_lavanderia(texto_completo: str) -> Optional[bool]:
    """Detecta lavanderia ou área de serviço."""
    txt = remover_acentos(texto_completo)
    if not txt:
        return None
    if re.search(r"\b(lavanderia|area de servico|area de servicos)\b", txt):
        return True
    return None


def detectar_escritorio(texto_completo: str) -> bool:
    """Detecta escritório ou home office no anúncio."""
    txt = remover_acentos(texto_completo)
    if not txt:
        return False
    return bool(re.search(r"\b(escritorio|home office|sala de estudos)\b", txt))
