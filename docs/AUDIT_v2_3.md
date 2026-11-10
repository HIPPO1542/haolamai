**MyAI v2.3 — kiểm tra tiếp theo ngày 09/11/2026**

Cập nhật mới: [AUDIT_v2_4.md](../AUDIT_v2_4.md). Theo yêu cầu sau đó của chủ dự án,
ba venv đã được xóa; các mô tả môi trường trong v2.3 bên dưới là lịch sử.

Đã khôi phục đường chạy backend trong môi trường mới, tạo candidate SFT đã cách
ly thêm rủi ro, chuẩn bị benchmark intent/ranking riêng và bổ sung preflight Qwen.
Chưa hoàn thành môi trường ML cho Qwen3.5-9B. Không có huấn luyện, thuê GPU, tạo key
trong database thật hoặc thay đổi database sản xuất.

Bằng chứng tổng hợp: [final_verification.json](../outputs/v2_3/final_verification.json),
[17 nhóm hồi quy](../outputs/v2_3/full_regression/summary.json),
[log unit/API](../outputs/v2_3/full_regression/unit.log).

**Môi trường Windows**

Audit v2.2 kết luận Python 3.11 gốc “đã mất” là quá mạnh. Phiên này xác minh được
thư mục gốc bị **Access denied** trong môi trường thực thi, và launcher cũ không
khởi chạy được interpreter mà `pyvenv.cfg` tham chiếu. Chưa chứng minh Python đã
bị xóa trên máy người dùng. `.venv` và cấu hình gốc được giữ nguyên.

Đã tạo `.venv-backend-v23` bằng Python 3.12.14 truy cập được. Môi trường này thừa
kế site-packages của runtime nền; không tự chứa toàn bộ dependency. Script phục
hồi chỉ tái đóng gói 11 distribution `py3-none-any` từ `.venv`, đối chiếu hash
RECORD từng tệp trước khi cài offline. Không sao chép extension CPython 3.11 sang
Python 3.12. [Báo cáo phục hồi](../outputs/v2_3/backend_repair/report.json) và
[`pip check`](../outputs/v2_3/backend_repair/pip_check.log) xác nhận backend hoạt động.

| Kiểm tra | Kết quả |
|---|---|
| FastAPI/Uvicorn/Pydantic trong môi trường mới | PASS; API TestClient và selector PowerShell chạy được |
| Dependency backend | `pip check`: không có requirement hỏng |
| Import thử thư viện cũ bằng runtime 3.12 để chẩn đoán | FastAPI, huggingface_hub, tokenizers import được; không đồng nghĩa toàn bộ ML hoạt động |
| Torch và các thư viện phụ thuộc Torch | BLOCKED: `torch_python.dll`, WinError 126 trong phép thử chéo ABI |
| Transformers/PEFT/TRL | BLOCKED ở regex extension khi thử thư viện cũ trên 3.12 |
| datasets | BLOCKED ở `pyarrow.lib` trong phép thử chéo ABI |
| Môi trường backend mới, riêng biệt | Chỉ cài dependency backend; các thư viện ML chưa có, không giả vờ đầy đủ |
| GPU thực tế | RTX 3050, 4.096 MiB VRAM; không đáp ứng ngưỡng 9B QLoRA hiện tại |
| Tải Python/gói từ shell | Kết nối bị chặn WinError 10013; không cài thêm qua mạng |

Các lỗi khi trộn package CPython 3.11 với 3.12 **không chứng minh** bản cài cũ sẽ
lỗi trên Python 3.11 đúng ABI. Chưa đủ căn cứ quy lỗi cho NVIDIA driver hoặc tự
thay Torch/CUDA. Chi tiết trong [legacy_imports.json](../outputs/v2_3/legacy_imports.json)
và [backend_imports.json](../outputs/v2_3/backend_imports.json).

`windows/python.ps1` chọn interpreter truy cập được theo thứ tự `.venv-qwen-v23`,
`.venv-backend-v23`, `.venv`; `MYAI_PYTHON` cho phép chỉ rõ interpreter. Các launcher
start/check/train/evaluate/download dùng selector này. `setup.ps1` mặc định tạo
môi trường Qwen mới, từ chối đường dẫn đã tồn tại và không ghi đè `.venv` cũ.
`scripts/preflight.py` giờ kiểm tra import thật và trả lỗi khi ngăn xếp chưa đủ.
Phiên này không chạy setup/download/start/train launcher.

**Candidate fine-tuning mới**

Nguồn được chọn là candidate v2.2 đã sửa lỗi ngân sách tại
`outputs/verified_v2_2/review_candidate`. Candidate mới:
[`outputs/v2_3/sft_candidate`](../outputs/v2_3/sft_candidate).

| Split | Nguồn | Candidate mới | Cách ly thêm |
|---|---:|---:|---:|
| Train | 7.833 | **7.127** | 706 |
| Validation | 290 | **272** | 18 |
| Test external | 1.033 | **1.033** | 0; giữ nguyên byte |
| Benchmark MyAI | 126 | **126** | 0; giữ nguyên byte |

