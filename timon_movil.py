# -*- coding: utf-8 -*-
"""TIMON MOVIL - pantalla "Hoy" de TIMON (reglas TIMON-2, estrategia AGRESIVA) para Android (Pydroid 3).
Mismas reglas que TIMON.bat: MOVE T2 2-2, R2 (logica MASTER de SEMAFORO) con salvaguarda de la media de 200,
agresiva = R2 o MOVE + entradas, stop 25 % del capital y comodin K5. S&P 500 (SPY) y Nasdaq-100 (QQQ).
Solo usa la libreria estandar de Python. Pulsa el boton de ejecutar; al terminar se abre la pagina en el navegador."""
import os, sys, csv, json, math, datetime as dt, urllib.request, webbrowser

def _carpeta():
    """carpeta donde estan los archivos de la app (Pydroid a veces ejecuta una copia temporal en otra carpeta)"""
    cands = []
    try: cands.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError: pass
    cands += [os.getcwd(), '/storage/emulated/0/Download', '/sdcard/Download', '/storage/emulated/0/Descargas', '/sdcard/Descargas']
    for c in cands:
        if c and os.path.exists(os.path.join(c, 'sp_mensual.csv')): return c
    return None
CARPETA = _carpeta()
if CARPETA is None:
    print('ERROR: no encuentro sp_mensual.csv. Pon los 4 archivos juntos en la carpeta Download (Descargas) del movil.')
    CARPETA = os.getcwd()
F_MENSUAL = os.path.join(CARPETA, 'sp_mensual.csv')
F_CREDITO = os.path.join(CARPETA, 'credito.csv')
F_PRECIOS = os.path.join(CARPETA, 'precios_movil.csv')
F_HOY = os.path.join(CARPETA, 'TIMON_hoy.html')
VERSION = 'TIMON movil 1.1 (reglas TIMON-2, agresiva)'
STOP = 0.25; COSTE = 0.001; INICIO = dt.date(2003, 11, 1)
MOVE_VENT, MOVE_MIN, MOVE_PCT, MOVE_VIER = 1260, 253, 90, 2
UA = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36'}

# ----------------------------------------------------------------- descargas
import http.cookiejar, time
_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_JAR))
_COOKIE_OK = False
CAB = {'User-Agent': UA['User-Agent'], 'Accept': 'text/html,application/json,text/csv,*/*;q=0.8', 'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'}

def bajar(url, seg=60):
    req = urllib.request.Request(url, headers=CAB)
    with _OPENER.open(req, timeout=seg) as r:
        return r.read().decode('utf-8', 'replace')

def cookie_yahoo():
    """Yahoo corta (error 429) las peticiones sin su cookie: se pide una vez, como hace un navegador"""
    global _COOKIE_OK
    if _COOKIE_OK: return
    for url in ('https://fc.yahoo.com', 'https://finance.yahoo.com'):
        try: bajar(url, 30)
        except Exception: pass          # fc.yahoo.com responde con error pero deja la cookie
        if len(_JAR) > 0: break
    _COOKIE_OK = True

def serie_yahoo(sym):
    """igual que Descargar-Serie de TIMON: precio ajustado si existe; fecha = marca de tiempo + desfase de la bolsa"""
    cookie_yahoo()
    p2 = int((dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).timestamp())
    err = ''
    for h in ('query1', 'query2'):
        url = 'https://%s.finance.yahoo.com/v8/finance/chart/%s?period1=880000000&period2=%d&interval=1d&events=div%%2Csplit' % (h, urllib.request.quote(sym), p2)
        for k in range(3):
            try:
                r = json.loads(bajar(url))['chart']['result'][0]
                off = int(r['meta'].get('gmtoffset', 0)); ts = r['timestamp']; cl = r['indicators']['quote'][0]['close']
                adj = r['indicators'].get('adjclose', [{}])[0].get('adjclose') if r['indicators'].get('adjclose') else None
                out = {}
                for i in range(len(ts)):
                    v = adj[i] if adj else cl[i]
                    if v is None: continue
                    d = (dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(ts[i]) + off)).strftime('%Y-%m-%d')
                    out[d] = float(v)
                return out
            except Exception as e:
                err = str(e)
                time.sleep(4 * (k + 1))
    raise RuntimeError('Yahoo no responde para %s: %s' % (sym, err))

