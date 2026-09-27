# model.json + out/*.json -> docs/service-manual/*.md
import json, re, os, sys, glob, shutil, html as H
sys.stdout.reconfigure(encoding='utf-8')
SM = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(SM, '..', '..', '..'))
DEST = os.path.abspath(os.path.join(SM, '..'))
SITE = os.environ.get('SM_SITE') or r"C:\Users\Admin\Downloads\Voyah Zhiyin 2024 v0.1\extracted\Руководство по ремонту электромобиля\site"
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
SPLIT = re.compile(r'(<br>|\n|!\[\]\(IMG:[^)]*\))')

m = json.load(open(os.path.join(SM, 'model.json'), encoding='utf-8'))
# память переводов {китайский сегмент: русский перевод}
TM = json.load(open(os.path.join(SM, 'translations.json'), encoding='utf-8'))
MISSING = set()


UNITS = [(r'(\d)\s*(?:N\s*[·.]?\s*m|Nm)\b', r'\1 Н·м'), (r'(\d)\s*mm\b', r'\1 мм'), (r'(\d)\s*kg\b', r'\1 кг'),
         (r'(\d)\s*km/h\b', r'\1 км/ч'), (r'(\d)\s*kWh\b', r'\1 кВт·ч'), (r'(\d)\s*kW\b', r'\1 кВт'), (r'(\d)\s*min\b', r'\1 мин')]


def units(s):
    for a, b in UNITS: s = re.sub(a, b, s)
    return s


def T(s):
    s = s.strip()
    if not CJK.search(s): return units(s)
    r = TM.get(s)
    if r is None:
        MISSING.add(s); return s
    return r


def tr_text(t):
    out = []
    for piece in SPLIT.split(t):
        if not piece or SPLIT.fullmatch(piece): out.append(piece); continue
        lead = piece[:len(piece) - len(piece.lstrip())]; trail = piece[len(piece.rstrip()):]
        out.append(lead + T(piece) + trail if piece.strip() else piece)
    return ''.join(out) if CJK.search(t) else units(''.join(out))
    return ''.join(out)


def slug(s, n=60):
    s = re.sub(r'\]\(#[0-9a-f]+\)|[\[\]*]', '', s).lower()
    s = re.sub(r'[^0-9a-zа-яё]+', '-', s).strip('-')
    if len(s) > n: s = s[:n].rsplit('-', 1)[0]
    return s or 'page'


# ---------- раскладка файлов
L1 = []            # (dir, title_ru, title_zh, node)
PATH = {}          # page id -> relative path from DEST
for i, n in enumerate(m['tree'], 1):
    d = f'{i:02d}-{slug(T(n["name_zh"]), 40)}'
    L1.append((d, T(n['name_zh']), n['name_zh'], n))
    cnt = [0]

    def assign(nodes):
        for c in nodes:
            if c['is_page'] and c['id'] in m['pages']:
                cnt[0] += 1
                PATH[c['id']] = f'{d}/{cnt[0]:03d}-{slug(T(c["name_zh"]), 55)}.md'
            assign(c['children'])
    if n['is_page'] and n['id'] in m['pages']:
        cnt[0] += 1; PATH[n['id']] = f'{d}/{cnt[0]:03d}-{slug(T(n["name_zh"]), 55)}.md'
    assign(n['children'])


def rel(frm, to):
    return os.path.relpath(os.path.join(DEST, to), os.path.dirname(os.path.join(DEST, frm))).replace('\\', '/')


def links_md(t, here):
    t = re.sub(r'\]\(#([0-9a-f]+)\)', lambda g: f']({rel(here, PATH[g[1]])})' if g[1] in PATH else ']', t)
    return re.sub(r'!\[\]\(IMG:([^)]*)\)', lambda g: f'![]({rel(here, "images/" + g[1])})', t)


def to_html_inline(t, here):
    t = H.escape(t, quote=False).replace('&lt;br&gt;', '<br>')
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'!\[\]\(IMG:([^)]*)\)', lambda g: f'<img src="{rel(here, "images/" + g[1])}">', t)
    t = re.sub(r'\[([^\]]*)\]\(#([0-9a-f]+)\)', lambda g: f'<a href="{rel(here, PATH[g[2]])}">{g[1]}</a>' if g[2] in PATH else g[1], t)
    return t.replace('**', '')


