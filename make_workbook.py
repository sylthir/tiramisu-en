"""Tạo "Miramisu Eng.xlsx" (cấu trúc giống bộ Translation_EN của tool Utage) từ các bundle kịch bản của game.
Dùng:  python make_workbook.py
       python make_workbook.py --merge cu.xlsx      (giữ bản dịch cũ theo ID)"""
import argparse, collections, json, os, re
import openpyxl
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import gamedata as gd
import scenario as sc
from xungho import Table, fit_widths

HERE = os.path.dirname(os.path.abspath(__file__))
HEAD = ['ID', 'Tiếng Nhật / gốc', 'Bản dịch tiếng Anh', 'Loại text', 'Ngữ cảnh', 'Ghi chú của người dịch']
F_HEAD = Font(name='Arial', size=11, bold=True, color='FFFFFF')
F_BODY = Font(name='Arial', size=11, color='252525')
F_SPK = Font(name='Arial', size=11, italic=True, color='7F7F7F')
FILL_HEAD = PatternFill('solid', fgColor='314F4C')
FILL_TR = PatternFill('solid', fgColor='FFF3CF')
WRAP = Alignment(wrap_text=True, vertical='top')
BAD = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
UI_DESC = {'Character_names': 'Tên nhân vật (nhãn 【..】 ở khung thoại, áp cho mọi chỗ)',
           'Speaker_labels': 'Nhãn người nói khác (NPC, ？？？, A/B...)',
           'Dic_terms': 'Từ điển trong game ([dic no=..]): thuật ngữ được tô sáng',
           'Dictionary': 'Từ điển trong game: tên mục + giải thích (Dictionary TextAsset)'}
GUIDE = [
    ('Bản dịch', 'Chỉ sửa cột C (tiếng Anh, ô vàng). Cột F dành cho ghi chú. Giữ nguyên cột A (ID) và B (gốc). ID = tên file kịch bản|số dòng bắt đầu.'),
    ('Tiến độ', 'TOC chỉ đếm dòng có ID. Dòng speaker là ngữ cảnh, không tính tiến độ và không được chèn vào game.'),
    ('Tên nhân vật', 'Sheet Character_names / Speaker_labels: nhãn 【..】 ở khung thoại. Sửa ở đây là đổi trong toàn game (cột Arg: mọi dòng thoại dùng nhãn đó). '
                     'Nhãn dạng A/B (vd ゼノ/？？？): A là nhân vật thật, B là tên hiển thị. Tên theo bảng xưng hô xung_ho.tsv (Given Family).'),
    ('Xưng hô / giới tính', 'Aria (nữ chính, người chơi), Ahès, Mavis là nữ (she/her). Các nhân vật có tên trong bảng là nam (he/him). NPC khác: suy từ tiếng Nhật (女の子, 母, 夫人...), không mặc định là nam.'),
    ('Lời dẫn', 'Dòng không có người nói thường là nữ chính (Aria) kể ngôi thứ nhất (わたし). Chương DLC / extra có thể khác, hãy xem ngữ cảnh.'),
    ('Thẻ cần giữ', '[主人公] = tên người chơi (giữ nguyên). <dic=số>từ</dic> = từ điển (giữ thẻ, chỉ dịch chữ bên trong). <sprite name=..> giữ nguyên. <ruby=..> chỉ là furigana, được bỏ khi build.'),
    ('Dấu ngoặc', '「」 -> "..." ; （） -> (...) ; 『』 -> “...” ; lời dẫn không ngoặc.'),
    ('Ngắt dòng', 'Viết thoại thành 1 đoạn liền. Khi build, tool tự ngắt dòng theo config.json -> layout (width, max_lines) và tự giảm cỡ chữ <size=NN%> nếu quá 3 dòng.'),
    ('Dịch tự động', 'TRANSLATE.bat dịch các ô trống THEO LÔ bằng Groq / Gemini / DeepL (khoá trong .env). Luật dịch lấy từ sheet Huong_dan và xung_ho.tsv. Hết hạn mức thì dừng, lần sau chạy lại dịch tiếp. Dòng máy dịch có "MT:..." ở cột F.'),
    ('Sửa xưng hô', 'FIX_XUNGHO.bat rà lại các ô đã dịch: tên, Mr./Ms., he/she, dòng thừa, thẻ <dic>. Ô tô đỏ + ghi chú "KT đại từ" / "Lỗi thẻ" cần kiểm tra tay.'),
    ('Màu ô', 'Vàng: đã dịch. Đỏ nhạt: bản dịch khác thẻ gốc (thiếu/thừa). Đỏ đậm: nghi sai he/she.'),
    ('Build', 'BUILD_PATCH.bat -> dist\\ (các bundle đã vá). BUILD_AND_INSTALL.bat -> build rồi chép vào thư mục mod. Kiểm tra trong game: font, khung thoại, lựa chọn.'),
]


