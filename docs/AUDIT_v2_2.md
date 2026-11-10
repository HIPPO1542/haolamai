**Kết quả kiểm tra MyAI ngày 09/11/2026**

Cập nhật tiếp theo: [AUDIT_v2_3.md](AUDIT_v2_3.md) ghi kết quả phục hồi backend,
candidate 7.127/272/1.033, holdout mới và các chặn preflight Qwen. Kết luận cũ
“Python 3.11 gốc đã mất” được đính chính: xác minh được đường dẫn bị chặn truy cập,
chưa chứng minh interpreter đã bị xóa. Phần dưới giữ làm lịch sử kiểm tra v2.2.

Đã sửa luồng tìm kiếm và các lỗi kiểm thử trong workspace, bổ sung API `/search`
độc lập với model, chạy lại pipeline dữ liệu từ raw sang output riêng. Chưa thể
coi toàn bộ SaaS là sẵn sàng production hoặc xác nhận chất lượng Qwen: không có
trọng số/adapter trong workspace và chưa thực hiện inference thật, fine-tune hay thuê GPU.

Bằng chứng chính: [summary.json](../outputs/verified_v2_2/summary.json),
[log unit tests](../outputs/verified_v2_2/unit.log),
[kết quả 126 ca truy xuất](../outputs/verified_v2_2/search_benchmark.json),
[audit dữ liệu cũ](../outputs/verified_v2_2/dataset_audit.json),
[audit candidate mới](../outputs/verified_v2_2/new_candidate_audit.json).

**Cấu trúc và dữ liệu đã kiểm tra**

| Thành phần | Kết quả |
|---|---|
| `myai/` | SQLite, tenant/API key, retrieval, FastAPI, local Qwen, kiểm tra giá trong câu trả lời |
| `scripts/`, `windows/` | Quản trị, tải model, sinh dữ liệu, train/evaluate và các launcher; chỉ chạy công cụ offline/kiểm thử |
| SQLite hiện tại | Đọc qua `mode=ro`: 2 cửa hàng, 60 sản phẩm, 12 chính sách, 0 API key; quick_check=ok; không lỗi FK/JSON thuộc tính |
| `data/prepared_v2` | 8.005 train / 300 validation / 1.072 test / 126 benchmark |
| `data/prepared_v2_1_review` | 7.833 train / 290 validation / 1.033 test / 126 benchmark |
| Raw SaaS/Empath/addon | Đã đọc lại toàn bộ qua pipeline chuẩn bị, kiểm tra schema và quy tắc lọc |
| Raw intent tiếng Việt | 2.014 dòng, 12 nhãn, 223 `search_product`; 2 lần lặp câu với nhãn mâu thuẫn |
| WANDS | 42.994 sản phẩm, 480 query, 233.448 judgments; 1.575 lần lặp cặp, trong đó 16 lần khác nhãn; không FK thiếu |
| `MyAI_Search_Integration_v2_2` | Chưa tồn tại ở đầu phiên; đã tạo README và công cụ đánh giá truy xuất |

Workspace không có metadata Git. Các thay đổi hiện ở dạng tệp trong workspace;
không tạo commit hoặc push.

**Các sửa đổi chính**

- `myai/retrieval.py`: tách `search_products`/`SearchFilters`; hỗ trợ từ khóa/SKU,
  tiếng Việt có/không dấu, size/màu, thuộc tính dạng object/list, khoảng giá và
  giới hạn trên/dưới, tồn kho. Điều kiện tự nhiên và bộ lọc rõ ràng được giao nhau.
  Không trả sản phẩm không liên quan chỉ vì câu hỏi chứa “shop”, “sản phẩm” hoặc giá.
- `myai/db.py`: lọc tenant/active/giá/tồn kho bằng SQL có tham số trước khi xếp hạng;
  retrieval bỏ giới hạn ứng viên 2.000 sản phẩm. Không đổi schema/database hiện tại.
- Giữ sản phẩm hết hàng làm bằng chứng cho câu “X còn hàng không?”; yêu cầu tìm
  hàng có sẵn mới lọc stock>0. Ưu tiên tên SKU đầy đủ, tránh trả sản phẩm khác có
  một vài từ chung. Bảo toàn các từ “trắng”, “váy”, “tỏi” khi tìm kiếm.
- `myai/api.py`: thêm `POST /search`, tenant lấy từ API key; từ chối trường tenant
  do caller gửi, giá âm/khoảng sai, limit sai và thuộc tính sai cấu trúc. `/search`
  không tải model; `/chat` kiểm tra model khi sinh. `/health` có trạng thái tệp model/adapter.
