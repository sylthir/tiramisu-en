"""Phân tích kịch bản Le Mirage Mystique (dạng text có lệnh [..], tên người nói 【..】).
- parse(): tách các "đơn vị" cần dịch (thoại, lời dẫn, lựa chọn [seladd]).
- to_markup()/from_markup(): chuyển furigana [漢字'かな] và từ điển [dic ...] sang thẻ dễ dịch rồi đổi ngược lại.
- layout(): ngắt dòng tiếng Anh theo độ rộng, tự giảm cỡ chữ <size=NN%> nếu tràn khung.
- apply(): thay bản dịch vào danh sách dòng, trả về bảng đổi số dòng cũ -> mới."""
import json
import re

CJK = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
CMD_WHOLE = re.compile(r'^(?:\[[^\]]*\])+\s*$')
DIC = re.compile(r'\[dic no=(\d+) text=([^\]]*)\]')
RUBY_BR = re.compile(r"\[([^\[\]'=\s]+)'([^\[\]'=]*)\]")
RUBY_TAG = re.compile(r'<ruby=([^>]*)>(.*?)</ruby>', re.S)
DIC_TAG = re.compile(r'<dic=(\d+)>(.*?)</dic>', re.S)
SELADD = re.compile(r'^\[seladd text="((?:[^"\\]|\\.)*)"(.*)\]\s*$')
TAGS = re.compile(r'<[^>]*>')
TOKEN = re.compile(r'<[^>]*>|\[[^\]]*\]|[^\s]+')      # thẻ <..>/[..] luôn là 1 token, không bị cắt giữa chừng


def kind(line):
    s = line.strip()
    if not s:
        return 'blank'
    if line.startswith(';'):
        return 'comment'
    if line.startswith('@'):
        return 'at'
    if line.startswith('*'):
        return 'label'
    if line.startswith('【') and line.rstrip().endswith('】'):
        return 'spk'
    if line.startswith('['):
        rest = line[line.index(']') + 1:].strip(' \u3000') if ']' in line else ''
        if CMD_WHOLE.match(line) or (rest and set(rest) <= set(']|')):
            first = line[1:line.index(']')]
            head = first.split(' ')[0]
            if "'" in head or first == '主人公' or first.startswith('dic '):
                return 'text'
            return 'cmd'
        return 'text'
    return 'text'


class Unit:
    __slots__ = ('start', 'end', 'typ', 'spk_idx', 'label', 'lines', 'scene')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def parse(L):
    """-> list[Unit]. start/end là chỉ số dòng (end không gồm). Với thoại, start là dòng 【..】, lines là các dòng chữ."""
    units, i, n = [], 0, len(L)
    scene = ''
    while i < n:
        ln = L[i]
        if ln.lstrip().startswith('/*'):                       # khối ghi chú /* ... */ của người làm game
            while i < n and '*/' not in L[i]:
                i += 1
            i += 1
            continue
        if ln.startswith(';//●'):
            scene = ln[4:].strip()
        k = kind(ln)
        if k == 'spk':
            j = i + 1
            while j < n and kind(L[j]) == 'text':
                j += 1
            if j > i + 1:
                units.append(Unit(start=i, end=j, typ='dlg', spk_idx=i, label=ln.strip()[1:-1], lines=L[i + 1:j], scene=scene))
            i = max(j, i + 1)
            continue
        if k == 'text':
            j = i
            while j < n and kind(L[j]) == 'text' and not L[j].lstrip().startswith('/*'):
                j += 1
            units.append(Unit(start=i, end=j, typ='nar', spk_idx=None, label='', lines=L[i:j], scene=scene))
            i = j
            continue
        if ln.startswith('[seladd '):
            m = SELADD.match(ln)
            if m:
                units.append(Unit(start=i, end=i + 1, typ='sel', spk_idx=None, label='', lines=[m.group(1)], scene=scene))
        i += 1
    return units


# ---------------------------------------------------------------- thẻ
def _ruby_value(v):
    if "'" in v:
        b, r = v.split("'", 1)
        return '<ruby=%s>%s</ruby>' % (r, b)
    return v


def to_markup(text):
    text = DIC.sub(lambda m: '<dic=%s>%s</dic>' % (m.group(1), _ruby_value(m.group(2))), text)
    return RUBY_BR.sub(lambda m: '<ruby=%s>%s</ruby>' % (m.group(2), m.group(1)), text)


