# -*- coding: utf-8 -*-
"""TIMON MOVIL 3.2 - actualizador de datos (lo ejecuta GitHub a las 06:00 y a las 19:30, hora de Espana).
1. Datos del PC: lee timon_pc.csv de Google Drive (lo deja TIMON 4.1 al abrirse en el PC; datos de Yahoo).
   Solo se usa si es mas nuevo que el ultimo aceptado (fecha del ultimo cierre y hora de generacion). Siempre manda.
2. Dias posteriores al ultimo dato del PC:
   a) EODHD (clave secreta EODHD_API_KEY): S&P 500 (GSPC.INDX), Nasdaq-100 (NDX.INDX), SPY.US, QQQ.US, MOVE.INDX.
      Solo dias cerrados: se rechaza todo dato con la fecha de hoy en Nueva York.
      SPY y QQQ: ultimo valor guardado x (cierre ajustado de hoy / cierre ajustado de ayer), los dos de EODHD.
      Una serie solo se pide si le falta la ultima sesion cerrada (0 consultas si ya esta).
   b) FRED (S&P 500, Nasdaq-100) si EODHD no da el dato; SPY y QQQ se prolongan con la variacion de su indice.
   c) Letra a 3 meses: FRED. MOVE que falte: lo mete el usuario en la app.
3. Control: cuando llegan datos del PC de dias que vinieron de EODHD, se comparan (indices y MOVE: nivel;
   SPY y QQQ: variacion diaria). Diferencia > 0,05 % = aviso.
4. Credito (BAA, GS10): FRED.
Las senales las calcula la pagina (docs/index.html) en el movil."""
import os, re, csv, json, datetime as dt, urllib.request, time

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, 'docs', 'datos')
F_PC = os.path.join(DIR, 'pc.csv')                 # ultimos datos del PC aceptados
F_PC_EST = os.path.join(DIR, 'pc_estado.json')
F_PRECIOS = os.path.join(DIR, 'precios.csv')       # lo que lee la app: PC + EODHD/FRED
F_CREDITO = os.path.join(DIR, 'credito.csv')
F_ESTADO = os.path.join(DIR, 'estado.json')
F_EOD = os.path.join(DIR, 'eodhd.json')            # datos de EODHD guardados (sin la clave) y consultas de hoy
F_CONTROL = os.path.join(DIR, 'control.json')      # ultima comparacion EODHD frente a PC
F_DRIVE = os.path.join(BASE, 'drive_id.txt')       # identificador del archivo compartido de Drive
CAB = {'User-Agent': 'timon-movil/3.2 (GitHub Actions)'}
COLS = ['fecha', 'sp500', 'ndx', 'irx', 'move', 'spy', 'qqq']
SERIES = [('sp500', 'GSPC.INDX'), ('ndx', 'NDX.INDX'), ('spy', 'SPY.US'), ('qqq', 'QQQ.US'), ('move', 'MOVE.INDX')]
TOL = 0.0005                                       # 0,05 %

def bajar(url, intentos=3):
    err = ''
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, headers=CAB)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            err = str(e)
            if k < intentos - 1: time.sleep(5 * (k + 1))
    raise RuntimeError(err)

def fred(serie, desde):
    t = bajar('https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s' % (serie, desde))
    o = {}
    for l in t.splitlines():
        p = l.strip().split(',')
        if len(p) >= 2 and len(p[0]) == 10 and p[0][4] == '-' and p[1] not in ('', '.'):
            o[p[0]] = float(p[1])
    return o

def eodhd(codigo, desde, clave):
    """una consulta (sin reintentos: cada intento gasta una). Devuelve [{date, close, adjusted_close,...}]"""
    url = 'https://eodhd.com/api/eod/%s?api_token=%s&fmt=json&from=%s' % (codigo, clave, desde)
    try:
        t = bajar(url, intentos=1)
    except Exception as e:
        raise RuntimeError(str(e).replace(clave, '***'))
    try: d = json.loads(t)
    except Exception: raise RuntimeError('respuesta no valida')
    if not isinstance(d, list): raise RuntimeError('respuesta inesperada')
    return d