- `myai/engine.py`: xử lý mapping `input_ids`/`attention_mask` từ chat template
  của Transformers đang cài, truyền mask vào generate và cắt đúng phần prompt.
  Bổ sung nhận ký hiệu `₫`; chuỗi giá lỗi từ model quay về thông tin đã xác minh.
- `scripts/training_data_guard.py`: kiểm tra train/validation khác nhau, không dùng
  tên tệp heldout cho train, chặn prompt trùng validation/test ngay trước khi nạp ML.
  Đây là kiểm tra trùng chuẩn hóa, không phải chứng nhận không rò rỉ ngữ nghĩa.
- `windows/train.ps1` bỏ tự sinh dữ liệu; `scripts/make_train_data.py` từ chối ghi
  đè train/validation có sẵn; fine-tune từ chối output adapter không rỗng.
- `synthetic_cases.py`: sửa lọc ngân sách “dưới” thành so sánh nghiêm ngặt `<`.
  Không sửa JSONL cũ; chạy lại vào output mới để có candidate kiểm tra được.
- `verify_v2.py` đọc được manifest của tập review, báo lỗi rõ khi message sai
  cấu trúc hoặc split rỗng. Công cụ evaluate trả exit code thất bại đúng và không
  coi câu trả lời fallback là model đã vượt kiểm thử.
- Thêm runner giữ log/hash và audit dữ liệu/provenance/database. Các output không
  ghi vào dữ liệu đầu vào. `windows/start.ps1 -SearchOnly` cho phép chạy tìm kiếm
  trước khi cài model nếu môi trường Python và API key đã sẵn sàng.

[Hợp đồng API và ví dụ request](SEARCH_API.md) mô tả chi tiết hành vi mới.

**Kiểm thử thực tế**

| Nhóm | Kết quả |
|---|---|
| Unit/API/retrieval/inference contract/data safety | 30/30 PASS |
| Dataset preparer | 7/7 PASS |
| Quality gate rules | 7/7 PASS |
| Data Pack và database fixture | PASS: 60 SKU/12 policy, tenant isolation, cập nhật giá/tồn kho |
| Database hiện tại chỉ đọc | PASS: schema/counts/quick_check/FK/attributes |
| Verify dữ liệu v2 và v2.1 review | PASS: schema, trùng chuẩn hóa, đối chiếu số lượng manifest |
| Preflight độ dài/hash và hai nguồn search | PASS về cấu trúc; vẫn có các cảnh báo chất lượng nêu dưới |
| Hồi quy truy xuất | 126/126 PASS; mỗi ca dùng database trong RAM riêng |
| Prepare từ raw, verify, quality gate, verify/audit candidate mới | PASS, tách riêng train/validation/test/benchmark |
| Cú pháp PowerShell | PASS; chỉ parse, không thực thi script tải/train/start |

17 nhóm công cụ trong runner đều exit 0. PASS của audit chứng minh các kiểm tra
được mô tả đã qua; `ready_for_training` vẫn là **false**. Các ca API dùng TestClient,
generator được inject trong test; kiểm thử inference chỉ kiểm tra giao diện token
với fixture, không khẳng định Qwen đã chạy. 126 ca là hồi quy dùng trong quá trình
sửa, cần bộ blind holdout mới để đo khả năng khái quát.

Lệnh chạy toàn bộ khi Python của dự án hoạt động:

```powershell
python -m scripts.run_offline_checks --output outputs/another_unique_audit
```

Trong phiên này `.venv/Scripts/python.exe` lỗi vì Python 3.11 gốc đã mất. Dùng
Python 3.12.14 sẵn tại runtime, thêm cuối `sys.path` thư viện của `.venv` qua tùy
chọn `--legacy-site-packages .venv/Lib/site-packages`; các dependency biên dịch
của Python hiện tại được ưu tiên. Không sửa `.venv`, không cài dependency thành công,
không tải model. Lần thử cài dependency từ PyPI bị chặn kết nối mạng trong phiên.
Có cảnh báo Starlette/httpx deprecated; kiểm thử API vẫn qua.
Cần tạo môi trường Python riêng phù hợp trước khi vận hành ứng dụng thật.

**Chất lượng fine-tuning và tách dữ liệu**

