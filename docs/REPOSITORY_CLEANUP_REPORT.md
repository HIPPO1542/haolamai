# MyAI v2.4 — chuẩn bị repository, 10/11/2026

**`ready_for_git_push = false`**: index thật chưa được dọn do quyền ghi `.git`
bị chặn; vẫn chứa dữ liệu chưa duyệt và gitlink WANDS. Cần chạy lệnh mục cuối,
review/stage mã nguồn rồi kiểm tra lại trước commit/push.

**`ready_for_vastai_training = false`**: chưa có phê duyệt đầy đủ dữ liệu và chưa
chạy trọng số Qwen3.5-9B/QLoRA/resume trên GPU đủ lớn. Đã chuẩn bị đường chạy
đơn giản bằng entrypoint cũ: [Vast.ai](VASTAI_DEPLOYMENT.md).

## Những gì đã thực hiện

- Giữ cấu trúc hiện có; không đổi tên public API, không sửa thuật toán tìm kiếm,
  schema DB hoặc nội dung train/validation/test/holdout.
- `.gitignore`: bỏ qua raw datasets, prepared datasets, output/log, môi trường,
  database, model, adapter, private data/releases, wheel và archive.
  `.gitattributes` đặt LF cho Python/shell và CRLF cho PowerShell.
- Chỉ dùng `requirements.txt`; sửa setup Python/PowerShell đang tham chiếu hai
  requirements phụ đã bị người dùng xóa. Không đổi package đang cài. Bỏ index
  cu132 ép buộc khỏi file chung; hướng dẫn cài Torch theo image/driver Linux.
- `scripts.finetune`: default split là `private_data/myai-v24/{train,validation}.jsonl`,
  độ dài mặc định 2048; thêm `--run-preflight` để kiểm tra ở đầu cùng lần train.
  Thiếu dữ liệu/chưa xác nhận duyệt/launch check lỗi thì dừng, không sinh dữ liệu.
- Preflight tách rõ `technical_launch_checks_pass` với chứng minh train 9B thật.
  Không đổi BLOCKED thành PASS cho tải/backward 9B, resume hoặc quyền dữ liệu.
  Xác nhận duyệt vẫn do người vận hành qua cờ đã có, không thêm hệ thống phê duyệt.
- Downloader chốt immutable revision trước khi tải và lưu SHA revision trong manifest.
- Evaluator 126 dùng fixture benchmark canonical trong data pack, không phụ thuộc
  bản sao dưới prepared dữ liệu riêng. Fixture canonical và bản cũ cùng checksum.
- Offline runner mặc định chỉ chạy code/test/fixture. Các tác vụ audit/rebuild raw
  lịch sử cần `--include-local-data`; không tự dựng candidate trên clone sạch.
  Holdout baseline chỉ được nhận nếu đúng 63/65 và đúng H24-063/H24-065.
- Hai entrypoint shell cloud v2 cũ dừng với chỉ dẫn tới quy trình hiện tại, không
  chạy smoke training riêng hoặc dùng nhầm split prepared_v2.
- README/Windows/install cập nhật trạng thái một venv, đường dữ liệu và hướng dẫn
  hiện tại. Bỏ NUL lẫn trong README, giữ chữ `# haolamai`; bản byte cũ được sao lưu.

## File thêm/sửa

Thêm: `.gitattributes`, `configs/wands_source.json`, `configs/training_release_v24.json`,
`scripts/repository_inventory.py`, `scripts/cleanup_git_index.py`, `scripts/fetch_wands.py`,
`docs/VASTAI_DEPLOYMENT.md`, báo cáo này. Ba script mới phục vụ kiểm kê/dọn index/
tái tạo WANDS tùy chọn; không phải các bước bổ sung trong quy trình train.

Sửa: `.gitignore`, `requirements.txt`, `README.md`, `README_Windows.md`,
`INSTALL_v2_4.md`, `scripts/setup_qwen_environment.py`, `scripts/download_model.py`,
`scripts/finetune.py`, `scripts/qwen_preflight_v24.py`, `scripts/run_offline_checks.py`,
`windows/setup.ps1`, `windows/train.ps1`, `tests/test_preflight_safety.py`,
`MyAI_Search_Integration_v2_2/evaluate_search.py`,
`MyAI_Prepare_Datasets_v2/cloud_train_v2.sh`, `.../cloud_smoke_v2.sh`.

Các thay đổi staged/unstaged có từ trước được giữ; không tự stage, commit, push.
Không đổi tên/chuyển thư mục file hiện có. Không xóa file hiện có.
Các prototype mới của chính phiên này đã bỏ trước bàn giao; không phải dữ liệu
hoặc mã nguồn người dùng. Không còn launcher train trung gian hoặc quy trình receipt.

## Dung lượng, duplicate và cache

Trước: **4.344.431.033 byte**, 39.180 file, gồm `.venv` 3.884.200.196 byte,
datasets 216.856.580, outputs 156.419.166, data 32.143.572, models 23.007.907.
Sau kiểm chứng: **4.352.217.580 byte**, 39.983 file (snapshot trước khi viết chính
inventory đó), tăng khoảng 7,8 MB do thư viện kiểm thử thuần Python, log và export
xem trước. Chi tiết: `outputs/repository_cleanup_v24/after/inventory.json`.
Không tuyên bố đã giảm dung lượng ổ đĩa; `.venv`/dữ liệu/model giữ nguyên.

