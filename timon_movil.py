# -*- coding: utf-8 -*-
"""TIMON MOVIL 3.1 - actualizador de datos (lo ejecuta GitHub a las 06:00 y a las 19:30, hora de Espana).
1. Datos del PC: lee timon_pc.csv de Google Drive (lo deja TIMON 4.1 al abrirse en el PC; datos de Yahoo).
   Solo se usa si es mas nuevo que el ultimo aceptado (fecha del ultimo cierre y hora de generacion).
2. Dias posteriores al ultimo dato del PC: FRED (S&P 500, Nasdaq-100, letra a 3 meses). SPY y QQQ se
   prolongan con la variacion diaria de su indice. MOVE de esos dias lo mete el usuario en la app.
3. Credito (BAA, GS10): FRED.
Las senales las calcula la pagina (docs/index.html) en el movil."""
import os, re, csv, json, datetime as dt, urllib.request, time

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, 'docs', 'datos')
F_PC = os.path.join(DIR, 'pc.csv')                 # ultimos datos del PC aceptados
F_PC_EST = os.path.join(DIR, 'pc_estado.json')
F_PRECIOS = os.path.join(DIR, 'precios.csv')       # lo que lee la app: PC + FRED
F_CREDITO = os.path.join(DIR, 'credito.csv')
F_ESTADO = os.path.join(DIR, 'estado.json')
F_DRIVE = os.path.join(BASE, 'drive_id.txt')       # identificador del archivo compartido de Drive
CAB = {'User-Agent': 'timon-movil/3.1 (GitHub Actions)'}
COLS = ['fecha', 'sp500', 'ndx', 'irx', 'move', 'spy', 'qqq']

def bajar(url, intentos=3):
    err = ''
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, headers=CAB)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            err = str(e); time.sleep(5 * (k + 1))
    raise RuntimeError(err)

def fred(serie, desde):
    t = bajar('https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s' % (serie, desde))
    o = {}
    for l in t.splitlines():
        p = l.strip().split(',')
        if len(p) >= 2 and len(p[0]) == 10 and p[0][4] == '-' and p[1] not in ('', '.'):
            o[p[0]] = float(p[1])
    return o

def f(x): return '' if x is None else ('%.6f' % x).rstrip('0').rstrip('.')

def leer_json(fn, defecto):
    try:
        with open(fn) as fh: return json.load(fh)
    except Exception: return defecto

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

def main():
    avisos = []
    # ---------------- 1. datos del PC (Google Drive) ----------------
    with open(F_PC, newline='') as fh: pc = [p for p in csv.reader(fh)][1:]
    est_pc = leer_json(F_PC_EST, {'ultimo': pc[-1][0], 'generado': ''})
    drive_id = open(F_DRIVE).read().strip() if os.path.exists(F_DRIVE) else ''
    if drive_id:
        try:
            filas, gen, ult = leer_pc_texto(bajar('https://drive.google.com/uc?export=download&id=' + drive_id))
            if (ult, gen) > (est_pc['ultimo'], est_pc.get('generado', '')):
                pc = filas; est_pc = {'ultimo': ult, 'generado': gen}
                with open(F_PC, 'w', newline='') as fh: w = csv.writer(fh, lineterminator='\n'); w.writerow(COLS); w.writerows(pc)
                with open(F_PC_EST, 'w') as fh: json.dump(est_pc, fh)
                print('Datos del PC aceptados: hasta', ult, 'generados', gen)
            else:
                print('Datos del PC sin novedad (Drive: %s %s; guardado: %s %s)' % (ult, gen, est_pc['ultimo'], est_pc.get('generado', '')))
        except Exception as e:
            avisos.append('No se han podido leer los datos del PC en Google Drive (%s). Se usan los últimos aceptados y FRED.' % str(e)[:90])
    # ---------------- 2. FRED para los dias posteriores al PC ----------------
    filas = [p + ['pc'] for p in pc]
    ult = pc[-1]; dult = ult[0]
    desde = (dt.date.fromisoformat(dult) - dt.timedelta(days=40)).isoformat()
    try:
        sp = fred('SP500', desde); nd = fred('NASDAQ100', desde)
        try: tb = fred('DTB3', desde)
        except Exception: tb = {}; avisos.append('Sin tipo a 3 meses de FRED: se usa el último guardado.')
        sp_a, spy_a, qqq_a = float(ult[1]), float(ult[5]), float(ult[6])
        nd_a = float(ult[2]) if ult[2] else nd.get(dult)
        irx_a = float(ult[3]) if ult[3] else 0.0
        if dult in sp and abs(sp[dult] / sp_a - 1) > 0.001:
            avisos.append('El S&P 500 de FRED del %s (%.2f) no coincide con el del PC (%.2f).' % (dult, sp[dult], sp_a))
        for d in sorted(x for x in sp if x > dult):
            if d not in nd or nd_a is None: break       # se espera a tener los dos indices del mismo dia
            spy_a *= sp[d] / sp_a; qqq_a *= nd[d] / nd_a
            sp_a, nd_a = sp[d], nd[d]
            if d in tb: irx_a = tb[d]
            filas.append([d, f(sp_a), f(nd_a), f(irx_a), '', f(spy_a), f(qqq_a), 'fred'])
    except Exception as e:
        avisos.append('FRED no ha respondido (%s). Se usan los últimos datos guardados.' % str(e)[:80])
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
    esperado = (ahora - dt.timedelta(hours=5)).date() - dt.timedelta(days=1)   # ultima sesion que deberia estar publicada
    while esperado.weekday() >= 5: esperado -= dt.timedelta(days=1)
    falta = filas[-1][0] < esperado.isoformat()
    est = dict(actualizado=ahora.strftime('%Y-%m-%d %H:%M UTC'), ultimo=filas[-1][0], pc_ultimo=est_pc['ultimo'],
               pc_generado=est_pc.get('generado', ''), esperado=esperado.isoformat(), falta=falta, avisos=avisos)
    with open(F_ESTADO, 'w') as fh: json.dump(est, fh, ensure_ascii=False)
    print(json.dumps(est, ensure_ascii=False))

if __name__ == '__main__':
    main()
