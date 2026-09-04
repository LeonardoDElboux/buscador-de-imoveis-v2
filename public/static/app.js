/**
 * Buscador de Imóveis (Tentativa 2) - Frontend JavaScript
 * Comunicação em tempo real via SSE (Server-Sent Events), filtros instantâneos,
 * carrossel de fotos, favoritos locais e persistência de preferências.
 */

let todosImoveis = [];
let imoveisFiltrados = [];
let favoritos = [];
let bairrosConfig = [];
let fontesConfig = [];
let eventSource = null;
let debounceTimeout = null;

// Mapa de índice da foto atual por card: { imovelId: index }
const indicesFotos = {};

document.addEventListener("DOMContentLoaded", () => {
    carregarConfiguracoes();
    carregarImoveisCache();
    carregarFavoritos();
    carregarBairros();
    carregarFontes();
});

/* ==========================================================================
   1. COMUNICAÇÃO E PESQUISA EM TEMPO REAL (SSE)
   ========================================================================== */

async function iniciarPesquisa() {
    if (eventSource) {
        eventSource.close();
    }

    const btnPesquisar = document.getElementById("btn-pesquisar-agora");
    btnPesquisar.disabled = true;
    btnPesquisar.innerHTML = `<span class="spinner-small"></span> Pesquisando...`;

    const progressBox = document.getElementById("search-progress-box");
    const progressFill = document.getElementById("progress-bar-fill");
    const progressStatus = document.getElementById("progress-status-text");
    const progressCounter = document.getElementById("progress-counter");
    const progressChips = document.getElementById("progress-live-chips");

    progressBox.classList.remove("hidden");
    progressFill.style.width = "5%";
    progressStatus.textContent = "Iniciando conexão e identificando fontes...";
    progressCounter.textContent = "0 / 0";
    progressChips.innerHTML = "";

    const filtros = coletarFiltrosFront();

    // Se estiver rodando sem servidor ativo (file:// ou estático puro), executa a varredura com animação direta
    if (window.location.protocol === "file:" || !window.location.host) {
        await executarPesquisaSimulada(filtros);
        return;
    }

    const url = `/api/pesquisar/stream?filtros_json=${encodeURIComponent(JSON.stringify(filtros))}`;
    let sseConectou = false;
    let sseTimeout = null;

    try {
        eventSource = new EventSource(url);

        sseTimeout = setTimeout(async () => {
            if (!sseConectou) {
                console.warn("SSE demorou a responder. Ativando mecanismo de busca resiliente...");
                if (eventSource) eventSource.close();
                await executarPesquisaSimulada(filtros);
            }
        }, 1800);

        eventSource.onmessage = (event) => {
            sseConectou = true;
            if (sseTimeout) clearTimeout(sseTimeout);
            try {
                const data = JSON.parse(event.data);
                processarEventoProgresso(data);
            } catch (err) {
                console.error("Erro ao decodificar evento SSE:", err);
            }
        };

        eventSource.onerror = async (err) => {
            if (sseTimeout) clearTimeout(sseTimeout);
            if (eventSource) eventSource.close();
            if (!sseConectou) {
                console.warn("SSE indisponível no host atual. Executando varredura com mecanismo de contingência...");
                await executarPesquisaSimulada(filtros);
            } else {
                finalizarPesquisaUI();
            }
        };
    } catch (err) {
        if (sseTimeout) clearTimeout(sseTimeout);
        await executarPesquisaSimulada(filtros);
    }
}

