/* ECOFOOD PRO - ENGINE 16.0 (FINAL GOLD EDITION) */

const API_URL = "/gerar-solucao"; 

// --- CONTROLE DE ESTADO PRO (PERSISTÊNCIA) ---
let usuarioEhPro = false; 

const databaseProfissionais = [
    { nome: "Marcos Filho", area: "P&D Lácteos", foto: "assets/eu.jpg", emoji: "👨‍🔬", email: "marcos@ecofood.com" },
    { nome: "Ana Silva", area: "Regulatório & Qualidade", foto: "", emoji: "👩‍🔬", email: "ana@email.com" },
    { nome: "João Pedro", area: "P&D de Embalagens", foto: "", emoji: "👨‍💻", email: "joao@email.com" },
    { nome: "Júlia Costa", area: "Inovação Sustentável", foto: "", emoji: "👩‍🌾", email: "julia@email.com" }
];

let historicoGlobal = [];
let resultadosAtuais = [];

function mudarAba(aba) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`tab-${aba}`).classList.add('active');
    document.getElementById('view-basico').style.display = 'none';
    document.getElementById('view-avancado').style.display = 'none';
    document.getElementById(`view-${aba}`).style.display = 'block';
}

document.addEventListener('DOMContentLoaded', () => { mudarAba('basico'); });

function adicionarCampoIngrediente() {
    const container = document.getElementById('lista-ingredientes-extras');
    const div = document.createElement('div');
    div.className = 'ingrediente-row';
    div.innerHTML = `
        <select class="ing-operador"><option value="AND">E (AND)</option><option value="OR">OU (OR)</option></select>
        <input type="text" class="ing-nome" placeholder="Ingrediente extra...">
        <input type="text" class="ing-qtd" placeholder="Qtd" style="width: 80px;">
        <button onclick="this.parentElement.remove()" class="btn-remove">X</button>
    `;
    container.appendChild(div);
}

// --- LÓGICA DE DESBLOQUEIO PERSISTENTE ---
function desbloquearSistema() {
    // 1. Atualiza o estado lógico
    usuarioEhPro = true;

    // 2. Aplica o CSS IMEDIATAMENTE
    document.body.classList.add('pro-mode-active'); 
    document.getElementById('pro-badge').style.display = 'inline-block'; 

    // 3. Pequeno delay para o navegador renderizar a cor preta ANTES do alerta travar a tela
    setTimeout(() => {
        alert("✨ ACESSO PRO LIBERADO!\n\nAgora todas as suas pesquisas futuras virão completas automaticamente.");
        
        // Remove bloqueios visuais
        const overlays = document.querySelectorAll('.pro-lock-overlay');
        const conteudos = document.querySelectorAll('.blurred-content');
        
        overlays.forEach(el => el.style.display = 'none');
        conteudos.forEach(el => {
            el.classList.remove('blurred-content');
            el.style.pointerEvents = 'auto'; 
            el.style.userSelect = 'auto';
            el.style.opacity = '1';
        });
        
        // Habilita o clique nos cards antigos
        const cardsBloqueados = document.querySelectorAll('.locked-card');
        cardsBloqueados.forEach((card, index) => {
            card.classList.remove('locked-card');
            const itemIndex = index + 2; 
            if(resultadosAtuais[itemIndex]) {
                card.onclick = function() { abrirDetalhe(resultadosAtuais[itemIndex]); };
            }
        });
        
        // Re-renderiza para garantir que bordas e estilos peguem o novo CSS
        renderizarGrid(resultadosAtuais);
        
    }, 50); // 50ms é suficiente para o olho perceber a mudança de cor
}