Không có bản ghi hoặc toàn bộ user prompt trùng giữa các split v2.1 review theo
chuẩn hóa đã kiểm tra. Đối chiếu lại tất cả test SaaS, dev/test Empath sau chuẩn hóa
cũng không tìm thấy prompt/bản ghi trong train. Benchmark 126 ca giữ nguyên byte
so với Data Pack. Còn 10 trường hợp trùng câu hỏi train–validation, 9 train–test,
4 validation–test; cần xem ngữ cảnh và hội thoại để quyết định tách nhóm.

Train v2.1 review còn 488 dòng bị heuristic gắn cờ, gồm 475 câu dài, 6 dòng nghi
PII và 8 dòng có ngữ cảnh y tế; có dòng mang nhiều cờ nên không cộng trực tiếp.
Validation có 14 dòng và test có 97 dòng cần review. Cờ là yêu cầu đọc lại, không
phải kết luận mọi dòng đều sai. Đã kiểm tra 2.384 dòng train có JSON context
(884 addon + 1.500 synthetic). 115 dòng nhắc giá khách đưa ra trong câu phủ nhận
đã được phân biệt với khẳng định giá không có nguồn.

Tập cũ có 13 câu trả lời khuyến nghị sản phẩm bằng đúng ngân sách dù câu hỏi dùng
“dưới”. Sau sửa generator và chạy lại pipeline, candidate mới có 0 trường hợp
kiểu này; không có giá khẳng định ngoài context theo phép kiểm tra hiện có.
Candidate mới vẫn giữ các mục cần người duyệt và **chưa được đưa vào sử dụng**.

Candidate mới nằm tại
[`outputs/verified_v2_2/review_candidate`](../outputs/verified_v2_2/review_candidate).
Số lượng 7.833/290/1.033 giữ nguyên; raw preparation trước quality gate vẫn tạo
8.005/300/1.072, cách ly 2.076 dòng. Quality gate tiếp tục giữ riêng 221 dòng rủi ro
cao. Các tệp trong `data/prepared_v2_1_review` và dữ liệu cũ khác giữ nguyên.

**Việc còn tồn đọng**

1. Duyệt PII/ngữ cảnh y tế, các câu dài và câu hỏi trùng theo ngữ cảnh; quyết định
   phạm vi ngành và quyền sử dụng nguồn trước khi chốt train. Chưa tự loại/xóa hoặc
   phê duyệt các dòng này. Cần xác nhận nguồn gốc/giấy phép và độ đa dạng hội thoại.
2. Cách ly 2 câu intent nhãn mâu thuẫn và các cặp WANDS nhãn mâu thuẫn; deduplicate
   và chia theo nhóm query chuẩn hóa trước khi đánh giá router/ranker. Chưa trộn
   hai nguồn này vào SFT, chưa dùng WANDS làm ground truth giá/tồn kho.
3. Chưa có tokenizer/trọng số/adapter để đo số token, completion bị cắt ở max_length,
   VRAM, hỗ trợ Qwen/PEFT/TRL và chất lượng câu trả lời thật. Kiểm tra giá cơ bản
   hiện tại không bảo đảm chống bịa tên, tồn kho, thuộc tính, hành động hoặc chính sách.
4. Retrieval hiện là lexical bảo thủ, có thể bỏ sót diễn đạt đồng nghĩa, lỗi chính
   tả và câu hỏi dài; bộ lọc thuộc tính rõ ràng là đường đi ổn định. Chưa đo tải
   catalog lớn, chưa thêm chỉ mục FTS/vector/reranker. Tồn kho hiện theo SKU;
   thuộc tính nhiều giá trị không mô tả tồn kho riêng từng tổ hợp biến thể.
5. SaaS công khai còn cần phiên người dùng/backend giữ khóa cửa hàng, TLS, rate limit,
   giám sát, quản trị/thuê bao/thanh toán và quy trình triển khai. Database hiện
   chưa có API key; phiên này không tạo key hoặc đổi database thật.

**Bảo toàn dữ liệu**

[Manifest SHA-256 trước kiểm tra](../outputs/verified_v2_2/input_hashes.json) và
summary xác nhận không thay đổi tệp trong `data`/`datasets` được theo dõi (bỏ qua
cache download). Database chỉ mở read-only khi kiểm tra dữ liệu hiện tại; mọi
mutation trong test đều ở database tạm/in-memory. Không xóa dữ liệu cũ, không
đưa test vào train, không chạy fine-tune, không thuê GPU hoặc thay database sản xuất.
