"""Vá giao diện trong romfs:
  1. Nới khung thoại: RectTransform c?a Text trong level9 (Message(Normal)/Novel/SS) + prefab trong resources.assets.
  2. Đổi tên MC mặc định: chara_info (chara 00) và ô nhập tên trong scene_jp.
Các thay đổi float giữ nguyên kích thước object; thay chuỗi thì rebuild SerializedFile (SF.rebuild).
Dùng: python ui_patch.py                 -> dist/resources.assets, dist/level9, dist/scene_jp
      python ui_patch.py --install
      python ui_patch.py --left 0 --right 80
"""
import argparse, json, os, shutil, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import UnityPy
except ImportError:
    raise SystemExit('Cần cài UnityPy:  pip install UnityPy')

import gamedata as gd
from serialized import SF
from unityfs import UnityFS


# ------------------------------------------------------------------ tiện ích
def read_cfg():
    return json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))


def v2(v):
    if isinstance(v, dict):
        return float(v['x']), float(v['y'])
    return float(v.x), float(v.y)


def collect(env):
    objs = {o.path_id: o for o in env.objects}
    go_name, trans = {}, {}
    for pid, o in objs.items():
        if o.type.name == 'GameObject':
            try:
                go_name[pid] = o.read().m_Name
            except Exception:
                pass
        elif o.type.name in ('Transform', 'RectTransform'):
            try:
                trans[pid] = o.read_typetree()
            except Exception:
                pass
    t2go = {p: t.get('m_GameObject', {}).get('m_PathID')
            for p, t in trans.items() if isinstance(t, dict)}
    go2t = {g: p for p, g in t2go.items() if g}
    return objs, go_name, trans, t2go, go2t


def children(gpid, trans, t2go, go2t):
    tp = go2t.get(gpid)
    if not tp:
        return []
    out = []
    for c in trans.get(tp, {}).get('m_Children', []):
        cg = t2go.get(c.get('m_PathID'))
        if cg:
            out.append(cg)
    return out


def child_named(gpid, name, go_name, trans, t2go, go2t):
    hits = [c for c in children(gpid, trans, t2go, go2t) if go_name.get(c) == name]
    if len(hits) != 1:
        raise SystemExit('Không thấy duy nhất %s/%s (thấy %d)' % (go_name.get(gpid, '?'), name, len(hits)))
    return hits[0]


def patch_rect(raw, old_size, old_pos, new_w, new_x):
    """Tìm m_SizeDelta (2 float) trong raw; m_AnchoredPosition nằm ngay trước 8 byte."""
    pat = struct.pack('<2f', *old_size)
    i = raw.find(pat)
    if i < 0 or raw.find(pat, i + 1) >= 0:
        raise SystemExit('Không xác định duy nhất m_SizeDelta %r (offset %d)' % (old_size, i))
    got = struct.unpack_from('<2f', raw, i - 8)
    if abs(got[0] - old_pos[0]) > 0.01 or abs(got[1] - old_pos[1]) > 0.01:
        raise SystemExit('Không thấy m_AnchoredPosition %r ngay trước m_SizeDelta' % (old_pos,))
    out = bytearray(raw)
    struct.pack_into('<f', out, i, new_w)
    struct.pack_into('<f', out, i - 8, new_x)
    return bytes(out), i


def rect_resize(trans, go2t, gpid, L, R):
    """-> (rect_pid, new_raw, mô tả) với mép trái cố định +L, mép phải +R."""
    pid = go2t[gpid]
    size = v2(trans[pid]['m_SizeDelta'])
    pos = v2(trans[pid]['m_AnchoredPosition'])
    new_w = size[0] + L + R
    new_x = pos[0] + (R - L) / 2.0
    return pid, size, pos, new_w, new_x


# ------------------------------------------------------------ prefab (resources.assets)
def prefab_rects(env):
    objs, go_name, trans, t2go, go2t = collect(env)
    msgs = [g for g, n in go_name.items() if n == 'Message']
    if len(msgs) != 1:
        raise SystemExit('Prefab: không thấy duy nhất GameObject Message (thấy %d)' % len(msgs))
    msg = msgs[0]
    bg = child_named(msg, 'bg', go_name, trans, t2go, go2t)
    text = child_named(msg, 'Text', go_name, trans, t2go, go2t)
    name = child_named(msg, 'Name', go_name, trans, t2go, go2t)
    plate = child_named(bg, 'nameplate', go_name, trans, t2go, go2t)
    img = None
    for c in objs[bg].read().m_Component:
        cp = c.component.m_PathID
        co = objs.get(cp)
        if co is not None and co.type.name == 'MonoBehaviour':
            img = cp
            break
    if img is None:
        raise SystemExit('bg không có MonoBehaviour Image')
    return (bg, text, name, plate), img