function gerarImagemInteligente(item) {
    const categoria = item.categoria_visual || "GENERICO";
    const contextMap = {
        'ALIMENTO_SOLIDO': "Food product photography, appetizing, neutral studio background, packaging",
        'BEBIDA': "Beverage photography, condensation on glass, liquid texture, neutral studio background, studio lighting",
        'LACTEO': "Dairy product photography, creamy texture, opaque white liquid, neutral studio background, soft lighting",
        'COSMETICO': "Cosmetic product, spa aesthetic, marble background, NO FOOD, luxury",
        'FARMACO': "Pharmaceutical product, clean clinical background, medicine style",
        'AGRICOLA': "Garden product, soil texture background, outdoor light, fertilizer bag",
        'GENERICO': "Professional product mockup, neutral studio background"
    };
    const contextTrigger = contextMap[categoria] || contextMap['GENERICO'];
    const objectDescription = item.visual_prompt_en || `Packaging of ${item.nome}`;
    const promptFinal = `${contextTrigger}, ${objectDescription}, cinematic lighting, 8k, photorealistic, centered composition, upper center focus`.replace(/\s+/g, ' ').trim();
    return `https://pollinations.ai/p/${encodeURIComponent(promptFinal)}?width=600&height=450&seed=${Math.random()}&model=flux`;
}

function calcularSelo(item) {
    const econ = Number(item.sustentabilidade?.agua_economizada_litros_100kg || 0);
    const gasta = Number(item.sustentabilidade?.agua_gasta_processo_litros_100kg || 0);
    const saldo = econ - gasta;
    if (saldo >= 1000) return { img: "assets/selo_ouro.png", label: "Ouro", saldo: saldo };
    if (saldo >= 700) return { img: "assets/selo_prata.png", label: "Prata", saldo: saldo };
    return { img: "assets/selo_bronze.png", label: "Bronze", saldo: saldo };
}

async function executarPesquisaBasica() {
    const residuo = document.getElementById('inputResiduoBasico').value.trim();
    const nivel = document.getElementById('selectNivelBasico').value;
    if (!residuo) { alert("Informe o resíduo."); return; }
    enviarPedido({ residuo_principal: residuo, nivel_producao: nivel, modo_avancado: false }, 'view-basico');
}

async function executarPesquisaAvancada() {
    const residuo = document.getElementById('inputResiduoAdv').value.trim();
    const nivel = document.getElementById('selectNivelAdv').value;
    const qtd = document.getElementById('inputQtdAdv').value.trim();
    const produtoAlvo = document.getElementById('inputProdutoAlvo').value.trim();
    const ingredientesExtras = [];
    document.querySelectorAll('.ingrediente-row').forEach(row => {
        const nome = row.querySelector('.ing-nome').value.trim();
        const operador = row.querySelector('.ing-operador').value;
        const quantidade = row.querySelector('.ing-qtd').value.trim();
        if(nome) ingredientesExtras.push({ nome, operador, quantidade });
    });
    if (!residuo) { alert("Informe o Resíduo Principal."); return; }
    enviarPedido({ residuo_principal: residuo, nivel_producao: nivel, quantidade_semanal: qtd || null, produto_alvo: produtoAlvo || null, ingredientes_extras: ingredientesExtras, modo_avancado: true }, 'view-avancado');
}

