def mr(t, plain=False):
    r = OxmlElement('m:r')
    rp = OxmlElement('m:rPr')
    sty = OxmlElement('m:sty')
    sty.set(qn('m:val'), 'p' if plain else 'i')
    rp.append(sty)
    r.append(rp)
    wp = OxmlElement('w:rPr')
    fonts = OxmlElement('w:rFonts')
    for k in ['ascii', 'hAnsi', 'eastAsia', 'cs']:
        fonts.set(qn('w:' + k), 'MS Mincho')
    wp.append(fonts)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '21')
    wp.append(sz)
    r.append(wp)
    tt = OxmlElement('m:t')
    tt.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    tt.text = t
    r.append(tt)
    return r

class MathParser:

    def __init__(self, s):
        self.s = s
        self.i = 0

    def group(self):
        if self.i < len(self.s) and self.s[self.i] == '{':
            self.i += 1
            return self.parse('}')
        return [self.atom()]

    def container(self, tag, parts):
        el = OxmlElement(tag)
        for p in parts:
            el.append(p)
        return el

    def atom(self):
        if self.s.startswith('\\{', self.i) or self.s.startswith('\\}', self.i):
            c = self.s[self.i + 1]
            self.i += 2
            return mr(c, True)
        if self.s.startswith('\\frac', self.i) or self.s.startswith('\\binom', self.i):
            isbin = self.s.startswith('\\binom', self.i)
            self.i += 6 if isbin else 5
            a = self.group()
            b = self.group()
            f = OxmlElement('m:f')
            if isbin:
                prop = OxmlElement('m:fPr')
                typ = OxmlElement('m:type')
                typ.set(qn('m:val'), 'noBar')
                prop.append(typ)
                f.append(prop)
            f.append(self.container('m:num', a))
            f.append(self.container('m:den', b))
            if isbin:
                d = OxmlElement('m:d')
                d.append(self.container('m:e', [f]))
                return d
            return f
        number = re.match('\\d+(?:\\.\\d+)?', self.s[self.i:])
        if number:
            self.i += len(number[0])
            return mr(number[0], True)
        for word in ['exp', 'source', 'sector', 'common', 'total', 'search', 'best', 'cont', 'raw', 'MVP', 'ansatz', 'growth', 'CNOT', 'pool', 'root', 'child', 'loc', 'init', 'macro', 'out', 'cos', 'sin', 'tr', 'Re', 'min', 'max', 'Ha']:
            if self.s.startswith(word, self.i):
                self.i += len(word)
                return mr(word, True)
        c = self.s[self.i]
        self.i += 1
        return mr(c, c in 'IXYZ' or not (c.isalpha() or c in 'θφψαβρλχΩΠΔ'))

    def parse(self, end=None):
        out = []
        while self.i < len(self.s):
            if end and self.s[self.i] == end:
                self.i += 1
                break
            if self.s[self.i] in '_^':
                kind = self.s[self.i]
                self.i += 1
                parts = self.group()
                base = out.pop() if out else mr('')
                if kind == '^' and base.tag == qn('m:sSub'):
                    el = OxmlElement('m:sSubSup')
                    for child in list(base):
                        el.append(child)
                    el.append(self.container('m:sup', parts))
                else:
                    el = OxmlElement('m:sSub' if kind == '_' else 'm:sSup')
                    el.append(self.container('m:e', [base]))
                    el.append(self.container('m:sub' if kind == '_' else 'm:sup', parts))
                out.append(el)
            elif self.s[self.i] == '{':
                self.i += 1
                out.extend(self.parse('}'))
            else:
                out.append(self.atom())
        return out
