"""
Serviço de deduplicação de anúncios imobiliários entre múltiplos portais e imobiliárias.
Identifica o mesmo imóvel anunciado em fontes diferentes e consolida em um único card principal,
mantendo a lista de fontes alternativas e links originais acessíveis.
"""

import re
from typing import Dict, List, Any
from services.normalizacao import remover_acentos


def _similaridade_texto(t1: str, t2: str) -> float:
    """Calcula similaridade de Jaccard simples entre conjuntos de palavras."""
    palavras1 = set(re.findall(r"\w{4,}", remover_acentos(t1)))
    palavras2 = set(re.findall(r"\w{4,}", remover_acentos(t2)))
    if not palavras1 or not palavras2:
        return 0.0
    intersecao = len(palavras1.intersection(palavras2))
    uniao = len(palavras1.union(palavras2))
    return intersecao / uniao if uniao > 0 else 0.0


def sao_duplicados(imovel_a: Dict[str, Any], imovel_b: Dict[str, Any]) -> bool:
    """
    Avalia se dois anúncios representam o mesmo imóvel físico.
    Requisitos de correspondência:
    1. Mesmo bairro oficial (ou aliases idênticos)
    2. Mesma quantidade de quartos (se ambos informados)
    3. Área muito próxima (variação <= 7%) se informada em ambos
    4. Valor do aluguel próximo (variação <= 8%)
    5. Similaridade em endereço, título ou descrição
    """
    # 1. Bairro
    bairro_a = remover_acentos(imovel_a.get("bairro") or "")
    bairro_b = remover_acentos(imovel_b.get("bairro") or "")
    if bairro_a and bairro_b and bairro_a != bairro_b:
        return False

    # 2. Quartos
    q_a = imovel_a.get("quartos")
    q_b = imovel_b.get("quartos")
    if q_a is not None and q_b is not None and q_a != q_b:
        return False

    # 3. Valor do aluguel
    v_a = imovel_a.get("aluguel")
    v_b = imovel_b.get("aluguel")
    if v_a and v_b:
        diff_val = abs(v_a - v_b) / max(v_a, v_b)
        if diff_val > 0.08:  # Mais de 8% de diferença no aluguel
            return False

    # 4. Área construída / útil
    area_a = imovel_a.get("area")
    area_b = imovel_b.get("area")
    if area_a and area_b:
        diff_area = abs(area_a - area_b) / max(area_a, area_b)
        if diff_area > 0.07:  # Mais de 7% de diferença na área
            return False

    # 5. Endereço explícito idêntico
    end_a = remover_acentos(imovel_a.get("endereco") or "")
    end_b = remover_acentos(imovel_b.get("endereco") or "")
    if end_a and end_b and len(end_a) > 5 and len(end_b) > 5:
        if end_a in end_b or end_b in end_a:
            return True

    # 6. Similaridade semântica em título e descrição
    desc_a = (imovel_a.get("titulo") or "") + " " + (imovel_a.get("descricao") or "")
    desc_b = (imovel_b.get("titulo") or "") + " " + (imovel_b.get("descricao") or "")
    sim = _similaridade_texto(desc_a, desc_b)
    if sim >= 0.30:
        return True

    # Se bateu bairro, quartos, área e valor com alta precisão
    if (
        bairro_a == bairro_b
        and q_a is not None and q_a == q_b
        and area_a is not None and abs((area_a - (area_b or 0)) / area_a) <= 0.03
        and v_a is not None and abs((v_a - (v_b or 0)) / v_a) <= 0.03
    ):
        return True

    return False


def deduplicar_imoveis(lista_imoveis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Agrupa imóveis duplicados.
    O card principal é aquele com mais fotos ou mais informações preenchidas.
    Fontes adicionais são salvas em 'outras_fontes'.
    """
    grupos: List[List[Dict[str, Any]]] = []

    for imovel in lista_imoveis:
        alocado = False
        for grupo in grupos:
            if sao_duplicados(imovel, grupo[0]):
                grupo.append(imovel)
                alocado = True
                break
        if not alocado:
            grupos.append([imovel])

    imoveis_unicos: List[Dict[str, Any]] = []

    for grupo in grupos:
        # Ordena o grupo para escolher o melhor representante:
        # Prioriza quem tem mais fotos e mais campos preenchidos
        def score_completude(item: Dict[str, Any]) -> int:
            score = len(item.get("fotos") or []) * 2
            if item.get("endereco"):
                score += 3
            if item.get("area"):
                score += 2
            if item.get("quartos"):
                score += 2
            if item.get("condominio") is not None:
                score += 1
            if item.get("iptu") is not None:
                score += 1
            return score

        grupo_ordenado = sorted(grupo, key=score_completude, reverse=True)
        principal = dict(grupo_ordenado[0])

        outras_fontes = []
        # Registra as fontes e links alternativos
        urls_vistas = {principal.get("url")}
        for outro in grupo_ordenado[1:]:
            url = outro.get("url")
            if url and url not in urls_vistas:
                urls_vistas.add(url)
                outras_fontes.append({
                    "fonte": outro.get("fonte", "Outra fonte"),
                    "url": url,
                    "aluguel": outro.get("aluguel")
                })

        principal["outras_fontes"] = outras_fontes
        imoveis_unicos.append(principal)

    return imoveis_unicos
