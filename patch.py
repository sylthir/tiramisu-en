"""Ghi bản dịch vào bundle: sửa file .txt, ScenarioData.json (scriptText, scriptText_Line, text, talkName, selText,
loadLine, selLine) cho khớp nhau, rồi ghi bundle mới (không nén)."""
import json
import os

import gamedata as gd
import scenario as sc
from serialized import SF


def txt_lines(raw):
    t = raw.decode('utf-8')
    bom = t.startswith('\ufeff')
    t = t.lstrip('\ufeff')
    eol = '\r\n' if '\r\n' in t else '\n'
    lines = t.replace('\r\n', '\n').split('\n')
    tail = lines[-1] == ''
    if tail:
        lines = lines[:-1]
    return lines, bom, eol, tail


def txt_bytes(lines, bom, eol, tail):
    t = eol.join(lines) + (eol if tail else '')
    return ('\ufeff' if bom else '').encode('utf-8') + t.encode('utf-8')


def patch_bundle(b, trans, labels, cfg, out_path, log, jpmap=None):
    repl, rep_stats = {}, dict(units=0, lines=0, labels=0, choices=0, shrunk=0, overflow=[], warn=0, txt=0)
    for stem, x, L in b.entries():
        if stem in gd.SKIP_STEMS:
            continue
        newL, old2new, rp, st = sc.apply(L, stem, trans, labels, cfg, jpmap)
        if not rp:
            continue
        sel_changed = any(o[0].startswith('[seladd ') for o, n in rp)
        rep_stats['warn'] += sc.patch_entry(x, newL, old2new, rp, sel_changed)
        for k in ('units', 'lines', 'labels', 'choices', 'shrunk'):
            rep_stats[k] += st[k]
        rep_stats['overflow'] += st['overflow']
        rep_stats.setdefault('missing', []).extend(st['missing'])
        if stem in b.assets:                                   # file .txt tương ứng
            pid = b.assets[stem]
            raw = b.sf.raw(pid)
            _, _, data = gd.ta_parse(raw)
            _, bom, eol, tail = txt_lines(data)
            repl[pid] = gd.ta_make(raw, txt_bytes(newL, bom, eol, tail))
            rep_stats['txt'] += 1
    if not repl:
        log('%s: không có gì để vá (chưa có bản dịch cho bundle này)' % b.key)
        return None
    pid = b.assets['ScenarioData']
    js = ('\ufeff' if b.bom['ScenarioData'] else '') + json.dumps(b.scen, ensure_ascii=False, separators=(',', ':'))
    repl[pid] = gd.ta_make(b.sf.raw(pid), js.encode('utf-8'))
    new_ser = b.sf.rebuild(repl)
    chk = SF(new_ser)                                           # kiểm tra lại cấu trúc
    assert len(chk.objs) == len(b.sf.objs)
    for p in b.sf.objs:
        if p not in repl and chk.raw(p) != b.sf.raw(p):
            raise SystemExit('Lỗi: object %d ngoài danh sách sửa bị đổi' % p)
    for p in repl:
        assert chk.raw(p) == repl[p]
    n = b.u.save(out_path, [new_ser])
    log('%s: %d đơn vị vá (%d thoại/lời dẫn, %d nhãn tên, %d lựa chọn), %d câu bị thu nhỏ, %d file txt, ghi %.1f MB' % (
        b.key, rep_stats['units'], rep_stats['lines'], rep_stats['labels'], rep_stats['choices'], rep_stats['shrunk'],
        rep_stats['txt'], n / 1e6))
    return rep_stats
