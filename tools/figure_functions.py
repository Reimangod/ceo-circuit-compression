def label(a):
    return f"{MOL[a['molecule']]} {a['distance_A']:.2f}"

def fmte(v):
    x = 1000 * v
    if abs(x) < 1e-12:
        return '0'
    if abs(x) < 1e-05:
        return f'{x:+.2e}'
    return f'{x:+.5f}'.rstrip('0').rstrip('.')

def font(n=36):
    return ImageFont.truetype(FONT, n)

def tx(draw, xy, s, n=36, anchor=None, fill='black'):
    if n in (28, 29, 30, 31, 32, 34):
        n = 36
    draw.text(xy, str(s), font=font(n), fill=fill, anchor=anchor)

def canvas(w=1900, h=1260):
    im = Image.new('RGB', (w, h), 'white')
    return (im, ImageDraw.Draw(im))

def finish(im, name, records):
    p = FIG / (name + '.png')
    im.save(p, dpi=(300, 300))
    FIGDATA[name] = records
    return p

def paired_bars(rows, name):
    im, d = canvas()
    w, h = im.size
    for k, m in enumerate(METRICS):
        ox = k % 2 * 950
        oy = k // 2 * 605
        L, R, T, B = (ox + 112, ox + 902, oy + 108, oy + 492)
        tx(d, (ox + 475, oy + 35), JP[m], 42, 'mt')
        vmax = max((a['ceo'][m] for a in rows)) * 1.12
        for j in range(5):
            val = vmax * j / 4
            y = B - (B - T) * j / 4
            d.line((L, y, R, y), fill='#dddddd', width=2)
            tx(d, (L - 16, y), f'{val:.0f}', 28, 'rm')
        d.line((L, T, L, B, R, B), fill='black', width=3)
        space = (R - L) / len(rows)
        bw = min(31, space * 0.28)
        for j, a in enumerate(rows):
            mid = L + (j + 0.5) * space
            for offset, color, key in [(-bw, 'white', 'ceo'), (0, '#454545', 'child')]:
                yy = B - a[key][m] / vmax * (B - T)
                d.rectangle((mid + offset, yy, mid + offset + bw, B), fill=color, outline='black', width=2)
            tx(d, (mid, B + 15), f"{a['distance_A']:.2f}", 28, 'mt')
        tx(d, ((L + R) / 2, B + 62), '結合長 / Å', 32, 'mt')
    d.rectangle((470, 1210, 506, 1242), fill='white', outline='black', width=2)
    tx(d, (520, 1225), '比較CEO途中回路', 31, 'lm')
    d.rectangle((1080, 1210, 1116, 1242), fill='#454545', outline='black', width=2)
    tx(d, (1130, 1225), '圧縮後', 31, 'lm')
    return finish(im, name, [a['candidate_id'] for a in rows])

def reduction_matrix(rows, name, title='各資源の総削減率'):
    hh = 180 + len(rows) * 62
    im, d = canvas(1900, hh)
    xs = [680, 980, 1280, 1580]
    tx(d, (950, 18), title, 42, 'mt')
    for x, m in zip(xs, METRICS):
        tx(d, (x, 90), JP[m], 33, 'mm')
    for i, a in enumerate(rows):
        y = 150 + i * 62
        tx(d, (45, y + 27), label(a), 34, 'lm')
        for x, m in zip(xs, METRICS):
            v = a['reduction_pct'][m]
            shade = round(255 - min(100, max(0, v)) * 1.65)
            d.rectangle((x - 128, y, x + 128, y + 54), fill=(shade,) * 3, outline='#bbbbbb', width=1)
            tx(d, (x, y + 27), f'{v:.1f}%', 32, 'mm', fill='white' if shade < 140 else 'black')
            if v < 0:
                d.rectangle((x - 128, y, x + 128, y + 54), outline='black', width=2)
    return finish(im, name, [a['candidate_id'] for a in rows])

def energy_gaps(rows, name):
    im, d = canvas(1900, 170 + len(rows) * 59)
    L, R = (550, 1670)
    top = 115
    bound = max((-a['delta_energy_Ha'] * 1000 for a in rows)) * 1.04
    tx(d, (950, 15), '比較CEOを基準とした圧縮後のエネルギー差', 42, 'mt')
    for j in range(5):
        x = R - (R - L) * j / 4
        d.line((x, top - 10, x, top + 59 * len(rows)), fill='#cccccc', width=2)
        tx(d, (x, top - 20), f'{-bound * j / 4:.1f}', 30, 'mb')
    for i, a in enumerate(rows):
        y = top + 59 * i
        tx(d, (40, y + 24), label(a), 34, 'lm')
        v = a['delta_energy_Ha'] * 1000
        x = R + v / bound * (R - L)
        d.rectangle((min(x, R), y + 8, max(x, R), y + 40), fill='#777777', outline='black', width=1)
        tx(d, (R + 20, y + 24), '≈0' if abs(v) <= 1e-06 else f'{v:.4f}', 30, 'lm')
    tx(d, ((L + R) / 2, top + 59 * len(rows) + 10), 'ΔE / mHa', 34, 'mt')
    return finish(im, name, [a['candidate_id'] for a in rows])

