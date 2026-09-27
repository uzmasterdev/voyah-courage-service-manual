# HTML-страницы руководства по ремонту -> блочная модель + уникальные китайские сегменты.
import json, re, os, sys, html
from html.parser import HTMLParser

SITE = os.environ.get('SM_SITE') or r"C:\Users\Admin\Downloads\Voyah Zhiyin 2024 v0.1\extracted\Руководство по ремонту электромобиля\site"
OUT = os.path.dirname(os.path.abspath(__file__))
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
BLOCK = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'ul', 'ol'}


def norm(s):
    s = s.replace('\xa0', ' ').replace('\u3000', ' ')
    s = re.sub(r'[ \t\r\n]+', ' ', s)
    s = re.sub(r'\*\*\s*\*\*', '', s)
    return s.strip()


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []      # ('p', text) | ('img', src) | ('table', rows)
        self.buf = []
        self.table = None     # list of rows; row = list of cells {text, rs, cs}
        self.cell = None
        self.link = None
        self.bold = 0
        self.skip = 0

    # --- text sink: cell buffer or paragraph buffer
    def sink(self):
        return self.cell['buf'] if self.cell is not None else self.buf

    def flush(self):
        if self.cell is not None:
            self.cell['buf'].append('<br>')
            return
        t = norm(''.join(self.buf))
        if t and t != '**':
            self.blocks.append(('p', t))
        self.buf = []

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ('script', 'style', 'head'):
            self.skip += 1; return
        if tag == 'table':
            self.flush(); self.table = []; return
        if tag == 'tr' and self.table is not None:
            self.table.append([]); return
        if tag in ('td', 'th') and self.table is not None:
            if not self.table: self.table.append([])
            self.cell = {'buf': [], 'rs': int(a.get('rowspan') or 1), 'cs': int(a.get('colspan') or 1)}
            return
        if tag == 'img':
            src = os.path.basename(a.get('src', ''))
            if self.cell is not None:
                self.cell['buf'].append(f'![](IMG:{src})')
            else:
                self.flush(); self.blocks.append(('img', src))
            return
        if tag == 'br':
            self.sink().append('\n' if self.cell is None else '<br>'); return
        if tag in ('strong', 'b'):
            self.sink().append('**'); return
        if tag == 'a':
            self.link = a.get('href', '').replace('.html', '')
            self.sink().append('['); return
        if tag in BLOCK:
            if self.cell is not None:
                if ''.join(self.cell['buf']).strip(): self.cell['buf'].append('<br>')
            else:
                self.flush()

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'):
            self.skip -= 1; return
        if tag in ('td', 'th') and self.cell is not None:
            t = norm(''.join(self.cell['buf']))
            t = re.sub(r'^(<br>\s*)+|(\s*<br>)+$', '', t)
            t = re.sub(r'(\s*<br>\s*){2,}', '<br>', t)
            self.table[-1].append({'t': t, 'rs': self.cell['rs'], 'cs': self.cell['cs']})
            self.cell = None; return
        if tag == 'table' and self.table is not None:
            rows = [r for r in self.table if r]
            if rows: self.blocks.append(('table', rows))
            self.table = None; return
        if tag in ('strong', 'b'):
            self.sink().append('**'); return
        if tag == 'a':
            self.sink().append(f'](#{self.link})'); self.link = None; return
        if tag in BLOCK and self.cell is None:
            self.flush()

    def handle_data(self, d):
        if self.skip: return
        self.sink().append(d)

    def close(self):
        super().close(); self.flush()


def segs_of(text):
    """Сегменты для перевода: строки абзаца / ячейки (по <br>/\\n), содержащие иероглифы."""
    for part in re.split(r'<br>|\n|!\[\]\(IMG:[^)]*\)', text):
        part = part.strip()
        if CJK.search(part): yield part


def main():
    c = json.load(open(os.path.join(SITE, 'content.json'), encoding='utf-8'))
    pages = {}
    segs = {}
    for pid, meta in c['flat_pages'].items():
        p = P(); p.feed(open(os.path.join(SITE, meta['page_file']), encoding='utf-8').read()); p.close()
        pages[pid] = p.blocks
        for kind, v in p.blocks:
            if kind == 'p':
                for s in segs_of(v): segs[s] = segs.get(s, 0) + 1
            elif kind == 'table':
                for r in v:
                    for cell in r:
                        for s in segs_of(cell['t']): segs[s] = segs.get(s, 0) + 1
        for n in meta['path_names']:
            if CJK.search(n): segs[n] = segs.get(n, 0) + 1

    def walk(nodes):
        for n in nodes:
            if CJK.search(n['name_zh']): segs[n['name_zh']] = segs.get(n['name_zh'], 0) + 1
            walk(n['children'])
    walk(c['tree'])
    json.dump({'tree': c['tree'], 'flat': c['flat_pages'], 'pages': pages},
              open(os.path.join(OUT, 'model.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(segs, open(os.path.join(OUT, 'segments.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    n = sum(len(CJK.findall(s)) for s in segs)
    print('pages', len(pages), 'segments', len(segs), 'cjk chars', n)


if __name__ == '__main__':
    main()
