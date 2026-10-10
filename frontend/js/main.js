/* Sinapse: Protocolo Silencioso (MVP)
 * Phaser cuida das cenas (menu, atmosfera do interrogatório, finais).
 * O HUD e o diálogo são DOM sobre o canvas. As regras vivem no servidor (FastAPI). */
(function () {
  "use strict";
  const W = 1280, H = 720;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ------------------------------------------------------------------ estado do cliente
  let bus;                       // emissor de eventos DOM <-> Phaser
  let S = null;                  // estado público do jogo (vem do servidor)
  let health = { llm: false, model: "" };
  let assetsMap = {};            // imagens de IA encontradas em frontend/assets
  let portraitSrc = {};          // key -> url ou data URL
  let view = "interrogation";
  let current = "beatriz";
  let tone = "perguntar";
  let selEv = new Set();
  let busy = false;
  let confirmClose = false, confirmDay7 = false;
  let boardSuspect = null, boardEvs = new Set();
  const srcLog = { beatriz: [], rafael: [], aurora: [] };   // 'gpt' | 'fallback' por fala
  const lastNote = { beatriz: "", rafael: "", aurora: "" };

  async function api(path, body) {
    const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined;
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || "Erro de comunicação com o servidor.");
    return data;
  }

  // ------------------------------------------------------------------ efeitos sonoros (WebAudio, sem arquivos)
  let audioCtx = null, muted = false;
  try { muted = localStorage.getItem("sinapse_mute") === "1"; } catch (_) {}
  function beep(freq, dur, type, vol, delay) {
    if (muted) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const t0 = audioCtx.currentTime + (delay || 0);
      const o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.type = type || "sine"; o.frequency.value = freq;
      g.gain.setValueAtTime(vol || 0.06, t0);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      o.connect(g); g.connect(audioCtx.destination);
      o.start(t0); o.stop(t0 + dur);
    } catch (_) {}
  }
  const sfx = {
    send: () => beep(520, 0.07, "square", 0.04),
    reply: () => { beep(660, 0.09, "sine"); beep(880, 0.12, "sine", 0.05, 0.09); },
    evidence: () => { beep(740, 0.1, "triangle"); beep(988, 0.16, "triangle", 0.06, 0.1); },
    unlock: () => [440, 554, 659, 880].forEach((f, i) => beep(f, 0.18, "sawtooth", 0.05, i * 0.1)),
    error: () => beep(160, 0.2, "square", 0.05),
    end: () => [392, 330, 262].forEach((f, i) => beep(f, 0.4, "sine", 0.06, i * 0.25)),
  };
  document.addEventListener("DOMContentLoaded", () => {
    const b = $("#mute");
    b.textContent = muted ? "🔇" : "🔊";
    b.addEventListener("click", () => {
      muted = !muted;
      b.textContent = muted ? "🔇" : "🔊";
      try { localStorage.setItem("sinapse_mute", muted ? "1" : "0"); } catch (_) {}
    });
  });

  // ------------------------------------------------------------------ escala do palco
  function fit() {
    const s = Math.min(innerWidth / W, innerHeight / H);
    $("#stage").style.transform = `translate(-50%,-50%) scale(${s})`;
  }
  addEventListener("resize", fit);
  fit();

  let toastTimer;
  function toast(msg, bad) {
    const t = $("#toast");
    t.textContent = msg;
    t.className = "show" + (bad ? " bad" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.className = ""), 3600);
  }

  // ------------------------------------------------------------------ navegação das telas
  const VIEWS = ["scene", "suspects", "interrogation", "evidence", "state", "board"];

  function showView(name) {
    view = name;
    confirmClose = false;
    confirmDay7 = false;
    VIEWS.forEach((v) => $("#view-" + v).classList.toggle("active", v === name));
    $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
    renderAll();
  }

  function renderBanner() {
    let txt;
    if (S.day === S.total_days) txt = `⚠ DIA 7 · PRAZO FINAL · MONTE SUA ACUSAÇÃO ANTES DA MEIA-NOITE ⚠`;
    else if (view === "interrogation") txt = `⚠ INTERROGATÓRIO EM ANDAMENTO · DIA ${S.day} DE ${S.total_days} · NEXORA TECH · CASO #0041 · IA GENERATIVA ⚠`;
    else txt = `⚠ DIA ${S.day} DE ${S.total_days} · NEXORA TECH · CASO #0041 ⚠`;
    $("#banner").textContent = txt;
    const found = S.evidences.filter((e) => e.found).length;
    $("#tab-evidence").textContent = `EVIDÊNCIAS ${found}/${S.evidences.length}`;
  }

  function renderAll() {
    if (!S) return;
    renderBanner();
    ({ scene: renderScene, suspects: renderSuspects, interrogation: renderInterrogation, evidence: renderEvidence, state: renderState, board: renderBoard })[view]();
  }

  // ------------------------------------------------------------------ cena do crime
  const HOTSPOTS = {
    log_acesso: { name: "Terminal da sala de servidores", text: "Um terminal ainda logado guarda o histórico de acessos da madrugada." },
    email: { name: "Caixa de e-mail corporativa", text: "A caixa de saída de um setor sensível foi marcada pelo filtro de auditoria." },
    autorizacao: { name: "Gabinete da chefia", text: "A chefia analisa o pedido de mandado formal. Isso pode levar alguns dias." },
  };

  function renderScene() {
    $("#hotspots").innerHTML = Object.keys(HOTSPOTS).map((id) => {
      const ev = S.evidences.find((e) => e.id === id);
      const h = HOTSPOTS[id];
      let action;
      if (ev.found) action = `<span class="tag ok">Coletada</span>`;
      else if (!ev.available) action = `<span class="tag lock">Disponível a partir do Dia 4</span>`;
      else action = `<button class="primary small" data-collect="${id}">Examinar e coletar</button>`;
      return `<div class="card hotspot"><h3>${esc(h.name)}</h3><p>${esc(h.text)}</p>${action}</div>`;
    }).join("");
    $$("[data-collect]").forEach((b) => (b.onclick = () => collect(b.dataset.collect)));
  }

  async function collect(id) {
    try {
      S = await api("/api/collect", { sid: S.sid, evidence_id: id });
      const ev = S.evidences.find((e) => e.id === id);
      sfx.evidence();
      toast("Evidência coletada: " + ev.title);
      renderAll();
    } catch (e) { toast(e.message, true); }
  }

  // ------------------------------------------------------------------ suspeitos
  function meterHtml(label, val, cls) {
    return `<div class="meter"><label>${label} <b>${val}%</b></label><div class="bar"><i class="${cls}" style="width:${val}%"></i></div></div>`;
  }

  function renderSuspects() {
    $("#suspect-cards").innerHTML = Object.entries(S.suspects).map(([k, s]) => {
      const extra = k === "aurora"
        ? `<div class="meter"><span class="pill ${s.cooperating ? "cool" : "hot"}">${s.cooperating ? "COOPERATIVA" : "PROTOCOLO RESTRITO"}</span></div>`
        : meterHtml("PRESSÃO", s.pressure, "red");
      return `<div class="card scard"><img src="${portraitSrc["portrait_" + k]}" alt="">
        <h3>${esc(s.name)}</h3><div class="role">${esc(s.role)}</div>
        ${meterHtml("CONFIANÇA", s.trust, "green")}${extra}
        <button class="primary small" data-talk="${k}" ${S.ending ? "disabled" : ""}>Interrogar</button></div>`;
    }).join("");
    $$("[data-talk]").forEach((b) => (b.onclick = () => { current = b.dataset.talk; selEv.clear(); showView("interrogation"); }));
  }

  // ------------------------------------------------------------------ interrogatório
  function renderInterrogation() {
    const s = S.suspects[current];
    const portrait = $("#portrait");
    portrait.src = portraitSrc["portrait_" + current];
    $("#portrait-tag").textContent = assetsMap["portrait_" + current] ? "retrato gerado por IA (Nano Banana)" : "placeholder (arte procedural)";
    $("#s-name").textContent = s.name;
    $("#s-role").textContent = s.role;
    $("#trust-bar").style.width = s.trust + "%";
    $("#press-bar").style.width = s.pressure + "%";
    $("#trust-val").textContent = s.trust + "%";
    $("#press-val").textContent = current === "aurora" ? "n/a" : s.pressure + "%";
    $("#ap").textContent = `Ações hoje: ${S.actions_left}/${S.actions_per_day}`;
    const left = S.total_days - S.day;
    $("#day-box").textContent = `DIA ${S.day} / ${S.total_days} · restam ${left} ${left === 1 ? "dia" : "dias"}`;
    const endBtn = $("#btn-endday");
    endBtn.textContent = S.day === S.total_days ? "Encerrar prazo ▸" : "Encerrar dia ▸";

    // diálogo
    let html = "";
    if (!s.history.length) html += `<div class="sys">Você está diante de ${esc(s.name)}. Faça a primeira pergunta.</div>`;
    let npcIdx = 0;
    s.history.forEach((m) => {
      if (m.role === "player") html += `<div class="msg you"><div class="who">Você</div>${esc(m.text)}</div>`;
      else {
        const fb = srcLog[current][npcIdx++] === "fallback" ? " fb" : "";
        html += `<div class="msg npc${fb}"><div class="who">${esc(s.name)}</div>${esc(m.text)}</div>`;
      }
    });
    if (busy) html += `<div class="msg npc"><div class="typing">${esc(s.name)} está digitando...</div></div>`;
    const chat = $("#chat");
    chat.innerHTML = html;
    chat.scrollTop = chat.scrollHeight;
    $("#ai-note").textContent = lastNote[current] || "O texto das respostas é gerado em tempo real pelo GPT (motor de interação por IA generativa).";

    // evidências
    $("#evchips").innerHTML = S.evidences.map((e) => e.found
      ? `<button class="chip ${selEv.has(e.id) ? "sel" : ""}" data-ev="${e.id}">${esc(e.short)}</button>`
      : `<span class="chip locked">🔒 ${esc(e.short)}</span>`).join("");
    $$("[data-ev]").forEach((b) => (b.onclick = () => {
      selEv.has(b.dataset.ev) ? selEv.delete(b.dataset.ev) : selEv.add(b.dataset.ev);
      renderInterrogation();
    }));

    const blocked = busy || S.actions_left <= 0 || !!S.ending;
    $("#msg").disabled = blocked;
    $("#btn-send").disabled = blocked;
    $("#msg").placeholder = S.actions_left <= 0 ? "Sem ações hoje. Encerre o dia para continuar." : "Faça sua pergunta ao suspeito...";
    $$("#tones button").forEach((b) => b.classList.toggle("on", b.dataset.tone === tone));
    bus.emit("pressure", current === "aurora" ? 0 : s.pressure, false);
  }

  async function send() {
    const input = $("#msg");
    const message = input.value.trim();
    if (!message || busy) return;
    const before = S.suspects[current].pressure;
    busy = true;
    sfx.send();
    S.suspects[current].history.push({ role: "player", text: message });
    input.value = "";
    renderInterrogation();
    try {
      const r = await api("/api/interrogate", { sid: S.sid, suspect: current, message, tone, evidence_ids: Array.from(selEv) });
      S = r.state;
      srcLog[current].push(r.reply.source);
      lastNote[current] = r.reply.source === "gpt"
        ? `Texto gerado em tempo real pelo GPT (${r.reply.note}), via API do jogo: POST ${r.reply.via}.`
        : `Modo offline: fala pré-escrita (${r.reply.note}). Configure OPENAI_API_KEY e IA_API_KEY para o GPT ao vivo.`;
      sfx.reply();
      selEv.clear();
      const after = S.suspects[current].pressure;
      if (after - before >= 10) { $("#portrait").classList.remove("shake"); void $("#portrait").offsetWidth; $("#portrait").classList.add("shake"); bus.emit("shake"); }
      if (r.just_unlocked) {
        bus.emit("flash");
        sfx.unlock();
        const msgs = {
          beatriz: "Beatriz cedeu: o nome do subordinado protegido foi revelado.",
          rafael: "Rafael confessou! Nova evidência: Confissão de Rafael.",
          aurora: "Aurora liberou os logs! Nova evidência: Logs completos da Aurora.",
        };
        toast(msgs[current]);
      }
    } catch (e) {
      S.suspects[current].history.pop();   // desfaz o otimismo
      input.value = message;
      sfx.error();
      toast(e.message, true);
    } finally {
      busy = false;
      renderAll();
      if (!S.ending) $("#msg").focus();
    }
  }

  async function endDay() {
    if (S.day === S.total_days && !confirmDay7) {
      confirmDay7 = true;
      $("#btn-endday").textContent = "Confirmar: encerra sem acusar";
      $("#btn-endday-2").textContent = "Confirmar: encerra sem acusar";
      toast("No Dia 7, encerrar sem acusar termina o caso sem culpado. Clique de novo para confirmar.", true);
      return;
    }
    try {
      const r = await api("/api/end-day", { sid: S.sid });
      S = r.state;
      if (S.ending) return goEnding();
      toast(r.result.event || `Dia ${S.day} começou. A pressão dos suspeitos diminuiu um pouco.`);
      confirmDay7 = false;
      renderAll();
    } catch (e) { toast(e.message, true); }
  }

  // ------------------------------------------------------------------ evidências / estado
  function renderEvidence() {
    $("#ev-cards").innerHTML = S.evidences.map((e) => e.found
      ? `<div class="card evcard"><h3>${esc(e.title)}</h3><div class="meta">${esc(e.where)} · Implica: ${esc(e.implicates)}</div><p>${esc(e.desc)}</p></div>`
      : `<div class="card evcard locked"><h3>🔒 Evidência bloqueada</h3><div class="meta">${esc(e.where)}</div><p>Ainda não coletada.</p></div>`).join("");
  }

  function renderState() {
    const found = S.evidences.filter((e) => e.found).length;
    const rows = Object.entries(S.suspects).map(([k, s]) => {
      const pill = s.cooperating ? `<span class="pill cool">COOPERANDO</span>` : `<span class="pill hot">RESISTINDO</span>`;
      return `<tr><td>${esc(s.name)}</td><td>${s.trust}%</td><td>${k === "aurora" ? "n/a" : s.pressure + "%"}</td><td>${pill}</td></tr>`;
    }).join("");
    $("#state-body").innerHTML = `
      <p class="lead">Objetivo: descobrir quem vazou os dados e reunir provas que sustentem a acusação antes do fim do Dia 7.</p>
      <div class="facts">
        <div class="card"><b>${S.day}/${S.total_days}</b>dia da investigação</div>
        <div class="card"><b>${S.actions_left}/${S.actions_per_day}</b>ações restantes hoje</div>
        <div class="card"><b>${found}/${S.evidences.length}</b>evidências coletadas</div>
      </div>
      <table><tr><th>SUSPEITO</th><th>CONFIANÇA</th><th>PRESSÃO</th><th>SITUAÇÃO</th></tr>${rows}</table>`;
    $("#btn-endday-2").textContent = S.day === S.total_days ? "Encerrar prazo ▸" : "Encerrar dia ▸";
  }

  // ------------------------------------------------------------------ quadro de investigação
  function renderBoard() {
    $("#board-cards").innerHTML = Object.entries(S.suspects).map(([k, s]) =>
      `<div class="bcard ${boardSuspect === k ? "sel" : ""}" data-b="${k}"><img src="${portraitSrc["portrait_" + k]}" alt="">
       <b>${esc(s.name)}</b><small>${esc(s.role)}</small><small>${k === "aurora" ? (s.cooperating ? "COOPERATIVA" : "RESTRITA") : "PRESSÃO " + s.pressure + "% · CONF. " + s.trust + "%"}</small></div>`).join("");
    $("#board-suspects").innerHTML = Object.entries(S.suspects).map(([k, s]) =>
      `<button data-b="${k}" class="${boardSuspect === k ? "sel" : ""}">${esc(s.name)}</button>`).join("");
    const foundEvs = S.evidences.filter((e) => e.found);
    let html = foundEvs.map((e) => `<button class="chip ${boardEvs.has(e.id) ? "sel" : ""}" data-be="${e.id}">${esc(e.short)}</button>`).join("");
    html += `<span class="slot">+</span>`;
    $("#board-evs").innerHTML = html;
    $$("[data-b]").forEach((el) => (el.onclick = () => { boardSuspect = el.dataset.b; confirmClose = false; renderBoard(); }));
    $$("[data-be]").forEach((el) => (el.onclick = () => { boardEvs.has(el.dataset.be) ? boardEvs.delete(el.dataset.be) : boardEvs.add(el.dataset.be); renderBoard(); }));
    $("#btn-close-case").textContent = confirmClose ? "CONFIRMAR ACUSAÇÃO" : "ENCERRAR CASO";
  }

  async function closeCase() {
    if (!boardSuspect) return toast("Selecione quem você quer acusar.", true);
    if (!confirmClose) { confirmClose = true; renderBoard(); return toast("Clique de novo para confirmar. Não dá para voltar atrás.", true); }
    try {
      S = await api("/api/accuse", { sid: S.sid, suspect: boardSuspect, evidence_ids: Array.from(boardEvs) });
      goEnding();
    } catch (e) { toast(e.message, true); }
  }

  function goEnding() {
    try { localStorage.removeItem("sinapse_sid"); } catch (_) {}
    sfx.end();
    window.__game.scene.getScene("Game").scene.start("End", S.ending_info);  // para a cena Game e abre o final
  }

  // ------------------------------------------------------------------ ligações de interface
  function wireUI() {
    $$("#tabs button").forEach((b) => (b.onclick = () => showView(b.dataset.view)));
    $("#btn-back").onclick = () => showView("suspects");
    $("#btn-send").onclick = send;
    $("#msg").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
    $$("#tones button").forEach((b) => (b.onclick = () => { tone = b.dataset.tone; renderInterrogation(); }));
    $("#btn-endday").onclick = endDay;
    $("#btn-endday-2").onclick = endDay;
    const toBoard = () => { boardSuspect = null; boardEvs.clear(); showView("board"); };
    $("#btn-to-board").onclick = toBoard;
    $("#btn-to-board-2").onclick = toBoard;
    $("#btn-board-back").onclick = () => showView("interrogation");
    $("#btn-close-case").onclick = closeCase;
  }

  // ------------------------------------------------------------------ cenas Phaser
  function rain(scene, g, drops, color, alpha) {
    g.clear();
    g.lineStyle(1, color, alpha);
    drops.forEach((d) => {
      d.y += d.v; d.x -= d.v * 0.12;
      if (d.y > H) { d.y = -20; d.x = Math.random() * (W + 100); }
      g.lineBetween(d.x, d.y, d.x - 2, d.y + d.l);
    });
  }
  const makeDrops = (n) => Array.from({ length: n }, () => ({ x: Math.random() * W, y: Math.random() * H, v: 8 + Math.random() * 8, l: 8 + Math.random() * 12 }));

  class BootScene extends Phaser.Scene {
    constructor() { super("Boot"); }
    preload() {
      this.add.text(W / 2, H / 2, "Carregando...", { fontFamily: "sans-serif", fontSize: 24, color: "#7f95b5" }).setOrigin(0.5);
      Object.entries(assetsMap).forEach(([k, url]) => this.load.image(k, url));
    }
    create() {
      window.SinapseArt.ensure(this);
      ["beatriz", "rafael", "aurora"].forEach((k) => {
        const key = "portrait_" + k;
        portraitSrc[key] = assetsMap[key] || this.textures.getBase64(key);
      });
      this.scene.start("Menu");
    }
  }

  class MenuScene extends Phaser.Scene {
    constructor() { super("Menu"); }
    async create() {
      this.add.image(0, 0, "bg_menu").setOrigin(0).setDisplaySize(W, H);
      this.add.rectangle(0, 0, W, H, 0x050912, 0.35).setOrigin(0);
      this.rg = this.add.graphics();
      this.drops = makeDrops(110);

      this.add.text(W / 2, 78, "S I N A P S E", { fontFamily: "Segoe UI, sans-serif", fontStyle: "bold", fontSize: 78, color: "#ffffff" }).setOrigin(0.5);
      const line = this.add.rectangle(W / 2, 128, 240, 4, 0xe8394a);
      this.tweens.add({ targets: line, alpha: 0.35, duration: 900, yoyo: true, repeat: -1 });
      this.add.text(W / 2, 168, "P R O T O C O L O   S I L E N C I O S O", { fontFamily: "sans-serif", fontSize: 22, color: "#9fb4d6" }).setOrigin(0.5);
      this.add.text(W / 2, 205, "Investigue · interrogue · deduza", { fontFamily: "sans-serif", fontStyle: "italic", fontSize: 17, color: "#6f87ab" }).setOrigin(0.5);

      const panel = this.add.graphics();
      panel.fillStyle(0x0e1a30, 0.88).fillRoundedRect(440, 400, 400, 280, 16);
      panel.lineStyle(1, 0x22324f, 1).strokeRoundedRect(440, 400, 400, 280, 16);

      let hasSave = false;
      try {
        const sid = localStorage.getItem("sinapse_sid");
        if (sid) { await api("/api/state/" + sid); hasSave = true; }
      } catch (_) {}

      this.button(420, "NOVO CASO", true, true, () => this.newGame());
      this.button(480, "CONTINUAR INVESTIGAÇÃO", false, hasSave, () => this.continueGame());
      this.button(540, "CONFIGURAÇÕES", false, true, () => this.settings());
      this.button(600, "SAIR", false, true, () => this.quit());

      const ia = health.llm ? `IA de texto: GPT ao vivo (${health.model})` : "IA de texto: modo offline (sem OPENAI_API_KEY), falas pré-escritas";
      this.add.text(20, H - 26, ia, { fontFamily: "sans-serif", fontSize: 14, color: health.llm ? "#4fd1a5" : "#e8b800" });
      this.add.text(W - 20, H - 26, "v1.0 MVP · CP5", { fontFamily: "sans-serif", fontSize: 14, color: "#46618a" }).setOrigin(1, 0);
      this.cameras.main.fadeIn(500);
    }
    button(y, label, primary, enabled, cb) {
      const x = 480, w = 320, h = 48;
      const r = this.add.rectangle(x, y + 40, w, h, primary ? 0xe8394a : 0x131d33).setOrigin(0).setStrokeStyle(1, primary ? 0xff6b6b : 0x22324f);
      const t = this.add.text(x + w / 2, y + 40 + h / 2, label, { fontFamily: "sans-serif", fontStyle: "bold", fontSize: 18, color: primary ? "#ffffff" : "#8fb0dd" }).setOrigin(0.5);
      if (!enabled) { r.setAlpha(0.4); t.setAlpha(0.4); return; }
      r.setInteractive({ useHandCursor: true });
      r.on("pointerover", () => r.setFillStyle(primary ? 0xff6b6b : 0x1c2c4d));
      r.on("pointerout", () => r.setFillStyle(primary ? 0xe8394a : 0x131d33));
      r.on("pointerdown", cb);
    }
    async newGame() {
      try {
        S = await api("/api/new", {});
        Object.keys(srcLog).forEach((k) => { srcLog[k] = []; lastNote[k] = ""; });
        selEv.clear(); current = "beatriz"; view = "scene";
        try { localStorage.setItem("sinapse_sid", S.sid); } catch (_) {}
        this.cameras.main.fadeOut(300, 5, 9, 18);
        this.cameras.main.once("camerafadeoutcomplete", () => this.scene.start("Game"));
      } catch (e) { toast(e.message, true); }
    }
    async continueGame() {
      try {
        S = await api("/api/state/" + localStorage.getItem("sinapse_sid"));
        view = "interrogation";
        this.scene.start("Game");
      } catch (e) { toast(e.message, true); }
    }
    settings() {
      const loaded = Object.keys(assetsMap);
      const lines = [
        "CONFIGURAÇÕES",
        "",
        `Modelo de texto: ${health.llm ? "GPT (" + health.model + ") ativo" : "offline (defina OPENAI_API_KEY no .env)"}`,
        `Imagens de IA carregadas: ${loaded.length ? loaded.join(", ") : "nenhuma (arte procedural no lugar)"}`,
        "",
        "Clique para fechar",
      ];
      const box = this.add.container(0, 0);
      const bg = this.add.rectangle(0, 0, W, H, 0x050912, 0.82).setOrigin(0).setInteractive();
      const t = this.add.text(W / 2, H / 2, lines.join("\n"), { fontFamily: "sans-serif", fontSize: 22, color: "#dbe6f5", align: "center", lineSpacing: 8, wordWrap: { width: 900 } }).setOrigin(0.5);
      box.add([bg, t]);
      bg.on("pointerdown", () => box.destroy());
    }
    quit() {
      this.cameras.main.fadeOut(500, 0, 0, 0);
      this.cameras.main.once("camerafadeoutcomplete", () => {
        this.add.text(W / 2, H / 2, "Obrigado por jogar. Você já pode fechar esta aba.", { fontFamily: "sans-serif", fontSize: 24, color: "#8fb0dd" }).setOrigin(0.5);
        this.cameras.main.fadeIn(300);
      });
    }
    update() { rain(this, this.rg, this.drops, 0x6aa7ff, 0.18); }
  }

  class GameScene extends Phaser.Scene {
    constructor() { super("Game"); }
    create() {
      this.add.image(0, 0, "bg_room").setOrigin(0).setDisplaySize(W, H);
      this.add.rectangle(0, 0, W, H, 0x050912, 0.55).setOrigin(0);
      this.rg = this.add.graphics();
      this.drops = makeDrops(60);
      // vinheta vermelha: quanto maior a pressão, mais forte
      const tex = this.textures.createCanvas("vig", W, H);
      const ctx = tex.getContext();
      const gr = ctx.createRadialGradient(W / 2, H / 2, 220, W / 2, H / 2, 760);
      gr.addColorStop(0, "rgba(232,57,74,0)");
      gr.addColorStop(1, "rgba(232,57,74,0.9)");
      ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H); tex.refresh();
      this.vig = this.add.image(0, 0, "vig").setOrigin(0).setAlpha(0);
      this.flash = this.add.rectangle(0, 0, W, H, 0x5cc8f0, 0).setOrigin(0);

      this.onPressure = (v) => this.tweens.add({ targets: this.vig, alpha: Math.min(0.85, (v / 100) * 0.9), duration: 500 });
      this.onShake = () => this.cameras.main.shake(220, 0.006);
      this.onFlash = () => { this.flash.setAlpha(0.35); this.tweens.add({ targets: this.flash, alpha: 0, duration: 700 }); };
      bus.on("pressure", this.onPressure);
      bus.on("shake", this.onShake);
      bus.on("flash", this.onFlash);
      this.events.once("shutdown", () => {
        bus.off("pressure", this.onPressure); bus.off("shake", this.onShake); bus.off("flash", this.onFlash);
        $("#ui").classList.add("hidden");
      });

      $("#ui").classList.remove("hidden");
      showView(view);
      this.cameras.main.fadeIn(400);
    }
    update() { rain(this, this.rg, this.drops, 0x6aa7ff, 0.1); }
  }

  class EndScene extends Phaser.Scene {
    constructor() { super("End"); }
    create(info) {
      this.add.image(0, 0, "bg_menu").setOrigin(0).setDisplaySize(W, H);
      this.add.rectangle(0, 0, W, H, 0x050912, 0.72).setOrigin(0);
      const good = !!info.good;
      this.add.text(W / 2, 170, good ? "FINAL" : "FIM DE JOGO", { fontFamily: "sans-serif", fontSize: 18, color: "#7f95b5" }).setOrigin(0.5);
      const title = this.add.text(W / 2, 240, info.title, { fontFamily: "Segoe UI, sans-serif", fontStyle: "bold", fontSize: 56, color: good ? "#4fd1a5" : "#e8394a" }).setOrigin(0.5).setAlpha(0);
      const text = this.add.text(W / 2, 400, info.text, { fontFamily: "sans-serif", fontSize: 24, color: "#dbe6f5", align: "center", wordWrap: { width: 860 }, lineSpacing: 8 }).setOrigin(0.5).setAlpha(0);
      this.tweens.add({ targets: title, alpha: 1, y: 250, duration: 900 });
      this.tweens.add({ targets: text, alpha: 1, duration: 1200, delay: 600 });
      const r = this.add.rectangle(W / 2 - 160, 580, 320, 52, 0xe8394a).setOrigin(0).setInteractive({ useHandCursor: true });
      this.add.text(W / 2, 606, "VOLTAR AO MENU", { fontFamily: "sans-serif", fontStyle: "bold", fontSize: 19, color: "#fff" }).setOrigin(0.5);
      r.on("pointerdown", () => this.scene.start("Menu"));
      this.cameras.main.fadeIn(500);
    }
  }

  // ------------------------------------------------------------------ inicialização
  async function start() {
    try { health = await api("/api/health"); } catch (_) {}
    try { assetsMap = await api("/api/assets"); } catch (_) {}
    window.__game = new Phaser.Game({
      type: Phaser.AUTO, width: W, height: H, parent: "game", backgroundColor: "#0b1220",
      scale: { mode: Phaser.Scale.NONE },
      scene: [BootScene, MenuScene, GameScene, EndScene],
    });
    bus = new Phaser.Events.EventEmitter();
    wireUI();
  }
  window.addEventListener("load", start);
})();
