"""Đổi tên MC mặc định trong global-metadata.dat (IL2CPP metadata v38+).
Metadata v38+ dùng bảng literal 4 byte/dataIndex; độ dài literal = dataIndex kế tiếp - dataIndex
hiện tại. Vì vậy để rút ngắn chuỗi, phải dời phần data phía sau lên và trừ dataIndex của các
literal sau — không thể chỉ ghi đè tại chỗ như v24-v31.
Dùng: python patch_meta_name.py            -> xem trước
      python patch_meta_name.py --apply    -> ghi dist/global-metadata.dat
      python patch_meta_name.py --apply --install
"""
import argparse, json, os, shutil, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SANITY = 0xFAB11BAF


def read_header(d):
    sanity, ver = struct.unpack_from('<Ii', d, 0)
    if sanity != SANITY:
        raise SystemExit('Không phải global-metadata.dat (sanity %08X)' % sanity)
    if ver < 38:
        raise SystemExit('Chỉ hỗ trợ metadata v38+ (file là v%d)' % ver)
    lit_off, lit_size, lit_count = struct.unpack_from('<III', d, 8)
    data_off, data_size, data_count = struct.unpack_from('<III', d, 20)
    return ver, lit_off, lit_size, lit_count, data_off, data_size, data_count


def parse(d):
    ver, lit_off, lit_size, lit_count, data_off, data_size, data_count = read_header(d)
    n = lit_size // 4
    dis = [struct.unpack_from('<I', d, lit_off + i * 4)[0] for i in range(n)]
    def text(i):
        di = dis[i]
        ln = (dis[i + 1] - di) if i + 1 < n else (data_size - di)
        return d[data_off + di:data_off + di + ln]
    return (ver, lit_off, lit_size, lit_count, data_off, data_size, data_count, n, dis, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', default='アリア')
    ap.add_argument('--new', default='Aria')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--install', action='store_true')
    a = ap.parse_args()

    cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    meta_rel = 'Data/Managed/Metadata/global-metadata.dat'
    romfs = os.path.expandvars(cfg['romfs_dir'].strip().strip('"'))
    src = os.path.join(romfs, *meta_rel.split('/'))
    if not os.path.isfile(src):
        raise SystemExit('Không thấy %s' % src)
    orig = open(src, 'rb').read()
    d = bytearray(orig)
    (ver, lit_off, lit_size, lit_count, data_off, data_size, data_count, n, dis, text) = parse(d)
    old_b, new_b = a.old.encode('utf-8'), a.new.encode('utf-8')
    if len(new_b) > len(old_b):
        raise SystemExit('Chuỗi mới dài hơn chuỗi cũ (%d > %d byte) — không hỗ trợ' % (len(new_b), len(old_b)))
    old_texts = [bytes(text(i)) for i in range(n)]          # chụp trước khi sửa
    hits = [i for i in range(n) if old_texts[i] == old_b]
    if len(hits) != 1:
        raise SystemExit('Cần đúng 1 literal %r, thấy %d' % (a.old, len(hits)))
    idx = hits[0]
    di = dis[idx]
    ln = dis[idx + 1] - di
    delta = len(old_b) - len(new_b)
    print('metadata v%d: %d literal | index %d di %d len %d (file 0x%X)' % (ver, n, idx, di, ln, data_off + di))
    print('   %r -> %r  (bỏ %d byte)' % (a.old, a.new, delta))
    if delta == 0:
        print('Không có gì để làm')
        return

    # Dời phần data sau literal lên delta byte
    blob = bytes(d[data_off:data_off + data_size])
    new_blob = blob[:di] + new_b + blob[di + ln:]
    assert len(new_blob) == data_size - delta
    d[data_off:data_off + data_size] = new_blob + b'\0' * delta
    struct.pack_into('<I', d, 24, data_size - delta)          # stringLiteralData.size
    for i in range(n):
        if dis[i] > di:
            struct.pack_into('<I', d, lit_off + i * 4, dis[i] - delta)

    # kiểm tra lại toàn bộ literal
    (ver2, lit_off2, _, _, data_off2, data_size2, _, n2, dis2, text2) = parse(d)
    bad = []
    for i in range(n2):
        want = new_b if i == idx else old_texts[i]
        got = text2(i)
        if got != want:
            bad.append((i, want, got))
            if len(bad) > 5:
                break
    if bad:
        raise SystemExit('Sai literal sau khi vá: %r' % bad[:3])
    if (ver2, lit_off2, data_off2, data_size2, n2) != (ver, lit_off, data_off, data_size - delta, n):
        raise SystemExit('Header/size không khớp sau khi vá')
    print('   kiểm tra: %d/%d literal giữ nguyên, literal %d = %r' % (n - 1, n, idx, a.new))

    if not a.apply:
        print('   chạy thử — thêm --apply để ghi')
        return
    out_dir = os.path.join(HERE, cfg.get('out_dir', 'dist'))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'global-metadata.dat')
    open(out, 'wb').write(bytes(d))
    print('   dist: %s (%.1f MB, file size %s)' % (out, len(d) / 1e6, 'giữ nguyên' if len(d) == len(orig) else 'ĐỔI'))

    if a.install:
        tid = cfg.get('title_id', '').strip()
        parent = cfg.get('mod_parent', '').replace('<TITLE_ID>', tid)
        mod_root = os.path.normpath(os.path.join(os.path.expandvars(parent), cfg.get('mod_name', 'English'), 'romfs'))
        target = os.path.normpath(os.path.join(mod_root, *meta_rel.split('/')))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(out, target)
        print('đã cài -> %s' % target)


if __name__ == '__main__':
    main()