724 dòng được cách ly bằng tham chiếu `source_line` và hash bản ghi, không xóa
khỏi nguồn. Lý do có thể chồng lấp: 489 câu dài cần duyệt, 133 dòng thuộc nhóm câu
hỏi đã dành cho heldout, 101 dòng có khẳng định số liệu chưa có context xác minh,
5 cờ trạng thái chưa có kết quả hệ thống, 6 cờ PII, 8 cờ ngữ cảnh y tế.

Đã đọc 18 bản ghi chọn lọc, gồm toàn bộ 6 cờ PII và 8 cờ y tế. Sáu cờ PII khớp
vào hậu tố số của mã đơn chữ–số, không phải bằng chứng chắc chắn có số điện thoại;
vẫn cách ly do chưa xác nhận nguồn gốc/quyền riêng tư của các định danh. Một số
mẫu y tế có tool result hỗ trợ việc chuyển người tư vấn; cờ này là giới hạn phạm
vi ngành, không phải kết luận câu trả lời sai. Một cờ trạng thái khớp nhầm câu điều
kiện trong chính sách; mẫu vẫn bị cờ câu dài. Không khôi phục hàng loạt.
[Ghi chú đọc mẫu](../outputs/v2_3/manual_review_notes.json) ghi rõ phạm vi 18 mẫu,
không gọi đây là duyệt thủ công toàn bộ 7.127 dòng.

Quy tắc giữ test trước, rồi validation đã làm sạch, rồi train. Không còn trùng
câu hỏi chuẩn hóa giữa ba split; kiểm tra độc lập cũng không tìm thấy prompt/bản
ghi train trùng test/dev gốc sau chuẩn hóa. Test được chép nguyên byte, không lọc
hoặc đưa vào train. Test vẫn chứa các cờ chất lượng ban đầu để báo riêng; không
sửa test nhằm cải thiện điểm. Xem
[audit candidate](../outputs/v2_3/sft_candidate/audit_report.json) và
[đối chiếu độc lập](../outputs/v2_3/sft_candidate_independent_audit.json).

Đây vẫn là **candidate tự động, `ready_for_training=false`**. Cách ly không đồng
nghĩa mọi mẫu bị cờ đều sai; số còn lại không phải chứng nhận sạch PII/ngữ nghĩa.

**Tìm kiếm đa ngành và dữ liệu nguồn**

Đã bổ sung giao nhau bộ lọc với các cách nói “ngân sách”, “không vượt quá”, phân
biệt sắc độ như “đỏ đô”, và alias thuộc tính `color/material/brand/capacity` với
`màu/chất liệu/thương hiệu/dung tích`. Thêm BM25 index độc lập, hiện dùng làm
baseline đánh giá nguồn search; chưa triển khai router/ranker mới vào API.

Tất cả output nguồn search nằm tại
[`outputs/v2_3/search_benchmarks`](../outputs/v2_3/search_benchmarks), **không phải
SFT chatbot**. Nguồn gốc, SHA-256 và điểm đo trong
[report.json](../outputs/v2_3/search_benchmarks/report.json).

| Nguồn | Xử lý | Split mới | Kết quả baseline test |
|---|---|---|---|
| Vietnamese E-commerce Intent | Cách ly 2 nhóm/4 dòng nhãn mâu thuẫn; bỏ 2 bản trùng cùng nhãn sau chuẩn hóa | 1.601 train / 201 validation / 206 test; chia theo nhóm câu, phân tầng nhãn | Accuracy 0,7427; macro-F1 0,7283; nearest-neighbor lexical từ train |
| WANDS | 1.575 dòng lặp cặp; cách ly 14 cặp/30 dòng có nhãn mâu thuẫn; còn 231.859 phán xét duy nhất | 384 train / 48 validation / 48 test query; sản phẩm là catalog chung | nDCG@10 0,6447; recall@10 0,0584; Exact MRR@10 0,4487 |

Con số 16 trong preflight trước là số lần nhãn lặp khác nhãn đầu tiên; 14 ở đây
là số **cặp** mâu thuẫn duy nhất, không phải thay đổi nguồn. WANDS không cung cấp
ground truth giá/tồn kho; query_class và nhãn độ liên quan không vào BM25 index.
Unjudged products được tính relevance=0; trung bình 1,479 sản phẩm trong top 10
không có judgment. Không chọn tham số hoặc sửa baseline sau khi xem test metrics.
Đã kiểm tra lại nhóm câu hỏi trong các tệp output, overlap train/validation/test=0.

Bộ acceptance mới có 42 ca/7 ngành, catalog hoàn toàn mới trong SQLite RAM,
được tạo **sau khi** development tests và 126 ca hồi quy đã qua. Hash mã thuật
toán và tệp suite được khóa trong
[`freeze.json`](../evaluations/search_holdout_v23/freeze.json) trước lần chạy đầu.
Kết quả **37/42**, không sửa thuật toán sau khi xem kết quả. Đây là holdout tự biên
soạn, không phải nghiên cứu blind bởi bên thứ ba.

