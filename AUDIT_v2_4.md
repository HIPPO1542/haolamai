**MyAI v2.4 — audit ngày 09–10/11/2026**

**Kết luận: `ready_for_training = false`.** Đã triển khai và kiểm thử tìm kiếm,
curation dữ liệu, guard chống xác nhận hành động chưa thực hiện và hợp đồng
preflight/loss mask/checkpoint. Chưa import được ngăn xếp ML hoặc chạy Qwen3.5-9B
thật. Theo yêu cầu mới nhất của chủ dự án, đã xóa cả ba venv; không tạo lại môi
trường. Cài thủ công qua [requirements.txt](requirements.txt) và
[INSTALL_v2_4.md](INSTALL_v2_4.md).

Nguồn bằng chứng: [xác minh cuối](outputs/v2_4/verification_final.json),
[kiểm tra trước khi khóa holdout](outputs/v2_4/pre_freeze_checks.json),
[log unit trước cleanup](outputs/v2_4/unit_before_freeze.log),
[kiểm tra sau cleanup](outputs/v2_4/after_cleanup_tests.json),
[preflight hiện tại](outputs/v2_4/preflight_after_cleanup/report.json).

**1. Tệp thêm và sửa**

| Nhóm | Tệp |
|---|---|
| Thêm: cài đặt và audit | `requirements.txt`, `INSTALL_v2_4.md`, `AUDIT_v2_4.md`, `docs/AUDIT_v2_4.md`, `scripts/audit_workspace.py`, `scripts/verify_v24.py` |
| Thêm: chuẩn hóa/grounding | `myai/normalization.py`, `myai/search_lexicon.json`, `myai/grounding.py` |
| Thêm: dữ liệu | `scripts/dataset_quality_v24.py`, `scripts/grounded_sales_v24.py`, `scripts/build_sft_v24.py`, `scripts/verify_sft_v24.py` |
| Thêm: môi trường/QLoRA | `scripts/setup_qwen_environment.py`, `scripts/qwen_training_contract.py`, `scripts/qwen_preflight_v24.py`, `windows/setup_qwen_v24.ps1` |
| Thêm: đánh giá | `scripts/create_holdout_v24.py`, `scripts/create_grounded_evaluation_v24.py`, `MyAI_Search_Integration_v2_2/benchmark_retrieval_v24.py`, `MyAI_Search_Integration_v2_2/evaluate_router_v24.py` |
| Thêm: unit test | `tests/test_search_v24_development.py`, `tests/test_sft_v24_quality.py`, `tests/test_qwen_contract_v24.py` |
| Sửa: runtime | `myai/retrieval.py`, `myai/engine.py` |
| Sửa: script | `scripts/diagnose_environment.py`, `scripts/download_model.py`, `scripts/finetune.py`, `MyAI_Prepare_Datasets_v2/prepare_v2.py` |
| Sửa: launcher | `windows/python.ps1`, `windows/setup.ps1`, `windows/train.ps1`, `windows/evaluate.ps1`, `windows/download.ps1` |
| Sửa: test/evaluator | `tests/test_core.py`, `tests/test_preflight_safety.py`, `MyAI_Search_Integration_v2_2/evaluate_frozen_holdout.py` |
| Sửa: tài liệu | `README.md`, `README_Windows.md`, `docs/SEARCH_API.md`, `docs/AUDIT_v2_3.md`, `MyAI_Search_Integration_v2_2/README.md` |

Artifact mới ở `outputs/v2_4`, `evaluations/search_holdout_v24` và
`evaluations/sales_grounding_v24`; dữ liệu đầu vào và output các phiên trước giữ
nguyên. Manifest cuối có danh sách thay đổi trong các thư mục được snapshot;
`scripts/audit_workspace.py` được tạo trước snapshot và thay đổi import ở
`MyAI_Prepare_Datasets_v2/prepare_v2.py` được liệt kê thủ công thêm ở bảng này.

