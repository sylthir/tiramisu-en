"""Build TOÀN BỘ mod vào dist (không cài Eden).
Kết quả để copy:
  dist/<title_id>/<mod_name>/romfs/...        (game gốc)
  dist/<dlc_title_id>/<mod_name>/romfs/...    (từng DLC, nếu config có "dlc")
Dùng: python build_dist.py [--skip-build]
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(args):
    print('\n>>> ' + ' '.join(args))
    r = subprocess.run(args, cwd=HERE)
    if r.returncode != 0:
        raise SystemExit('Lệnh thất bại: %s' % ' '.join(args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-build', action='store_true', help='chỉ đóng gói lại dist từ file đã build')
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    dist = os.path.join(HERE, cfg.get('out_dir', 'dist'))
    mod = cfg.get('mod_name', 'English')

    if not a.skip_build:
        run([PY, 'build.py'])                        # kịch bản -> dist/scenario*
        run([PY, 'ui_patch.py'])                     # scene_jp (tên MC)
        run([PY, 'patch_meta_name.py', '--apply'])   # dist/global-metadata.dat
        run([PY, 'build_dictionary.py'])             # dist/resources.assets
        if cfg.get('dlc'):
            run([PY, 'build_dlc.py'])                # dist/novel_aoc*

    def cp(file_name, root, rel):
        src = os.path.join(dist, file_name)
        if not os.path.isfile(src):
            raise SystemExit('Thiếu file build: %s' % src)
        dst = os.path.join(root, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print('  %-62s <- %s' % (rel, file_name))

    # ---- game gốc ----
    base_title = cfg.get('title_id', 'TITLE_ID')
    base_root = os.path.join(dist, base_title, mod, 'romfs')
    for p in (base_root, os.path.join(dist, mod)):          # xoá cấu trúc cũ nếu có
        shutil.rmtree(p, ignore_errors=True)
    cp('resources.assets', base_root, 'Data/resources.assets')
    cp('global-metadata.dat', base_root, 'Data/Managed/Metadata/global-metadata.dat')
    for f in ('scenario01', 'scenario_aoc01', 'scenario_aoc02'):
        cp(f, base_root, 'Data/StreamingAssets/scenario/%s' % f)
    cp('scene_jp', base_root, 'Data/StreamingAssets/scene/scene_jp')

    # ---- DLC ----
    dlc_lines = []
    for d in cfg.get('dlc', []):
        tid = d.get('title_id')
        rel = d['bundle'].replace('\\', '/')
        flat = os.path.basename(rel)
        root = os.path.join(dist, tid, mod, 'romfs')
        shutil.rmtree(os.path.join(dist, tid), ignore_errors=True)
        cp(flat, root, rel)
        dlc_lines.append('  dist\\%s\\%s  ->  %%APPDATA%%\\eden\\load\\%s\\' % (tid, mod, tid))

    readme = os.path.join(dist, 'README.txt')
    with open(readme, 'w', encoding='utf-8') as fh:
        fh.write(
            'MOD %s (Switch)\n\n'
            'Copy từng thư mục title vào %%APPDATA%%\\eden\\load\\<title_id>\\:\n'
            '  dist\\%s\\%s  ->  %%APPDATA%%\\eden\\load\\%s\\\n' % (
                cfg.get('game', 'Game'), base_title, mod, base_title))
        for line in dlc_lines:
            fh.write(line + '\n')
        fh.write(
            '\nNội dung game gốc:\n'
            '  Data\\StreamingAssets\\scenario\\scenario01, scenario_aoc01, scenario_aoc02\n'
            '  Data\\StreamingAssets\\scene\\scene_jp (tên MC trong ô nhập tên)\n'
            '  Data\\Managed\\Metadata\\global-metadata.dat (tên mặc định Aria)\n'
            '  Data\\resources.assets (từ điển tiếng Anh)\n'
            'Nội dung DLC: novel\\novel_aoc01 (truyện ngắn DLC).\n\n'
            'Chỉ copy các thư mục title; không cần chép file build phẳng ở dist.\n')
    print('\nĐã đóng gói: %s' % os.path.join(dist, base_title, mod, 'romfs'))
    for d in cfg.get('dlc', []):
        print('            %s' % os.path.join(dist, d.get('title_id', '?'), mod, 'romfs'))
    print('README: %s' % readme)


if __name__ == '__main__':
    main()