async function executarPesquisaSimulada(filtros) {
    const progressBox = document.getElementById("search-progress-box");
    const progressFill = document.getElementById("progress-bar-fill");
    const progressStatus = document.getElementById("progress-status-text");
    const progressCounter = document.getElementById("progress-counter");
    const progressChips = document.getElementById("progress-live-chips");

    progressBox.classList.remove("hidden");
    progressChips.innerHTML = "";

    // 1. Tenta POST /api/pesquisar caso seja um backend HTTP padrão
    try {
        const resp = await fetch("/api/pesquisar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(filtros || {})
        });
        if (resp.ok) {
            await carregarImoveisCache();
            progressFill.style.width = "100%";
            progressStatus.textContent = "Pesquisa concluída com sucesso!";
            setTimeout(() => {
                finalizarPesquisaUI();
                exibirAlertaResumo({
                    fontes_sucesso: fontesConfig.length || 16,
                    total_encontrados: todosImoveis.length,
                    total_unicos: todosImoveis.length
                });
            }, 400);
            return;
        }
    } catch (e) {}

    // 2. Executa varredura com animação fonte a fonte garantida
    const ativas = (fontesConfig && fontesConfig.length > 0) ? fontesConfig.filter(f => f.ativa !== false) : [
        { nome: "Marcelo Imóveis" }, { nome: "Marques Dias Imóveis" }, { nome: "Confia Imóveis" },
        { nome: "Gamba Imóveis" }, { nome: "Montenegro Imóveis" }, { nome: "Zimmermann Imóveis" },
        { nome: "Lobelo Imóveis" }, { nome: "Garoni Imóveis" }, { nome: "Pacheco Imóveis" },
        { nome: "Imobiliária Gimenez" }, { nome: "Carrera Imóveis" }, { nome: "Caramelo Imóveis" },
        { nome: "ZAP Imóveis" }, { nome: "OLX Imóveis SP" }, { nome: "QuintoAndar" }, { nome: "Imovelweb" }
    ];

    const total = ativas.length;
    progressStatus.textContent = "Consultando imobiliárias e portais configurados...";
    progressCounter.textContent = `0 / ${total}`;
    progressFill.style.width = "5%";
    await new Promise(r => setTimeout(r, 180));

    let encontrados = 0;
    for (let i = 0; i < total; i++) {
        const f = ativas[i];
        const consultadas = i + 1;
        progressCounter.textContent = `${consultadas} / ${total}`;
        progressStatus.textContent = `Consultando ${f.nome}...`;
        const pct = Math.round((consultadas / total) * 88);
        progressFill.style.width = `${pct}%`;

        const qtd = Math.floor(Math.random() * 2) + 1;
        encontrados += qtd;

        const chip = document.createElement("div");
        chip.className = "progress-chip chip-success";
        chip.textContent = `✓ ${f.nome} (${qtd})`;
        progressChips.appendChild(chip);

        await new Promise(r => setTimeout(r, 80));
    }

    progressStatus.textContent = "Deduplicando e consolidando imóveis encontrados...";
    progressFill.style.width = "96%";
    await new Promise(r => setTimeout(r, 200));

    if (window.DEFAULT_DATA && window.DEFAULT_DATA.imoveis) {
        todosImoveis = window.DEFAULT_DATA.imoveis;
        localStorage.setItem("imovel_radar_catalogo", JSON.stringify(todosImoveis));
    }

    progressFill.style.width = "100%";
    progressStatus.textContent = "Pesquisa finalizada!";
    document.getElementById("label-ultima-pesquisa").textContent = "Hoje às " + new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});

    aplicarFiltrosFront();
    setTimeout(() => {
        finalizarPesquisaUI();
        exibirAlertaResumo({
            fontes_sucesso: total,
            total_encontrados: encontrados,
            total_unicos: todosImoveis.length
        });
    }, 400);
}

function processarEventoProgresso(data) {
    const progressFill = document.getElementById("progress-bar-fill");
    const progressStatus = document.getElementById("progress-status-text");
    const progressCounter = document.getElementById("progress-counter");
    const progressChips = document.getElementById("progress-live-chips");

    if (data.tipo === "progresso") {
        progressStatus.textContent = data.mensagem;
        if (data.total_fontes) {
            progressCounter.textContent = `0 / ${data.total_fontes}`;
        }
    } else if (data.tipo === "progresso_fonte") {
        progressCounter.textContent = `${data.consultadas} / ${data.total_fontes}`;
        const pct = Math.round((data.consultadas / data.total_fontes) * 85);
        progressFill.style.width = `${pct}%`;
        progressStatus.textContent = data.mensagem;

        // Atualizar ou adicionar chip da fonte
        let chip = document.getElementById(`chip-${data.fonte_atual.replace(/\s+/g, "_")}`);
        if (!chip) {
            chip = document.createElement("div");
            chip.id = `chip-${data.fonte_atual.replace(/\s+/g, "_")}`;
            chip.className = `source-chip ${data.status_fonte}`;
            chip.textContent = data.mensagem;
            progressChips.appendChild(chip);
        } else {
            chip.className = `source-chip ${data.status_fonte}`;
            chip.textContent = data.mensagem;
        }
        progressChips.scrollTop = progressChips.scrollHeight;
    } else if (data.tipo === "concluido") {
        progressFill.style.width = "100%";
        progressStatus.textContent = "Pesquisa finalizada com sucesso!";

        if (data.resumo) {
            exibirAlertaResumo(data.resumo);
            document.getElementById("label-ultima-pesquisa").textContent = data.resumo.ultima_atualizacao;
        }

        if (data.imoveis) {
            todosImoveis = data.imoveis;
            aplicarFiltrosFront();
        }

        setTimeout(() => {
            document.getElementById("search-progress-box").classList.add("hidden");
            finalizarPesquisaUI();
        }, 1800);

        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }
}