Git chưa có khi bắt đầu đợt kiểm tra, nhưng đã có ở lần đọc trạng thái cuối, trên
`main` theo `origin/main`, với nhiều tệp đã staged. Không sửa index, không commit,
không push; giữ các thay đổi song song của chủ dự án, kể cả nội dung README.

**2. Môi trường Python/ML và yêu cầu xóa venv**

| Thời điểm | Kết quả thực tế |
|---|---|
| Kiểm tra `.venv` cũ | Launcher không chạy được interpreter 3.11; đường dẫn gốc bị chặn truy cập. Không kết luận Python đã bị xóa |
| `.venv-backend-v23` trước cleanup | Python 3.12 chạy được FastAPI/Uvicorn và các unit/API test |
| Tạo `.venv-qwen-v24` | Venv sạch, không kế thừa site-packages, không copy extension 3.11 sang 3.12 |
| Cài Torch từ cu128 | Thất bại; probe kết nối xác nhận WinError 10013 |
| Lệnh cu132 do chủ dự án chỉ định | Đã chạy `pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu132`; thất bại do WinError 10013 |
| Import sau lệnh cu132 | `ModuleNotFoundError: No module named 'torch'`; không báo PASS |
| Yêu cầu tiếp theo của chủ dự án | Đã xóa `.venv`, `.venv-backend-v23`, `.venv-qwen-v24`; cả ba đường dẫn không còn tồn tại |
| Trạng thái hiện tại | Không có project venv; chủ dự án tự cài bằng `requirements.txt`. Runtime công cụ dùng cho kiểm tra stdlib không phải môi trường ML của dự án |

Log: [setup ban đầu](outputs/v2_4/environment/report.json),
[network probe](outputs/v2_4/network_probe.json),
[pip cu132](outputs/v2_4/environment/cu132_install.log),
[import cu132](outputs/v2_4/environment/cu132_import.log),
[cleanup theo yêu cầu](outputs/v2_4/environment/user_requested_cleanup.json).
`No matching distribution` sau lỗi socket không đủ chứng minh cu132 không có wheel
phù hợp: phiên này chưa truy cập được danh sách wheel.

`requirements.txt` là dải phiên bản cho resolver, chưa phải lockfile đã nghiệm thu.
Nguồn cu132 được thêm theo yêu cầu; cần kiểm tra `torch.version.cuda` và CUDA thực
tế sau cài. `pip check` của một venv rỗng không chứng minh ngăn xếp ML hoạt động.
Launcher chỉ tìm `.venv` hoặc `MYAI_PYTHON`; không tự tạo lại ba môi trường.

**3. Năm lỗi tìm kiếm đã giải quyết**

- “Còn sẵn” lọc `stock > 0`; câu hỏi “X còn sẵn không?” vẫn giữ X hết hàng làm bằng chứng.
- “Không dây” chấp nhận Bluetooth/Wi-Fi/2.4 GHz khi có bằng chứng trong thuộc tính
  kết nối hoặc tên sản phẩm; không tự gán wireless cho hàng chưa có dữ liệu kết nối.
- Đơn vị được so theo dimension và Decimal: ml/L, g/kg, mm/cm/m, W/kW, MB/GB/TB;
  GiB khác GB. `1800ml` bằng `1.8L`; khối lượng không được so như dung tích.
- Nhóm “đồ vệ sinh cho mèo” dùng từ vựng ngành có cấu hình, kiểm tra bằng chứng từ
  tên/thuộc tính catalog. Không có ID, tên SKU đầy đủ hoặc giá benchmark trong luật.
- Khoảng giá `300–360k`, `300-360k`, dấu ≤/≥ và dạng `1tr2` được chuẩn hóa; điều kiện
  giá, tồn kho, size, màu, đơn vị và thuộc tính được giao nhau. Cách viết mơ hồ bị từ chối.

Có sửa chính tả/viết tắt có giới hạn như `ko`, `khg`, `bluetooh`, `blutooth`;
không fuzzy-match tùy ý SKU hoặc giá. Các điều kiện phủ định chưa hiểu được fail
closed. SQL vẫn dùng tham số và khóa tenant/active trước lọc/xếp hạng; không đổi
schema hay database sản xuất, không thay retrieval bằng LLM.