def clean(v):
    return BAD.sub('', v) if isinstance(v, str) else v


def read_old(paths):
    old = {}
    for p in paths or []:
        if p.lower().endswith('.json'):
            old.update({k: v for k, v in json.load(open(p, encoding='utf-8')).items() if v})
            continue
        wb = openpyxl.load_workbook(p, read_only=True)
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            hdr = next(it, None)
            if not hdr or hdr[0] != 'ID':
                continue
            ci = next((i for i, h in enumerate(hdr) if h in ('Bản dịch tiếng Anh', 'Tiếng Anh', 'Bản dịch')), 2)
            for row in it:
                if row and row[0] and row[0] != 'speaker' and len(row) > ci and row[ci] and str(row[ci]).strip():
                    old[row[0]] = str(row[ci])
    return old


def collect(cfg):
    bundles = gd.load_all(os.path.join(HERE, cfg['source_dir']), cfg['bundles'])
    scen = collections.OrderedDict()
    for b in bundles:
        for stem, x, L in b.entries():
            if stem not in gd.SKIP_STEMS:
                scen[stem] = L
    return collections.OrderedDict(sorted(scen.items()))


def build_sheets(scen, old, tb):
    en = lambda i, d='': old.get(i, d)
    labels, dics = collections.Counter(), {}
    for stem, L in scen.items():
        for u in sc.parse(L):
            if u.typ == 'dlg':
                labels[u.label] += 1
            for ln in (u.lines if u.typ != 'sel' else []):
                for m in sc.DIC.finditer(ln):
                    d = dics.setdefault(m.group(1), [collections.Counter(), '%s dòng %d' % (stem, u.start + 1)])
                    d[0][sc._ruby_value(m.group(2))] += 1
    sheets = collections.OrderedDict()
    chars, others = [], []
    for lab, n in labels.most_common():
        if lab == 'player':
            continue                                   # tên người chơi do game tự điền
        rid = 'Speaker|' + lab
        guess = tb.label_en(lab)
        is_char = '/' not in lab and tb.speaker(lab) is not None and guess
        row = [rid, lab, en(rid, guess), 'Tên nhân vật' if is_char else 'Người nói', '%d dòng thoại' % n,
               'Thay vào nhãn 【..】 của mọi dòng thoại có nhãn này']
        (chars if is_char else others).append(row)
    sheets['Character_names'] = chars
    sheets['Speaker_labels'] = others
    sheets['Dic_terms'] = [['Dic|' + k, v[0].most_common(1)[0][0], en('Dic|' + k), 'Từ điển', '%d lần, vd %s' % (sum(v[0].values()), v[1]),
                            'Dịch thuật ngữ; trong thoại giữ thẻ <dic=%s>..</dic>' % k] for k, v in sorted(dics.items(), key=lambda kv: int(kv[0]))]
    # Bảng từ điển đầy đủ (dictionary.json) — 2 dòng/mục: tên + giải thích
    dic_json = os.path.join(HERE, 'dict', 'dictionary.json')
    if os.path.exists(dic_json):
        term_en = {r[0][4:]: r[2] for r in sheets['Dic_terms'] if r[2]}
        rows = []
        for e in json.load(open(dic_json, encoding='utf-8'))['data']:
            no = str(e.get('no', ''))
            tid, xid = 'Dict|%s|title' % no, 'Dict|%s|text' % no
            ctx = 'no=%s / %s' % (no, e.get('category', ''))
            rows.append([tid, e.get('title', ''), en(tid, term_en.get(no, '')), 'Từ điển - tên', ctx, 'Tên mục'])
            rows.append([xid, e.get('text', ''), en(xid), 'Từ điển - giải thích', ctx, ''])
        sheets['Dictionary'] = rows

    # Truyện ngắn DLC (bundle novel/novel_aoc0x) — mỗi dòng truyện 1 dòng sheet
    for dlc in cfg.get('dlc', []):
        try:
            import UnityPy
            romfs = os.path.expandvars(dlc['romfs_dir'].strip().strip('"'))
            path = os.path.join(romfs, *dlc['bundle'].replace('\\', '/').split('/'))
            env = UnityPy.load(path)
            rows = []
            for o in env.objects:
                if o.type.name != 'TextAsset':
                    continue
                t = o.read(); name = t.m_Name; data = t.m_Script
                if isinstance(data, str):
                    data = data.encode('utf-8')
                txt = data.decode('utf-8-sig')
                for idx, line in enumerate(txt.replace('\r\n', '\n').split('\n')):
                    if not line.strip():
                        continue
                    rid = 'Novel|%s|%d' % (name, idx)
                    rows.append([rid, line, en(rid), 'Truyện ngắn DLC',
                                 '%s / dòng %d' % (name, idx + 1), ''])
            if rows:
                sheet = dlc.get('sheet', 'DLC_Novel')
                sheets[sheet] = rows
                UI_DESC[sheet] = 'Truyện ngắn DLC (%s)' % dlc['bundle']
        except Exception as e:
            print('! bỏ qua DLC %s: %s' % (dlc.get('title_id', '?'), e))
    lab_en = {r[1]: r[2] for r in chars + others}
    for stem, L in scen.items():
        rows = []
        for u in sc.parse(L):
            rid = '%s|%d' % (stem, u.start + 1)
            if u.typ == 'sel':
                rows.append([rid, sc.to_markup(u.lines[0]), en(rid), 'Lựa chọn', '%s / dòng %d / lựa chọn' % (stem, u.start + 1), ''])
                continue
            if u.typ == 'dlg':
                rows.append(['speaker', u.label, lab_en.get(u.label, ''), 'Người nói', '', ''])
            ctx = '%s / dòng %d / %s' % (stem, u.start + 1, '【%s】' % u.label if u.typ == 'dlg' else 'lời dẫn')
            if u.scene:
                ctx += ' / ' + u.scene
            rows.append([rid, sc.to_markup('\n'.join(u.lines)), en(rid), 'Thoại', ctx, ''])
        if rows:
            sheets[gd.sheet_name(stem)] = (stem, rows)
    return sheets