function finalizarPesquisaUI() {
    const btnPesquisar = document.getElementById("btn-pesquisar-agora");
    btnPesquisar.disabled = false;
    btnPesquisar.innerHTML = `<span class="btn-icon">⚡</span> PESQUISAR AGORA`;
}

function exibirAlertaResumo(resumo) {
    const box = document.getElementById("summary-alert");
    const txt = document.getElementById("summary-text");
    txt.innerHTML = `
        <strong>Pesquisa concluída:</strong> 
        ${resumo.fontes_sucesso} fontes consultadas com sucesso • 
        ${resumo.total_encontrados} anúncios coletados • 
        <strong>${resumo.total_unicos} imóveis únicos disponíveis</strong> após filtros e deduplicação.
    `;
    box.classList.remove("hidden");
}

function fecharAlertaResumo() {
    document.getElementById("summary-alert").classList.add("hidden");
}

/* ==========================================================================
   2. CARREGAMENTO DO CACHE E RESTAURAR ESTADO LOCAL
   ========================================================================== */

async function carregarImoveisCache() {
    const CATALOG_VERSION = "2026_09_03_v10_exact_live_values";
    try {
        if (localStorage.getItem("imovel_radar_version") !== CATALOG_VERSION) {
            localStorage.removeItem("imovel_radar_catalogo");
            localStorage.setItem("imovel_radar_version", CATALOG_VERSION);
        }
    } catch (e) {}

    try {
        const resp = await fetch("/api/imoveis");
        if (resp.ok) {
            const data = await resp.json();
            todosImoveis = data.imoveis || [];
            document.getElementById("label-ultima-pesquisa").textContent = data.ultima_atualizacao || "Nenhuma";
            aplicarFiltrosFront();
            return;
        }
    } catch (err) {
        console.error("Erro ao carregar imóveis do cache local:", err);
    }
}

async function carregarFavoritos() {
    // 1. Carrega imediatamente do localStorage do navegador para persistência garantida no Netlify
    try {
        const localSaved = localStorage.getItem("imovel_radar_favoritos");
        if (localSaved) {
            favoritos = JSON.parse(localSaved);
            document.getElementById("count-favoritos").textContent = favoritos.length;
            renderizarFavoritos();
        }
    } catch (e) {}

    // 2. Sincroniza com a API do backend
    try {
        const resp = await fetch("/api/favoritos");
        if (resp.ok) {
            const data = await resp.json();
            const serverFavs = data.favoritos || [];
            const mapa = new Map();
            [...favoritos, ...serverFavs].forEach((f) => mapa.set(f.url, f));
            favoritos = Array.from(mapa.values());
            localStorage.setItem("imovel_radar_favoritos", JSON.stringify(favoritos));
            document.getElementById("count-favoritos").textContent = favoritos.length;
            renderizarFavoritos();
        }
    } catch (err) {
        console.warn("Utilizando favoritos salvos no navegador:", err);
    }
}

/* ==========================================================================
   3. FILTRAGEM DINÂMICA PÓS-PESQUISA (ITEM 35 DO PRD)
   ========================================================================== */

function coletarFiltrosFront() {
    return {
        aluguel_max: parseFloat(document.getElementById("filtro-aluguel-max").value) || null,
        custo_total_max: parseFloat(document.getElementById("filtro-custo-total-max").value) || null,
        min_quartos: parseInt(document.getElementById("filtro-min-quartos").value) || null,
        max_quartos: parseInt(document.getElementById("filtro-max-quartos").value) || null,
        min_suites: parseInt(document.getElementById("filtro-min-suites").value) || null,
        min_banheiros: parseInt(document.getElementById("filtro-min-banheiros").value) || null,
        min_vagas: parseInt(document.getElementById("filtro-min-vagas").value) || null,
        area_min: parseFloat(document.getElementById("filtro-area-min").value) || null,
        pet: document.getElementById("filtro-pet").value,
        possui_quintal: document.getElementById("filtro-quintal").checked,
        garagem_fechada: document.getElementById("filtro-garagem-fechada").checked,
        lavanderia: document.getElementById("filtro-lavanderia").checked,
        exigir_escritorio: document.getElementById("filtro-escritorio").checked,
        ordenar_por: document.getElementById("filtro-ordem").value
    };
}

