"""Đọc "Miramisu Eng.xlsx" (cột C) và ghi bản dịch vào các bundle -> dist/ (và chép vào thư mục mod nếu --install).
Dùng:  python build.py            build ra dist/
       python build.py --install  build rồi chép vào thư mục mod của giả lập (cần title_id + install_subdir trong config.json)
       python build.py --no-layout   không ngắt dòng / không đổi cỡ chữ (giữ nguyên bản dịch)"""
import argparse, json, os, re, shutil, sys
import openpyxl

import gamedata as gd
import scenario as sc
import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ID_UNIT = re.compile(r'^\d\d_\d\d\|\d+$')


def read_workbook(path):
    trans, jp, labels, dics = {}, {}, {}, {}
    wb = openpyxl.load_workbook(path, read_only=True)
    for ws in wb.worksheets:
        it = ws.iter_rows(values_only=True)
        hdr = next(it, None)
        if not hdr or hdr[0] != 'ID':
            continue
        ci = next((i for i, h in enumerate(hdr) if h in ('Bản dịch tiếng Anh', 'Tiếng Anh', 'Bản dịch')), 2)
        for row in it:
            if not row or not row[0] or row[0] == 'speaker' or len(row) <= ci:
                continue
            rid, v = str(row[0]), row[ci]
            if ID_UNIT.match(rid):
                jp[rid] = str(row[1] or '')
                if v is not None and str(v).strip():
                    trans[rid] = str(v).replace('\r\n', '\n').strip()
            elif rid.startswith('Speaker|') and v is not None and str(v).strip():
                labels[rid[8:]] = str(v).strip()
    return trans, jp, labels


def label_map(labels, mode):
    if mode != 'display_only':
        return labels
    out = {}                                               # chỉ đổi phần hiển thị (sau dấu /), giữ phần định danh gốc
    for k, v in labels.items():
        if '/' in k and '/' in v:
            out[k] = k.split('/')[0] + '/' + v.split('/', 1)[1]
        else:
            out[k] = v
    return out


def main():
    cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=cfg['workbook'])
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--no-layout', action='store_true')
    a = ap.parse_args()
    if a.no_layout:
        cfg['layout'] = dict(cfg.get('layout', {}), enabled=False)
    os.makedirs(os.path.join(HERE, 'logs'), exist_ok=True)
    fh = open(os.path.join(HERE, 'logs', 'latest.log'), 'w', encoding='utf-8')

    def log(msg):
        print(msg)
        fh.write(msg + '\n')
    trans, jp, labels = read_workbook(os.path.join(HERE, a.xlsx))
    labels = label_map(labels, cfg.get('speaker_mode', 'translate_all'))
    log('đọc %d dòng đã dịch, %d nhãn người nói' % (len(trans), len(labels)))
    # kiểm tra thẻ
    warns = []
    for rid, vi in trans.items():
        for e in tag_check(jp.get(rid, ''), vi):
            warns.append('%s: %s' % (rid, e))
    bundles = gd.load_all(os.path.join(HERE, cfg['source_dir']), cfg['bundles'])
    out_dir = os.path.join(HERE, cfg['out_dir'])
    os.makedirs(out_dir, exist_ok=True)
    written, overflow, missing = [], [], []
    for b in bundles:
        out = os.path.join(out_dir, b.key)
        st = patch.patch_bundle(b, trans, labels, cfg, out, log, jpmap=jp)
        if st:
            written.append(out)
            overflow += st['overflow']
            missing += st.get('missing', [])
            if st['warn']:
                log('  ! %d cảnh báo khi vá ScenarioData ở %s' % (st['warn'], b.key))
    if warns:
        log('\n%d CẢNH BÁO thẻ (build vẫn chạy):' % len(warns))
        for w in warns[:300]:
            log('  ' + w)
    if overflow:
        log('\n%d câu vẫn tràn khung dù đã thu nhỏ tối đa (nên rút gọn bản dịch):' % len(overflow))
        for w in overflow[:300]:
            log('  ' + w)
    if missing:
        log('\n%d dòng bị bỏ qua vì chữ gốc trong game khác với cột B (game đã update? chạy lại MAKE_WORKBOOK --merge):' % len(missing))
        for w in missing[:100]:
            log('  ' + w)
    if not written:
        sys.exit('Chưa có bản dịch nào để build.')
    log('OK -> %s' % out_dir)
    if a.install:
        install(cfg, written, log)


def tag_check(src, dst):
    """Thẻ nguồn phải còn đủ trong bản dịch ([主人公], <dic=N>, <sprite>, ...). <ruby> không bắt buộc."""
    from collections import Counter
    T = re.compile(r'</?[A-Za-z]+(?:=[^>]*)?>|\[[^\]]+\]')
    def cnt(s):
        c = Counter()
        for m in T.findall(s or ''):
            if m.startswith(('<ruby', '</ruby')):
                continue
            c[m] += 1
        return c
    a, b = cnt(src), cnt(dst)
    errs = []
    if a - b:
        errs.append('thiếu thẻ: ' + ' '.join((a - b).elements()))
    if b - a:
        errs.append('thừa thẻ: ' + ' '.join((b - a).elements()))
    return errs


def find_in_romfs(romfs, name):
    """Tìm đường dẫn tương đối của bundle `name` (không đuôi) trong romfs gốc. -> chuỗi như 'Data/xxx' hoặc None."""
    hits = []
    for root, _, files in os.walk(romfs):
        for f in files:
            if f == name or f.lower() == name.lower():
                rel = os.path.relpath(os.path.join(root, f), romfs)
                hits.append(rel.replace('\\', '/'))
    if len(hits) > 1:
        raise SystemExit('Trùng tên %s trong romfs: %s' % (name, ', '.join(hits)))
    return hits[0] if hits else None


def install(cfg, files, log):
    """Chép bundle đã vá vào: <mod_parent>/<mod_name>/romfs/<đúng đường dẫn như trong romfs gốc>."""
    tid = cfg.get('title_id', '').strip()
    romfs = os.path.expandvars(cfg.get('romfs_dir', '').strip().strip('"'))
    if not tid:
        log('Chưa cài: điền title_id trong config.json')
        return
    if not romfs or not os.path.isdir(romfs):
        log('Chưa cài: điền romfs_dir trong config.json = thư mục romfs gốc của game (chứa scenario01...)')
        return
    parent = os.path.expandvars(cfg['mod_parent'].replace('<TITLE_ID>', tid)).replace('/', os.sep)
    mod_root = os.path.join(parent, cfg['mod_name'], 'romfs')
    missing = []
    for f in files:
        name = os.path.basename(f)
        rel = find_in_romfs(romfs, name)
        if rel is None:
            missing.append(name)
            continue
        dst = os.path.join(mod_root, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(f, dst)
        log('đã cài %s -> %s' % (name, dst))
    if missing:
        log('KHÔNG tìm thấy trong romfs_dir: ' + ', '.join(missing))


if __name__ == '__main__':
    main()