def write(sheets, path, title):
    wb = openpyxl.Workbook(write_only=True)
    names = list(sheets)

    def c(ws, v, font=F_BODY, fill=None, align=None, fmt=None):
        x = WriteOnlyCell(ws, value=clean(v))
        x.font = font
        if fill: x.fill = fill
        if align: x.alignment = align
        if fmt: x.number_format = fmt
        return x

    def rows_of(name):
        v = sheets[name]
        return v[1] if isinstance(v, tuple) else v
    toc = wb.create_sheet('TOC')
    for col, w in zip('ABCDEFG', (31.86, 11.57, 12.14, 13.43, 51, 15.57, 15.86)):
        toc.column_dimensions[col].width = w
    n_sheets = len(names)
    last = 6 + n_sheets
    toc.append([])
    toc.append([c(toc, title, Font(name='Arial', size=14, bold=True, color='252525'))])
    toc.append([c(toc, 'Điền bản dịch vào cột C màu vàng. Ô trống giữ nguyên text gốc.')])
    toc.append([c(toc, 'Dòng speaker là ngữ cảnh, không tính tiến độ và không được chèn vào game. Tên nhân vật sửa ở sheet Character_names / Speaker_labels.')])
    toc.append([c(toc, 'TỔNG', F_HEAD, FILL_HEAD), c(toc, '=SUM(B7:B%d)' % last, F_HEAD, FILL_HEAD),
                c(toc, '=SUM(C7:C%d)' % last, F_HEAD, FILL_HEAD), c(toc, '=C5/B5', F_HEAD, FILL_HEAD, fmt='0.0%'),
                c(toc, '', F_HEAD, FILL_HEAD), c(toc, 'Người sửa', F_HEAD, FILL_HEAD)])
    toc.append([c(toc, h, F_HEAD, FILL_HEAD) for h in ('Sheet', 'Số dòng', 'Đã dịch', 'Hoàn thành', 'Nội dung', 'Sửa dấu', 'Sửa từ')])
    for k, name in enumerate(names):
        rows = rows_of(name)
        n = len(rows) + 1
        real = sum(1 for r in rows if r[0] != 'speaker')
        if any(r[0] == 'speaker' for r in rows):
            f = '=COUNTIFS(%s!A2:A%d,"<>speaker",%s!A2:A%d,"<>",%s!C2:C%d,"<>")' % (name, n, name, n, name, n)
        else:
            f = '=B%d-COUNTBLANK(%s!C2:C%d)' % (7 + k, name, n)
        stem = sheets[name][0] if isinstance(sheets[name], tuple) else None
        toc.append([c(toc, name), c(toc, real), c(toc, f), c(toc, '=C%d/B%d' % (7 + k, 7 + k), fmt='0.0%'),
                    c(toc, UI_DESC.get(name) or gd.sheet_desc(stem))])
    for name in names:
        rows = rows_of(name)
        ws = wb.create_sheet(name)
        ws.freeze_panes = 'A2'
        for i, w in enumerate(fit_widths(HEAD, rows, max_w=60), 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.append([c(ws, h, F_HEAD, FILL_HEAD) for h in HEAD])
        for r in rows:
            spk = r[0] == 'speaker'
            f = F_SPK if spk else F_BODY
            ws.append([c(ws, r[0], f, align=WRAP), c(ws, r[1], f, align=WRAP),
                       c(ws, r[2] or None, f, None if spk else FILL_TR, WRAP),
                       c(ws, r[3], f, align=WRAP), c(ws, r[4] or None, f, align=WRAP), c(ws, r[5] or None, f, align=WRAP)])
    hd = wb.create_sheet('Huong_dan')
    hd.column_dimensions['A'].width = 24
    hd.column_dimensions['B'].width = 120
    hd.append([c(hd, 'Mục', F_HEAD, FILL_HEAD), c(hd, 'Cách dùng', F_HEAD, FILL_HEAD)])
    for a, b in GUIDE:
        hd.append([c(hd, a, Font(name='Arial', size=11, bold=True, color='252525'), align=WRAP), c(hd, b, align=WRAP)])
    wb.save(path)


def main():
    cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    ap = argparse.ArgumentParser()
    ap.add_argument('--merge', nargs='*', help='file xlsx/json cũ để chép bản dịch theo ID')
    ap.add_argument('--out', default=cfg['workbook'])
    a = ap.parse_args()
    old = read_old(a.merge)
    if a.merge:
        print('đọc %d bản dịch cũ' % len(old))
    scen = collect(cfg)
    sheets = build_sheets(scen, old, Table())
    write(sheets, os.path.join(HERE, a.out), cfg.get('game', 'Game') + ' - bản dịch tiếng Anh')
    rs = [r for v in sheets.values() for r in (v[1] if isinstance(v, tuple) else v)]
    print('đã ghi %s: %d sheet, %d dòng cần dịch, %d dòng đã có tiếng Anh' % (
        a.out, len(sheets), sum(1 for r in rs if r[0] != 'speaker'), sum(1 for r in rs if r[0] != 'speaker' and r[2])))


if __name__ == '__main__':
    main()