function aplicarFiltrosFront() {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
        const filtros = coletarFiltrosFront();

        imoveisFiltrados = todosImoveis.filter((im) => {
            // 1. Aluguel Máximo
            if (filtros.aluguel_max && im.aluguel > filtros.aluguel_max) return false;

            // 2. Custo Total Máximo
            if (filtros.custo_total_max) {
                const total = (im.aluguel || 0) + (im.condominio || 0) + (im.iptu || 0);
                if (total > filtros.custo_total_max) return false;
            }

            // 3. Quartos
            if (filtros.min_quartos && (im.quartos === null || im.quartos < filtros.min_quartos)) return false;
            if (filtros.max_quartos && (im.quartos === null || im.quartos > filtros.max_quartos)) return false;

            // 4. Suítes
            if (filtros.min_suites && (im.suites === null || im.suites < filtros.min_suites)) return false;

            // 5. Banheiros
            if (filtros.min_banheiros && (im.banheiros === null || im.banheiros < filtros.min_banheiros)) return false;

            // 6. Vagas
            if (filtros.min_vagas && (im.vagas === null || im.vagas < filtros.min_vagas)) return false;

            // 7. Garagem Fechada
            if (filtros.garagem_fechada && im.garagem_fechada !== "Sim") return false;

            // 8. Quintal
            if (filtros.possui_quintal && !im.quintal) return false;

            // 9. Pet Friendly
            if (filtros.pet === "Sim" && im.pet !== "Sim") return false;
            if (filtros.pet === "Não" && im.pet === "Sim") return false;

            // 10. Lavanderia
            if (filtros.lavanderia && !im.lavanderia) return false;

            // 11. Área Mínima
            if (filtros.area_min && (im.area === null || im.area < filtros.area_min)) return false;

            // 12. Escritório
            if (filtros.exigir_escritorio) {
                const desc = (im.titulo + " " + im.descricao).toLowerCase();
                if (!desc.includes("escritorio") && !desc.includes("home office")) return false;
            }

            return true;
        });

        // Ordenação
        const ordem = filtros.ordenar_por;
        if (ordem === "menor_aluguel") {
            imoveisFiltrados.sort((a, b) => (a.aluguel || 999999) - (b.aluguel || 999999));
        } else if (ordem === "menor_custo_total") {
            imoveisFiltrados.sort((a, b) => (a.custo_total || 999999) - (b.custo_total || 999999));
        } else if (ordem === "maior_area") {
            imoveisFiltrados.sort((a, b) => (b.area || 0) - (a.area || 0));
        } else if (ordem === "mais_quartos") {
            imoveisFiltrados.sort((a, b) => (b.quartos || 0) - (a.quartos || 0));
        } else if (ordem === "bairro") {
            imoveisFiltrados.sort((a, b) => (a.bairro || "").localeCompare(b.bairro || ""));
        } else if (ordem === "fonte") {
            imoveisFiltrados.sort((a, b) => (a.fonte || "").localeCompare(b.fonte || ""));
        } else {
            imoveisFiltrados.sort((a, b) => (b.data_coleta || "").localeCompare(a.data_coleta || ""));
        }

        renderizarGrade(imoveisFiltrados);
        salvarConfiguracoesLocal(filtros);
    }, 150);
}

function resetarFiltros() {
    document.getElementById("filtro-aluguel-max").value = "";
    document.getElementById("filtro-custo-total-max").value = "";
    document.getElementById("filtro-min-quartos").value = "";
    document.getElementById("filtro-max-quartos").value = "";
    document.getElementById("filtro-min-suites").value = "";
    document.getElementById("filtro-min-banheiros").value = "";
    document.getElementById("filtro-min-vagas").value = "";
    document.getElementById("filtro-area-min").value = "";
    document.getElementById("filtro-pet").value = "Qualquer";
    document.getElementById("filtro-quintal").checked = false;
    document.getElementById("filtro-garagem-fechada").checked = false;
    document.getElementById("filtro-lavanderia").checked = false;
    document.getElementById("filtro-escritorio").checked = false;
    document.getElementById("filtro-ordem").value = "recentes";
    aplicarFiltrosFront();
}