def descargar_precios():
    s = {}
    for k in ('SPY', '^GSPC', '^IRX', '^MOVE', 'QQQ'):
        print('Descargando ' + k + ' de Yahoo...'); s[k] = serie_yahoo(k); time.sleep(1)
    ahora = dt.datetime.now(dt.timezone.utc); hoy = ahora.strftime('%Y-%m-%d')
    cerrado = ahora.hour + ahora.minute / 60.0 >= 21.5        # 22:30 en Madrid (invierno): la sesion de hoy ya ha cerrado
    filas = []
    for d in sorted(s['SPY']):
        if d > hoy or (d == hoy and not cerrado): continue
        if d not in s['^GSPC']: continue
        filas.append([d, s['SPY'][d], s['^GSPC'][d], s['^IRX'].get(d), s['^MOVE'].get(d), s['QQQ'].get(d)])
    if len(filas) < 5000: raise RuntimeError('Descarga incompleta de Yahoo (pocas sesiones).')
    with open(F_PRECIOS, 'w', newline='') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(['fecha', 'spy', 'sp500', 'irx', 'move', 'qqq'])
        for r in filas: w.writerow([x if x is not None else '' for x in r])

def descargar_credito():
    def serie(i):
        t = bajar('https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=1990-01-01' % i)
        o = {}
        for l in t.splitlines():
            p = l.strip().split(',')
            if len(p) >= 2 and len(p[0]) == 10 and p[0][4] == '-' and p[1] not in ('', '.'): o[p[0]] = p[1]
        if len(o) < 100: raise RuntimeError('FRED devolvio pocos datos de ' + i)
        return o
    print('Descargando credito de FRED...'); baa = serie('BAA'); gs = serie('GS10')
    with open(F_CREDITO, 'w', newline='') as f:
        f.write('mes;baa;gs10\n')
        for d in sorted(baa):
            if d in gs: f.write('%s;%s;%s\n' % (d, baa[d].replace('.', ','), gs[d].replace('.', ',')))

# ----------------------------------------------------------------- carga
def num(x):
    x = (x or '').strip()
    return float(x.replace(',', '.')) if x else None

def cargar():
    D = []; SPY = []; G = []; IRX = []; MV = []; Q = []; ui = 0.0; uq = None
    with open(F_PRECIOS, newline='') as f:
        r = list(csv.reader(f, delimiter=';'))
    for p in r[1:]:
        if len(p) < 6 or not p[1] or not p[2]: continue
        D.append(dt.date.fromisoformat(p[0])); SPY.append(num(p[1])); G.append(num(p[2]))
        if p[3]: ui = num(p[3])
        IRX.append(ui); MV.append(num(p[4]))
        if p[5]: uq = num(p[5])
        Q.append(uq)
    return D, SPY, G, IRX, MV, Q

# ----------------------------------------------------------------- reglas (copia de TIMON.bat)
def semana(d): return d - dt.timedelta(days=d.weekday())

def percentil(a, p):
    b = sorted(a); pos = (len(b) - 1) * p / 100.0; lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    return b[lo] + (b[hi] - b[lo]) * (pos - lo)

def calcular_move(D, MV):
    n = len(D); mv = []; posmv = [0] * n
    for i in range(n):
        if MV[i] is not None: mv.append(MV[i])
        posmv[i] = len(mv) - 1
    calma = 1; ca = cb = 0; cambios = []; semanas = []
    for i in range(n):
        fin = semana(D[i + 1]) != semana(D[i]) if i < n - 1 else D[i].weekday() == 4
        if not fin: continue
        k = posmv[i]
        if k < 0: continue
        ini = max(0, k - MOVE_VENT + 1)
        if k - ini + 1 < MOVE_MIN: continue
        th = percentil(mv[ini:k + 1], MOVE_PCT); v = mv[k]
        if v > th: ca += 1; cb = 0
        else: cb += 1; ca = 0
        nuevo = calma
        if calma == 1 and ca >= MOVE_VIER: nuevo = 0
        if calma == 0 and cb >= MOVE_VIER: nuevo = 1
        cambio = nuevo != calma
        if cambio: calma = nuevo; cambios.append((i + 1, nuevo))
        semanas.append(dict(i=i, estado=calma, cambio=cambio, move=v, umbral=th))
    st = [1] * n; cur = 1; k = 0
    for i in range(n):
        while k < len(cambios) and cambios[k][0] <= i: cur = cambios[k][1]; k += 1
        st[i] = cur
    return dict(st=st, semanas=semanas)

def b3p(x): return 0 if x >= 5 else (1 if x >= 0 else (2 if x >= -5 else 3))