Thêm guard từ chối các câu tự nhận đặt hàng, hoàn tiền, đặt lịch, chuyển nhân viên
khi backend catalog không thực hiện hành động đó; kiểm tra thêm tồn kho được nêu
trong câu trả lời một sản phẩm. Đây là guard bảo thủ, có thể fallback với câu hợp
lệ; chưa bảo đảm phát hiện toàn bộ sai thuộc tính, sai chính sách hay tráo giá giữa nhiều sản phẩm.

**4. Hồi quy, holdout mới và chi phí truy xuất**

| Bộ | Kết quả |
|---|---|
| 126 ca hồi quy trước | **126/126** |
| 42 ca v2.3 đã chuyển thành regression | **42/42**, trước sửa là 37/42 |
| Holdout v2.4 | **63/65**, 22 sản phẩm/10 nhóm catalog mới; khóa trước lần chạy đầu |

Hai finding còn lại: H24-063 “đồ bảo vệ hô hấp” chưa ánh xạ tới mặt nạ lọc bụi;
H24-065 “đồ bảo hộ cho thợ hàn” chưa ánh xạ tới găng tay hàn. Đều là bỏ sót truy vấn,
không dùng kết quả này để tiếp tục sửa thuật toán rồi gọi lại là test độc lập.
Mã runtime, lexicon và tệp suite vẫn đúng hash đã khóa; tên sản phẩm của holdout
không xuất hiện trong train cuối hoặc fixture phát triển. Đây là holdout tự biên
soạn, không phải nghiệm thu blind của bên thứ ba.

Bằng chứng: [regression 42](outputs/v2_4/regression_42_final.json),
[regression 126](outputs/v2_4/regression_126_final.json),
[holdout](outputs/v2_4/holdout_v24.json),
[freeze](evaluations/search_holdout_v24/freeze.json).

Đo warm, cùng 42 fixture nhỏ, 210 calls mỗi phiên bản, không tính setup database:

| Phiên bản | Median | p95 |
|---|---:|---:|
| Baseline v2.3 giữ trong snapshot | 0,061 ms | 0,085 ms |
| v2.4 | 0,121 ms | 0,169 ms |

Chi phí tăng do chuẩn hóa/lọc; không gọi đây là load test SaaS hoặc số đo catalog
lớn. Chưa triển khai BM25/FTS/reranker vào API.
[Báo cáo đo](outputs/v2_4/retrieval_cost_final.json).

**5. Intent và WANDS được giữ riêng**

Đã đọc và kiểm tra lại output v2.3, tái dựng output riêng tại
`outputs/v2_4/search_benchmarks_verified`. Không đưa các cặp WANDS vào SFT.

| Nguồn | Xử lý và đánh giá |
|---|---|
| Intent tiếng Việt | 1.601 train / 201 validation / 206 test; cách ly 2 nhóm/4 dòng mâu thuẫn, bỏ 2 bản trùng cùng nhãn |
| Router | Chọn k=5 bằng macro-F1 validation; test đo một lần: accuracy **0,7816**, macro-F1 **0,7816**, so với baseline k=1 v2.3 0,7427/0,7283 |
| Chi phí router | Median 0,563 ms/query, p95 0,991 ms/query trong phép đo này; chưa tích hợp router vào backend |
| WANDS | 42.994 sản phẩm / 480 query; loại lặp và cách ly 14 cặp/30 dòng mâu thuẫn, còn **231.859** phán xét duy nhất |
| Ranking WANDS | 384/48/48 query train/validation/test; nDCG@10 **0,6447**, Exact MRR@10 **0,4487**, Recall@10 **0,0584** |