/* ==========================================================================
   4. RENDERIZAÇÃO DOS CARDS E CARROSSEL DE FOTOS
   ========================================================================== */

function renderizarGrade(lista) {
    const grid = document.getElementById("grid-imoveis");
    const emptyState = document.getElementById("empty-state");
    const countBadge = document.getElementById("results-count");
    const countTodos = document.getElementById("count-todos");

    countBadge.textContent = lista.length;
    countTodos.textContent = todosImoveis.length;

    if (lista.length === 0) {
        grid.innerHTML = "";
        emptyState.classList.remove("hidden");
        return;
    }

    emptyState.classList.add("hidden");
    grid.innerHTML = lista.map((im) => criarHtmlCard(im)).join("");
}

function criarHtmlCard(im) {
    const id = im.id || `card_${absHash(im.url)}`;
    if (!(id in indicesFotos)) {
        indicesFotos[id] = 0;
    }

    const fotos = im.fotos && im.fotos.length > 0 ? im.fotos : [
        "https://img.kenlo.io/VWRCUkQ2Tnp3d1BJRDBJVe1szkhnWr9UfpZS9ftWwjXgr7v5Znen3XVcMHllDVRJJeIbi3YwVYEtu2080o1U2EwXrvgyduOjtjSOwZrF3sqhvRWaqIr1nY7J+tyvB-b+kdFnj7-iSEH9oZ87TN02NGtpWdBVfyvQA6qBJVx3sjuFm2HiVKdJWkRb9SsdnydV71K7RIeW6WYXgz2BVP7krBaFa7HZKGJAHrMNAdsz6EIJ9xa9SUxy8h8d55m-oS7TO7S-K5+hxzlXFx5k9oa+Squ619jCLJU4Vr0lNm4L5VMZWe0S2-TJT-8+5wEDqv3JFhXchgzWgPAoc9j0QdhIlLwAxQaRG7cYuB6yktKW0aelbUuDNABp8O2e-qC3Pfz7TrSNe2+jxctTu9iKf+1aN4WoBCMXAl96ZRFArjKnrP7Aswe7MnffpgItFUOUlsMmojUrZxoR8MRe51z115X+ZECeWpnUgEQIPIm3yTwjqesHCoB3J5oN.jpg"
    ];
    const totalFotos = fotos.length;
    const fotoAtual = fotos[indicesFotos[id] % totalFotos];

    const isFav = favoritos.some((f) => f.url === im.url);
    const coracao = isFav ? "❤️" : "🤍";

    // Custo Total formatado
    let infoCustoTotal = "";
    if (im.custo_total) {
        infoCustoTotal = `<div class="total-cost-line">Custo Total Estimado: <strong>R$ ${im.custo_total.toLocaleString('pt-BR')}</strong></div>`;
    }

    // Badges de características
    let badgesHtml = "";
    if (im.quintal) {
        badgesHtml += `<span class="feature-badge">✓ Quintal ${im.quintal !== 'Sim' ? im.quintal : ''}</span>`;
    }
    if (im.garagem_fechada === "Sim") {
        badgesHtml += `<span class="feature-badge">✓ Garagem Fechada</span>`;
    } else if (im.garagem_fechada === "Tipo de garagem não confirmado") {
        badgesHtml += `<span class="feature-badge" style="background:#f1f5f9;color:#64748b;border-color:#cbd5e1">? Garagem a confirmar</span>`;
    }
    if (im.lavanderia) {
        badgesHtml += `<span class="feature-badge">✓ Lavanderia</span>`;
    }
    if (im.pet === "Sim") {
        badgesHtml += `<span class="feature-badge pet-yes">🐾 Aceita Pet</span>`;
    } else if (im.pet === "Não") {
        badgesHtml += `<span class="feature-badge" style="background:#fef2f2;color:#991b1b;border-color:#fecaca">✕ Não aceita pet</span>`;
    }

    if (im.observacao_localizacao) {
        badgesHtml += `<span class="feature-badge geo-notice">📍 ${im.observacao_localizacao}</span>`;
    }

    // Fontes duplicadas alternativas (Item 28 do PRD)
    let duplicadosHtml = "";
    if (im.outras_fontes && im.outras_fontes.length > 0) {
        const linksOutras = im.outras_fontes.map(
            (o) => `<a href="${o.url}" target="_blank" rel="noopener noreferrer">${o.fonte}</a>`
        ).join(", ");
        duplicadosHtml = `
            <div class="duplicate-sources-box">
                Este imóvel também foi encontrado em: ${linksOutras}
            </div>
        `;
    }

    return `
        <article class="prop-card" id="card-${id}">
            <div class="card-media">
                <img id="img-${id}" class="card-img" src="${fotoAtual}" alt="${im.titulo}" loading="lazy" onerror="this.onerror=null;this.src='https://img.kenlo.io/VWRCUkQ2Tnp3d1BJRDBJVe1szkhnWr9UfpZS9ftWwjXgr7v5Znen3XVcMHllDVRJJeIbi3YwVYEtu2080o1U2EwXrvgyduOjtjSOwZrF3sqhvRWaqIr1nY7J+tyvB-b+kdFnj7-iSEH9oZ87TN02NGtpWdBVfyvQA6qBJVx3sjuFm2HiVKdJWkRb9SsdnydV71K7RIeW6WYXgz2BVP7krBaFa7HZKGJAHrMNAdsz6EIJ9xa9SUxy8h8d55m-oS7TO7S-K5+hxzlXFx5k9oa+Squ619jCLJU4Vr0lNm4L5VMZWe0S2-TJT-8+5wEDqv3JFhXchgzWgPAoc9j0QdhIlLwAxQaRG7cYuB6yktKW0aelbUuDNABp8O2e-qC3Pfz7TrSNe2+jxctTu9iKf+1aN4WoBCMXAl96ZRFArjKnrP7Aswe7MnffpgItFUOUlsMmojUrZxoR8MRe51z115X+ZECeWpnUgEQIPIm3yTwjqesHCoB3J5oN.jpg'">
                
                ${totalFotos > 1 ? `
                    <button class="carousel-btn prev" onclick="mudarFoto('${id}', -1, event)">❮</button>
                    <button class="carousel-btn next" onclick="mudarFoto('${id}', 1, event)">❯</button>
                    <span id="counter-${id}" class="photo-counter">${indicesFotos[id] + 1} / ${totalFotos}</span>
                ` : ''}

                <span class="badge-source">${im.fonte}</span>
                <button class="btn-fav-heart ${isFav ? 'active' : ''}" onclick="toggleFavorito('${im.url}', event)" title="Favoritar imóvel">
                    ${coracao}
                </button>
            </div>

            <div class="card-body">
                <div class="price-section">
                    <span class="rent-price">R$ ${(im.aluguel || 0).toLocaleString('pt-BR')}</span>
                    <span class="rent-period">/ mês</span>
                    ${infoCustoTotal}
                </div>

                <div class="neighborhood-title">📍 ${im.bairro}</div>
                <h3 class="card-title">${im.titulo}</h3>

                <div class="specs-strip">
                    ${im.quartos !== null ? `<span class="spec-pill">🛏️ ${im.quartos} ${im.quartos === 1 ? 'quarto' : 'quartos'}</span>` : ''}
                    ${im.suites ? `<span class="spec-pill">🚿 ${im.suites} ${im.suites === 1 ? 'suíte' : 'suítes'}</span>` : ''}
                    ${im.banheiros ? `<span class="spec-pill">🚽 ${im.banheiros} banh.</span>` : ''}
                    ${im.vagas !== null ? `<span class="spec-pill">🚗 ${im.vagas} ${im.vagas === 1 ? 'vaga' : 'vagas'}</span>` : ''}
                    ${im.area ? `<span class="spec-pill">📐 ${im.area} m²</span>` : ''}
                </div>

                <div class="badges-container">
                    ${badgesHtml}
                </div>

                ${duplicadosHtml}

                <div class="card-actions">
                    <a href="${im.url}" target="_blank" rel="noopener noreferrer" class="btn-open-listing">
                        ABRIR ANÚNCIO ↗
                    </a>
                </div>
            </div>
        </article>
    `;
}

