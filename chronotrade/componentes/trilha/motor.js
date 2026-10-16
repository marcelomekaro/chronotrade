/* Motor da trilha sonora do Chrono Trade: música gerada na hora com a Web Audio API.
   Quatro climas (incentivo, tensão, euforia, felicidade), sem arquivos de áudio e sem direitos de terceiros.
   Funciona ao vivo (AudioContext) e em lote (OfflineAudioContext), para gravar a trilha do vídeo. */
(function (raiz) {
  const midi = n => 440 * Math.pow(2, (n - 69) / 12);

  const HUMORES = {
    incentivo: { nome: 'Incentivo', emoji: '💪', bpm: 100, tom: 60,
      prog: [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]], escala: [0, 2, 4, 7, 9, 12, 14, 16] },
    tensao: { nome: 'Tensão', emoji: '⚡', bpm: 76, tom: 50,
      prog: [[0, 3, 7], [8, 12, 15], [0, 3, 7], [1, 5, 8]], escala: [0, 1, 3, 5, 7, 8, 12] },
    euforia: { nome: 'Euforia', emoji: '🚀', bpm: 126, tom: 57,
      prog: [[9, 12, 16], [5, 9, 12], [0, 4, 7], [7, 11, 14]], escala: [0, 2, 4, 7, 9, 12, 14, 16, 19] },
    felicidade: { nome: 'Felicidade', emoji: '😊', bpm: 112, tom: 55,
      prog: [[0, 4, 7], [5, 9, 12], [0, 4, 7], [7, 11, 14]], escala: [0, 2, 4, 7, 9, 12, 14, 16] },
  };

  function rng(semente) { let s = semente >>> 0 || 1; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; }

  function criarMotor(ctx, saida) {
    const ruido = (() => { const b = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate), d = b.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; return b; })();

    function env(g, t, vol, ataque, dur, solta) {
      g.gain.setValueAtTime(0.0001, t);
      g.gain.linearRampToValueAtTime(vol, t + ataque);
      g.gain.setValueAtTime(vol, t + Math.max(ataque, dur - solta));
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    }
    function tom(dest, t, f, dur, o = {}) {
      const osc = ctx.createOscillator(), g = ctx.createGain();
      osc.type = o.tipo || 'triangle'; osc.frequency.setValueAtTime(f, t); if (o.detune) osc.detune.value = o.detune;
      let no = osc;
      if (o.corte) { const fl = ctx.createBiquadFilter(); fl.type = 'lowpass'; fl.frequency.value = o.corte; fl.Q.value = o.q || 0.7;
        osc.connect(fl); no = fl; }
      if (o.vibrato) { const l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = 5.2; lg.gain.value = f * 0.006;
        l.connect(lg); lg.connect(osc.frequency); l.start(t); l.stop(t + dur + 0.05); }
      no.connect(g); g.connect(dest);
      env(g, t, o.vol || 0.2, o.ataque || 0.005, dur, o.solta || dur * 0.7);
      osc.start(t); osc.stop(t + dur + 0.05);
    }
    function bumbo(dest, t, vol = 0.9) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'sine'; o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.13);
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.38);
      o.connect(g); g.connect(dest); o.start(t); o.stop(t + 0.4);
    }
    function chiado(dest, t, dur, tipo, freq, vol, q = 0.8) {
      const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      s.buffer = ruido; f.type = tipo; f.frequency.value = freq; f.Q.value = q;
      s.connect(f); f.connect(g); g.connect(dest);
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      s.start(t, Math.random() * 0.5); s.stop(t + dur + 0.02);
    }
    const prato = (d, t, aberto, vol = 0.06) => chiado(d, t, aberto ? 0.22 : 0.05, 'highpass', 7500, vol);
    const palma = (d, t, vol = 0.22) => { [0, 0.012, 0.024].forEach(x => chiado(d, t + x, 0.12, 'bandpass', 1400, vol, 1.2)); };
    const chocalho = (d, t, vol = 0.035) => chiado(d, t, 0.06, 'highpass', 5200, vol);
    function colchao(dest, t, notas, dur, vol, corte = 1100) {
      notas.forEach(n => [-7, 7].forEach(dt => tom(dest, t, midi(n), dur, { tipo: 'sawtooth', vol: vol / notas.length,
        ataque: Math.min(0.6, dur * 0.3), solta: dur * 0.45, corte, detune: dt })));
    }

    // Um passo de semicolcheia (16 por compasso). bus = {principal, colchao}
    function passo(humor, i, t, bus, sorte) {
      const h = HUMORES[humor], b = 60 / h.bpm, s = b / 4;
      const compasso = Math.floor(i / 16), p = i % 16, acorde = h.prog[compasso % h.prog.length].map(x => x + h.tom);
      const raizNota = acorde[0] - 12, M = bus.principal;
      if (humor === 'incentivo') {
        if (p === 0 || p === 8 || p === 10) bumbo(M, t, 0.8);
        if (p === 4 || p === 12) palma(M, t, 0.18);
        if (p % 2 === 0) prato(M, t, p % 4 === 2, 0.045);
        if (p % 4 === 0) tom(M, t, midi(raizNota - 12), b * 0.9, { tipo: 'square', vol: 0.11, corte: 380 });
        if (p % 2 === 0) { const arp = [0, 1, 2, 1, 0, 2, 1, 2]; tom(M, t, midi(acorde[arp[(p / 2) % 8]] + 12), s * 1.8, { vol: 0.07 }); }
        if (p === 0) colchao(bus.colchao, t, acorde, b * 4, 0.18);
        if ((p === 6 || p === 14) && sorte() < 0.55) tom(M, t, midi(h.tom + 12 + h.escala[Math.floor(sorte() * h.escala.length)]),
          s * 3, { tipo: 'sine', vol: 0.06, vibrato: true });
      } else if (humor === 'tensao') {
        if (p === 0 || p === 3) bumbo(M, t, p === 0 ? 0.9 : 0.55);
        if (p % 2 === 0) tom(M, t, midi(raizNota + (p % 4 === 2 ? 1 : 0)), s * 1.6, { tipo: 'sawtooth', vol: 0.05, corte: 900 });
        if (p === 0) { colchao(bus.colchao, t, [acorde[0] - 12, acorde[1] - 12, acorde[2]], b * 4, 0.16, 600);
          tom(M, t, midi(raizNota - 12), b * 4, { tipo: 'sine', vol: 0.12, ataque: 0.3, solta: 1.2 }); }
        if (p === 8 && compasso % 2 === 1) chiado(M, t, b * 2, 'bandpass', 600 + sorte() * 800, 0.05, 3);
        if (p === 12 && sorte() < 0.4) tom(M, t, midi(h.tom + 13), b, { tipo: 'sine', vol: 0.04, vibrato: true });
      } else if (humor === 'euforia') {
        if (p % 4 === 0) { bumbo(M, t, 1.0); bus.colchao.gain.cancelScheduledValues(t);
          bus.colchao.gain.setValueAtTime(0.25, t); bus.colchao.gain.linearRampToValueAtTime(1, t + b * 0.6); }
        if (p % 4 === 2) prato(M, t, true, 0.06);
        if (p === 4 || p === 12) palma(M, t, 0.2);
        if (p % 2 === 1) prato(M, t, false, 0.025);
        tom(M, t, midi(acorde[p % 3] + 12 + (p >= 8 ? 12 : 0)), s * 0.9, { tipo: 'square', vol: 0.035, corte: 2600 });
        if (p % 2 === 0) tom(M, t, midi(raizNota - 12 + (p % 4 === 2 ? 12 : 0)), s * 1.8, { tipo: 'sawtooth', vol: 0.09, corte: 500 });
        if (p === 0) colchao(bus.colchao, t, acorde.map(n => n + 12), b * 4, 0.2, 2200);
        if ((p === 0 || p === 6 || p === 10) && compasso % 4 === 3) tom(M, t, midi(acorde[2] + 24), s * 3, { tipo: 'sawtooth', vol: 0.05, corte: 3000 });
      } else if (humor === 'felicidade') {
        if (p === 0 || p === 7 || p === 10) bumbo(M, t, 0.6);
        if (p === 4 || p === 12) palma(M, t, 0.13);
        chocalho(M, t, p % 2 ? 0.02 : 0.035);
        if ([0, 6, 8, 12, 14].includes(p)) acorde.forEach((n, k) => tom(M, t + k * 0.014, midi(n + 12), s * 2.5, { vol: 0.05, solta: s * 2 }));
        if (p % 4 === 0) tom(M, t, midi(raizNota - 12 + (p === 8 ? 7 : 0)), b * 0.8, { tipo: 'sine', vol: 0.16 });
        if (p % 4 === 2 && sorte() < 0.7) tom(M, t, midi(h.tom + 24 + h.escala[Math.floor(sorte() * h.escala.length)]),
          s * 2, { tipo: 'sine', vol: 0.045, vibrato: true });
        if (p === 0 && compasso % 2 === 0) colchao(bus.colchao, t, acorde, b * 8, 0.1, 1400);
      }
    }

    function criarBus(destino) {
      const principal = ctx.createGain(), colchao = ctx.createGain();
      principal.connect(destino); colchao.connect(destino); colchao.gain.value = 1;
      return { principal, colchao };
    }
    return { passo, criarBus, saida };
  }

  function criarSaida(ctx) {
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -16; comp.ratio.value = 3; comp.attack.value = 0.01;
    const mestre = ctx.createGain(); mestre.gain.value = 0.8;
    mestre.connect(comp); comp.connect(ctx.destination);
    return mestre;
  }

  /* Toca ao vivo. Devolve {mudar(humor), parar(), volume(v)} */
  function tocador(ctx) {
    const saida = criarSaida(ctx), motor = criarMotor(ctx, saida);
    let humor = null, bus = null, passoAtual = 0, proximo = 0, timer = null, sorte = rng(Date.now() & 0xffff);
    function agenda() {
      if (!humor) return;
      const s = 60 / HUMORES[humor].bpm / 4;
      while (proximo < ctx.currentTime + 0.18) { motor.passo(humor, passoAtual, proximo, bus, sorte); passoAtual++; proximo += s; }
    }
    function mudar(novo) {
      if (novo === humor) return;
      const agora = ctx.currentTime;
      if (bus) { const velho = bus; const g = ctx.createGain(); // fade out do antigo
        [velho.principal, velho.colchao].forEach(n => { n.gain.cancelScheduledValues(agora); n.gain.setValueAtTime(n.gain.value, agora);
          n.gain.linearRampToValueAtTime(0.0001, agora + 1.2); });
        setTimeout(() => { try { velho.principal.disconnect(); velho.colchao.disconnect(); } catch (e) {} g.disconnect(); }, 1600); }
      const entrada = ctx.createGain(); entrada.gain.setValueAtTime(0.0001, agora); entrada.gain.linearRampToValueAtTime(1, agora + 1.2);
      entrada.connect(saida);
      bus = motor.criarBus(entrada); humor = novo; passoAtual = 0; proximo = agora + 0.05;
      if (!timer) timer = setInterval(agenda, 25);
    }
    function parar() {
      clearInterval(timer); timer = null; const agora = ctx.currentTime;
      saida.gain.cancelScheduledValues(agora); saida.gain.setValueAtTime(saida.gain.value, agora);
      saida.gain.linearRampToValueAtTime(0.0001, agora + 0.6);
      humor = null;
    }
    function volume(v) { saida.gain.setTargetAtTime(Math.max(0.0001, v), ctx.currentTime, 0.1); }
    return { mudar, parar, volume, get humor() { return humor; }, saida };
  }

  /* Grava em lote: devolve um AudioBuffer com a sequência de climas [[humor, segundos], ...] */
  async function gravar(sequencia, taxa = 44100) {
    const total = sequencia.reduce((n, [, s]) => n + s, 0);
    const ctx = new OfflineAudioContext(2, Math.ceil(total * taxa), taxa);
    const saida = criarSaida(ctx), motor = criarMotor(ctx, saida);
    let t0 = 0; const sorte = rng(7);
    for (const [humor, seg] of sequencia) {
      const entrada = ctx.createGain(); entrada.connect(saida);
      entrada.gain.setValueAtTime(0.0001, t0); entrada.gain.linearRampToValueAtTime(1, t0 + 1.0);
      entrada.gain.setValueAtTime(1, t0 + seg - 1.0); entrada.gain.linearRampToValueAtTime(0.0001, t0 + seg + 0.4);
      const bus = motor.criarBus(entrada), s = 60 / HUMORES[humor].bpm / 4;
      for (let i = 0, t = t0; t < t0 + seg; i++, t += s) motor.passo(humor, i, t, bus, sorte);
      t0 += seg;
    }
    return ctx.startRendering();
  }

  raiz.ChronoTrilha = { HUMORES, tocador, gravar };
})(typeof window !== 'undefined' ? window : this);