Nhóm query không trùng giữa các split; cặp mâu thuẫn không còn trong judgments
sạch. WANDS dùng baseline cố định, điểm giữ nguyên v2.3, không có cải thiện mới
được khẳng định. Unjudged products tính relevance=0; trung bình 1,479 mục top 10
chưa có judgment. Điểm tiếng Anh không chứng minh chất lượng tìm sản phẩm tiếng
Việt, giá/tồn kho hoặc câu trả lời chatbot.
[Router](outputs/v2_4/router.json), [nguồn/ranking](outputs/v2_4/search_benchmarks_verified/report.json).

**6. Candidate fine-tuning cuối đợt v2.4**

Vị trí: [`outputs/v2_4/sft_candidate_final`](outputs/v2_4/sft_candidate_final).
Chữ “final” là bản chốt artifact của đợt kiểm tra, không phải phê duyệt huấn luyện.

| Split | v2.3 | Candidate v2.4 |
|---|---:|---:|
| Train | 7.127 | **3.866** |
| Validation | 272 | **263** |
| External test | 1.033 | **1.033**, nguyên byte |
| Benchmark MyAI | 126 | **126**, nguyên byte |

Từ pool 7.127 train + 272 validation + 1.080 mẫu mới, giữ 3.866 train và 263
validation; 4.350 dòng được cách ly bằng tham chiếu nguồn, không xóa dữ liệu cũ.
Các cờ chồng lấp gồm: 388 khẳng định số ngày/giờ/% thiếu context, 36 câu nhận đã
thực hiện hành động ngoài backend catalog, 3 gần trùng câu hỏi heldout, 303 cờ
vượt giới hạn template chăm sóc và 3.867 cờ vượt quota kỹ năng.

1.080 mẫu mới có task specification và gold tính từ catalog; verifier kiểm tra
lại toàn bộ, gồm lọc nhiều điều kiện, so sánh hàng còn kho, giá/tồn kho/thuộc tính
thay đổi theo context và lịch sử hội thoại. Oracle không gọi retrieval hoặc LLM.
Các assertion consistency và test cố ý làm sai đáp án/tenant đã chạy; điều này
không thay thế duyệt ngôn ngữ/ngữ nghĩa bởi người.

| Kỹ năng | Mẫu | Tỷ lệ hỗn hợp ước tính |
|---|---:|---:|
| Tra cứu/tìm/lọc sản phẩm | 1.600 | 41,4% |
| Tư vấn/so sánh/nhiều lượt | 666 | 17,2% |
| Chính sách/giao hàng/thanh toán/đổi trả | 600 | 15,5% |
| Chăm sóc/khiếu nại | 600 | 15,5% |
| Thiếu dữ liệu/phạm vi/chống bịa | 400 | 10,3% |

**Nhãn của 2.786 mẫu seed là ước tính theo regex/cấu trúc prompt.** Chỉ 1.080 mẫu
mới có kỹ năng được xác định trực tiếp bởi task specification; không trình bày
toàn bộ tỷ lệ trên như nhãn đã được người xác minh. Validation/test cũng có phân
bổ ước tính riêng trong manifest.

Nguồn train: 1.292 Empath train, 268 SaaS train, 368 addon train, 858 synthetic v2,
1.080 quy tắc v2.4. Các nguồn cũ được đối chiếu fingerprint sau chuẩn hóa; không
có mẫu train lấy từ raw test/dev/validation. Ít nhất **50,1%** train có nguồn
synthetic v2/v2.4 rõ ràng; addon cũng là dữ liệu minh họa. Chưa chứng nhận quyền sử
dụng hoặc tính tự nhiên của toàn bộ nguồn.

Không còn trùng câu hỏi chuẩn hóa giữa ba split. Near-duplicate dùng word-trigram
Jaccard ≥0,82, tối thiểu 8 từ và cùng tập token số; kiểm tra độc lập không tìm thấy
cặp còn lại theo tiêu chí này. Đây không phải phát hiện toàn bộ paraphrase/ngữ nghĩa.
Trong train còn 101 nhóm lặp câu hỏi, tối đa 72 context/nhóm, chủ yếu template
grounded/counterfactual; mức đa dạng này vẫn cần duyệt, không coi số dòng là chất lượng.