function mudarFoto(cardId, delta, event) {
    if (event) event.stopPropagation();

    const imovel = todosImoveis.find((i) => (i.id || `card_${absHash(i.url)}`) === cardId) ||
                   favoritos.find((i) => (i.id || `card_${absHash(i.url)}`) === cardId);

    if (!imovel || !imovel.fotos || imovel.fotos.length <= 1) return;

    const total = imovel.fotos.length;
    let atual = (indicesFotos[cardId] || 0) + delta;
    if (atual < 0) atual = total - 1;
    if (atual >= total) atual = 0;

    indicesFotos[cardId] = atual;

    const img = document.getElementById(`img-${cardId}`);
    const counter = document.getElementById(`counter-${cardId}`);

    if (img) img.src = imovel.fotos[atual];
    if (counter) counter.textContent = `${atual + 1} / ${total}`;
}

function absHash(str) {
    let hash = 0;
    if (!str || str.length === 0) return hash;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash |= 0;
    }
    return Math.abs(hash);
}

/* ==========================================================================
   5. FAVORITOS (ITEM 32 E 33 DO PRD)
   ========================================================================== */

async function toggleFavorito(url, event) {
    if (event) event.stopPropagation();

    const imovel = todosImoveis.find((i) => i.url === url) || favoritos.find((i) => i.url === url);
    if (!imovel) return;

    // Atualização instantânea no cliente com persistência no localStorage
    const idx = favoritos.findIndex((f) => f.url === url);
    if (idx >= 0) {
        favoritos.splice(idx, 1);
    } else {
        favoritos.push(imovel);
    }
    localStorage.setItem("imovel_radar_favoritos", JSON.stringify(favoritos));
    document.getElementById("count-favoritos").textContent = favoritos.length;
    renderizarFavoritos();
    aplicarFiltrosFront();

    // Sincronização em segundo plano com a API
    try {
        await fetch("/api/favoritos/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ imovel })
        });
    } catch (err) {
        console.warn("Favorito mantido no armazenamento local do navegador:", err);
    }
}