| Ca chưa đạt | Khoảng trống đã bộc lộ |
|---|---|
| H23-038 | “còn sẵn” chưa lọc stock>0, trả bình đã hết hàng |
| H23-039 | Chưa ánh xạ “không dây” sang kết nối Bluetooth |
| H23-040 | Chưa quy đổi `1800ml` thành `1.8L` trong thuộc tính |
| H23-041 | Chưa ánh xạ truy vấn “đồ vệ sinh cho mèo” sang loại sản phẩm |
| H23-042 | Chưa hiểu khoảng giá viết tắt `300-360k` |

[Kết quả giữ nguyên](../outputs/v2_3/heldout_results.json) là các mục tồn đọng cho
phiên bản thuật toán sau. Khi dùng chúng để sửa, suite này phải chuyển thành hồi
quy và cần holdout mới; không tiếp tục gọi nó là test chưa từng dùng.

**Preflight Qwen3.5-9B**

`scripts.finetune --preflight-only` đi vào nhánh kiểm tra trước mọi lệnh huấn luyện.
Không có optimizer/trainer chạy, không tải trọng số. Script kiểm tra schema và
tách split, import API thật, cấu hình QLoRA, tokenizer/chat template và số completion
token còn lại sau truncation nếu tokenizer có sẵn. Nó chuẩn bị phép save/load
tensor Torch/safetensors và adapter CPU rất nhỏ, chưa huấn luyện, khi đủ thư viện.
Các nhánh chưa chạy không được báo PASS.

| Kiểm tra hiện tại | Trạng thái |
|---|---|
| Schema và split candidate mới | PASS |
| Ghi/flush/fsync/rename/đọc file checkpoint thử | PASS, chỉ chứng minh filesystem |
| Cú pháp script train | PASS |
| Import đầy đủ ngăn xếp Qwen | BLOCKED |
| Tokenizer Qwen/token counts/truncation | BLOCKED: chưa có tokenizer đúng model và transformers hoạt động |
| Trọng số model | BLOCKED: chưa có local config/weights |
| Config/API QLoRA | BLOCKED bởi import; chưa xác nhận tương thích runtime |
| Torch/safetensors model checkpoint, PEFT roundtrip | BLOCKED; chưa thực hiện, không giả lập thành công |
| GPU cho cấu hình 9B hiện tại | BLOCKED: máy chỉ có 4 GB VRAM |

Kết quả chi tiết: [qwen_preflight_verified/report.json](../outputs/v2_3/qwen_preflight_verified/report.json).
Lựa chọn text-only `Qwen3_5ForCausalLM` cần dùng text config; đường đa phương thức
có config/processor riêng theo
[tài liệu Transformers chính thức](https://huggingface.co/docs/transformers/model_doc/qwen3_5).
Đã đối chiếu nguồn thư viện cài tại máy; load model/adapter thật vẫn chưa kiểm chứng.

Chạy lại preflight khi có môi trường ML và tokenizer hợp lệ bằng output mới:

```powershell
$env:MYAI_PYTHON = '.venv-qwen-v23/Scripts/python.exe'
& $env:MYAI_PYTHON -m scripts.finetune --preflight-only `
  --preflight-output outputs/new_qwen_preflight `
  --train outputs/v2_3/sft_candidate/train.jsonl `
  --valid outputs/v2_3/sft_candidate/validation.jsonl --max-length 1024
```

Không chạy lệnh này với kỳ vọng “ready” trước khi có interpreter tương thích,
tokenizer/model files và phần cứng phù hợp. Không hạ âm thầm xuống model khác.

**Kiểm thử và việc còn lại**

- 37 unit/API/data-safety/development tests + 7 preparer + 7 quality-gate = **51/51 PASS**.
- 126/126 ca hồi quy truy xuất cũ PASS; 17 nhóm offline runner đều exit 0.
- Holdout mới: **37/42**, giữ 5 finding như trên, tách khỏi kết luận hồi quy.
- 48 tệp Python parse không có SyntaxWarning; 9 script PowerShell parse thành công.
  Selector interpreter đã được chạy trong test bằng execution policy chỉ cho tiến
  trình test; không đổi policy toàn máy, không chạy train/setup/download launcher.
- Schema, hash và phép đối chiếu độc lập xác nhận nguồn `data`/`datasets` không đổi;
  DB thật chỉ đọc để kiểm tra, không tạo key trong DB thật. Mọi key trong API unit
  test là fixture database tạm, không phải credential cửa hàng đang vận hành.

Ưu tiên tiếp theo là khôi phục một interpreter Python 3.11 có thể truy cập hoặc
cài bộ wheel đúng ABI trong môi trường Qwen mới. Phiên này chưa làm được vì ràng
buộc truy cập interpreter và kết nối shell. Sau đó chạy lại import/tokenizer/
checkpoint preflight, duyệt candidate và quyền sử dụng dữ liệu trước bất kỳ train
nào. Chưa đo VRAM/tốc độ/chất lượng Qwen, chưa khẳng định các câu trả lời không bịa.
Năm finding holdout, router/ranker tốt hơn, tải lớn và các hạng mục SaaS production
ở audit trước vẫn còn; không dùng PASS cấu trúc để thay cho nghiệm thu đó.
