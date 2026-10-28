"""Sửa các ô đã dịch theo bảng xưng hô (xung_ho.tsv): đúng tên/thứ tự tên, Mr./Ms., đại từ he/she, bỏ dòng trống thừa.
Dùng:  python fix_workbook.py            (sửa Translation_EN.xlsx tại chỗ, có file backup)
       python fix_workbook.py --xlsx a.xlsx --out b.xlsx"""
import argparse, json, os, re, shutil, sys
import openpyxl
from openpyxl.styles import PatternFill
from xungho import Table, fix_text, fit_sheet
from make_workbook import GUIDE
from tagfix import learn_dic, restore_dic, tag_diff

HERE = os.path.dirname(os.path.abspath(__file__))
RED = PatternFill('solid', fgColor='F8CBAD')
YELLOW = PatternFill('solid', fgColor='FFF3CF')
LIGHT_RED = PatternFill('solid', fgColor='FADBD8')      # khác thẻ ngoài <param>: đỏ nhạt
KEEP_PREFIX = ('Auto:', 'KT đại từ', 'Lỗi thẻ', 'Thiếu thẻ', 'Thừa thẻ', 'Đã thêm thẻ')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=cfg['workbook'])
    ap.add_argument('--out')
    a = ap.parse_args()
    path = os.path.join(HERE, a.xlsx)
    out = os.path.join(HERE, a.out) if a.out else path
    tb = Table()
    print('đang mở', path, '...')
    wb = openpyxl.load_workbook(path)
    titles, pairs = {}, []
    if 'Dic_terms' in wb.sheetnames:
        for r in wb['Dic_terms'].iter_rows(min_row=2, values_only=True):
            m = re.match(r'Dic\|(\d+)$', str(r[0] or ''))
            if m and r[2]:
                titles[m.group(1)] = str(r[2])
    for ws in wb.worksheets:
        if ws.title in ('TOC', 'Huong_dan'):
            continue
        for r in ws.iter_rows(min_row=2, values_only=True):
            if r and r[0] and r[0] != 'speaker' and r[1] and r[2]:
                pairs.append((str(r[1]), str(r[2])))
    learned = learn_dic(pairs)
    # Tên người nói: lấy từ Speaker_labels và Character_names để đồng bộ vào các dòng 'speaker' của sheet tập
    label_en = {}
    for sh in ('Speaker_labels', 'Character_names'):
        if sh in wb.sheetnames:
            for r in wb[sh].iter_rows(min_row=2, values_only=True):
                if r and r[1] and r[2] and str(r[2]).strip():
                    label_en.setdefault(str(r[1]), str(r[2]).strip())
    st = dict(cells=0, changed=0, auto=0, flagged=0, speakers=0, names=0, named=0, tips=0, red=0, kt=0)
    report = []                       # (sheet, id, before, after, notes)
    for ws in wb.worksheets:
        if ws.title in ('TOC', 'Huong_dan'):
            continue
        hdr = [c.value for c in ws[1]]
        if not hdr or hdr[0] != 'ID':
            continue
        ci = next((i for i, h in enumerate(hdr) if h in ('Bản dịch tiếng Anh', 'Tiếng Anh', 'Bản dịch')), 2) + 1
        ti = hdr.index('Loại text') + 1 if 'Loại text' in hdr else 4
        ni = hdr.index('Ghi chú của người dịch') + 1 if 'Ghi chú của người dịch' in hdr else None
        for row in range(2, ws.max_row + 1):
            rid = ws.cell(row, 1).value
            if not rid:
                continue
            jp = ws.cell(row, 2).value or ''
            if rid == 'speaker':
                name_en = label_en.get(str(jp)) or (tb.speaker(jp) or (None,))[0]
                if name_en and ws.cell(row, ci).value != name_en:
                    ws.cell(row, ci).value = name_en
                    st['speakers'] += 1
                continue
            if ws.title == 'Character_names':
                sp = tb.speaker(jp)
                if sp and ws.cell(row, ci).value != sp[0]:
                    ws.cell(row, ci).value = sp[0]
                    st['names'] += 1
                continue
            cell = ws.cell(row, ci)
            en = cell.value
            if not en or not str(en).strip():
                continue
            st['cells'] += 1
            typ = ws.cell(row, ti).value or ''
            new, notes = fix_text(tb, jp, str(en), typ)
            if any(tb.tok.get(w) for w in tb.names_in(str(en))):
                st['named'] += 1
            added = 0
            if '<dic=' in jp:
                new, added, unres = restore_dic(jp, new, learned, titles)
                if added:
                    notes.append('Đã thêm thẻ dic: %d' % added)
                    st['tips'] += added
            miss, extra = tag_diff(jp, new)
            if miss:
                notes.append('Thiếu thẻ: ' + ' '.join(miss))
            if extra:
                notes.append('Thừa thẻ: ' + ' '.join(extra))
            tag_flag = bool(miss or extra)
            if new != en:
                cell.value = new
                st['changed'] += 1
            if new != en or any(n.startswith(('KT', 'Auto', 'Thiếu', 'Thừa', 'Đã thêm')) for n in notes):
                report.append((ws.title, rid, str(en), new, '; '.join(notes)))
            if ni:
                nc = ws.cell(row, ni)
                old = [p for p in (nc.value or '').split(' | ') if p and not p.startswith(KEEP_PREFIX)]
                nc.value = ' | '.join(old + notes) or None
            flagged = any(n.startswith('KT') for n in notes) or tag_flag
            if tag_flag:
                cell.fill = LIGHT_RED
                st['red'] += 1
            elif any(n.startswith('KT') for n in notes):
                cell.fill = RED
                st['kt'] += 1
            else:
                cell.fill = YELLOW
            st['auto'] += any(n.startswith('Auto') for n in notes)
            st['flagged'] += flagged
    if 'Huong_dan' in wb.sheetnames:                  # cập nhật hướng dẫn mới nhất vào sheet
        hd = wb['Huong_dan']
        hd.delete_rows(2, hd.max_row)
        for a_, b_ in GUIDE:
            hd.append([a_, b_])
        hd.column_dimensions['A'].width = 24
        hd.column_dimensions['B'].width = 120
    for ws in wb.worksheets:
        fit_sheet(ws)                                   # mọi sheet đều fit to data
    tmp = out + '.tmp'
    try:
        wb.save(tmp)
        os.replace(tmp, out)
    except PermissionError:
        sys.exit('Không ghi được file (đang mở trong Excel?). Đóng Excel rồi chạy lại.')
    os.makedirs(os.path.join(HERE, 'logs'), exist_ok=True)
    rp = os.path.join(HERE, 'logs', 'xungho_report.txt')
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write('BÁO CÁO XƯNG HÔ - %d ô đã dịch được kiểm tra, %d ô có nhân vật trong bảng\n\n' % (st['cells'], st['named']))
        for sh, rid, before, after, notes in report:
            fh.write('[%s] %s\n  TRƯỚC: %s\n  SAU  : %s\n  GHI CHÚ: %s\n\n' % (sh, rid, before.replace('\n', ' / '), after.replace('\n', ' / '), notes or '-'))
    print('\n=== KẾT QUẢ KIỂM TRA XƯNG HÔ ===')
    print('đã rà %(cells)d ô đã dịch, trong đó %(named)d ô có nhân vật theo bảng xưng hô' % st)
    print('sửa tự động: %(changed)d ô (tên, Mr./Ms., he/she, dòng trống thừa, thẻ dic)' % st)
    print('thêm thẻ dic còn thiếu: %(tips)d thẻ' % st)
    print('đỏ nhạt (khác thẻ ngoài param): %(red)d ô' % st)
    print('đỏ đậm (nghi sai he/she, cần đọc lại): %(kt)d ô' % st)
    print('chi tiết từng ô: logs\\xungho_report.txt')
    if st['changed'] == 0 and st['flagged'] == 0 and st['tips'] == 0:
        print('không có lỗi nào để sửa: bản dịch hiện đã khớp bảng xưng hô.')

if __name__ == '__main__':
    main()