def paso_master(prev, ppB, sp, b3):
    pB, pF, pG, pH, pI, pL, pM, pN, pR, pX = [prev[k] for k in 'BFGHILMNRX']
    nF = pB if (pB is not None and ppB is not None and pB > ppB and pB >= sp) else pF
    nG = pB if (pB is not None and ppB is not None and pB < ppB and pB <= sp) else pG
    nH = pF is not None and sp > pF; nI = pG is not None and sp < pG
    nJ = ('A' if sp > pF else 'R') if pH else ''
    nK = ('A' if sp < pG else 'R') if pI else ''
    nL = 0 if nJ == 'A' else (pL + 1 if (nK == 'A' and pG != pR) else pL)
    nM = 0 if nK == 'A' else (pM + 1 if (nJ == 'A' and pF != pX) else pM)
    if nL >= 2: nN = 'BAJISTA'
    elif nM >= 2: nN = 'ALCISTA'
    elif nL == 1 or nM == 1: nN = 'LATERAL'
    else: nN = pN
    nP = 'ALTO' if (b3 >= 2 or nK == 'A') else 'NO ALTO'
    nR = None if nJ == 'A' else (pG if (nK == 'A' and pG != pR) else pR)
    nX = None if nK == 'A' else (pF if (nJ == 'A' and pF != pX) else pX)
    return dict(B=sp, F=nF, G=nG, H=nH, I=nI, L=nL, M=nM, N=nN, R=nR, X=nX, fuera=(nN == 'BAJISTA' and nP == 'ALTO'))

def fin_mes(y, m): return dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)

def ultimo_laborable(d):
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d

def media30(D, G, fm):
    ini = fm - dt.timedelta(days=29); v = [G[i] for i in range(len(D)) if ini <= D[i] <= fm]
    return sum(v) / len(v) if v else None

def leer_mensual():
    out = []
    with open(F_MENSUAL, newline='', encoding='utf-8-sig') as f:
        for p in list(csv.reader(f, delimiter=';'))[1:]:
            if len(p) >= 2 and p[1]: out.append([(int(p[0][:4]), int(p[0][5:7])), num(p[1]), p[2] if len(p) > 2 else ''])
    return out

def calcular_r2(D, G):
    meses = leer_mensual(); ultD = D[-1]; hoy = dt.date.today(); nuevos = []
    while True:
        y, m = meses[-1][0]; y, m = (y + (m == 12), m % 12 + 1)
        fm = fin_mes(y, m); ulab = ultimo_laborable(fm)
        cerrado = (ultD > fm) or (ultD >= ulab) or (hoy > fm + dt.timedelta(days=1) and ultD >= ulab - dt.timedelta(days=3))
        if not cerrado or ultD < dt.date(y, m, 1): break
        r = media30(D, G, fm)
        if r is None: break
        meses.append([(y, m), r, 'TIMON media 30 dias']); nuevos.append('%04d-%02d;%s;TIMON media 30 dias' % (y, m, ('%.4f' % r).replace('.', ',')))
    if nuevos:
        with open(F_MENSUAL, 'a', encoding='utf-8') as f: f.write('\n'.join(nuevos) + '\n')
    sp0 = meses[0][1]
    prev = dict(B=sp0, F=sp0, G=sp0, H=False, I=False, L=0, M=0, N='ALCISTA', R=None, X=None, fuera=False); ppB = sp0
    vals = [sp0]; est = [(meses[0][0], False)]
    for k in range(1, len(meses)):
        sp = meses[k][1]; vals.append(sp); b3 = 1
        if k >= 9: ma = sum(vals[k - 9:k + 1]) / 10; b3 = b3p((sp / ma - 1) * 100)
        nw = paso_master(prev, ppB, sp, b3); est.append((meses[k][0], nw['fuera'])); ppB = prev['B']; prev = nw
    n = len(D); ev = []
    for k in range(1, len(est)):
        if est[k][1] != est[k - 1][1]:
            y, m = est[k][0]; fm = fin_mes(y, m); ej = next((i for i in range(n) if D[i] > fm), -1)
            ev.append((ej, est[k][1]))
    st = [1] * n; cur = 1; q = 0
    for i in range(n):
        while q < len(ev) and ev[q][0] >= 0 and ev[q][0] <= i: cur = 0 if ev[q][1] else 1; q += 1
        st[i] = cur
    cs = [0.0]
    for x in G: cs.append(cs[-1] + x)
    def MA(j, L): return (cs[j + 1] - cs[j + 1 - L]) / L
    eff = [1] * n; pend = False; prevSt = 1; e = 1
    for i in range(n):
        if st[i] == 1: e = 1; pend = False
        elif prevSt == 1:
            if i >= 201 and G[i - 1] >= MA(i - 1, 200): pend = True
            else: e = 0
        elif pend:
            j = i - 1; finSem = (j < n - 1 and semana(D[j + 1]) != semana(D[j]))
            if finSem and G[j] < MA(j, 200): e = 0; pend = False
        eff[i] = e; prevSt = st[i]
    return dict(st=eff, eventos=ev, pendienteMA200=pend, mes=meses[-1], ma200=MA(n - 1, 200))