Validation cũ còn thiếu tình huống so sánh/nhiều lượt theo bộ phân loại ước tính.
Đã thêm **120 ca grounding độc lập, 30 sản phẩm chưa có trong train** tại
[`evaluations/sales_grounding_v24`](evaluations/sales_grounding_v24). Có 12 kỹ năng,
gold facts nhất quán và hash cố định; **chưa chạy Qwen để chấm** và tuyệt đối không
đưa file này vào train. Canonical validation 263 và external test không bị ghi đè.

Chi tiết: [manifest](outputs/v2_4/sft_candidate_final/audit_report.json),
[oracle/near-duplicate scan](outputs/v2_4/candidate_verification.json),
[grounding-eval manifest](evaluations/sales_grounding_v24/manifest.json).

**7. Preflight Qwen3.5-9B**

Đã đối chiếu model ID `Qwen/Qwen3.5-9B` và cấu hình text backbone theo
[config chính thức](https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/config.json).
Đường text-only dùng `Qwen3_5ForCausalLM`/text config theo
[Transformers](https://huggingface.co/docs/transformers/model_doc/qwen3_5).
Không chuyển sang 4B hoặc model khác để báo thành công cho 9B.

| Kiểm tra | Trạng thái hiện tại |
|---|---|
| Định dạng prompt/completion và split | PASS |
| Filesystem checkpoint write/fsync/rename | PASS cho file thử; không phải checkpoint model |
| Import thư viện ML thật | BLOCKED sau cleanup/cài mạng thất bại |
| Local config/trọng số/tokenizer/chat template | BLOCKED, chưa có file model/tokenizer hợp lệ |
| Token count, completion truncation, loss mask bằng tokenizer Qwen thật | BLOCKED; không dùng số ký tự thay token |
| Collator TRL thật và config QLoRA | BLOCKED vì import; unit fixture chỉ kiểm tra logic helper |
| Tensor/adapter roundtrip Qwen | BLOCKED, chưa chạy |
| Qwen3.5-9B forward/backward/checkpoint/resume thật | BLOCKED, không huấn luyện trong đợt này |
| Phần cứng hiện tại | GPU RTX 3050 4 GB; RAM khoảng 15,7 GiB và disk free khoảng 54,9 GiB tại phép đo; dưới các floor planning của script |

Preflight và train dùng chung pretokenization contract. Prompt phải là prefix
token của hội thoại đầy đủ; prompt/padding được mask `-100`. Collator TRL được
kiểm tra thực tế khi import được; train từ chối completion bị cắt một phần/toàn
bộ. Đây phù hợp với đường prompt/completion được mô tả trong
[tài liệu TRL](https://huggingface.co/docs/trl/en/sft_trainer), nhưng chưa được nghiệm
thu bằng tokenizer Qwen tại máy này.

QLoRA cấu hình NF4/double quantization, bf16 khi GPU hỗ trợ, gradient checkpointing,
AdamW; các config chỉ được báo PASS nếu construct thực sự thành công. Checkpoint
không tự prune; resume phải có adapter tensors, optimizer, scheduler, trainer state
và RNG state, với bước huấn luyện đã hoàn thành. Kiểm tra file và tensor probe
không được gọi là xác minh resume sau một bước QLoRA thật.

Train yêu cầu preflight report khớp interpreter/model/data SHA/max_length và
xác nhận candidate đã được người vận hành duyệt; không có report hợp lệ thì dừng
trước huấn luyện. Các runner v2 cũ cần cập nhật tham số mới, không phải đường bypass.

Floor planning trong script: 32 GiB RAM, 60 GiB disk trống, ≥14 GiB VRAM tổng và
≥12 GiB VRAM rảnh. Đây là gate ban đầu, **không phải peak-memory benchmark hoặc
cam kết GPU đó train được 9B**. Chưa có cơ sở chốt cấu hình thuê Vast.ai hoặc giá thuê.
Thư viện bitsandbytes cũng phải kiểm tra đúng runtime theo
[hướng dẫn chính thức](https://huggingface.co/docs/bitsandbytes/main/en/installation).

**8. Kiểm thử thực tế và giới hạn sau cleanup**

- Trước cleanup: **51/51 unit/API/development test PASS**; 42/42 và 126/126 hồi quy PASS.
- Sau cleanup: **49 non-API test chạy, 48 PASS và 1 SKIP** vì venv backend không
  còn; hai API test không chạy lại do thiếu FastAPI/TestClient. Không ghi SKIP/BLOCKED thành PASS.
- Dataset preparer **7/7**, quality-gate **7/7** PASS sau cleanup bằng runtime công cụ.
- Candidate schema, 1.080 oracle, tenant trong context, exact/near leakage và nguyên
  byte test/benchmark PASS theo các phép kiểm tra đã mô tả.
- Holdout mới 63/65; 120 ca grounding mới chỉ xác minh gold, chưa có model metrics.
- Python/PowerShell parse chỉ là syntax check. Không dùng chúng để báo import ML PASS.
- Không chạy optimizer step, model training, thuê GPU, deploy production hoặc tải trọng số.

**9. Lệnh cho môi trường có quyền/mạng phù hợp**

Không cần thêm venv thứ hai. Từ root, dùng Python 3.11/3.12 x64 bạn đã cài:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.diagnose_environment --output outputs/import_check_after_install.json
```

Sau khi imports đã hoạt động, có thể tải tokenizer/config riêng vào thư mục mới
(không tải weights) rồi đo token; nên dùng revision commit cụ thể:

```powershell
.\.venv\Scripts\python.exe -m scripts.download_model --model Qwen/Qwen3.5-9B --tokenizer-only --revision <commit-sha> --output models/Qwen3.5-9B-tokenizer-v24
.\.venv\Scripts\python.exe -m scripts.qwen_preflight_v24 --model models/Qwen3.5-9B-tokenizer-v24 --train outputs/v2_4/sft_candidate_final/train.jsonl --valid outputs/v2_4/sft_candidate_final/validation.jsonl --max-length 2048 --output outputs/qwen_preflight_after_install
```

Thay `<commit-sha>` bằng revision thật; chọn output chưa tồn tại. Tokenizer-only
vẫn phải báo weights/target-model checks BLOCKED. Để preflight full, chuẩn bị model
9B đầy đủ trên máy chủ có tài nguyên phù hợp và chạy cùng lệnh với model path đó.
Linux dùng `.venv/bin/python` tương ứng. Không có lệnh thuê GPU hoặc train trong
chuỗi khắc phục này. Chưa có lockfile được xác nhận; lưu tên/version package và
import report sau khi cài thành công để chốt môi trường tái lập.

**10. Việc chưa xử lý và bảo toàn dữ liệu**

Hai paraphrase holdout còn bỏ sót, taxonomy chưa phủ mọi ngành/cách nói; chưa đo
tải lớn/concurrency, chưa deploy router/ranker mới. Cần đánh giá Qwen thật trên
120 ca grounding và dữ liệu người dùng được duyệt, kiểm tra toàn diện bịa thuộc
tính/chính sách/tồn kho nhiều sản phẩm, privacy/rights và mức đa dạng template.

Tệp trong `data`, `datasets`, model/adapter cũ và output các phiên trước khớp hash
ban đầu. Chỉ ba venv bị xóa theo yêu cầu rõ ràng của chủ dự án; dữ liệu và database
sản xuất không thay đổi, không tạo API key trong DB thật. Các mutation/key trong
test nằm ở fixture tạm/in-memory. External test và benchmark không vào train.

`ready_for_training=false` dựa trên các BLOCKED thực tế: chưa có môi trường ML,
tokenizer/model 9B, token/loss-mask/checkpoint/resume kiểm chứng và tài nguyên phù
hợp; candidate chưa được duyệt đầy đủ. Kết quả hồi quy tốt không thay thế những điều kiện đó.
