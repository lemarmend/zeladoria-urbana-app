// --- CONFIGURAÇÃO DINÂMICA DA API ---
let API = window.location.origin;
if (API === 'null' || API.startsWith('file:')) {
    API = "http://127.0.0.1:8000";
    console.warn("Modo arquivo detectado. Usando localhost.");
}

var map, userLat = 0, userLng = 0, role = 'cidadao';
var mapaTiposCache = {}; 

// --- FACEBOOK INIT ---
window.fbAsyncInit = function() {
    FB.init({ appId: 'SEU_APP_ID', cookie: true, xfbml: true, version: 'v18.0' });
};

// --- 1. AUTENTICAÇÃO ---

function alternarForms() {
    const login = document.getElementById('formLogin');
    const cadastro = document.getElementById('formCadastro');
    if (login.style.display === 'none') {
        login.style.display = 'block'; cadastro.style.display = 'none';
    } else {
        login.style.display = 'none'; cadastro.style.display = 'block';
    }
}

async function fazerLoginReal() {
    const email = document.getElementById('emailLogin').value;
    const senha = document.getElementById('senhaLogin').value;
    try {
        const res = await fetch(`${API}/auth/login`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, senha})
        });
        if(res.ok) {
            const data = await res.json();
            localStorage.setItem('token_zeladoria', data.access_token);
            entrarApp(data.perfil);
        } else {
            const err = await res.json();
            alert("Erro: " + (err.detail || "Falha no login"));
        }
    } catch(e) { console.error(e); alert("Erro de conexão"); }
}

async function cadastrar() {
    const load = {
        email: document.getElementById('emailCad').value,
        senha: document.getElementById('senhaCad').value,
        perfil: document.getElementById('perfilCad').value
    };
    const res = await fetch(`${API}/auth/cadastro`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(load)
    });
    const json = await res.json();
    alert(json.msg || json.detail);
    if(res.ok && load.perfil !== 'prefeitura') alternarForms();
}

// --- 2. INICIALIZAÇÃO DO APP ---

function entrarApp(perfil) {
    role = perfil;
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('navBarApp').style.display = 'flex';
    document.getElementById('labelPerfil').innerText = role.toUpperCase();

    if(role === 'admin') document.getElementById('btnAdmin').style.display = 'inline-block';
    if(role !== 'prefeitura') document.getElementById('fabBtn').style.display = 'flex';
    else document.getElementById('fabBtn').style.display = 'none';

    iniciarMapa();
    carregarTudo();
}

function sair() {
    localStorage.removeItem('token_zeladoria');
    location.reload();
}

async function carregarTudo() {
    await carregarTipos();
    await carregarProblemas();
}

// --- 3. DADOS DINÂMICOS (TIPOS) ---

async function carregarTipos() {
    try {
        const res = await fetch(`${API}/tipos`);
        const tipos = await res.json();
        mapaTiposCache = {}; 
        const select = document.getElementById('tipoProblema');
        select.innerHTML = ""; 

        const categorias = {};
        tipos.forEach(t => {
            mapaTiposCache[t.chave] = t;
            if(!categorias[t.categoria]) categorias[t.categoria] = [];
            categorias[t.categoria].push(t);
        });

        for(let cat in categorias) {
            let group = document.createElement('optgroup');
            group.label = cat;
            categorias[cat].forEach(t => {
                let opt = document.createElement('option');
                opt.value = t.chave;
                opt.innerText = `${t.icone} ${t.titulo}`;
                group.appendChild(opt);
            });
            select.appendChild(group);
        }
    } catch(e) { console.error("Erro ao carregar tipos", e); }
}

// --- 4. MAPA E PROBLEMAS ---

function iniciarMapa() {
    if(map) return;
    map = L.map('map', {zoomControl: false}).setView([-23.5505, -46.6333], 13);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png').addTo(map);
    
    if(navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(pos => {
            userLat = pos.coords.latitude; userLng = pos.coords.longitude;
            map.setView([userLat, userLng], 16);
            L.circleMarker([userLat, userLng], {radius: 8, color: '#0d6efd'}).addTo(map);
        });
    }
}