def hoy_ny():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo('America/New_York')).date()
    except Exception:
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).date()

def sesion_anterior(d):
    d = d - dt.timedelta(days=1)
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d

def f(x): return '' if x is None else ('%.6f' % x).rstrip('0').rstrip('.')

def leer_json(fn, defecto):
    try:
        with open(fn) as fh: return json.load(fh)
    except Exception: return defecto

def guardar_json(fn, o):
    with open(fn, 'w') as fh: json.dump(o, fh, ensure_ascii=False)

def leer_pc_texto(t):
    """valida el archivo del PC; devuelve (filas, generado, ultimo)"""
    lin = [l.strip() for l in t.splitlines() if l.strip()]
    if not lin or not lin[0].startswith('#'): raise RuntimeError('el archivo de Drive no es de TIMON')
    m1 = re.search(r'generado=(\d{4}-\d\d-\d\d \d\d:\d\d)', lin[0]); m2 = re.search(r'ultimo=(\d{4}-\d\d-\d\d)', lin[0])
    if not m1 or not m2: raise RuntimeError('cabecera del archivo de Drive sin fecha')
    meta = {'generado': m1.group(1), 'ultimo': m2.group(1)}; gen = meta['generado']
    if lin[1].split(',') != COLS: raise RuntimeError('columnas inesperadas en el archivo de Drive')
    filas = [l.split(',') for l in lin[2:]]
    filas = [p for p in filas if len(p) == 7 and p[1] and p[5]]
    if len(filas) < 5000: raise RuntimeError('archivo de Drive incompleto (%d filas)' % len(filas))
    ult = filas[-1][0]
    if meta.get('ultimo') != ult: raise RuntimeError('archivo de Drive cortado (ultimo %s, filas hasta %s)' % (meta.get('ultimo'), ult))
    return filas, gen.strip(), ult

def num(x):
    try: return float(x) if x not in ('', None) else None
    except Exception: return None

def control_pc(viejas, pc):
    """compara los dias que vinieron de EODHD (precios.csv anterior) con los del PC recien llegados"""
    ve = {p[0]: p for p in viejas if len(p) >= 8 and p[7] == 'eodhd'}
    if not ve: return None
    idx = {p[0]: i for i, p in enumerate(pc)}
    vi = {p[0]: i for i, p in enumerate(viejas)}
    res = {'sp500': None, 'ndx': None, 'move': None, 'spy': None, 'qqq': None}
    dias = []
    for d in sorted(ve):
        if d not in idx: continue
        dias.append(d); a = ve[d]; b = pc[idx[d]]
        for col, k in (('sp500', 1), ('ndx', 2), ('move', 4)):
            x, y = num(a[k]), num(b[k])
            if x and y:
                dif = abs(x / y - 1)
                if res[col] is None or dif > res[col]: res[col] = dif
        for col, k in (('spy', 5), ('qqq', 6)):             # variacion diaria (los ajustes por dividendo cambian el nivel)
            i, j = vi[d], idx[d]
            if i == 0 or j == 0 or viejas[i - 1][0] != pc[j - 1][0]: continue
            x0, x1, y0, y1 = num(viejas[i - 1][k]), num(a[k]), num(pc[j - 1][k]), num(b[k])
            if x0 and x1 and y0 and y1:
                dif = abs((x1 / x0) - (y1 / y0))
                if res[col] is None or dif > res[col]: res[col] = dif
    if not dias: return None
    mal = any(v is not None and v > TOL for v in res.values())
    return {'comprobado': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'dias': dias,
            'max_pct': {c: (None if v is None else round(v * 100, 4)) for c, v in res.items()}, 'mal': mal}