def table(rows, here):
    spans = any(c['rs'] > 1 or c['cs'] > 1 for r in rows for c in r)
    widths = {len(r) for r in rows}
    if not spans and len(widths) == 1:
        def cell(c): return links_md(tr_text(c['t']), here).replace('|', '\\|') or ' '
        w = widths.pop()
        out = ['| ' + ' | '.join(cell(c) for c in rows[0]) + ' |', '|' + '---|' * w]
        out += ['| ' + ' | '.join(cell(c) for c in r) + ' |' for r in rows[1:]]
        return '\n'.join(out)
    out = ['<table>']
    for r in rows:
        tds = ''.join(f'<td{" rowspan=%d" % c["rs"] if c["rs"] > 1 else ""}{" colspan=%d" % c["cs"] if c["cs"] > 1 else ""}>'
                      f'{to_html_inline(tr_text(c["t"]), here)}</td>' for c in r)
        out.append(f'<tr>{tds}</tr>')
    out.append('</table>')
    return '\n'.join(out)


def page_md(pid, here):
    meta = m['flat'][pid]
    title = T(meta['name_zh'])
    crumbs = ' › '.join(T(x) for x in meta['path_names'][:-1])
    L = [f'# {title}', '',
         f'> {crumbs}  ',
         f'> Оригинал: `{meta["name_zh"]}` · [dongcheyun 56746](https://dongcheyun.com/p/56746), страница `{pid}` · '
         f'[оглавление]({rel(here, "README.md")})', '']
    for kind, v in m['pages'][pid]:
        if kind == 'img':
            L += [f'![]({rel(here, "images/" + v)})', '']
        elif kind == 'p':
            t = links_md(tr_text(v), here).replace('\n', '  \n')
            if re.fullmatch(r'\*\*[^*]{1,40}\*\*', t) and not re.match(r'\*\*\s*[-–•\d]', t):
                t = t  # короткий жирный заголовок оставляем как есть
            L += [t, '']
        elif kind == 'table':
            L += [table(v, here), '']
    return '\n'.join(L).rstrip() + '\n'


def index_md(nodes, here, depth):
    L = []
    for n in nodes:
        name = T(n['name_zh'])
        if n['is_page'] and n['id'] in PATH:
            L.append('  ' * depth + f'- [{name}]({rel(here, PATH[n["id"]])})')
        else:
            L.append('  ' * depth + f'- **{name}**')
        L += index_md(n['children'], here, depth + 1)
    return L


def main():
    os.makedirs(DEST, exist_ok=True)
    for d, *_ in L1:
        if os.path.isdir(os.path.join(DEST, d)): shutil.rmtree(os.path.join(DEST, d))
    for pid, p in PATH.items():
        fp = os.path.join(DEST, p); os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, 'w', encoding='utf-8', newline='\n').write(page_md(pid, p))
    for d, ru, zh, n in L1:
        here = f'{d}/README.md'
        body = [f'# {ru}', '', f'> Раздел руководства по ремонту 2024 岚图知音 (оригинал: `{zh}`) · [общее оглавление](../README.md)', '']
        body += index_md(n['children'] if not n['is_page'] else [n], here, 0)
        open(os.path.join(DEST, here), 'w', encoding='utf-8', newline='\n').write('\n'.join(body) + '\n')
    toc = [f'{i}. [{ru}]({d}/README.md) — `{zh}`' for i, (d, ru, zh, n) in enumerate(L1, 1)]
    open(os.path.join(SM, 'toc.md'), 'w', encoding='utf-8').write('\n'.join(toc) + '\n')
    img = os.path.join(DEST, 'images')
    if not os.path.isdir(img): shutil.copytree(os.path.join(SITE, 'images'), img)
    print('pages', len(PATH), 'sections', len(L1), 'missing translations', len(MISSING))
    for s in list(MISSING)[:10]: print('  MISSING', s[:80])


if __name__ == '__main__':
    main()
