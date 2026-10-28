"""Build TOÀN BỘ mod vào dist (không cài Eden).
Kết quả để copy: dist/<mod_name>/romfs/Data/...
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

    if not a.skip_build:
        run([PY, 'build.py'])                 # kịch bản -> dist/scenario*
        run([PY, 'ui_patch.py'])              # scene_jp (tên MC); config đang tắt nới khung
        run([PY, 'patch_meta_name.py', '--apply'])   # dist/global-metadata.dat
        run([PY, 'build_dictionary.py'])      # dist/resources.assets (từ điển)

    # đóng gói thành cây mod
    mod = cfg.get('mod_name', 'English')
    root = os.path.join(dist, mod, 'romfs')
    shutil.rmtree(os.path.join(dist, mod), ignore_errors=True)
    def cp(src, rel):
        src = os.path.join(dist, src)
        if not os.path.isfile(src):
            raise SystemExit('Thiếu file build: %s' % src)
        dst = os.path.join(root, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print('  %-58s <- %s' % (rel, os.path.basename(src)))
    cp('resources.assets', 'Data/resources.assets')
    cp('global-metadata.dat', 'Data/Managed/Metadata/global-metadata.dat')
    for f in ('scenario01', 'scenario_aoc01', 'scenario_aoc02'):
        cp(f, 'Data/StreamingAssets/scenario/%s' % f)
    cp('scene_jp', 'Data/StreamingAssets/scene/scene_jp')

    readme = os.path.join(dist, 'README.txt')
    with open(readme, 'w', encoding='utf-8') as fh:
        fh.write(
            'MOD %s (Switch)\n\n'
            'Cách dùng: copy thư mục "%s" vào\n'
            '  %%APPDATA%%\\eden\\load\\%s\\\n'
            'sao cho thành ...\\load\\%s\\%s\\romfs\\Data\\...\n\n'
            'Nội dung:\n'
            '  Data\\StreamingAssets\\scenario\\scenario01, scenario_aoc01, scenario_aoc02\n'
            '  Data\\StreamingAssets\\scene\\scene_jp (tên MC trong ô nhập tên)\n'
            '  Data\\Managed\\Metadata\\global-metadata.dat (tên mặc định Aria)\n'
            '  Data\\resources.assets (từ điển tiếng Anh)\n\n'
            'Chỉ copy thư mục romfs; không cần chép file build phẳng ở dist.\n'
            % (cfg.get('game', 'Game'), mod, cfg.get('title_id', 'TITLE_ID'),
               cfg.get('title_id', 'TITLE_ID'), mod))
    print('\nĐã đóng gói: %s' % root)
    print('README: %s' % readme)


if __name__ == '__main__':
    main()
