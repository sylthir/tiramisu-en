"""Tạo bản vá THỬ CỠ CHỮ: thay 12 dòng thoại đầu của chương 00_01 bằng chuỗi "MMMM" dài nhiều mức và thẻ <size=NN%>.
Cách dùng: python size_test.py -> dist/scenario01 -> chép vào mod, mở game, xem dòng nào tràn khung / thẻ size có hiệu lực không.
Dựa trên kết quả chỉnh config.json -> layout (width, max_lines, size_open). Xong nhớ chạy lại BUILD_PATCH.bat."""
import json, os
import gamedata as gd, scenario as sc, patch

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
cfg['layout'] = dict(cfg.get('layout', {}), enabled=False)
b = gd.load_all(os.path.join(HERE, cfg['source_dir']), ['scenario01'])[0]
stem, x, L = next(e for e in b.entries() if e[0] == '00_01')
units = [u for u in sc.parse(L) if u.typ != 'sel'][:12]
tests = []
for w in (36, 40, 44, 48, 52, 56):
    tests.append('W%d: ' % w + ('M' * (w - 5)))
for pct in (100, 90, 80, 70, 60, 50):
    tests.append('<size=%d%%>SIZE %d%%: ' % (pct, pct) + 'The quick brown fox jumps over the lazy dog, again and again.</size>')
trans = {'%s|%d' % (stem, u.start + 1): t for u, t in zip(units, tests)}
os.makedirs(os.path.join(HERE, cfg['out_dir']), exist_ok=True)
patch.patch_bundle(b, trans, {}, cfg, os.path.join(HERE, cfg['out_dir'], 'scenario01'), print)
print('Đã tạo dist\\scenario01 (bản thử). Mỗi dòng ghi độ rộng W.. hoặc cỡ chữ size%.')
