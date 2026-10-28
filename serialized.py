import struct
class SF:
    """Unity SerializedFile reader (v>=17..22, LE metadata); keeps raw bytes, can swap object data."""
    def __init__(self, d):
        self.d = d
        self.version = struct.unpack('>I', d[8:12])[0]
        if self.version >= 22:
            self.meta_size = struct.unpack('>I', d[20:24])[0]
            self.file_size = struct.unpack('>Q', d[24:32])[0]
            self.data_off = struct.unpack('>Q', d[32:40])[0]
            p = 48
        else:
            raise NotImplementedError('version %d' % self.version)
        e = d.index(b'\0', p); self.unity = d[p:e].decode(); p = e + 1
        self.platform = struct.unpack('<I', d[p:p+4])[0]; p += 4
        self.typetree = bool(d[p]); p += 1
        n = struct.unpack('<i', d[p:p+4])[0]; p += 4
        self.types = []
        for _ in range(n):
            cid = struct.unpack('<i', d[p:p+4])[0]; p += 4
            stripped = d[p]; p += 1
            sti = struct.unpack('<h', d[p:p+2])[0]; p += 2
            if cid == 114: p += 16
            p += 16
            nodes = []
            if self.typetree:
                nn, sb = struct.unpack('<ii', d[p:p+8]); p += 8
                nb = d[p:p+nn*32]; p += nn*32
                strs = d[p:p+sb]; p += sb
                def S(o):
                    if o & 0x80000000:
                        o &= 0x7fffffff
                        return COMMON.get(o, '?%d' % o)
                    return strs[o:strs.index(b'\0', o)].decode()
                for i in range(nn):
                    ver, lvl, fl, t, nm, bs, idx, mf = struct.unpack_from('<HBBIIiiI', nb, i*32)
                    nodes.append((lvl, S(t), S(nm), bs, mf))
            if self.typetree:                                         # bảng phụ thuộc chỉ có khi có typetree
                dep_n = struct.unpack('<i', d[p:p+4])[0]; p += 4 + 4*dep_n
            self.types.append((cid, sti, nodes))
        cnt = struct.unpack('<i', d[p:p+4])[0]; p += 4
        self.objs = {}
        self.table_start = p
        for _ in range(cnt):
            p = (p + 3) & ~3
            pid, bs, sz, tid = struct.unpack('<qQIi', d[p:p+24])
            self.objs[pid] = [bs, sz, tid, p]
            p += 24
        self.table_end = p
        starts = [v[0] for v in self.objs.values()]
        self.align = 16 if all(s % 16 == 0 for s in starts) else 8
    def class_id(self, pid): return self.types[self.objs[pid][2]][0]
    def raw(self, pid):
        bs, sz = self.objs[pid][:2]
        return self.d[self.data_off+bs:self.data_off+bs+sz]
    def rebuild(self, repl):
        d = self.d
        order = sorted(self.objs.items(), key=lambda kv: kv[1][0])
        out = bytearray(d[:self.data_off]); pos = 0
        for pid, (bs, sz, tid, tp) in order:
            pad = (-pos) % self.align
            out += b'\0'*pad; pos += pad
            raw = repl[pid] if pid in repl else d[self.data_off+bs:self.data_off+bs+sz]
            struct.pack_into('<qQIi', out, tp, pid, pos, len(raw), tid)
            out += raw; pos += len(raw)
        last = max(v[0]+v[1] for v in self.objs.values())
        out += d[self.data_off+last:]
        struct.pack_into('>Q', out, 24, len(out))
        return bytes(out)
COMMON = {}