def from_markup(text, strip_ruby=True):
    def dic(m):
        inner = RUBY_TAG.sub(r'\2', m.group(2))
        if re.search(r'[\s\]"]', inner):
            inner = inner.replace('"', "'")
            return '[dic no=%s text="%s"]' % (m.group(1), inner)
        return '[dic no=%s text=%s]' % (m.group(1), inner)
    text = DIC_TAG.sub(dic, text)
    if strip_ruby:
        text = RUBY_TAG.sub(r'\2', text)
        text = re.sub(r'</?ruby(?:=[^>]*)?>', '', text)
    return text


def visible_len(s):
    s = re.sub(r'\[[^\]]*\]', 'XXXXXX', s)               # [主人公] = tên người chơi (~6 ký tự)
    return len(TAGS.sub('', s))


# ---------------------------------------------------------------- ngắt dòng / cỡ chữ
def _wrap(text, width):
    lines, cur = [], ''
    for tok in TOKEN.findall(text):                        # giữ nguyên thẻ có dấu cách, vd <sprite name=".." color=#FFF>
        cand = (cur + ' ' + tok) if cur else tok
        if cur and visible_len(cand) > width:
            lines.append(cur)
            cur = tok
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def layout(text, cfg):
    """Ngắt dòng + đặt cỡ chữ chung.
    - cfg['width'] = số ký tự mỗi dòng ở cỡ 100% (đo từ khung trong game).
    - cfg['scale_pct'] = cỡ chữ mong muốn (vd 115 = to hơn 15%). Áp cho mọi dòng bằng thẻ <size=..%>.
    - Nếu vượt cfg['max_lines'] thì hạ cỡ theo từng bước trong cfg['steps_pct'] (vd 110, 105, 100...) cho tới khi vừa.
    -> (lines, pct đã dùng, vừa khung?)"""
    text = text.replace('\r\n', '\n').strip('\n')
    if not cfg.get('enabled', True):
        return text.split('\n'), None, True
    if cfg.get('keep_newlines', False) and '\n' in text:
        parts = [x.strip() for x in text.split('\n') if x.strip()]
    else:
        parts = [re.sub(r'\s+', ' ', text).strip()]
    base_w = int(cfg.get('width', 41))
    maxl = int(cfg.get('max_lines', 2))
    want = int(cfg.get('scale_pct', 100))
    steps = [p for p in cfg.get('steps_pct', [110, 105, 100, 95, 90, 85, 80]) if p <= want]
    cands = [want] + [p for p in steps if p != want]
    open_t, close_t = cfg.get('size_open', '<size={pct}%>'), cfg.get('size_close', '</size>')
    chosen, fits, lines = None, False, []
    for pct in cands:
        w = int(base_w * 100 / pct)
        lines = []
        for p in parts:
            lines += _wrap(p, w)
        chosen = pct
        if len(lines) <= maxl:
            fits = True
            break
    if chosen == 100 or chosen is None:
        return lines, None, fits
    lines = [open_t.format(pct=chosen) + x + close_t for x in lines]
    return lines, chosen, fits


# ---------------------------------------------------------------- áp bản dịch
def esc_sel(t):
    return t.replace('"', "'").replace('\n', ' ')