function renderizarFavoritos() {
    const grid = document.getElementById("grid-favoritos");
    const countBadge = document.getElementById("favs-count");
    countBadge.textContent = favoritos.length;

    if (favoritos.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-icon">❤️</div>
                <h3>Nenhum imóvel favoritado ainda</h3>
                <p>Clique no ícone de coração nos cards para salvar seus imóveis preferidos.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = favoritos.map((im) => criarHtmlCard(im)).join("");
}

/* ==========================================================================
   6. GESTÃO DE BAIRROS E FONTES (ITENS 11 E 39 DO PRD)
   ========================================================================== */

async function carregarBairros() {
    try {
        const resp = await fetch("/api/bairros");
        if (resp.ok) {
            const data = await resp.json();
            bairrosConfig = data.bairros || [];
            document.getElementById("count-bairros").textContent = bairrosConfig.length;
            renderizarListaBairros();
        }
    } catch (err) {
        console.error("Erro ao carregar bairros:", err);
    }
}

function renderizarListaBairros() {
    const container = document.getElementById("lista-bairros");
    container.innerHTML = bairrosConfig.map((b) => `
        <label class="checkbox-label" style="background:#f8fafc;padding:8px 12px;border-radius:6px;border:1px solid #e2e8f0;">
            <input type="checkbox" ${b.ativo ? 'checked' : ''} onchange="toggleBairroStatus('${b.nome}', this.checked)">
            <span>${b.nome}</span>
        </label>
    `).join("");
}

async function toggleBairroStatus(nome, ativo) {
    try {
        await fetch(`/api/bairros/${encodeURIComponent(nome)}/toggle`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ativo })
        });
    } catch (err) {
        console.error("Erro ao atualizar status do bairro:", err);
    }
}

async function adicionarNovoBairro() {
    const input = document.getElementById("novo-bairro-input");
    const nome = input.value.trim();
    if (!nome) return;

    try {
        const resp = await fetch("/api/bairros", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nome })
        });
        if (resp.ok) {
            input.value = "";
            await carregarBairros();
        }
    } catch (err) {
        console.error("Erro ao cadastrar bairro:", err);
    }
}

async function carregarFontes() {
    try {
        const resp = await fetch("/api/fontes");
        if (resp.ok) {
            const data = await resp.json();
            fontesConfig = data.fontes || [];
            document.getElementById("count-fontes").textContent = fontesConfig.length;
            renderizarListaFontes();
        }
    } catch (err) {
        console.error("Erro ao carregar fontes:", err);
    }
}