def combinar_agr(r2, mv):
    n = len(r2); pos = [0] * n; p = 1; perm = False
    for i in range(n):
        if r2[i] == 1: perm = False; p = mv[i]
        else:
            if i > 0 and r2[i - 1] == 1: perm = False
            if i > 0 and mv[i] == 1 and mv[i - 1] == 0: perm = True
            p = mv[i] if perm else 0
        pos[i] = p
    return pos

def calcular_credito(D):
    n = len(D); st = [1] * n; m = []
    if not os.path.exists(F_CREDITO): return st
    with open(F_CREDITO, newline='') as f:
        for p in list(csv.reader(f, delimiter=';'))[1:]:
            if len(p) >= 3 and p[1] and p[2]: m.append((dt.date.fromisoformat(p[0]), num(p[1]) - num(p[2])))
    ev = {}; ult = None
    for k in range(11, len(m)):
        media = sum(x[1] for x in m[k - 11:k + 1]) / 12; al = m[k][1] > media
        mm = m[k][0]; nm = dt.date(mm.year + (mm.month == 12), mm.month % 12 + 1, 1)
        j = next((i for i in range(n) if D[i] >= nm), -1)
        if j >= 0 and j + 4 < n: ev[j + 4] = 0 if al else 1
        ult = mm
    cur = 1
    for i in range(n):
        if i in ev: cur = ev[i]
        st[i] = cur
    if ult is not None:
        for i in range(n):
            if (D[i].year - ult.year) * 12 + D[i].month - ult.month > 3: st[i] = 1
    return st

def stop_k5(D, px, IRX, pos, i0, cred):
    n = len(D); ma = [None] * n; s = 0.0; c = 0
    for i in range(n):
        if px[i] is not None: s += px[i]; c += 1
        if i >= 200 and px[i - 200] is not None: s -= px[i - 200]; c -= 1
        if c >= 200: ma[i] = s / 200
    def finsem(i): return semana(D[i + 1]) != semana(D[i]) if i < n - 1 else D[i].weekday() == 4
    cap = 10000.0; pk = cap; out = False; held = pos[i0]; pe = False; pin = False; credmode = False
    eq = [0.0] * n; eq[i0] = cap; eff = [0] * n; eff[i0] = held
    for i in range(i0 + 1, n):
        cap = cap * px[i] / px[i - 1] if held == 1 else cap * (1 + IRX[i - 1] / 100 / 252)
        if out:
            if pin: out = False; pin = False; pk = cap
            elif credmode:
                if cred[i] == 1: out = False; pk = cap
            elif finsem(i) and i >= 20 and ma[i] is not None and ma[i - 20] is not None and px[i] >= ma[i] and ma[i] > ma[i - 20]: pin = True
        tgt = 0 if out else pos[i]
        if pe: tgt = 0; out = True; pe = False; credmode = (cred[i] == 0)
        if tgt != held: cap *= (1 - COSTE); held = tgt
        if cap > pk: pk = cap
        if held == 1 and not out and (cap / pk - 1) <= -STOP: pe = True
        eq[i] = cap; eff[i] = held
    return dict(eq=eq, eff=eff, out=out, pin=pin, pe=pe, credmode=credmode, pk=pk, c=cap, held=held, px=px[n - 1], dd=(cap / pk - 1) * 100)

def manana(D, G, M, R):
    """posicion de TIMON para la siguiente sesion (ordenes pendientes de MOVE o R2), igual que Manana en TIMON.bat"""
    n = len(D); pend = []
    u = M['semanas'][-1]
    if u['cambio'] and u['i'] == n - 1: pend.append(('MOVE', u['estado']))
    ev = R['eventos']
    if ev and ev[-1][0] < 0: pend.append(('R2', 0 if ev[-1][1] else 1))
    mvN = M['st'][n - 1]; r2N = R['st'][n - 1]; ret = False
    for q, v in pend:
        if q == 'MOVE': mvN = v
        elif v == 1: r2N = 1
        elif G[n - 1] < R['ma200']: r2N = 0
        else: ret = True
    p = combinar_agr(R['st'] + [r2N], M['st'] + [mvN])
    return p[n], ret

