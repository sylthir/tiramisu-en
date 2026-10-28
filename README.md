**MIRAMISU** - MOD version

*Respiratory chỉ build ra thư mục dist. Không cài gì vào Eden, không sửa save. Chỉnh sửa từ tool gốc Miramisu_EN_Tool.*

## Cài đặt
  1. Python 3.10+ và:  `pip install openpyxl UnityPy lz4`
  2. Chép 3 bundle gốc vào source\ : `scenario01`, `scenario_aoc01`, `scenario_aoc02`
  3. Mở `config.json`, điền `romfs_dir` = thư mục `romfs` gốc của game (chứa `Data\resources.assets`, `Data\Managed\Metadata\global-metadata.dat`, `Data\StreamingAssets\scene\scene_jp`). `romfs_dir` chỉ dùng để ĐỌC file gốc khi vá; không dùng để cài.
  4. Nếu có DLC: điền `config.json` -> `dlc[].romfs_dir` = thư mục `romfs` của title DLC
     (vd `...\dump\0100E81024F41001\romfs`) và `dlc[].bundle = novel/novel_aoc01`.
  5. `BUILD_DIST.bat` patch cả game gốc + DLC; `BUILD_DLC.bat` chỉ build DLC và cập nhật thẳng
     `dist\<title_id>\English\romfs\novel\...` (không cần chạy lại toàn bộ).

WORKBOOK: "Miramisu Eng.xlsx" (81 sheet)
  - TOC, Character_names, Speaker_labels, Dic_terms, Dictionary, DLC_Novel_aoc01, các sheet chương, Huong_dan.
  - `Dic_terms`: 144 thuật ngữ [dic no=..] trong thoại.
  - `Dictionary`: 144 mục từ điển trong game, mỗi mục 2 dòng:
    ```
      Dict|<no>|title  = tên mục (cột C đã điền sẵn từ Dic_terms)
      Dict|<no>|text   = phần giải thích (cột C để trống, cần dịch)
    ```
  - `DLC_Novel_aoc01`: 546 dòng truyện ngắn DLC (novel01..novel05), ID Novel|<tên>|<dòng>. Dòng trống và thụt đầu dòng được giữ khi build. Điền cột C. Ô trống -> khi build giữ nguyên tiếng Nhật.
  - Tên MC mặc định đã đổi thành Aria trong `metadata`; ô nhập tên trong `scene_jp` cũng là Aria.

## Quy trình
```
  TRANSLATE.bat     dịch các ô trống (ưu tiên Character_names, Speaker_labels, Dic_terms, Dictionary)
  MAKE_WORKBOOK.bat tạo lại workbook, giữ bản dịch cũ theo ID; sheet Dictionary tự sinh từ
                    dict\dictionary.json (nếu đã có thì giữ bản dịch cũ)
  python add_dictionary_sheet.py   thêm/cập nhật riêng sheet Dictionary
  BUILD_DIST.bat    build TOÀN BỘ mod vào dist\English\romfs  (python build_dist.py)
```
## Kết quả
```
  dist\0100E81024F40000\English\romfs\Data\resources.assets                      (từ điển)
  dist\0100E81024F40000\English\romfs\Data\Managed\Metadata\global-metadata.dat  (tên Aria)
  dist\0100E81024F40000\English\romfs\Data\StreamingAssets\scenario\scenario01, scenario_aoc01, scenario_aoc02
  dist\0100E81024F40000\English\romfs\Data\StreamingAssets\scene\scene_jp         (ô nhập tên Aria)
  dist\0100E81024F41001\English\romfs\novel\novel_aoc01                           (truyện ngắn DLC)
  dist\README.txt
```
  Cài: copy từng thư mục title vào đúng chỗ:
```
  dist\0100E81024F40000\English  ->  %APPDATA%\eden\load\0100E81024F40000\
  dist\0100E81024F41001\English  ->  %APPDATA%\eden\load\0100E81024F41001\
```
  sao cho thành `...\load\<title_id>\English\romfs\...`

## Ghi chú
  - Tool trên đang áp dụng cho update 1.0.1.
  - Không đổi `chara_info`: scenario dùng lệnh [アリア ...] nên `charaname` là khoá tra sprite/voice.
  - Từ điển: tên mục đã dịch (lấy từ `Dic_terms`); phần giải thích còn tiếng Nhật cho tới khi dịch các dòng `Dict|<no>|text` rồi build lại.
  - Tên MC: `metadata` (mặc định) + `scene_jp` (ô nhập). Save cũ đã có tên thì không bị đổi.
  - Sau mỗi bản update game: dump lại `romfs`, chép lại 3 bundle vào source\, chạy `BUILD_DIST.bat`.
  - Bản này không có `BUILD_AND_INSTALL` / `FIX_SAVE_NAME`.

## LICENSE
This is an unofficial, non-commercial fan translation. This patch distributes modified game data files and will not function without a legitimate copy of the game. All copyrights for the original game belong to their respective owners. This project is neither affiliated nor authorized by the publisher, should the copyright holders request its removal, this repository will be taken down.
