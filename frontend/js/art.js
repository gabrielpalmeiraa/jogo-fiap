/* Arte procedural de reserva (placeholders).
 * Se existir uma imagem gerada por IA em frontend/assets (bg_menu, bg_room, portrait_beatriz,
 * portrait_rafael, portrait_aurora), o jogo usa a imagem. Se não, desenha estas versões. */
(function () {
  // gerador pseudoaleatório com semente, para a arte sair sempre igual
  function rng(seed) {
    let s = seed >>> 0;
    return function () {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  // degradê vertical feito com faixas (evita bugs de degradê com alpha em alguns drivers de vídeo)
  function vgrad(g, x, y, w, h, c1, c2, a1, a2) {
    const step = 6;
    const r1 = (c1 >> 16) & 255, g1 = (c1 >> 8) & 255, b1 = c1 & 255;
    const r2 = (c2 >> 16) & 255, g2 = (c2 >> 8) & 255, b2 = c2 & 255;
    for (let i = 0; i < h; i += step) {
      const t = i / h;
      const col = (Math.round(r1 + (r2 - r1) * t) << 16) | (Math.round(g1 + (g2 - g1) * t) << 8) | Math.round(b1 + (b2 - b1) * t);
      g.fillStyle(col, a1 + (a2 - a1) * t);
      g.fillRect(x, y + i, w, Math.min(step, h - i));
    }
  }

  function skyline(scene, key, W, H, withFog) {
    const g = scene.make.graphics({ x: 0, y: 0, add: false });
    vgrad(g, 0, 0, W, H, 0x070b18, 0x1a1030, 1, 1);
    const r = rng(41);
    const layers = [
      { n: 18, hmin: 0.25, hmax: 0.55, col: 0x0d1530, win: 0x244a7a },
      { n: 14, hmin: 0.35, hmax: 0.75, col: 0x0a1026, win: 0xff3ea5 },
    ];
    layers.forEach((L, li) => {
      let x = -20;
      for (let i = 0; i < L.n; i++) {
        const w = 40 + r() * 70;
        const h = H * (L.hmin + r() * (L.hmax - L.hmin));
        g.fillStyle(L.col, 1);
        g.fillRect(x, H - h, w, h);
        for (let wy = H - h + 10; wy < H - 10; wy += 14) {
          for (let wx = x + 6; wx < x + w - 6; wx += 12) {
            if (r() > 0.72) {
              g.fillStyle(r() > 0.5 ? L.win : 0x35c4ff, 0.35 + r() * 0.5);
              g.fillRect(wx, wy, 5, 7);
            }
          }
        }
        if (li === 1 && r() > 0.5) {
          g.fillStyle(r() > 0.5 ? 0xff3ea5 : 0x35c4ff, 0.9);
          g.fillRect(x + w * 0.3, H - h - 6, w * 0.4, 3);
        }
        x += w * (0.7 + r() * 0.3);
      }
    });
    if (withFog) {
      vgrad(g, 0, H * 0.45, W, H * 0.55, 0x1a1030, 0x0b1220, 0, 0.85);
    }
    g.generateTexture(key, W, H);
    g.destroy();
  }

  function room(scene, key, W, H) {
    const g = scene.make.graphics({ x: 0, y: 0, add: false });
    vgrad(g, 0, 0, W, H, 0x0a1224, 0x060a14, 1, 1);
    // parede com espelho unidirecional
    g.fillStyle(0x0f1a33, 1);
    g.fillRect(W * 0.12, H * 0.14, W * 0.6, H * 0.42);
    g.lineStyle(3, 0x35c4ff, 0.7);
    g.strokeRect(W * 0.12, H * 0.14, W * 0.6, H * 0.42);
    g.fillStyle(0x1b3a63, 0.35);
    g.fillTriangle(W * 0.12, H * 0.56, W * 0.12, H * 0.14, W * 0.42, H * 0.14);
    // luz fria no teto
    g.fillStyle(0xcfe8ff, 0.12);
    g.fillRect(W * 0.2, 0, W * 0.4, 8);
    // mesa e cadeiras
    g.fillStyle(0x16233f, 1);
    g.fillRect(W * 0.2, H * 0.68, W * 0.44, 16);
    g.fillRect(W * 0.23, H * 0.68, 10, H * 0.28);
    g.fillRect(W * 0.6, H * 0.68, 10, H * 0.28);
    g.fillStyle(0x0e182d, 1);
    g.fillRect(W * 0.1, H * 0.7, 46, 90);
    g.fillRect(W * 0.76, H * 0.7, 46, 90);
    // neon baixo
    g.fillStyle(0xff3ea5, 0.5);
    g.fillRect(0, H - 6, W, 3);
    g.fillStyle(0x35c4ff, 0.5);
    g.fillRect(0, H - 12, W, 2);
    g.generateTexture(key, W, H);
    g.destroy();
  }

  function portrait(scene, key, accent, ai) {
    const S = 240;
    const g = scene.make.graphics({ x: 0, y: 0, add: false });
    vgrad(g, 0, 0, S, S, 0x14213d, 0x0a1224, 1, 1);
    g.fillStyle(accent, 0.18);
    g.fillCircle(S / 2, S * 0.42, 100);
    if (ai) {
      // rosto holográfico: malha de linhas
      g.lineStyle(2, accent, 0.9);
      g.strokeCircle(S / 2, S * 0.42, 62);
      g.strokeCircle(S / 2, S * 0.42, 40);
      for (let i = -3; i <= 3; i++) {
        g.lineStyle(1, accent, 0.45);
        g.lineBetween(S / 2 + i * 18, S * 0.42 - 62, S / 2 + i * 18, S * 0.42 + 62);
        g.lineBetween(S / 2 - 62, S * 0.42 + i * 18, S / 2 + 62, S * 0.42 + i * 18);
      }
      g.fillStyle(accent, 1);
      g.fillCircle(S / 2 - 20, S * 0.4, 5);
      g.fillCircle(S / 2 + 20, S * 0.4, 5);
      g.fillStyle(accent, 0.25);
      g.fillRect(40, S * 0.72, S - 80, 60);
    } else {
      g.fillStyle(0x1e2f52, 1);
      g.fillCircle(S / 2, S * 0.38, 46); // cabeça
      g.fillStyle(0x16233f, 1);
      g.fillRoundedRect(S * 0.18, S * 0.62, S * 0.64, S * 0.5, 30); // ombros
      g.fillStyle(accent, 0.9);
      g.fillTriangle(S / 2, S * 0.62, S / 2 - 16, S * 0.8, S / 2 + 16, S * 0.8); // gola/gravata
    }
    g.generateTexture(key, S, S);
    g.destroy();
  }

  window.SinapseArt = {
    ensure(scene, loaded) {
      const need = (k) => !scene.textures.exists(k);
      if (need("bg_menu")) skyline(scene, "bg_menu", 1280, 720, true);
      if (need("bg_room")) room(scene, "bg_room", 1280, 720);
      if (need("portrait_beatriz")) portrait(scene, "portrait_beatriz", 0xe8394a, false);
      if (need("portrait_rafael")) portrait(scene, "portrait_rafael", 0x4fd1a5, false);
      if (need("portrait_aurora")) portrait(scene, "portrait_aurora", 0x5cc8f0, true);
    },
  };
})();
