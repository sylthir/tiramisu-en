"""Kiểm tra và bổ sung thẻ trong bản dịch.
- restore_dic(): thêm <dic=N>...</dic> còn thiếu. Cách dịch của từng tip được học từ các dòng đã có thẻ đúng trong
  chính file; nếu chưa có thì dùng title trong Dic_terms, chỉ khi cụm đó thật sự xuất hiện trong bản dịch.
- tag_diff(): so thẻ giữa gốc và bản dịch, bỏ qua <ruby>. Khác biệt còn lại được tô màu đỏ nhạt."""
import re
from collections import Counter, defaultdict

TAG = re.compile(r'</?[A-Za-z]+(?:=[^>]*)?>|\{\d+\}|\[[^\]]+\]')
RUBYT = re.compile(r'</?ruby(?:=[^>]*)?>')
TIPS = re.compile(r'<dic=(\d+)>(.*?)</dic>', re.S)
HONOR = r'(?:-(?:san|kun|chan|sama|senpai))?'


def _count(s):
    s = RUBYT.sub('', s)
    c = Counter()
    for m in TAG.findall(s):
        c[m] += 1
    return c


def tag_diff(jp, en):
    """-> (missing, extra) lists of tags, không tính <ruby>."""
    a, b = _count(jp or ''), _count(en or '')
    return list((a - b).elements()), list((b - a).elements())


def learn_dic(cells):
    """cells: iterable of (jp, en). -> {tip_id: Counter(english inner text)} từ các dòng đã có thẻ đúng."""
    learned = defaultdict(Counter)
    for jp, en in cells:
        if not jp or not en:
            continue
        for tid, _ in TIPS.findall(jp):
            m = re.search(r'<dic=%s>(.*?)</dic>' % tid, en, re.S)
            if m and m.group(1).strip():
                learned[tid][m.group(1)] += 1
    return learned


def _outside_tags(s, start, end):
    for m in TAG.finditer(s):
        if m.start() < end and start < m.end():
            return False
    return True


def _find(en, phrase):
    """Chỉ trả về vị trí khi cụm xuất hiện đúng MỘT lần ngoài thẻ (nếu mơ hồ thì bỏ qua, để người dịch xử lý)."""
    pat = re.compile(r'(?<![A-Za-z])' + re.escape(phrase) + r'(?![A-Za-z])', re.I)
    hits = [m for m in pat.finditer(en) if _outside_tags(en, m.start(), m.end())]
    if len(hits) == 1:
        return hits[0].start(), hits[0].end()
    return None


def restore_dic(jp, en, learned, titles):
    """Thêm các cặp <dic=N> còn thiếu. -> (new_en, added_count, unresolved_ids)."""
    added, unresolved = 0, []
    for tid, inner in TIPS.findall(jp or ''):
        if f'<dic={tid}>' in en:
            continue
        cands = []
        if learned.get(tid):
            cands += [p for p, _ in learned[tid].most_common(3)]
        t = titles.get(tid)
        if t:
            cands.append(t)                      # chỉ dùng title đầy đủ, không đoán theo từng từ
        placed = False
        for ph in cands:
            span = _find(en, ph)
            if span is None and ph:
                hits = [m for m in re.finditer(r'(?<![A-Za-z])' + re.escape(ph) + HONOR + r'(?![A-Za-z])', en, re.I)
                        if _outside_tags(en, m.start(), m.end())]
                span = (hits[0].start(), hits[0].end()) if len(hits) == 1 else None
            if span:
                s, e = span
                en = en[:s] + '<dic=%s>' % tid + en[s:e] + '</dic>' + en[e:]
                added += 1
                placed = True
                break
        if not placed:
            unresolved.append(tid)
    return en, added, unresolved
