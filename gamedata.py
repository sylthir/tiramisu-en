"""Đọc kịch bản từ các bundle (scenario01, scenario_aoc01, scenario_aoc02) và ghi bản vá lại vào bundle."""
import json
import os
import re
import struct

from serialized import SF
from unityfs import UnityFS
import scenario as sc

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTES = {'00': ('Common', 'Prologue chung'), '01': ('Leon', 'Route Leon'), '02': ('Charles', 'Route Charles'),
          '03': ('Rudy', 'Route Rudy'), '04': ('Jack', 'Route Jack'), '05': ('Evan', 'Route Evan'),
          '06': ('Verite', 'Route Vérité (true end)'), '07': ('Extra', 'Extra story'), '08': ('DLC', 'DLC / After story')}
SKIP_STEMS = ('00_live2d_check', 'test')


def sheet_name(stem):
    m = re.match(r'(\d\d)_(\d\d)$', stem)
    if not m:
        return stem
    return '%s_%s_%s' % (ROUTES.get(m.group(1), (m.group(1),))[0], m.group(1), m.group(2))


def sheet_desc(stem):
    m = re.match(r'(\d\d)_(\d\d)$', stem)
    if not m:
        return stem
    return '%s - chương %d (%s)' % (ROUTES.get(m.group(1), ('', m.group(1)))[1], int(m.group(2)), stem)


def ta_parse(raw):
    L = struct.unpack_from('<i', raw, 0)[0]
    name = raw[4:4 + L].decode('utf-8')
    p = (4 + L + 3) & ~3
    sl = struct.unpack_from('<i', raw, p)[0]
    return name, p, raw[p + 4:p + 4 + sl]


def ta_make(raw, data):
    name, p, _ = ta_parse(raw)
    out = bytearray(raw[:p]) + struct.pack('<i', len(data)) + data
    out += b'\0' * ((-len(out)) % 4)
    return bytes(out)


class Bundle:
    def __init__(self, path):
        self.path = path
        self.key = os.path.basename(path)
        self.u = UnityFS(path)
        self.ser = self.u.node_data(0)
        self.sf = SF(self.ser)
        self.assets = {}                                     # tên -> path_id
        for pid in self.sf.objs:
            if self.sf.class_id(pid) == 49:
                n, _, _ = ta_parse(self.sf.raw(pid))
                self.assets[n] = pid
        if 'ScenarioData' not in self.assets:
            raise ValueError('%s không có ScenarioData' % self.key)
        self.scen = self.read_json('ScenarioData')
        self.slist = self.read_json('scenariolist')
        self.stems = {}                                      # scenarioID -> tên file
        for k, v in zip(self.slist['keys'], self.slist['values']):
            self.stems[v] = k

    def text(self, name):
        _, _, data = ta_parse(self.sf.raw(self.assets[name]))
        return data

    def read_json(self, name):
        t = self.text(name).decode('utf-8')
        self.bom = getattr(self, 'bom', {})
        self.bom[name] = t.startswith('\ufeff')
        return json.loads(t.lstrip('\ufeff'))

    def entries(self):
        """-> [(stem, entry, lines)] theo thứ tự ScenarioData."""
        out = []
        for x in self.scen['target']:
            stem = self.stems.get(x['scenarioID'])
            if stem is None:
                continue
            out.append((stem, x, [l.replace('\r', '') for l in x['scriptText_Line']]))
        return out


def load_all(source_dir, names):
    bundles = []
    for n in names:
        p = os.path.join(source_dir, n)
        if os.path.exists(p):
            bundles.append(Bundle(p))
    if not bundles:
        raise SystemExit('Không thấy bundle nào trong %s (cần: %s)' % (source_dir, ', '.join(names)))
    return bundles