async function enviarPedido(payload, viewId) {
    const areaLista = document.getElementById('area-lista-resultados');
    const areaDetalhe = document.getElementById('area-detalhes-produto');
    if(areaLista) { areaLista.innerHTML = ""; areaLista.style.display = 'grid'; }
    if(areaDetalhe) areaDetalhe.style.display = 'none';

    const btnAtivo = document.querySelector(`#${viewId} .btn-gerar`);
    let txtOriginal = "Gerar";
    if (btnAtivo) { txtOriginal = btnAtivo.innerText; btnAtivo.innerText = "Processando..."; btnAtivo.disabled = true; }

    try {
        const response = await fetch(API_URL, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        let dadosRaw = await response.json();
        if (!Array.isArray(dadosRaw)) dadosRaw = [dadosRaw];
        let listaLimpa = dadosRaw.flat().filter(item => item && typeof item === 'object' && item.nome);
        if (listaLimpa.length === 0) throw new Error("A IA não retornou resultados válidos.");

        listaLimpa.forEach(solucao => {
            solucao.id = Math.random().toString(36).substr(2, 9);
            solucao.nivel = solucao.nivel || payload.nivel_producao;
            solucao.imagem_url = gerarImagemInteligente(solucao);
        });
        resultadosAtuais = listaLimpa;
        adicionarAoHistorico(`${payload.residuo_principal} (${payload.nivel_producao})`, resultadosAtuais);
        renderizarGrid(resultadosAtuais);
    } catch (error) { console.error("Erro JS:", error); alert("Erro na conexão."); } 
    finally { if (btnAtivo) { btnAtivo.innerText = txtOriginal; btnAtivo.disabled = false; } }
}

function renderizarGrid(lista) {
    const grid = document.getElementById('area-lista-resultados');
    if (!grid) return;
    grid.innerHTML = ""; 

    lista.forEach((item, index) => {
        const card = document.createElement('div');
        
        // --- LÓGICA: Se usuário JÁ é pro, NÃO bloqueia nada. Se não, bloqueia >= 2 ---
        const isLocked = !usuarioEhPro && index >= 2; 
        
        if (isLocked) {
            card.className = 'result-card locked-card';
            card.innerHTML = `
                <div class="pro-lock-overlay">
                    <h3>🔒 Versão PRO</h3>
                    <p style="font-size:0.9rem; margin-top:5px; color:#555;">Desbloqueie análises de ROI e Fluxogramas.</p>
                    <button class="btn-upgrade" onclick="desbloquearSistema()">Testar gratuitamente por 7 dias</button>
                </div>
                <div class="blurred-content">
                    <div class="card-img"><img src="${item.imagem_url}" alt="Bloqueado"></div>
                    <div class="card-body">
                        <span class="card-tag">PREMIUM</span>
                        <h3 style="margin: 10px 0;">${item.nome}</h3>
                        <p>${item.pitch}</p>
                    </div>
                </div>
            `;
        } else {
            card.className = 'result-card';
            card.onclick = function() { abrirDetalhe(item); };
            card.innerHTML = `
                <div class="card-img"><img src="${item.imagem_url}" alt="${item.nome}"></div>
                <div class="card-body">
                    <span class="card-tag">${item.nivel}</span>
                    <h3 style="margin: 10px 0; color: #333;">${item.nome}</h3>
                    <p style="font-size: 0.9rem; color: #666;">${item.pitch || ""}</p>
                </div>
            `;
        }
        grid.appendChild(card);
    });
    setTimeout(() => { grid.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 200);
}

function ativarContato(id, produtoNome) {
    document.getElementById(`btn-contact-${id}`).style.display = 'none';
    document.getElementById(`form-contact-${id}`).style.display = 'block';
    const txtArea = document.getElementById(`msg-contact-${id}`);
    txtArea.value = `Olá, estou entrando em contato para solicitar orçamento quanto ao desenvolvimento do produto "${produtoNome}" para minha agroindústria.\n\nContato: (escreva seu nome e telefone aqui)`;
}

function enviarEmailSimulado(id) {
    const btn = document.querySelector(`#form-contact-${id} button`);
    const txtArea = document.getElementById(`msg-contact-${id}`);
    if(!txtArea.value.trim()) { alert("Por favor, escreva uma mensagem."); return; }
    const txtOriginal = btn.innerText;
    btn.innerText = "Enviando..."; btn.disabled = true; btn.style.background = "#999";
    setTimeout(() => {
        document.getElementById(`form-contact-${id}`).innerHTML = `
            <div style="padding:15px; background:#e8f5e9; border-radius:5px; border:1px solid #c8e6c9; text-align:center;">
                <h4 style="color:#2e7d32; margin-bottom:5px;">✅ Solicitação Enviada!</h4>
                <p style="font-size:0.8rem; color:#555;">O profissional recebeu seu contato.</p>
            </div>
        `;
    }, 1500);
}

function abrirDetalhe(item) {
    document.getElementById('area-lista-resultados').style.display = 'none';
    const areaDetalhe = document.getElementById('area-detalhes-produto');
    areaDetalhe.style.display = 'block';
    
    const conteudo = document.getElementById('conteudo-detalhe');
    const selo = calcularSelo(item);
    
    const passos = item.fluxograma;
    let grafo = "graph LR;\n";
    if (Array.isArray(passos) && passos.length > 0) {
        passos.forEach((p, i) => {
            let txt = typeof p === 'object' ? (p.etapa || JSON.stringify(p)) : String(p);
            const txtClean = txt.replace(/[^a-zA-Z0-9 à-úÀ-ÚçÇ:0-9°/,-]/g, ""); 
            grafo += i < passos.length - 1 ? `s${i}["${txtClean}"] --> s${i+1};\n` : `s${i}["${txtClean}"];\n`;
        });
    } else grafo += `s1["Ver texto"];\n`;
    grafo += "classDef default fill:#fff,stroke:#FFD700,stroke-width:2px,color:#000;\n";

    const nutri = item.nutricao || {};
    const eco = item.economia || {};
    let ingr = Array.isArray(item.lista_ingredientes) ? item.lista_ingredientes.join(", ") : (item.lista_ingredientes || "N/A");
    let htmlAlertas = "";
    if (nutri.alertas_fop && Array.isArray(nutri.alertas_fop)) htmlAlertas = `<div class="fop-alert">` + nutri.alertas_fop.map(a => `<div class="magnifying-glass">🔍 ${a}</div>`).join('') + `</div>`;

    const cardsProfissionais = databaseProfissionais.map((pro, idx) => {
        const avatarHtml = pro.foto 
            ? `<img src="${pro.foto}" class="avatar-img" alt="${pro.nome}" onerror="this.style.display='none'; this.nextElementSibling.style.display='block'"> <div class="expert-avatar" style="display:none">${pro.emoji}</div>` 
            : `<div class="expert-avatar">${pro.emoji}</div>`;
        return `
        <div class="expert-card">
            ${avatarHtml}
            <strong>${pro.nome}</strong>
            <div style="font-size:0.8rem; color:#666;">${pro.area}</div>
            <button id="btn-contact-${idx}" class="btn-contact" onclick="ativarContato(${idx}, '${item.nome}')">💬 Entrar em Contato</button>
            <div id="form-contact-${idx}" class="contact-form-area" style="display:none; margin-top:10px;">
                <textarea id="msg-contact-${idx}" rows="4" style="width:100%; padding:5px; font-size:0.8rem; border:1px solid #ccc; border-radius:4px;"></textarea>
                <button onclick="enviarEmailSimulado(${idx})" style="background:#000; color:#FFD700; border:1px solid #FFD700; padding:5px 10px; border-radius:4px; margin-top:5px; cursor:pointer; width:100%; font-weight:bold;">✈️ Enviar</button>
            </div>
        </div>
    `}).join('');

    conteudo.innerHTML = `
        <div class="detail-card">
            <div class="report-header">
                <h1>${item.nome}</h1>
                <p>${item.nivel} • Origem: ${item.regiao || "Brasil"}</p>
            </div>
            <div class="dashboard-grid">
                <div class="area-imagem"><img src="${item.imagem_url}" alt="${item.nome}"></div>
                <div class="area-conceito">
                    <h4 style="color:#000; font-size:0.8rem;">CONCEITO</h4>
                    <p style="font-style:italic; font-size:1.1rem;">"${item.pitch}"</p>
                </div>
                <div class="area-economia">
                    <h4 style="font-size:0.8rem; margin-bottom:5px;">VIABILIDADE ECONÔMICA</h4>
                    <div style="font-size:0.9rem;">Custo: <strong>${eco.custo_producao_estimado || "-"}</strong></div>
                    <div style="font-size:0.9rem;">Venda: <strong>${eco.preco_venda_estimado || "-"}</strong></div>
                    <div style="font-size:0.9rem; color:green;">Margem: <strong>${eco.margem_lucro || "-"}</strong></div>
                    <div style="font-size:0.8rem; margin-top:5px;">ROI: ${eco.roi_estimado || "-"}</div>
                </div>
                <div class="area-selo">
                    <div class="seal-wrapper">
                        <img src="${selo.img}" alt="Selo">
                        <div class="seal-value">+${selo.saldo} L<div style="font-size:0.35em; font-weight:normal; margin-top:3px; color:#f0f0f0;">/ 100kg de<br>alimento processado</div></div>
                    </div>
                </div>
                <div class="area-fluxograma">
                    <h4 style="color:#000;">PROCESSO PRODUTIVO</h4>
                    <div class="mermaid">${grafo}</div>
                </div>
                <div class="area-tabela">
                    <div class="nutrition-table">
                        <div class="nutri-header">INFORMAÇÃO NUTRICIONAL (100g)</div>
                        <div class="nutri-row bold"><span>Valor Energético</span><span>${nutri.valor_energetico || "-"}</span></div>
                        <div class="nutri-row"><span>Carboidratos</span><span>${nutri.carboidratos || "-"}</span></div>
                        <div class="nutri-row" style="padding-left:10px; font-size:0.8em"><span>Açúcares Totais</span><span>${nutri.acucares_totais || "-"}</span></div>
                        <div class="nutri-row" style="padding-left:10px; font-size:0.8em"><span>Açúcares Adic.</span><span>${nutri.acucares_adicionados || "-"}</span></div>
                        <div class="nutri-row"><span>Proteínas</span><span>${nutri.proteinas || "-"}</span></div>
                        <div class="nutri-row"><span>Gorduras Totais</span><span>${nutri.gorduras_totais || "-"}</span></div>
                        <div class="nutri-row" style="padding-left:10px; font-size:0.8em"><span>Gorduras Sat.</span><span>${nutri.gorduras_saturadas || "-"}</span></div>
                        <div class="nutri-row"><span>Fibra Alimentar</span><span>${nutri.fibra_alimentar || "-"}</span></div>
                        <div class="nutri-row"><span>Sódio</span><span>${nutri.sodio || "-"}</span></div>
                    </div>
                    ${htmlAlertas}
                </div>
                <div class="area-dados">
                    <div style="margin-bottom:15px;">
                        <h4 style="color:#000;">📋 Ingredientes</h4>
                        <p style="font-size:0.9rem;">${ingr}</p>
                    </div>
                    <div>
                        <h4 style="color:#000;">🛡️ Legislação & Segurança</h4>
                        <p style="font-size:0.9rem;">${item.seguranca || "-"}</p>
                    </div>
                </div>
            </div> 
            
            <div class="expert-section">
                <div style="text-align:center; margin-bottom:20px;">
                    <p style="color:#666; margin-bottom:10px;">⚠️ Esta solução é gerada por IA. Para viabilidade industrial, consulte um RT.</p>
                    <button id="btn-show-experts" onclick="document.getElementById('grid-experts').style.display='grid'; this.style.display='none'" style="background:#000; color:#FFD700; border:1px solid #FFD700; padding:10px 20px; border-radius:20px; cursor:pointer; font-weight:bold;">🔍 Procurar o Profissional Ideal</button>
                </div>
                <div id="grid-experts" class="experts-grid" style="display:none;">${cardsProfissionais}</div>
            </div>

            <button onclick="window.print()" style="margin-top:30px; width:100%; padding:15px; background:#000; color:#FFD700; border:2px solid #FFD700; cursor:pointer; font-weight:bold;">🖨️ Gerar PDF do Relatório</button>
        </div>
    `;
    setTimeout(() => { try { mermaid.init(undefined, document.querySelectorAll('.mermaid')); } catch(e){} }, 200);
    setTimeout(() => { areaDetalhe.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 200);
}

function voltarParaLista() {
    document.getElementById('area-lista-resultados').style.display = 'grid';
    document.getElementById('area-detalhes-produto').style.display = 'none';
    document.getElementById('area-lista-resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function adicionarAoHistorico(termo, resultados) {
    const projeto = { id: Date.now(), termo: termo, data: new Date().toLocaleTimeString(), resultados: resultados };
    historicoGlobal.unshift(projeto);
    atualizarPainelHistorico();
}
function atualizarPainelHistorico() {
    const lista = document.getElementById('lista-historico');
    if(lista) {
        lista.innerHTML = "";
        historicoGlobal.forEach(proj => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.innerHTML = `<h4>${proj.termo}</h4><span>${proj.data}</span>`;
            item.onclick = () => { resultadosAtuais = proj.resultados; toggleHistorico(); renderizarGrid(resultadosAtuais); };
            lista.appendChild(item);
        });
    }
}
function toggleHistorico() { document.getElementById('painel-historico').classList.toggle('open'); }