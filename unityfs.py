"""Đọc / ghi UnityFS (AssetBundle) bằng Python thuần. Hỗ trợ nén LZ4/LZ4HC (đọc) và ghi không nén.
Nếu máy có thư viện lz4 (pip install lz4) thì dùng cho nhanh hơn, không có cũng chạy được."""
import struct

try:
    import lz4.block as _lz4b
except Exception:                                  # không có lz4: dùng bản Python thuần
    _lz4b = None


def lz4_block(src, usize):
    if _lz4b is not None:
        return _lz4b.decompress(src, uncompressed_size=usize)
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        t = src[i]; i += 1
        l = t >> 4
        if l == 15:
            while True:
                b = src[i]; i += 1; l += b
                if b != 255:
                    break
        out += src[i:i + l]; i += l
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        m = t & 15
        if m == 15:
            while True:
                b = src[i]; i += 1; m += b
                if b != 255:
                    break
        m += 4
        s = len(out) - off
        if off >= m:
            out += out[s:s + m]
        else:                                       # vùng chép chồng lên nhau
            pat = bytes(out[s:])
            out += (pat * (m // off + 1))[:m]
    return bytes(out)


def _dec(b, usize, comp):
    if comp == 0:
        return bytes(b)
    if comp in (2, 3):
        return lz4_block(b, usize)
    if comp == 1:
        import lzma
        props = b[:5]
        d = lzma.LZMADecompressor(lzma.FORMAT_RAW, None,
                                  [{'id': lzma.FILTER_LZMA1, 'dict_size': struct.unpack('<I', props[1:5])[0],
                                    'lc': props[0] % 9, 'lp': (props[0] // 9) % 5, 'pb': props[0] // 45}])
        return d.decompress(b[5:], usize)
    raise ValueError('kiểu nén không hỗ trợ: %d' % comp)


class UnityFS:
    """.nodes = [(offset, size, flags, path)], .data = dữ liệu đã giải nén, .blocks = kích thước các block gốc."""

    def __init__(self, path):
        d = self.raw = open(path, 'rb').read()
        e = d.index(b'\0')
        if d[:e] != b'UnityFS':
            raise ValueError('không phải file UnityFS')
        p = e + 1
        self.version = struct.unpack('>I', d[p:p + 4])[0]; p += 4
        e1 = d.index(b'\0', p); self.player = d[p:e1]; p = e1 + 1
        e2 = d.index(b'\0', p); self.engine = d[p:e2]; p = e2 + 1
        size, cs, us, flags = struct.unpack('>QIII', d[p:p + 20]); p += 20
        self.flags = flags
        if flags & 0x80:
            raise NotImplementedError('block info nằm cuối file')
        if self.version >= 7:
            p = (p + 15) // 16 * 16
        bi = _dec(d[p:p + cs], us, flags & 0x3F); p += cs
        if flags & 0x200:
            p = (p + 15) // 16 * 16
        self.bi_hash = bi[:16]
        q = 16
        nb = struct.unpack('>I', bi[q:q + 4])[0]; q += 4
        self.blocks = []
        for _ in range(nb):
            u, c, f = struct.unpack('>IIH', bi[q:q + 10]); q += 10
            self.blocks.append((u, c, f))
        nn = struct.unpack('>I', bi[q:q + 4])[0]; q += 4
        self.nodes = []
        for _ in range(nn):
            o, s, f = struct.unpack('>QQI', bi[q:q + 20]); q += 20
            e3 = bi.index(b'\0', q)
            self.nodes.append((o, s, f, bi[q:e3].decode())); q = e3 + 1
        parts = []
        for u, c, f in self.blocks:
            parts.append(_dec(d[p:p + c], u, f & 0x3F)); p += c
        self.data = b''.join(parts)

    def node_data(self, i=0):
        o, s, _, _ = self.nodes[i]
        return self.data[o:o + s]

    def save(self, path, new_nodes):
        """new_nodes: list bytes cùng thứ tự self.nodes. Ghi bundle KHÔNG NÉN (Unity vẫn đọc bình thường)."""
        data, nodes, off = bytearray(), [], 0
        for (o, s, f, name), blob in zip(self.nodes, new_nodes):
            pad = (-off) % 16 if False else 0
            nodes.append((off, len(blob), f, name))
            data += blob; off += len(blob)
        blk = []
        step = 1 << 17
        for i in range(0, len(data), step):
            n = min(step, len(data) - i)
            blk.append((n, n, 0))
        bi = bytearray(self.bi_hash)
        bi += struct.pack('>I', len(blk))
        for u, c, f in blk:
            bi += struct.pack('>IIH', u, c, f)
        bi += struct.pack('>I', len(nodes))
        for o, s, f, name in nodes:
            bi += struct.pack('>QQI', o, s, f) + name.encode() + b'\0'
        flags = (self.flags & ~0x3F) | 0x40            # bỏ nén, giữ cờ còn lại (0x40 = block info gộp, 0x200 = đệm)
        head = bytearray(b'UnityFS\0' + struct.pack('>I', self.version) + self.player + b'\0' + self.engine + b'\0')
        size_pos = len(head)
        head += struct.pack('>QIII', 0, len(bi), len(bi), flags)
        if self.version >= 7:
            head += b'\0' * ((-len(head)) % 16)
        out = bytearray(head) + bi
        if flags & 0x200:
            out += b'\0' * ((-len(out)) % 16)
        out += data
        struct.pack_into('>Q', out, size_pos, len(out))
        open(path, 'wb').write(out)
        return len(out)