async function carregarProblemas() {
    const res = await fetch(`${API}/problemas`);
    const dados = await res.json();
    
    map.eachLayer(l => { if(l instanceof L.Marker) map.removeLayer(l); });

    dados.forEach(d => {
        let info = mapaTiposCache[d.tipo] || {icone: '📍', titulo: d.tipo};
        let cor = d.status === 'aberto' ? '#dc3545' : (d.status === 'analise' ? '#fd7e14' : '#198754');
        
        // --- LÓGICA DE TAMANHO DINÂMICO ---
        let tamanho = 35 + ((d.confirmacoes - 1) * 4); 
        if (tamanho > 70) tamanho = 70;
        let fonte = tamanho * 0.5;
        let ancoraX = tamanho / 2;
        let ancoraY = tamanho;

        let iconHtml = `<div class="custom-marker" style="border: 3px solid ${cor}; width:${tamanho}px; height:${tamanho}px; font-size:${fonte}px;">${info.icone}</div>`;
        let icon = L.divIcon({ html: iconHtml, className: '', iconSize: [tamanho, tamanho], iconAnchor: [ancoraX, ancoraY] });

        let marker = L.marker([d.lat, d.lng], {icon: icon}).addTo(map);
        
        // --- POPUP COM CONTADORES ---
        let botoes = "";
        if(role === 'cidadao') {
             if(d.status === 'resolvido') botoes = `<button onclick="acao(${d.id}, 'validar')" class="btn btn-sm btn-success w-100 mt-2">✅ Validar (${d.validacoes_cidadao}/3)</button>`;
             else botoes = `<button onclick="acao(${d.id}, 'votar')" class="btn btn-sm btn-outline-primary w-100 mt-2">👍 Eu também vi (${d.confirmacoes})</button>`;
        } else if(role === 'prefeitura') {
            botoes = `
                <div class="mt-2 btn-group w-100">
                    <button onclick="acao(${d.id}, 'analise')" class="btn btn-sm btn-warning">👀</button>
                    <button onclick="acao(${d.id}, 'nota')" class="btn btn-sm btn-secondary">📝</button>
                    <button onclick="acao(${d.id}, 'resolvido')" class="btn btn-sm btn-success">✅</button>
                </div>`;
        } else if(role === 'admin') {
            botoes = `<button onclick="deletarProb(${d.id})" class="btn btn-sm btn-danger w-100 mt-2">🗑️ Apagar</button>`;
        }

        marker.bindPopup(`
            <div class="d-flex justify-content-between align-items-center">
                <b>${info.titulo}</b>
                <span class="badge bg-light text-dark border">📢 ${d.confirmacoes}</span>
            </div>
            ${d.descricao}<br>
            <span class="badge bg-secondary">${d.status.toUpperCase()}</span>
            ${d.nota_prefeitura ? `<div class="alert alert-warning p-1 mt-1 mb-0 small">${d.nota_prefeitura}</div>` : ''}
            ${botoes}
        `);
    });
}

async function salvarRelato() {
    const load = {
        tipo: document.getElementById('tipoProblema').value,
        descricao: document.getElementById('descricao').value,
        lat: userLat, lng: userLng
    };
    await fetch(`${API}/problemas`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(load)
    });
    bootstrap.Modal.getInstance(document.getElementById('modalRelato')).hide();
    carregarProblemas();
}

// --- 5. AÇÕES ---

// Substitua a função acao antiga por esta:

async function acao(id, tipo) {
    let url = "";
    let method = "POST"; // Padrão para votar e validar

    if(tipo === 'votar') url = `${API}/problemas/${id}/votar`;
    if(tipo === 'validar') url = `${API}/problemas/${id}/validar`;
    
    // Casos de Status (Analise e Resolvido) exigem PATCH
    if(tipo === 'resolvido' || tipo === 'analise') {
        url = `${API}/problemas/${id}/status?status=${tipo}`;
        method = "PATCH"; // <--- Correção aqui
    }
    
    // Caso de Nota (também exige PATCH)
    if(tipo === 'nota') {
        let txt = prompt("Nota oficial:");
        if(txt) {
            url = `${API}/problemas/${id}/status?status=analise&nota=${encodeURIComponent(txt)}`;
            method = "PATCH";
        } else {
            return; // Cancela se não digitar nada
        }
    }

    // Executa a requisição com o método e URL corretos
    await fetch(url, {method: method});
    carregarProblemas();
}

async function deletarProb(id) {
    if(confirm("Apagar?")) {
        await fetch(`${API}/problemas/${id}`, {method:'DELETE'});
        carregarProblemas();
    }
}

// --- 6. ADMIN ---

function abrirAdmin() {
    carregarListaAdmin();
    new bootstrap.Modal(document.getElementById('modalAdmin')).show();
}

async function carregarListaAdmin() {
    const res = await fetch(`${API}/tipos`);
    const tipos = await res.json();
    const tbody = document.getElementById('listaTiposAdmin');
    tbody.innerHTML = '';
    tipos.forEach(t => {
        tbody.innerHTML += `
            <tr>
                <td class="fs-4">${t.icone}</td>
                <td>${t.titulo}<br><small class="text-muted">${t.chave}</small></td>
                <td>${t.categoria}</td>
                <td><button onclick="adminDelTipo(${t.id})" class="btn btn-sm btn-outline-danger">🗑️</button></td>
            </tr>`;
    });
}

async function adminCriarTipo() {
    const load = {
        chave: document.getElementById('newKey').value,
        titulo: document.getElementById('newTitle').value,
        categoria: document.getElementById('newCat').value,
        icone: document.getElementById('newIcon').value
    };
    const res = await fetch(`${API}/admin/tipos`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(load)
    });
    if(res.ok) { carregarListaAdmin(); carregarTipos(); }
    else alert("Erro ao criar");
}

async function adminDelTipo(id) {
    if(confirm("Apagar tipo?")) {
        await fetch(`${API}/admin/tipos/${id}`, {method:'DELETE'});
        carregarListaAdmin(); carregarTipos();
    }
}

function abrirRelato() { new bootstrap.Modal(document.getElementById('modalRelato')).show(); }

function loginComFacebook() { 
    FB.login(r => { 
        if(r.authResponse) fetchFB(r.authResponse.accessToken, r.authResponse.userID); 
    }, {scope:'email'}); 
}
async function fetchFB(tok, uid) {
    const res = await fetch(`${API}/auth/facebook`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({accessToken:tok, userID:uid})
    });
    if(res.ok) { const d=await res.json(); localStorage.setItem('token_zeladoria', d.access_token); entrarApp(d.perfil); }
}