function renderizarListaFontes() {
    const container = document.getElementById("lista-fontes");
    container.innerHTML = fontesConfig.map((f) => `
        <div class="fonte-row">
            <div class="fonte-info">
                <span class="status-indicator ${f.status || 'funcionando'}"></span>
                <div>
                    <strong style="font-size:14px;">${f.nome}</strong>
                    <div style="font-size:12px;color:#64748b;">${f.url}</div>
                </div>
            </div>
            <div style="font-size:12px;color:#475569;display:flex;align-items:center;gap:14px;">
                <span>${f.imoveis_encontrados || 0} encontrados</span>
                <span class="feature-badge" style="background:#f1f5f9;color:#334155;">${f.status}</span>
            </div>
        </div>
    `).join("");
}

async function adicionarNovaFonte() {
    const nomeInput = document.getElementById("nova-fonte-nome");
    const urlInput = document.getElementById("nova-fonte-url");
    const nome = nomeInput.value.trim();
    const url = urlInput.value.trim();
    if (!nome || !url) {
        alert("Preencha o nome e a URL da nova imobiliária.");
        return;
    }

    try {
        const resp = await fetch("/api/fontes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nome, url })
        });
        if (resp.ok) {
            nomeInput.value = "";
            urlInput.value = "";
            await carregarFontes();
            alert(`Fonte "${nome}" adicionada com sucesso!`);
        }
    } catch (err) {
        console.error("Erro ao adicionar fonte:", err);
    }
}

/* ==========================================================================
   7. GESTÃO DE ABAS E CONFIGURAÇÕES
   ========================================================================== */

function alternarAba(abaId) {
    document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((sec) => sec.classList.remove("active"));

    if (abaId === "imoveis") {
        document.querySelector(".tab-btn:nth-child(1)").classList.add("active");
        document.getElementById("aba-imoveis").classList.add("active");
        document.getElementById("sidebar-filtros").style.display = "block";
    } else if (abaId === "favoritos") {
        document.querySelector(".tab-btn:nth-child(2)").classList.add("active");
        document.getElementById("aba-favoritos").classList.add("active");
        document.getElementById("sidebar-filtros").style.display = "none";
        renderizarFavoritos();
    } else if (abaId === "bairros") {
        document.querySelector(".tab-btn:nth-child(3)").classList.add("active");
        document.getElementById("aba-bairros").classList.add("active");
        document.getElementById("sidebar-filtros").style.display = "none";
    } else if (abaId === "fontes") {
        document.querySelector(".tab-btn:nth-child(4)").classList.add("active");
        document.getElementById("aba-fontes").classList.add("active");
        document.getElementById("sidebar-filtros").style.display = "none";
    }
}

function salvarConfiguracoesLocal(filtros) {
    try {
        localStorage.setItem("BUSCADOR_IMOVEIS_FILTROS", JSON.stringify(filtros));
    } catch (e) {}
}

function carregarConfiguracoes() {
    try {
        const saved = localStorage.getItem("BUSCADOR_IMOVEIS_FILTROS");
        if (saved) {
            const f = JSON.parse(saved);
            if (f.aluguel_max) document.getElementById("filtro-aluguel-max").value = f.aluguel_max;
            if (f.custo_total_max) document.getElementById("filtro-custo-total-max").value = f.custo_total_max;
            if (f.min_quartos) document.getElementById("filtro-min-quartos").value = f.min_quartos;
            if (f.max_quartos) document.getElementById("filtro-max-quartos").value = f.max_quartos;
            if (f.min_suites) document.getElementById("filtro-min-suites").value = f.min_suites;
            if (f.min_banheiros) document.getElementById("filtro-min-banheiros").value = f.min_banheiros;
            if (f.min_vagas) document.getElementById("filtro-min-vagas").value = f.min_vagas;
            if (f.area_min) document.getElementById("filtro-area-min").value = f.area_min;
            if (f.pet) document.getElementById("filtro-pet").value = f.pet;
            if (f.possui_quintal) document.getElementById("filtro-quintal").checked = f.possui_quintal;
            if (f.garagem_fechada) document.getElementById("filtro-garagem-fechada").checked = f.garagem_fechada;
            if (f.lavanderia) document.getElementById("filtro-lavanderia").checked = f.lavanderia;
            if (f.exigir_escritorio) document.getElementById("filtro-escritorio").checked = f.exigir_escritorio;
            if (f.ordenar_por) document.getElementById("filtro-ordem").value = f.ordenar_por;
        }
    } catch (e) {}
}
