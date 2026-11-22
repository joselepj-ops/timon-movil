// TIMON movil 3.0 - motor de reglas (copia exacta de timon_movil.py 2.1, que a su vez copia TIMON.bat)
// Agresiva = R2 o MOVE + entradas; stop 25 % del capital desde su maximo; comodin K5.
var TM = (function () {
  var STOP = 0.25, COSTE = 0.001, INICIO = '2003-11-01';
  var MOVE_VENT = 1260, MOVE_MIN = 253, MOVE_PCT = 90, MOVE_VIER = 2;

  function dn(s) { return Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 86400000; }
  function ds(n) { return new Date(n * 86400000).toISOString().slice(0, 10); }
  function wd(n) { return (new Date(n * 86400000).getUTCDay() + 6) % 7; }   // lunes = 0
  function semana(n) { return n - wd(n); }

  function percentil(a, p) {
    var b = a.slice().sort(function (x, y) { return x - y; });
    var pos = (b.length - 1) * p / 100, lo = Math.floor(pos), hi = Math.ceil(pos);
    return b[lo] + (b[hi] - b[lo]) * (pos - lo);
  }

  function calcularMove(D, MV) {
    var n = D.length, mv = [], posmv = new Array(n), i;
    for (i = 0; i < n; i++) { if (MV[i] != null) mv.push(MV[i]); posmv[i] = mv.length - 1; }
    var calma = 1, ca = 0, cb = 0, cambios = [], semanas = [];
    for (i = 0; i < n; i++) {
      var fin = i < n - 1 ? semana(D[i + 1]) != semana(D[i]) : wd(D[i]) == 4;
      if (!fin) continue;
      var k = posmv[i]; if (k < 0) continue;
      var ini = Math.max(0, k - MOVE_VENT + 1);
      if (k - ini + 1 < MOVE_MIN) continue;
      var th = percentil(mv.slice(ini, k + 1), MOVE_PCT), v = mv[k];
      if (v > th) { ca++; cb = 0; } else { cb++; ca = 0; }
      var nuevo = calma;
      if (calma == 1 && ca >= MOVE_VIER) nuevo = 0;
      if (calma == 0 && cb >= MOVE_VIER) nuevo = 1;
      var cambio = nuevo != calma;
      if (cambio) { calma = nuevo; cambios.push([i + 1, nuevo]); }
      semanas.push({ i: i, estado: calma, cambio: cambio, move: v, umbral: th });
    }
    var st = new Array(n), cur = 1, q = 0;
    for (i = 0; i < n; i++) { while (q < cambios.length && cambios[q][0] <= i) { cur = cambios[q][1]; q++; } st[i] = cur; }
    return { st: st, semanas: semanas };
  }

  function b3p(x) { return x >= 5 ? 0 : (x >= 0 ? 1 : (x >= -5 ? 2 : 3)); }

  function pasoMaster(p, ppB, sp, b3) {
    var nF = (p.B != null && ppB != null && p.B > ppB && p.B >= sp) ? p.B : p.F;
    var nG = (p.B != null && ppB != null && p.B < ppB && p.B <= sp) ? p.B : p.G;
    var nH = p.F != null && sp > p.F, nI = p.G != null && sp < p.G;
    var nJ = p.H ? (sp > p.F ? 'A' : 'R') : '';
    var nK = p.I ? (sp < p.G ? 'A' : 'R') : '';
    var nL = nJ == 'A' ? 0 : ((nK == 'A' && p.G !== p.R) ? p.L + 1 : p.L);
    var nM = nK == 'A' ? 0 : ((nJ == 'A' && p.F !== p.X) ? p.M + 1 : p.M);
    var nN;
    if (nL >= 2) nN = 'BAJISTA'; else if (nM >= 2) nN = 'ALCISTA'; else if (nL == 1 || nM == 1) nN = 'LATERAL'; else nN = p.N;
    var nP = (b3 >= 2 || nK == 'A') ? 'ALTO' : 'NO ALTO';
    var nR = nJ == 'A' ? null : ((nK == 'A' && p.G !== p.R) ? p.G : p.R);
    var nX = nK == 'A' ? null : ((nJ == 'A' && p.F !== p.X) ? p.F : p.X);
    return { B: sp, F: nF, G: nG, H: nH, I: nI, L: nL, M: nM, N: nN, R: nR, X: nX, fuera: (nN == 'BAJISTA' && nP == 'ALTO') };
  }

  function finMes(y, m) { return dn((m == 12 ? y + 1 : y) + '-' + ('0' + (m % 12 + 1)).slice(-2) + '-01') - 1; }
  function ultimoLaborable(n) { while (wd(n) >= 5) n--; return n; }
  function media30(D, G, fm) {
    var ini = fm - 29, s = 0, c = 0;
    for (var i = 0; i < D.length; i++) if (D[i] >= ini && D[i] <= fm) { s += G[i]; c++; }
    return c ? s / c : null;
  }

  function calcularR2(D, G, mensual, hoy) {
    var meses = mensual.map(function (x) { return [x[0], x[1]]; }), ultD = D[D.length - 1], nuevos = 0;
    while (true) {
      var y = meses[meses.length - 1][0][0], m = meses[meses.length - 1][0][1];
      if (m == 12) { y++; m = 1; } else m++;
      var fm = finMes(y, m), ulab = ultimoLaborable(fm);
      var cerrado = (ultD > fm) || (ultD >= ulab) || (hoy > fm + 1 && ultD >= ulab - 3);
      if (!cerrado || ultD < dn(y + '-' + ('0' + m).slice(-2) + '-01')) break;
      var r = media30(D, G, fm); if (r == null) break;
      meses.push([[y, m], r]); nuevos++;
    }
    var sp0 = meses[0][1];
    var prev = { B: sp0, F: sp0, G: sp0, H: false, I: false, L: 0, M: 0, N: 'ALCISTA', R: null, X: null, fuera: false }, ppB = sp0;
    var vals = [sp0], est = [[meses[0][0], false]], k;
    for (k = 1; k < meses.length; k++) {
      var sp = meses[k][1]; vals.push(sp); var b3 = 1;
      if (k >= 9) { var s = 0; for (var j = k - 9; j <= k; j++) s += vals[j]; b3 = b3p((sp / (s / 10) - 1) * 100); }
      var nw = pasoMaster(prev, ppB, sp, b3); est.push([meses[k][0], nw.fuera]); ppB = prev.B; prev = nw;
    }
    var n = D.length, ev = [], i;
    for (k = 1; k < est.length; k++) {
      if (est[k][1] != est[k - 1][1]) {
        var fm2 = finMes(est[k][0][0], est[k][0][1]), ej = -1;
        for (i = 0; i < n; i++) if (D[i] > fm2) { ej = i; break; }
        ev.push([ej, est[k][1]]);
      }
    }
    var st = new Array(n), cur = 1, q = 0;
    for (i = 0; i < n; i++) { while (q < ev.length && ev[q][0] >= 0 && ev[q][0] <= i) { cur = ev[q][1] ? 0 : 1; q++; } st[i] = cur; }
    var cs = [0]; for (i = 0; i < n; i++) cs.push(cs[i] + G[i]);
    function MA(j, L) { return (cs[j + 1] - cs[j + 1 - L]) / L; }
    var eff = new Array(n), pend = false, prevSt = 1, e = 1;
    for (i = 0; i < n; i++) {
      if (st[i] == 1) { e = 1; pend = false; }
      else if (prevSt == 1) {
        if (i >= 201 && G[i - 1] >= MA(i - 1, 200)) pend = true; else e = 0;
      } else if (pend) {
        var jj = i - 1, finSem = (jj < n - 1 && semana(D[jj + 1]) != semana(D[jj]));
        if (finSem && G[jj] < MA(jj, 200)) { e = 0; pend = false; }
      }
      eff[i] = e; prevSt = st[i];
    }
    return { st: eff, eventos: ev, pendienteMA200: pend, mes: meses[meses.length - 1], ma200: MA(n - 1, 200), nuevos: nuevos };
  }

  function combinarAgr(r2, mv) {
    var n = r2.length, pos = new Array(n), p = 1, perm = false;
    for (var i = 0; i < n; i++) {
      if (r2[i] == 1) { perm = false; p = mv[i]; }
      else {
        if (i > 0 && r2[i - 1] == 1) perm = false;
        if (i > 0 && mv[i] == 1 && mv[i - 1] == 0) perm = true;
        p = perm ? mv[i] : 0;
      }
      pos[i] = p;
    }
    return pos;
  }

  function calcularCredito(D, cred) {   // cred: [[ 'YYYY-MM-DD', baa-gs10 ], ...]
    var n = D.length, st = new Array(n).fill(1), ev = {}, ult = null, k, i;
    for (k = 11; k < cred.length; k++) {
      var s = 0; for (var j = k - 11; j <= k; j++) s += cred[j][1];
      var al = cred[k][1] > s / 12;
      var y = +cred[k][0].slice(0, 4), m = +cred[k][0].slice(5, 7);
      var nm = dn((m == 12 ? y + 1 : y) + '-' + ('0' + (m % 12 + 1)).slice(-2) + '-01'), jx = -1;
      for (i = 0; i < n; i++) if (D[i] >= nm) { jx = i; break; }
      if (jx >= 0 && jx + 4 < n) ev[jx + 4] = al ? 0 : 1;
      ult = [y, m];
    }
    var cur = 1;
    for (i = 0; i < n; i++) { if (ev[i] !== undefined) cur = ev[i]; st[i] = cur; }
    if (ult) for (i = 0; i < n; i++) {
      var d = ds(D[i]); if ((+d.slice(0, 4) - ult[0]) * 12 + (+d.slice(5, 7)) - ult[1] > 3) st[i] = 1;
    }
    return st;
  }

  function stopK5(D, px, IRX, pos, i0, cred) {
    var n = D.length, ma = new Array(n).fill(null), s = 0, c = 0, i;
    for (i = 0; i < n; i++) {
      if (px[i] != null) { s += px[i]; c++; }
      if (i >= 200 && px[i - 200] != null) { s -= px[i - 200]; c--; }
      if (c >= 200) ma[i] = s / 200;
    }
    function finsem(i) { return i < n - 1 ? semana(D[i + 1]) != semana(D[i]) : wd(D[i]) == 4; }
    var cap = 10000, pk = cap, out = false, held = pos[i0], pe = false, pin = false, credmode = false;
    var eq = new Array(n).fill(0), eff = new Array(n).fill(0); eq[i0] = cap; eff[i0] = held;
    for (i = i0 + 1; i < n; i++) {
      cap = held == 1 ? cap * px[i] / px[i - 1] : cap * (1 + IRX[i - 1] / 100 / 252);
      if (out) {
        if (pin) { out = false; pin = false; pk = cap; }
        else if (credmode) { if (cred[i] == 1) { out = false; pk = cap; } }
        else if (finsem(i) && i >= 20 && ma[i] != null && ma[i - 20] != null && px[i] >= ma[i] && ma[i] > ma[i - 20]) pin = true;
      }
      var tgt = out ? 0 : pos[i];
      if (pe) { tgt = 0; out = true; pe = false; credmode = (cred[i] == 0); }
      if (tgt != held) { cap *= (1 - COSTE); held = tgt; }
      if (cap > pk) pk = cap;
      if (held == 1 && !out && (cap / pk - 1) <= -STOP) pe = true;
      eq[i] = cap; eff[i] = held;
    }
    return { eq: eq, eff: eff, out: out, pin: pin, pe: pe, credmode: credmode, pk: pk, c: cap, held: held, px: px[n - 1], dd: (cap / pk - 1) * 100 };
  }

  function manana(D, G, M, R) {
    var n = D.length, pend = [], u = M.semanas[M.semanas.length - 1];
    if (u.cambio && u.i == n - 1) pend.push(['MOVE', u.estado]);
    var ev = R.eventos;
    if (ev.length && ev[ev.length - 1][0] < 0) pend.push(['R2', ev[ev.length - 1][1] ? 0 : 1]);
    var mvN = M.st[n - 1], r2N = R.st[n - 1], ret = false;
    pend.forEach(function (x) {
      if (x[0] == 'MOVE') mvN = x[1];
      else if (x[1] == 1) r2N = 1;
      else if (G[n - 1] < R.ma200) r2N = 0;
      else ret = true;
    });
    var p = combinarAgr(R.st.concat([r2N]), M.st.concat([mvN]));
    return { tm: p[n], ret: ret };
  }

  function orden(S, tm) {
    if (S.pe) return ['VENDER', 'ha saltado el stop del 25 %'];
    if (S.out) { if (S.pin && tm == 1) return ['COMPRAR', 'vuelta con el comodín K5']; return null; }
    if (tm != S.held) return tm == 1 ? ['COMPRAR', 'TIMÓN vuelve a entrar'] : ['VENDER', 'TIMÓN sale'];
    return null;
  }

  // datos: {D:[dn], G:[sp500], N:[ndx], IRX:[], MV:[], SPY:[], Q:[]}, mensual: [[[y,m],v]], cred: [[fecha, dif]]
  function calcular(dat, mensual, cred, hoy) {
    var D = dat.D, G = dat.G;
    var M = calcularMove(D, dat.MV), R = calcularR2(D, G, mensual, hoy);
    var pos = combinarAgr(R.st, M.st), i0 = 0;
    var ini = dn(INICIO); while (D[i0] < ini) i0++;
    var cr = calcularCredito(D, cred);
    var Ss = stopK5(D, dat.SPY, dat.IRX, pos, i0, cr), Sq = stopK5(D, dat.Q, dat.IRX, pos, i0, cr);
    var mm = manana(D, G, M, R);
    return { M: M, R: R, pos: pos, Ss: Ss, Sq: Sq, tm: mm.tm, ret: mm.ret, oS: orden(Ss, mm.tm), oQ: orden(Sq, mm.tm) };
  }

  return { calcular: calcular, dn: dn, ds: ds, wd: wd, STOP: STOP };
})();
if (typeof module !== 'undefined') module.exports = TM;