def main():
    avisos = []
    # ---------------- 1. datos del PC (Google Drive) ----------------
    with open(F_PC, newline='') as fh: pc = [p for p in csv.reader(fh)][1:]
    est_pc = leer_json(F_PC_EST, {'ultimo': pc[-1][0], 'generado': ''})
    pc_nuevo = False
    drive_id = open(F_DRIVE).read().strip() if os.path.exists(F_DRIVE) else ''
    if drive_id:
        try:
            filas, gen, ult = leer_pc_texto(bajar('https://drive.google.com/uc?export=download&id=' + drive_id))
            if (ult, gen) > (est_pc['ultimo'], est_pc.get('generado', '')):
                pc = filas; est_pc = {'ultimo': ult, 'generado': gen}; pc_nuevo = True
                with open(F_PC, 'w', newline='') as fh: w = csv.writer(fh, lineterminator='\n'); w.writerow(COLS); w.writerows(pc)
                guardar_json(F_PC_EST, est_pc)
                print('Datos del PC aceptados: hasta', ult, 'generados', gen)
            else:
                print('Datos del PC sin novedad (Drive: %s %s; guardado: %s %s)' % (ult, gen, est_pc['ultimo'], est_pc.get('generado', '')))
        except Exception as e:
            avisos.append('No se han podido leer los datos del PC en Google Drive (%s). Se usan los últimos aceptados.' % str(e)[:90])
    # control EODHD frente a PC (antes de reescribir precios.csv)
    if pc_nuevo and os.path.exists(F_PRECIOS):
        with open(F_PRECIOS, newline='') as fh: viejas = [p for p in csv.reader(fh)][1:]
        c = control_pc(viejas, pc)
        if c:
            guardar_json(F_CONTROL, c); print('Control EODHD frente a PC:', json.dumps(c))
    ult = pc[-1]; dult = ult[0]
    hny = hoy_ny(); hoy_s = hny.isoformat(); esperado = sesion_anterior(hny).isoformat()
    desde = (dt.date.fromisoformat(dult) - dt.timedelta(days=10)).isoformat()
    # ---------------- 2a. EODHD ----------------
    clave = os.environ.get('EODHD_API_KEY', '').strip()
    eod = leer_json(F_EOD, {'series': {}, 'uso': {}})
    E = eod.setdefault('series', {})
    consultas = 0
    if not clave:
        avisos.append('Sin clave de EODHD en GitHub: se usa FRED.')
    elif dult < esperado:
        for col, cod in SERIES:
            s = E.setdefault(col, {})
            if esperado in s: continue                      # ya tiene la ultima sesion cerrada: no se gasta consulta
            consultas += 1
            try:
                n = 0
                for r in eodhd(cod, desde, clave):
                    d = str(r.get('date', ''))[:10]
                    if len(d) != 10 or d >= hoy_s: continue  # solo dias cerrados
                    c, a = num(r.get('close')), num(r.get('adjusted_close'))
                    if not c: continue
                    s[d] = [c, a if a else c]; n += 1
                print('EODHD %s: %d dias cerrados' % (cod, n))
            except Exception as e:
                avisos.append('EODHD no ha dado %s (%s). Se usa FRED o el último dato.' % (cod, str(e)[:80]))
    lim = (dt.date.fromisoformat(dult) - dt.timedelta(days=15)).isoformat()
    for col in list(E): E[col] = {d: v for d, v in E[col].items() if d >= lim}
    k = dt.datetime.now(dt.timezone.utc).date().isoformat()   # EODHD reinicia el contador a medianoche GMT
    eod['uso'] = {k: eod.get('uso', {}).get(k, 0) + consultas}
    guardar_json(F_EOD, eod)
    # ---------------- 2b. FRED y montaje de los dias posteriores al PC ----------------
    filas = [p + ['pc'] for p in pc]
    sp, nd, tb = {}, {}, {}
    try:
        sp = fred('SP500', desde); nd = fred('NASDAQ100', desde)
    except Exception as e:
        avisos.append('FRED no ha respondido (%s).' % str(e)[:80])
    try: tb = fred('DTB3', desde)
    except Exception: avisos.append('Sin tipo a 3 meses de FRED: se usa el último guardado.')
    sp_e, nd_e, spy_e, qq_e, mv_e = (E.get(c, {}) for c in ('sp500', 'ndx', 'spy', 'qqq', 'move'))
    p_sp, p_spy, p_q = float(ult[1]), float(ult[5]), float(ult[6])
    p_nd = num(ult[2]) if ult[2] else nd.get(dult)
    p_irx = num(ult[3]) or 0.0; p_d = dult
    if dult in sp_e and abs(sp_e[dult][0] / p_sp - 1) > 0.001:
        avisos.append('El S&P 500 de EODHD del %s (%.2f) no coincide con el del PC (%.2f).' % (dult, sp_e[dult][0], p_sp))
    if dult in sp and abs(sp[dult] / p_sp - 1) > 0.001:
        avisos.append('El S&P 500 de FRED del %s (%.2f) no coincide con el del PC (%.2f).' % (dult, sp[dult], p_sp))
    for d in sorted(x for x in set(sp_e) | set(sp) if dult < x < hoy_s):
        v_sp = sp_e[d][0] if d in sp_e else sp.get(d)
        v_nd = nd_e[d][0] if d in nd_e else nd.get(d)
        if v_sp is None: break
        if d in spy_e and p_d in spy_e: v_spy = p_spy * spy_e[d][1] / spy_e[p_d][1]
        else: v_spy = p_spy * v_sp / p_sp
        if d in qq_e and p_d in qq_e: v_q = p_q * qq_e[d][1] / qq_e[p_d][1]
        elif v_nd is not None and p_nd: v_q = p_q * v_nd / p_nd
        else: break                                         # se espera a tener el Nasdaq de ese dia
        if d in tb: p_irx = tb[d]
        v_mv = mv_e[d][0] if d in mv_e else None
        filas.append([d, f(v_sp), f(v_nd), f(p_irx), f(v_mv), f(v_spy), f(v_q), 'eodhd' if d in sp_e else 'fred'])
        p_d, p_sp, p_nd, p_spy, p_q = d, v_sp, v_nd, v_spy, v_q
    with open(F_PRECIOS, 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n'); w.writerow(COLS + ['fuente']); w.writerows(filas)
    # ---------------- 3. credito ----------------
    try:
        baa = fred('BAA', '1990-01-01'); gs = fred('GS10', '1990-01-01')
        if len(baa) > 100:
            with open(F_CREDITO, 'w') as fh:
                fh.write('mes,baa,gs10\n')
                for d in sorted(baa):
                    if d in gs: fh.write('%s,%s,%s\n' % (d, f(baa[d]), f(gs[d])))
    except Exception:
        avisos.append('Sin crédito de FRED: se usa el último guardado.')
    # ---------------- 4. estado para la app ----------------
    ahora = dt.datetime.now(dt.timezone.utc)
    falta = filas[-1][0] < esperado
    ult_f = {}
    for p in filas: ult_f[p[7]] = p[0]
    est = dict(actualizado=ahora.strftime('%Y-%m-%d %H:%M UTC'), ultimo=filas[-1][0], pc_ultimo=est_pc['ultimo'],
               pc_generado=est_pc.get('generado', ''), esperado=esperado, falta=falta, avisos=avisos,
               ultimo_fuente=ult_f, eodhd_consultas_hoy=eod['uso'][k], eodhd_consultas_lectura=consultas,
               eodhd_ultimo={c: (max(E[c]) if E.get(c) else '') for c, _ in SERIES})
    guardar_json(F_ESTADO, est)
    print(json.dumps(est, ensure_ascii=False))

if __name__ == '__main__':
    main()