def apply(L, stem, trans, labels, cfg, jpmap=None):
    """L: các dòng gốc. trans: {id: bản dịch}. labels: {nhãn JP: nhãn EN}.
    -> (newL, old2new, repl, stats). repl = [(dòng gốc..., dòng mới...)] theo thứ tự để vá scriptText."""
    units = parse(L)
    out, repl, old2new = [], [], [0] * (len(L) + 1)
    stats = dict(units=0, lines=0, labels=0, choices=0, shrunk=0, overflow=[], missing=[])
    lay = cfg.get('layout', {})
    strip_ruby = cfg.get('strip_ruby', True)
    pos, k = 0, 0
    for u in units:
        # dòng không đổi trước đơn vị
        while pos < u.start:
            old2new[pos] = len(out); out.append(L[pos]); pos += 1
        old = L[u.start:u.end]
        rid = '%s|%d' % (stem, u.start + 1)
        tr = trans.get(rid)
        if tr and jpmap is not None:                           # kịch bản gốc đã đổi so với Excel -> bỏ qua dòng này
            cur = to_markup(u.lines[0] if u.typ == 'sel' else '\n'.join(u.lines))
            if re.sub(r'\s+', '', jpmap.get(rid, '')) != re.sub(r'\s+', '', cur):
                stats['missing'].append(rid)
                tr = None
        new = None
        if u.typ == 'sel':
            if tr:
                new = [re.sub(r'text="(?:[^"\\]|\\.)*"', lambda m: 'text="%s"' % esc_sel(from_markup(tr, strip_ruby)).replace('\\', '/'),
                              old[0], count=1)]
                stats['choices'] += 1
        else:
            body = u.lines
            if tr:
                text = from_markup(tr, strip_ruby)
                body, pct, fits = layout(text, lay)
                stats['lines'] += 1
                if pct:
                    stats['shrunk'] += 1
                if not fits:
                    stats['overflow'].append(rid)
            head = []
            if u.typ == 'dlg':
                en = labels.get(u.label)
                head = ['【%s】' % en] if en else [L[u.start]]
                if en:
                    stats['labels'] += 1
            if tr or head != [L[u.start]] if u.typ == 'dlg' else bool(tr):
                new = head + list(body)
        if new is None:
            new = old
        else:
            repl.append((tuple(old), tuple(new)))
            stats['units'] += 1
        old2new[u.start] = len(out)
        out.extend(new)
        pos = u.end
        for q in range(u.start + 1, u.end):
            old2new[q] = len(out) - 1
    while pos < len(L):
        old2new[pos] = len(out); out.append(L[pos]); pos += 1
    old2new[len(L)] = len(out)
    return out, old2new, repl, stats


def apply_repl(S, repl):
    """Áp cùng các thay thế lên danh sách dòng scriptText (đã bỏ comment). -> (new S, số đơn vị không tìm thấy)."""
    out, ptr, miss = list(S), 0, 0
    for old, new in repl:
        n = len(old)
        idx = next((i for i in range(ptr, len(out) - n + 1) if tuple(out[i:i + n]) == old), None)
        if idx is None:
            miss += 1
            continue
        out[idx:idx + n] = list(new)
        ptr = idx + len(new)
    return out, miss


def unit_text(L, s):
    """Quy tắc của game: dòng 【..】 (nếu có) + các dòng chữ đến dòng trống. -> (talkName, text)."""
    sp, k = '', s
    if k < len(L) and L[k].startswith('【'):
        sp = L[k]; k += 1
    buf = []
    while k < len(L) and kind(L[k]) == 'text':          # chữ kết thúc khi gặp dòng trống, lệnh [..], nhãn, comment
        buf.append(L[k]); k += 1
    return sp, '\n'.join(buf)


def patch_entry(x, newL, old2new, repl, sel_changed):
    """Cập nhật một phần tử trong ScenarioData.target. -> số cảnh báo."""
    oldL = x['scriptText_Line']
    warn = 0
    S = x['scriptText'].replace('\r', '').split('\n')
    S2, miss = apply_repl(S, repl)
    warn += miss
    for i, ll in enumerate(list(x['loadLine'])):
        orig_ok = ll < len(oldL) and i < len(x['text']) and i < len(x['talkName']) and unit_text(oldL, ll) == (x['talkName'][i], x['text'][i])
        nl = old2new[ll] if ll < len(old2new) else ll
        x['loadLine'][i] = nl
        if orig_ok:
            x['talkName'][i], x['text'][i] = unit_text(newL, nl)
    for i, sl in enumerate(x['selLine']):
        if sl is not None and sl >= 0 and sl < len(old2new):
            x['selLine'][i] = old2new[sl]
    if sel_changed:
        for i, st in enumerate(x['selText']):
            if not st:
                continue
            line = x['selLine'][i] if x['selLine'][i] >= 0 else x['loadLine'][i]
            j = line - 1
            ch = []
            while j >= 0 and (newL[j].startswith('[seladd ') or re.match(r'\[(?:if|ifend|else|elsif)\b', newL[j])):
                if newL[j].startswith('[seladd '):          # lựa chọn có điều kiện nằm giữa [if]..[ifend]
                    m = SELADD.match(newL[j])
                    ch.append(m.group(1) if m else '')
                j -= 1
            ch.reverse()
            try:
                old = json.loads(st)['target']
            except Exception:
                continue
            if len(ch) == len(old):
                x['selText'][i] = json.dumps({'target': ch}, ensure_ascii=False, separators=(',', ':'))
            else:
                warn += 1
    x['scriptText_Line'] = newL
    x['scriptText'] = '\n'.join(S2)
    return warn