def orden(S, tm):
    if S['pe']: return ('VENDER', 'ha saltado el stop del 25 %')
    if S['out']:
        if S['pin'] and tm == 1: return ('COMPRAR', 'vuelta con el comod&iacute;n K5')
        return None
    if tm != S['held']: return ('COMPRAR', 'TIM&Oacute;N vuelve a entrar') if tm == 1 else ('VENDER', 'TIM&Oacute;N sale')
    return None

def siguiente_laborable(d):
    x = d + dt.timedelta(days=1)
    while x.weekday() >= 5 or (x.month == 1 and x.day == 1) or (x.month == 12 and x.day == 25): x += dt.timedelta(days=1)
    return x

# ----------------------------------------------------------------- pagina "Hoy"
def es(x, d=0):
    s = ('{:,.%df}' % d).format(x)
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')

DIAS = ['lunes', 'martes', 'mi&eacute;rcoles', 'jueves', 'viernes', 's&aacute;bado', 'domingo']

def pagina(D, G, SPYp, Qp, res, avisos):
    n = len(D); ult = D[-1]; sig = siguiente_laborable(ult)
    filas = ''
    for nombre, idx, S, o, etf in res:
        if o and o[0] == 'VENDER': ico, txt, col = '&#128308;', 'VENDER', '#b00020'; cuando = 'Ma&ntilde;ana, ' + DIAS[sig.weekday()] + ' ' + sig.strftime('%d/%m') + ', al cierre. Motivo: ' + o[1] + '.'
        elif o and o[0] == 'COMPRAR': ico, txt, col = '&#128309;', 'COMPRAR', '#1565c0'; cuando = 'Ma&ntilde;ana, ' + DIAS[sig.weekday()] + ' ' + sig.strftime('%d/%m') + ', al cierre. Motivo: ' + o[1] + '.'
        elif S['held'] == 1: ico, txt, col = '&#128994;', 'MANTENER', '#0a7a2f'; cuando = 'No hagas nada.'
        else: ico, txt, col = '&#9898;', 'ESPERAR FUERA', '#666'; cuando = 'Sigue en liquidez.' + (' Fuera por el stop: vuelve con el comod&iacute;n K5.' if S['out'] else '')
        alarma = ''
        if S['held'] == 1 and not S['pe'] and not o:
            ps = S['px'] * (1 - STOP) * S['pk'] / S['c']
            if idx: txa = 'el <b>' + nombre + '</b> cierra por debajo de <b>' + es(idx * ps / S['px']) + '</b> puntos'
            else: txa = 'el <b>' + etf + '</b> cierra por debajo de <b>' + es(ps, 2) + '</b>'
            alarma = '<div class="al">Alarma: si ' + txa + ', vender (stop). Ahora est&aacute; un ' + es(-S['dd'], 1) + ' % por debajo de su m&aacute;ximo.</div>'
        filas += '<div class="caja" style="border-color:%s"><div class="nom">%s</div><div class="ord" style="color:%s">%s %s</div><div class="cu">%s</div>%s</div>' % (col, nombre + (' (fondo)' if 'S&amp;P' in nombre else ' (ETF)'), col, ico, txt, cuando, alarma)
    av = ''.join('<div class="aviso">%s</div>' % a for a in avisos)
    viejo = (dt.date.today() - ult).days > 4
    if viejo: av += '<div class="aviso">Los datos tienen m&aacute;s de 4 d&iacute;as. Comprueba la conexi&oacute;n y vuelve a ejecutar.</div>'
    html = ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>TIMON hoy</title><style>body{font-family:Roboto,Arial,sans-serif;margin:14px;color:#222;font-size:17px}'
            'h1{font-size:22px;margin:0 0 4px 0}.f{color:#666;font-size:14px;margin-bottom:12px}.caja{border:3px solid #999;border-radius:12px;padding:12px;margin:12px 0}'
            '.nom{font-size:15px;color:#555}.ord{font-size:30px;font-weight:bold;margin:4px 0}.cu{font-size:16px}.al{margin-top:8px;font-size:15px;background:#fff3cd;padding:6px;border-radius:6px}'
            '.aviso{background:#fde2e2;color:#7a0010;padding:8px;border-radius:6px;margin:8px 0;font-size:15px}.pie{color:#777;font-size:13px;margin-top:16px}</style></head><body>'
            '<h1>TIM&Oacute;N &middot; Hoy</h1><div class="f">Datos hasta el cierre del ' + DIAS[ult.weekday()] + ' ' + ult.strftime('%d/%m/%Y') + '</div>' + av + filas +
            '<div class="pie">Mira TIM&Oacute;N cada viernes por la noche y el &uacute;ltimo d&iacute;a de cada mes.<br>Estrategia agresiva (R2 o MOVE + entradas), stop 25 % y comod&iacute;n K5: las mismas reglas que TIM&Oacute;N en el PC.<br>' + VERSION + '</div></body></html>')
    with open(F_HOY, 'w', encoding='utf-8') as f: f.write(html)

