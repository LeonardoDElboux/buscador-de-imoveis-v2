"""
Serviço de filtragem dinâmica e ordenação de anúncios imobiliários (em memória e banco).
Permite alterar filtros pós-pesquisa sem refazer scraping (item 35 do PRD).
"""

from typing import Any, Dict, List, Optional
from services.normalizacao import remover_acentos, calcular_custo_total, detectar_escritorio


def filtrar_imovel(imovel: Dict[str, Any], filtros: Dict[str, Any]) -> bool:
    """Verifica se um imóvel atende aos critérios do conjunto de filtros."""
    # 1. Bairros selecionados
    bairros_selecionados = filtros.get("bairros")
    if bairros_selecionados:
        bairro_norm = remover_acentos(imovel.get("bairro") or "")
        bairros_norm = [remover_acentos(b) for b in bairros_selecionados]
        if not any(b in bairro_norm or bairro_norm in b for b in bairros_norm):
            return False

    # 2. Palavras a excluir (Hard reject)
    palavras_excluir = filtros.get("palavras_excluir", ["republica", "quarto compartilhado", "temporada", "comercial"])
    texto_busca = remover_acentos(f"{imovel.get('titulo', '')} {imovel.get('descricao', '')}")
    for termo in palavras_excluir:
        if termo and remover_acentos(termo) in texto_busca:
            return False

    # 3. Palavras obrigatórias
    palavras_obrigatorias = filtros.get("palavras_obrigatorias", [])
    for termo in palavras_obrigatorias:
        if termo and remover_acentos(termo) not in texto_busca:
            return False

    # 4. Tipo de Imóvel
    tipos_selecionados = filtros.get("tipos_imovel")
    if tipos_selecionados:
        tipo_imovel = remover_acentos(imovel.get("tipo", ""))
        tipos_norm = [remover_acentos(t) for t in tipos_selecionados]
        # Se tipo está cadastrado ou deduzido no título
        if tipo_imovel:
            if not any(t in tipo_imovel for t in tipos_norm):
                return False
        else:
            # Tenta verificar se alguma palavra de tipo está no título
            titulo_norm = remover_acentos(imovel.get("titulo", ""))
            if not any(t in titulo_norm for t in tipos_norm):
                # Se não puder identificar pelo título, não descarta imediatamente a não ser que haja conflito
                pass

    # 5. Valor de aluguel
    aluguel = imovel.get("aluguel")
    if aluguel is not None:
        aluguel_min = filtros.get("aluguel_min")
        if aluguel_min is not None and aluguel < float(aluguel_min):
            return False

        aluguel_max = filtros.get("aluguel_max")
        if aluguel_max is not None and aluguel > float(aluguel_max):
            return False

    # 6. Custo mensal total estimado
    custo_total_max = filtros.get("custo_total_max")
    if custo_total_max is not None:
        custo_total = calcular_custo_total(
            imovel.get("aluguel"),
            imovel.get("condominio"),
            imovel.get("iptu")
        )
        if custo_total is not None and custo_total > float(custo_total_max):
            return False

    # 7. Quartos
    quartos = imovel.get("quartos")
    min_quartos = filtros.get("min_quartos")
    max_quartos = filtros.get("max_quartos")
    exigir_escritorio = filtros.get("exigir_escritorio", False)

    if exigir_escritorio:
        tem_escritorio = detectar_escritorio(texto_busca)
        if not tem_escritorio:
            return False

    if quartos is not None:
        if min_quartos is not None and quartos < int(min_quartos):
            return False
        if max_quartos is not None and quartos > int(max_quartos):
            return False

    # 8. Suítes
    min_suites = filtros.get("min_suites")
    if min_suites is not None:
        suites = imovel.get("suites")
        if suites is None or suites < int(min_suites):
            return False

    # 9. Banheiros
    banheiros = imovel.get("banheiros")
    min_banheiros = filtros.get("min_banheiros")
    max_banheiros = filtros.get("max_banheiros")
    if banheiros is not None:
        if min_banheiros is not None and banheiros < int(min_banheiros):
            return False
        if max_banheiros is not None and banheiros > int(max_banheiros):
            return False

    # 10. Garagem / Vagas
    vagas = imovel.get("vagas")
    min_vagas = filtros.get("min_vagas")
    if min_vagas is not None and int(min_vagas) > 0:
        if vagas is None or vagas < int(min_vagas):
            return False

    exigir_garagem_fechada = filtros.get("garagem_fechada")
    if exigir_garagem_fechada:
        gf = imovel.get("garagem_fechada")
        if gf != "Sim":
            return False

    # 11. Quintal
    exigir_quintal = filtros.get("possui_quintal")
    tipo_quintal_exigido = filtros.get("tipo_quintal")  # "Privativo", "Fechado/murado", etc.
    if exigir_quintal:
        q = imovel.get("quintal")
        if not q:
            return False
        if tipo_quintal_exigido and tipo_quintal_exigido != "Qualquer":
            if q.lower() != tipo_quintal_exigido.lower():
                return False

    # 12. Pet
    filtro_pet = filtros.get("pet")  # "Sim", "Não", "Qualquer"
    if filtro_pet and filtro_pet != "Qualquer":
        pet_imovel = imovel.get("pet")
        if filtro_pet == "Sim" and pet_imovel != "Sim":
            return False
        if filtro_pet == "Não" and pet_imovel == "Sim":
            return False

    # 13. Lavanderia
    if filtros.get("lavanderia"):
        if not imovel.get("lavanderia"):
            return False

    # 14. Área útil / construída
    area = imovel.get("area")
    if area is not None:
        area_min = filtros.get("area_min")
        if area_min is not None and area < float(area_min):
            return False
        area_max = filtros.get("area_max")
        if area_max is not None and area > float(area_max):
            return False

    return True


def aplicar_filtros_e_ordenacao(
    imoveis: List[Dict[str, Any]],
    filtros: Dict[str, Any],
    ordenar_por: str = "recentes"
) -> List[Dict[str, Any]]:
    """Aplica todos os filtros e realiza a ordenação solicitada."""
    filtrados = [im for im in imoveis if filtrar_imovel(im, filtros)]

    # Ordenações
    if ordenar_por == "menor_aluguel":
        filtrados.sort(key=lambda x: x.get("aluguel") or 9999999)
    elif ordenar_por == "menor_custo_total":
        filtrados.sort(key=lambda x: calcular_custo_total(x.get("aluguel"), x.get("condominio"), x.get("iptu")) or 9999999)
    elif ordenar_por == "maior_area":
        filtrados.sort(key=lambda x: x.get("area") or 0, reverse=True)
    elif ordenar_por == "mais_quartos":
        filtrados.sort(key=lambda x: x.get("quartos") or 0, reverse=True)
    elif ordenar_por == "bairro":
        filtrados.sort(key=lambda x: (x.get("bairro") or "").lower())
    elif ordenar_por == "fonte":
        filtrados.sort(key=lambda x: (x.get("fonte") or "").lower())
    else:  # "recentes" padrão
        filtrados.sort(key=lambda x: x.get("data_coleta") or "", reverse=True)

    return filtrados