def decomposition(rows):
    im, d = canvas(1900, 180 + len(rows) * 59)
    L, R = (570, 1660)
    T = 122
    tx(d, (950, 15), '元分解からのCNOT削減率の内訳', 42, 'mt')
    for tick in (0, 25, 50, 75, 100):
        x = L + (R - L) * tick / 100
        d.line((x, T - 10, x, T + len(rows) * 59), fill='#dddddd', width=2)
        tx(d, (x, T - 20), str(tick), 30, 'mb')
    for i, a in enumerate(rows):
        y = T + i * 59
        raw = a['ceo']['cnot']
        common = a['common_resources']['cnot']
        child = a['child']['cnot']
        v1 = 100 * (raw - common) / raw
        v2 = 100 * (common - child) / raw
        tx(d, (35, y + 24), label(a), 34, 'lm')
        x1 = L + (R - L) * v1 / 100
        x2 = L + (R - L) * (v1 + v2) / 100
        d.rectangle((L, y + 7, x1, y + 42), fill='white', outline='black', width=2)
        for x in range(int(L) - 30, int(x1), 16):
            lo = max(L, x)
            hi = min(x1, x + 34)
            if hi > lo:
                d.line((lo, y + 40, hi, y + 9), fill='#777777', width=1)
        d.rectangle((x1, y + 7, x2, y + 42), fill='#555555', outline='black', width=2)
        tx(d, (x2 + 13, y + 24), f'{v1 + v2:.1f}%', 30, 'lm')
    yy = T + len(rows) * 59 + 10
    tx(d, (L, yy), '斜線: 共通簡約', 31, 'lt')
    tx(d, (L + 480, yy), '灰色: 追加の探索', 31, 'lt')
    return finish(im, 'decomposition', [a['candidate_id'] for a in rows])

def two_points(rows):
    im, d = canvas(1900, 1220)
    for k, a in enumerate(rows):
        ox = k % 2 * 950
        oy = k // 2 * 590
        L, R, T, B = (ox + 140, ox + 855, oy + 115, oy + 440)
        tx(d, (ox + 475, oy + 25), label(a) + ' Å', 42, 'mt')
        cs = [a['ceo']['cnot'], a['child']['cnot']]
        delta = a['delta_energy_Ha'] * 1000
        emin = min(0, delta)
        ymin = emin - 0.15 * max(abs(delta), 0.001)
        ymax = max(0, delta) + 0.15 * max(abs(delta), 0.001)
        xmin = min(cs) * 0.7
        xmax = max(cs) * 1.1
        xx = lambda v: L + (v - xmin) / (xmax - xmin) * (R - L)
        yy = lambda v: B - (v - ymin) / (ymax - ymin) * (B - T)
        d.line((L, T, L, B, R, B), fill='black', width=3)
        for val in (emin, 0):
            y = yy(val)
            d.line((L, y, R, y), fill='#dddddd', width=2)
            tx(d, (L - 12, y), f'{val:.3g}', 28, 'rm')
        for val in cs:
            tx(d, (xx(val), B + 13), str(val), 29, 'mt')
        p1 = (xx(cs[0]), yy(0))
        p2 = (xx(cs[1]), yy(delta))
        d.line((*p1, *p2), fill='#888888', width=2)
        d.ellipse((p1[0] - 10, p1[1] - 10, p1[0] + 10, p1[1] + 10), fill='white', outline='black', width=3)
        d.rectangle((p2[0] - 10, p2[1] - 10, p2[0] + 10, p2[1] + 10), fill='black')
        tx(d, ((L + R) / 2, B + 52), 'CNOT数', 32, 'mt')
        tx(d, (ox + 45, oy + 72), 'ΔE / mHa', 30)
    tx(d, (950, 1160), '○ 比較CEO途中回路    ■ 圧縮後    線は二点の対応', 32, 'mt')
    return finish(im, 'two-points', [a['candidate_id'] for a in rows])