# ----------------------------------------------------------------- principal
def calcular(avisos):
    D, SPY, G, IRX, MV, Q = cargar()
    M = calcular_move(D, MV); R = calcular_r2(D, G)
    pos = combinar_agr(R['st'], M['st'])
    i0 = next(i for i, d in enumerate(D) if d >= INICIO)
    cred = calcular_credito(D)
    Ss = stop_k5(D, SPY, IRX, pos, i0, cred); Sq = stop_k5(D, Q, IRX, pos, i0, cred)
    tm, ret = manana(D, G, M, R)
    if ret or R['pendienteMA200']: avisos.append('R2 ha dado salida pero el S&amp;P 500 est&aacute; por encima de su media de 200 sesiones: la salida queda pendiente y se revisa cada viernes.')
    return D, G, Ss, Sq, tm

def main(descargar=True):
    avisos = []
    if descargar:
        try: descargar_precios()
        except Exception as e: avisos.append('No se han podido descargar precios nuevos de Yahoo (' + str(e)[:120] + '). Se usan los &uacute;ltimos guardados.')
        try: descargar_credito()
        except Exception as e: avisos.append('No se ha podido descargar el cr&eacute;dito de FRED (' + str(e)[:100] + '). Se usa el &uacute;ltimo guardado (dato mensual; si tiene m&aacute;s de 3 meses, el comod&iacute;n K5 decide solo con la media de 200).')
    if not os.path.exists(F_PRECIOS):
        with open(F_HOY, 'w', encoding='utf-8') as f: f.write('<html><body><h2>Sin datos</h2><p>No hay conexi&oacute;n con Yahoo y no hay datos guardados.</p></body></html>')
        return None
    D, G, Ss, Sq, tm = calcular(avisos)
    n = len(D)
    res = [('S&amp;P 500', G[n - 1], Ss, orden(Ss, tm), 'SPY')]
    # Nasdaq-100: nivel del indice = QQQ x (indice/QQQ) del ultimo cierre (se descarga ^NDX solo para esta conversion)
    try: ndx = serie_yahoo('^NDX'); kq = D[-1].strftime('%Y-%m-%d'); ixq = ndx.get(kq)
    except Exception: ixq = None
    res.append(('Nasdaq-100', ixq, Sq, orden(Sq, tm), 'QQQ'))
    if not ixq: avisos.append('Sin dato del indice Nasdaq-100: la alarma del Nasdaq se muestra en precio del QQQ.')
    pagina(D, G, None, None, res, avisos)
    import html as _h, re as _re
    print('')
    print('TIMON - datos hasta el ' + D[-1].strftime('%d/%m/%Y'))
    for nombre, idx, S, o, etf in res:
        if o: t = o[0] + ' manana al cierre (' + _h.unescape(o[1]) + ')'
        elif S['held'] == 1: t = 'MANTENER'
        else: t = 'ESPERAR FUERA'
        print('  ' + _h.unescape(nombre) + ': ' + t)
    for a in avisos: print('  AVISO: ' + _re.sub('<[^>]+>', '', _h.unescape(a)))
    return dict(D=D, Ss=Ss, Sq=Sq, tm=tm)

if __name__ == '__main__':
    print('TIMON movil. Carpeta: ' + CARPETA)
    try:
        r = main(descargar=os.environ.get('TIMON_OFFLINE') is None)
        print('')
        print('Listo. Pagina: ' + F_HOY)
        try: webbrowser.open('file://' + F_HOY)
        except Exception: pass
    except Exception as e:
        import traceback
        print('')
        print('ERROR: ' + str(e))
        traceback.print_exc()
        print('Manda una captura de esta pantalla.')