# ------------------------------------------------------------ scene level9
def level9_texts(env):
    objs, go_name, trans, t2go, go2t = collect(env)
    def root(name):
        hits = [g for g, n in go_name.items() if n == name]
        if len(hits) != 1:
            raise SystemExit('level9: không thấy duy nhất %s (thấy %d)' % (name, len(hits)))
        return hits[0]
    text = child_named(child_named(root('Message(Normal)'), 'WindowTextRoot', go_name, trans, t2go, go2t),
                       'Text', go_name, trans, t2go, go2t)
    novel = child_named(root('Message(Novel)'), 'NovelText', go_name, trans, t2go, go2t)
    ss = child_named(root('Message(SS)'), 'SSText', go_name, trans, t2go, go2t)
    return [('Text(Normal)', text), ('NovelText', novel), ('SSText', ss)]


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--left', type=float, default=None)
    ap.add_argument('--right', type=float, default=None)
    a = ap.parse_args()

    cfg = read_cfg()
    up = cfg.get('ui_patch', {})
    if not up.get('enabled', True):
        raise SystemExit('ui_patch.enabled = false trong config.json')
    L = float(a.left if a.left is not None else up.get('extend_left', 0))
    R = float(a.right if a.right is not None else up.get('extend_right', 80))
    romfs = os.path.expandvars(cfg.get('romfs_dir', '').strip().strip('"'))
    rel_assets = up.get('file', 'Data/resources.assets').replace('\\', '/')
    rel_scene = up.get('scene', 'Data/level9').replace('\\', '/')
    rel_uitrans = up.get('scene_bundle', 'Data/StreamingAssets/scene/scene_jp').replace('\\', '/')
    out_dir = os.path.join(HERE, cfg.get('out_dir', 'dist'))
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(HERE, 'logs'), exist_ok=True)

    log = ['nới khung: trái +%.0f, phải +%.0f px' % (L, R)]
    written = []

    # ---------------- resources.assets: prefab + chara_info ----------------
    src = os.path.join(romfs, *rel_assets.split('/'))
    if not os.path.isfile(src):
        raise SystemExit('Không thấy %s (kiểm tra romfs_dir)' % src)
    env = UnityPy.load(src)
    (bg, text, name, plate), img_pid = prefab_rects(env)
    objs, go_name, trans, t2go, go2t = collect(env)
    sf = SF(open(src, 'rb').read())
    repl = {}
    for gpid, label in ((bg, 'bg'), (text, 'Text'), (name, 'Name'), (plate, 'nameplate')):
        pid = go2t[gpid]
        size = v2(trans[pid]['m_SizeDelta'])
        pos = v2(trans[pid]['m_AnchoredPosition'])
        if label in ('bg', 'Text'):                         # khung + vùng chữ: nới 2 mép
            nw, nx = size[0] + L + R, pos[0] + (R - L) / 2.0
        elif label == 'nameplate':                          # con của bg: giữ khoảng cách tới mép trái
            nw, nx = size[0], pos[0] - (L + R) / 2.0
        else:                                               # Name: con của Message
            nw, nx = size[0], pos[0] - L
        repl[pid], _ = patch_rect(sf.raw(pid), size, pos, nw, nx)
        log.append('prefab %-9s size %.0f -> %.0f, x %.0f -> %.0f' % (label, size[0], nw, pos[0], nx))
    if up.get('sliced', True):
        iraw = sf.raw(img_pid)
        if len(iraw) == 136 and struct.unpack_from('<i', iraw, 100)[0] == 0:
            inew = bytearray(iraw)
            struct.pack_into('<i', inew, 100, 1)
            repl[img_pid] = bytes(inew)
            log.append('prefab bg Image: Simple -> Sliced')

    mc = cfg.get('mc_name', {})
    if mc.get('enabled', True) and mc.get('chara_info', False):
        old, new = mc.get('from', 'アリア'), mc.get('to', 'Aria')
        ta = next((o for o in env.objects if o.type.name == 'TextAsset' and o.read().m_Name == 'chara_info'), None)
        if ta is None:
            log.append('! không thấy TextAsset chara_info')
        else:
            raw = sf.raw(ta.path_id)
            nm, p, data = gd.ta_parse(raw)
            old_line = ('charaname\t' + old).encode('utf-8')
            new_line = ('charaname\t' + new).encode('utf-8')
            parts = data.split(b'\r\n')
            n = sum(1 for i, x in enumerate(parts) if x == old_line)
            if n != 1:
                log.append('! chara_info: thấy %d dòng charaname "%s" (cần 1)' % (n, old))
            else:
                parts = [new_line if x == old_line else x for x in parts]
                repl[ta.path_id] = gd.ta_make(raw, b'\r\n'.join(parts))
                log.append('chara_info: charaname %s -> %s' % (old, new))

    data = sf.rebuild(repl)
    dst = os.path.join(out_dir, 'resources.assets')
    open(dst, 'wb').write(data)
    written.append((dst, rel_assets))
    log.append('resources.assets: %.1f MB, %d object đổi' % (len(data) / 1e6, len(repl)))

    # ---------------- level9: Text rects ----------------
    src9 = os.path.join(romfs, *rel_scene.split('/'))
    if not os.path.isfile(src9):
        raise SystemExit('Không thấy %s' % src9)
    env9 = UnityPy.load(src9)
    objs9, go_name9, trans9, t2go9, go2t9 = collect(env9)
    sf9 = SF(open(src9, 'rb').read())
    out9 = bytearray(sf9.d)
    for label, gpid in level9_texts(env9):
        pid, size, pos, nw, nx = rect_resize(trans9, go2t9, gpid, L, R)
        newraw, _ = patch_rect(sf9.raw(pid), size, pos, nw, nx)
        bs, sz = sf9.objs[pid][0], sf9.objs[pid][1]
        pos_b = sf9.data_off + bs
        out9[pos_b:pos_b + sz] = newraw
        log.append('level9 %-11s size %.0f -> %.0f, x %.0f -> %.0f' % (label, size[0], nw, pos[0], nx))
    dst9 = os.path.join(out_dir, 'level9')
    open(dst9, 'wb').write(out9)
    written.append((dst9, rel_scene))
    log.append('level9: %.1f KB' % (len(out9) / 1e3))

    # ---------------- scene_jp: tên mặc định trong ô nhập tên ----------------
    if mc.get('enabled', True):
        srcu = os.path.join(romfs, *rel_uitrans.split('/'))
        if not os.path.isfile(srcu):
            log.append('! không thấy %s' % srcu)
        else:
            old, new = mc.get('from', 'アリア'), mc.get('to', 'Aria')
            envu = UnityPy.load(srcu)
            target = None
            for o in envu.objects:
                if o.type.name != 'MonoBehaviour':
                    continue
                try:
                    t = o.read_typetree()
                except Exception:
                    continue
                if not isinstance(t, dict):
                    continue
                s = t.get('m_text')
                if isinstance(s, str) and s.startswith(old) and o.assets_file.name == 'BuildPlayer-NameInput':
                    target = o
                    break
            if target is None:
                log.append('! không thấy TMP m_text "%s" trong BuildPlayer-NameInput' % old)
            else:
                u = UnityFS(srcu)
                datas = [u.node_data(i) for i in range(len(u.nodes))]
                ni = next(i for i, nd in enumerate(u.nodes) if nd[3] == target.assets_file.name)
                sfo = SF(datas[ni])
                raw = sfo.raw(target.path_id)
                old_full = target.read_typetree()['m_text']          # vd 'アリア​'
                new_full = new + old_full[len(old):]                 # giữ hậu tố (ZWSP)
                old_b, new_b = old_full.encode('utf-8'), new_full.encode('utf-8')
                k = raw.find(old_b)
                if k < 4 or struct.unpack_from('<i', raw, k - 4)[0] != len(old_b):
                    log.append('! không xác định được chuỗi %s trong raw TMP' % old_full)
                else:
                    pad_old = (-len(old_b)) % 4
                    tail = raw[k + len(old_b) + pad_old:]
                    blk = struct.pack('<i', len(new_b)) + new_b + b'\0' * ((-len(new_b)) % 4)
                    nr = raw[:k - 4] + blk + tail
                    datas[ni] = sfo.rebuild({target.path_id: nr})
                    dstu = os.path.join(out_dir, 'scene_jp')
                    u.save(dstu, datas)
                    written.append((dstu, rel_uitrans))
                    log.append('scene_jp: TMP "%s..." -> "%s..." (obj %d)' % (old, new, target.path_id))
            del envu

    # ---------------- kiểm tra lại ----------------
    if mc.get('chara_info', False):
        chk = UnityPy.load(os.path.join(out_dir, 'resources.assets'))
        o = next(x for x in chk.objects if x.type.name == 'TextAsset' and x.read().m_Name == 'chara_info')
        log.append('  check chara_info: %s' % ('Aria' if 'charaname\tAria' in o.read_typetree()['m_Script'] else '?'))
    chk9 = UnityPy.load(os.path.join(out_dir, 'level9'))
    objs9b, go_name9b, trans9b, t2go9b, go2t9b = collect(chk9)
    for label, gpid in level9_texts(chk9):
        t = trans9b[go2t9b[gpid]]
        log.append('  check level9 %-11s size=%.0f x=%.0f' % (label, v2(t['m_SizeDelta'])[0], v2(t['m_AnchoredPosition'])[0]))
    p_scene = os.path.join(out_dir, 'scene_jp')
    if os.path.isfile(p_scene):
        echk = UnityPy.load(p_scene)
        try:
            tt = next(o for o in echk.objects if o.path_id == 210 and o.type.name == 'MonoBehaviour').read_typetree()
            log.append('  check scene_jp TMP: %s' % tt['m_text'].encode('unicode_escape').decode())
        except Exception:
            pass

    txt = '\n'.join(log)
    print(txt)
    open(os.path.join(HERE, 'logs', 'ui_patch.log'), 'w', encoding='utf-8').write(txt + '\n')

    if a.install:
        tid = cfg.get('title_id', '').strip()
        parent = cfg['mod_parent'].replace('<TITLE_ID>', tid)
        mod_root = os.path.normpath(os.path.join(os.path.expandvars(parent), cfg['mod_name'], 'romfs'))
        for path, rel in written:
            target = os.path.normpath(os.path.join(mod_root, *rel.split('/')))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(path, target)
            print('đã cài -> %s' % target)


if __name__ == '__main__':
    main()