83 nhóm SHA-256 trùng hoàn toàn, phần dư 87.670.906 byte ngoài `.venv`/`.git`.
Nhiều bản là split/audit snapshot có tham chiếu hoặc bằng chứng lịch sử: giữ nguyên
trên Windows, đề xuất loại khỏi Git thay vì xóa. Danh sách đầy đủ trong inventory.
Sáu thư mục cache mã nguồn khoảng 0,8 MB đã xác minh; lệnh xóa bị automatic approval
review từ chối vì cần approval nhưng phiên không cho yêu cầu. **Chưa xóa cache**.
Cache đã được Git bỏ qua; không ảnh hưởng kích thước clone dự kiến.

## Git và WANDS

Trước/sau: branch `main`, remote `https://github.com/HIPPO1542/haolamai.git`.
HEAD có 1 commit (`760a660`), chỉ README; phần lớn dự án là staged mới.
Ban đầu: A=466, AM=9, AD=2, M=1, untracked=17 nhóm. Hai AD là requirements phụ
đã bị xóa trên disk. Chưa xác nhận visibility public/private của remote.

Index thật có 478 entry; unique blob tổng 169.685.335 byte, blob lớn nhất
47.343.957 byte, không vượt 100 MiB. Dung lượng cộng theo path lớn hơn do trùng blob.
Giới hạn GitHub: [50 MiB cảnh báo, trên 100 MiB bị chặn](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
Không cần LFS cho cấu hình repository được đề xuất.

WANDS: gitlink thiếu `.gitmodules`; bản local ở revision
`3b74dcf4ba29ab8ff3e6a50b5b09fc627cb882b5`, nguồn
[Wayfair/WANDS](https://github.com/wayfair/WANDS), MIT. Chọn dataset ngoài repo.
Manifest cố định SHA-256 cho product/query/label CSV và LICENSE; `fetch_wands
--verify-only` đã xác minh cả bốn. Không ghi đè bản nested Git local, không đưa
WANDS vào SFT. Intent tiếng Việt cũng giữ riêng, không coi là dữ liệu trả lời chatbot.

**Chưa loại file nào khỏi index thật**: `git rm --cached` lỗi tạo `.git/index.lock`:
Permission denied. Không tìm cách ghi vòng qua đường `.git` bị bảo vệ.
Kế hoạch đã chốt 364 entry để untrack mà giữ disk:

- `datasets/raw/` (gồm WANDS gitlink), toàn bộ `outputs/` đang staged.
- `data/prepared_v2/`, `data/prepared_v2_1_review/`, `data/search_data_preflight/`.
- Data pack `03_sft_addon/`, Excel danh mục trùng nguồn fixture CSV.
- Hai requirements phụ không còn trên disk.

Danh sách path/mode/blob chính xác: `outputs/repository_cleanup_v24/index_plan.json`.
Index thật vẫn byte-identical với `before/index.backup`; staged edits khác không mất.
Một **index xem trước riêng** đã thử untrack và export: 114 file / 481.218 byte,
không còn gitlink. Overlay source/config/test hiện tại: 127 file / 703.063 byte
(trước bổ sung báo cáo cuối). Không có split riêng, không thiếu file train runtime.
Đây là mô phỏng nội dung sẽ commit, **không phải clone từ remote hoặc index thật**.

## Dữ liệu và quyền sử dụng

Candidate giữ nguyên: train 3.866 / 6.294.451 byte; validation 263 / 370.693 byte.
Schema prompt/completion hợp lệ, guard exact train/validation overlap không phát hiện
trùng. SHA-256 nằm trong public metadata và hướng dẫn Vast.ai. Rule ignore đã khớp
split nhưng chúng **vẫn tracked/staged cho tới khi áp dụng untrack**, không được push.
External test 1.033, benchmark MyAI 126, regression v2.3 42 và holdout v2.4 65
giữ riêng, không đưa vào train. Checksum toàn bộ 118 input được bảo vệ không đổi.

Screening candidate: email-like=0, phone-like=0, credential-like=0 theo regex.
Đây không phải chứng nhận không có PII hoặc đã đủ quyền sử dụng. Nguồn hỗn hợp
Empath/SaaS/addon và dữ liệu tổng hợp vẫn cần người duyệt. Báo cáo curation cũ và
quarantine giữ nguyên; không tự phê duyệt, sửa split hay upload dữ liệu.

Trên GPU chỉ cần hai split đã duyệt tại `private_data/myai-v24/`, chuyển qua SCP
với SSH sẵn có và kiểm tra SHA. Không cần database cửa hàng, raw datasets,
provenance text, external test hoặc WANDS để fine-tune.

## Kiểm thử thực tế

| Kiểm tra | Kết quả |
|---|---|
| `.venv\Scripts\python.exe -m pip check` | BLOCKED: launcher không truy cập được Python 3.11 gốc trong sandbox |
| Cùng interpreter chạy unittest | BLOCKED cùng nguyên nhân; không xóa/sửa venv |
| 51 unit hiện có qua runtime dự phòng | **51/51 PASS** |
| Thêm 2 guard test rồi chạy lại | **53/53 PASS** |
| Regression cũ | **126/126**, **42/42** |
| Holdout v2.4 | **63/65**, đúng hai finding cũ H24-063/H24-065 |
| Export đề xuất không raw/private data | Unit 53 (52 PASS, 1 SKIP Windows venv absent), preparer 7/7, quality 7/7, scratch DB, regression và baseline holdout đúng |
| PowerShell | Parse 10 script, 0 lỗi; selector chạy được với MYAI_PYTHON dự phòng |
| Shell | Git Bash `bash -n` PASS; không phải Linux GPU runtime PASS |
| WANDS | SHA-256 ba CSV + LICENSE PASS |
| Bảo toàn input/index | 118 input nguyên SHA, index thật nguyên byte |
| Preflight hiện tại bằng runtime công cụ | BLOCKED ML/CUDA/tokenizer/weights/host, exit 2; dataset/config/atomic filesystem PASS |

Runtime dự phòng: Python 3.12.14 của công cụ, pydantic cùng ABI; backend dùng
wheel `py3-none-any` đã lưu ở đợt v2.3, giải nén vào output riêng để namespace
package hoạt động. Không copy extension 3.11, không tạo thêm venv. Lần zip-import
đầu lỗi namespace opentelemetry, đã khắc phục bằng giải nén wheel thuần và chạy lại.

Bằng chứng ngoài lần chạy này: `outputs/import_check_after_install.json` có full
ML imports PASS; `outputs/qwen_preflight_tokenizer_v24_01/report.json` ghi tokenizer
thực 3.866/263, max 685/432 token, không cắt completion, loss mask/QLoRA/diagnostic
adapter roundtrip PASS. Giữ như bằng chứng lần chạy trước; sandbox hiện tại không
tái xác minh được `.venv`. Không coi diagnostic adapter là model 9B thật.

Các log mới ở `outputs/repository_cleanup_v24/tests/`, preflight mới ở
`.../preflight_current/`, export tests ở `.../preview/clone/outputs/clone_checks/`.
Lần chạy cuối `.../final_offline_checks/summary.json` có 7 nhóm kiểm tra thành
công/đúng baseline, không thay đổi input được bảo vệ; unit 53/53, preparer và
quality mỗi bộ 7/7. Index thật vẫn 478 entry; trạng thái cuối A=455, AM=20,
M=1, AD=2, untracked=12 nhóm. Các sửa đổi nguồn chưa tự stage.
Không có Linux GPU runtime, không thuê máy, tải 9B, train, tạo key hay thay DB.

## Trước khi push: thao tác còn cần ngoài sandbox

Từ PowerShell workspace, dùng interpreter Python đang hoạt động của bạn:

```powershell
python -m scripts.cleanup_git_index --plan outputs/repository_cleanup_v24/index_plan.json --apply
git status --short
git ls-files --cached --ignored --exclude-standard
git diff --cached --stat
```

Helper kiểm tra đúng path/mode/blob đã review, backup index rồi chỉ dùng
`git rm --cached -f`; **không xóa file trên disk**. `-f` cần cho gitlink staged mới.
Nếu index đã đổi kể từ plan, script dừng; tạo plan mới với đường output mới và review.
Không dùng reset hard/clean/rewrite history. Cache có thể để nguyên vì đã ignore.

Sau khi review, stage mã nguồn/cấu hình/tài liệu/test mới và các sửa đổi mong muốn;
đừng push khi dữ liệu cũ vẫn staged. File nên commit là source `myai/`, `scripts/`,
`windows/`, các công cụ chuẩn bị/quality/evaluation, `tests/`, `evaluations/`,
`configs/`, `docs/`, README/install/requirements, web và fixture CSV/policy/126 ca
do dự án tạo. Bao gồm các file untracked có từ phiên trước như
`scripts/verify_v24.py`, `scripts/create_grounded_evaluation_v24.py`,
`evaluations/sales_grounding_v24/`, audit v2.4.

Không commit `.venv`, database, model/tokenizer cache, adapter/checkpoint, raw,
SFT chưa duyệt, provenance/quarantine, output/log/wheel/archive hoặc credentials.
Audit lịch sử giữ đường dẫn log local; các log này cố ý không có trên GitHub.

History hiện chỉ có README, chưa phát hiện credential pattern mạnh trong source
đề xuất; scan heuristic không thay thế review. Không tự rewrite history/đổi khóa.
Đối tượng staged cũ vẫn có thể nằm trong `.git` local; chưa commit thì chúng không
được push theo lịch sử commit bình thường. Không chạy GC để cố giảm dung lượng.

Chỉ sau khi untrack, stage và review lại mới tự commit/push theo ý chủ dự án.
Remote hiện chưa chứa phần lớn source: clone remote **ngay bây giờ chưa train được**.
