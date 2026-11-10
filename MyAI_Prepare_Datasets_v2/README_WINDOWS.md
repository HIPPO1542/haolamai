# MyAI Prepare Datasets v2 — Windows, KHÔNG cần GPU

> **Mục tiêu:** mở rộng tập SFT đa ngành, lọc các bản ghi đáng ngờ, tạo tập huấn luyện có kiểm soát cho MyAI/Qwen3.5-9B. Đây là **công cụ chuẩn bị dữ liệu**, không phải mô hình đã fine-tune. Không tự động đảm bảo 8.000–10.000 mẫu chất lượng hoặc chứng nhận sẵn sàng thương mại.

## 1. Vị trí đặt thư mục

Giải nén `MyAI_Prepare_Datasets_v2.zip` trực tiếp vào thư mục gốc của dự án MyAI v0.3 trên Windows:

```text
H:\AICuaHao\MyAI_v0_3_Windows_Qwen35_Source\MyAI_v0_3_Windows\
├── .venv\
├── datasets\raw\
│   ├── saas_chatbot\data\train.jsonl
│   ├── saas_chatbot\data\test.jsonl
│   └── empath_ai\sft_train.jsonl, sft_dev.jsonl, sft_test.jsonl
├── MyAI_Data_Pack_v1\03_sft_addon\...
├── MyAI_Data_Pack_v1\04_evaluation\...
├── MyAI_Prepare_Datasets_v2\
│   ├── prepare_v2.py
│   ├── synthetic_cases.py
│   ├── verify_v2.py
│   ├── preflight_train_v2.py
│   ├── make_smoke_subset.py
│   ├── windows_train_v2.ps1
│   ├── cloud_smoke_v2.sh
│   └── cloud_train_v2.sh
└── data\
    ├── prepared_v1\         ← giữ nguyên
    └── prepared_v2\         ← tạo mới
```

**Không chép dữ liệu gốc vào ZIP để tải lại:** v2 đọc trực tiếp hai dataset đã tải trên máy bạn. Tất cả tệp trong `datasets/raw`, `MyAI_Data_Pack_v1`, `data/prepared_v1`, `data/train.jsonl` và `data/validation.jsonl` đều **không bị ghi đè**.

## 2. Chạy v2 — trước khi thuê Vast.ai

Mở PowerShell tại thư mục `MyAI_v0_3_Windows` (vẫn ở `(.venv)` cũng được):

```powershell
py -3.11 .\MyAI_Prepare_Datasets_v2\prepare_v2.py --project-root .
```

Sau đó:

```powershell
py -3.11 .\MyAI_Prepare_Datasets_v2\verify_v2.py --project-root .
py -3.11 .\MyAI_Prepare_Datasets_v2\preflight_train_v2.py --project-root .
py -3.11 -m unittest discover -s .\MyAI_Prepare_Datasets_v2\tests -v
```

Output ở `data/prepared_v2`:

| Tệp | Mục đích |
|---|---|
| `train.jsonl` | Fine-tuning (không chứa tập test) |
| `validation.jsonl` | Validation, mặc định tối đa 300 mẫu để giảm chi phí GPU |
| `test_external.jsonl` | Test độc lập từ SaaS + EmpathAI, **không train** |
| `myai_eval_cases.jsonl` | Giữ nguyên bộ 126 ca benchmark MyAI, **không train** |
| `review_queue.csv` | Mẫu bị cách ly vì nghi ngờ có PII, giao dịch, giá không có bằng chứng, lạc chủ đề...; **không tự động đưa vào train**. Số điện thoại/email trong đoạn xem trước được che, nhưng vẫn nên giữ file nội bộ |
| `review_samples.txt` | Mẫu đã qua lọc tự động để người kiểm tra đọc thủ công |
| `cross_split_question_warnings.json` | Cảnh báo các câu có cùng chữ ký từ vựng giữa những tập khác nhau; không phải kết luận rò rỉ ngữ nghĩa |
| `report.json` | Số lượng thực tế, nguồn, số mẫu bị loại, tỷ lệ dữ liệu tổng hợp |

> **Đọc `review_samples.txt`, `review_queue.csv` và `report.json` trước khi thuê GPU.** `PASS` của verify_v2 chỉ cho biết cấu trúc và việc tách dữ liệu, không chứng minh mọi câu trả lời đều đúng.

## 3. Tại sao v2 không chỉ lấy tất cả mẫu vào train?

- Bỏ giới hạn lấy 900 mẫu SaaS và 1.100 mẫu EmpathAI của v1, **nhưng** chỉ nhận mẫu qua bộ lọc tự động.
- Không để AI học từ câu trả lời tự nhận đã đặt hàng, xác nhận chuyển khoản, gửi email, hoàn tiền... khi chưa có bằng chứng rõ.
- Cách ly mẫu chứa số điện thoại, email hoặc giá được khẳng định nhưng không thể đối chiếu rõ với thông tin đầu vào.
- Cách ly một số câu có dấu hiệu trả lời sai trọng tâm (báo lỗi hàng nhưng chỉ nói về thanh toán).
- Rà soát trùng câu giống hệt, đồng thời xuất cảnh báo các câu giống nhau về từ vựng giữa train/test.
- Bổ sung tối đa 1.500 mẫu **tổng hợp có dữ liệu sản phẩm rõ ràng** cho hơn 10 ngành, với đáp án tính từ dữ liệu; mặc định không để loại này vượt quá khoảng 20% tổng train.
- Giới hạn nguồn EmpathAI để tránh bộ chăm sóc khiếu nại lấn át nội dung bán hàng đa ngành.
- Tách các tập trước khi chọn train; test không dùng để cập nhật trọng số.

**Đừng ép đủ 9.000 mẫu nếu nhiều mẫu không đạt.** Nếu `target_met=false`, hãy xem nguyên nhân ở `report.json`, bổ sung dữ liệu chất lượng thực tế sau. Số lượng tốt là số lượng *mẫu đúng, hữu ích*, không phải nhiều dòng JSONL.

Điều chỉnh mục tiêu:

```powershell
py -3.11 .\MyAI_Prepare_Datasets_v2\prepare_v2.py --project-root . --target-train 8500 --synthetic-max 1200 --max-validation 300 --output data/prepared_v2b
py -3.11 .\MyAI_Prepare_Datasets_v2\verify_v2.py --project-root . --output data/prepared_v2b
```

Dùng `--no-synthetic` để bỏ hoàn toàn phần sinh mẫu. **Nếu `data/prepared_v2` đã có dữ liệu, script sẽ dừng thay vì ghi đè; dùng `--output data/prepared_v2b` cho bản khác.**

## 4. Kiểm tra chất lượng thủ công (bắt buộc)

1. Mở `data/prepared_v2/review_samples.txt`, đọc các câu theo từng nguồn. Kiểm tra đúng ngữ cảnh, ngữ pháp, quyền riêng tư và lời hứa không có bằng chứng.
2. Mở `review_queue.csv`, kiểm tra loại lý do và quyết định mẫu nào thực sự nên chỉnh sửa thủ công. Đừng đổ toàn bộ review vào train.
3. Xem `report.json` — các nguồn có bị lệch không, tổng số train và tỷ lệ synthetic; nếu còn ít, **không tự nhân bản** câu trả lời.
4. Kiểm tra `cross_split_question_warnings.json`. Chữ ký giống nhau chỉ là **cảnh báo từ vựng**, chưa phải thuật toán xác minh trùng ngữ nghĩa.
5. Kiểm tra giấy phép, nguồn gốc dữ liệu, dữ liệu cá nhân. Nhãn MIT/Apache trên trang không tự chứng minh toàn bộ dữ liệu có đầy đủ quyền sử dụng thương mại.
6. Với dữ liệu giá/tồn kho: để backend truy vấn SQL và kiểm tra, **không kỳ vọng fine-tuning tự bảo đảm đúng 100%**.

## 5. Trước khi thuê GPU: test nhanh tập huấn luyện

V2 có công cụ tạo hai tập *smoke* riêng, không sửa tập đầy đủ:

```powershell
py -3.11 .\MyAI_Prepare_Datasets_v2\make_smoke_subset.py --project-root .
```

Tập `smoke_train.jsonl` (120 mẫu) và `smoke_valid.jsonl` (24 mẫu) giúp **thử chạy QLoRA thật** trên máy thuê trước khi chạy cả tập lớn. Vẫn cần tải đúng mô hình, cài dependencies và GPU. Đừng đánh giá chất lượng AI chỉ bằng 120 mẫu này.

## 6. Khi đã thuê Vast.ai

Mục tiêu là thuê máy chỉ khi dự án, dữ liệu và bộ model đã chuẩn bị. Cài phần mềm và tải model 9B trên instance tính tiền theo giờ sẽ tiêu tốn chi phí; nên chọn máy hoặc ổ lưu trữ bền vững có sẵn dữ liệu nếu phù hợp.

- **Trước full train**: chạy `bash MyAI_Prepare_Datasets_v2/cloud_smoke_v2.sh` trên instance Linux GPU, dự án đặt tại thư mục gốc và đã cài thư viện phù hợp. Tập smoke chỉ để bắt lỗi import/OOM/trình huấn luyện.
- **Nếu smoke chạy được**: chạy `bash MyAI_Prepare_Datasets_v2/cloud_train_v2.sh` từ thư mục gốc; script dùng **chính xác** `data/prepared_v2/train.jsonl` và `validation.jsonl`.
- Mặc định 1 epoch và max length 1024; nếu hết VRAM, giảm max length hoặc tăng GPU. Cấu hình, tốc độ và hỗ trợ Qwen3.5 của Transformers/TRL/PEFT **chưa được kiểm chứng trên máy thuê**.
- Chạy đánh giá bộ `test_external.jsonl` và benchmark 126 ca sau fine-tune; đừng coi training loss thấp là chứng minh AI không bịa giá.
- **Tải adapter + checkpoint + log + báo cáo về trước khi Destroy instance.** Ngừng GPU có thể vẫn tính phí ổ đĩa; xem quy định Vast.ai hiện hành.

`windows_train_v2.ps1` chỉ dành cho máy Windows **đủ VRAM**, không phù hợp để train Qwen3.5-9B trên laptop RTX 3050 4GB hiện tại của bạn. Laptop vẫn có thể chạy bước chuẩn bị dữ liệu.

Ở bản v2.2 đã kiểm tra, `windows/train.ps1` không còn tự gọi bộ sinh dữ liệu.
Vẫn phải chỉ rõ tập đã được duyệt qua `-TrainPath`/`-ValidationPath` hoặc
`--train`/`--valid`; chưa dùng candidate hiện tại để bắt đầu fine-tune.

## 7. Những giới hạn cần biết

- Không có mô hình pretrained, trọng số hoặc adapter trong gói dữ liệu này.
- Bộ lọc tự động có thể bỏ sót câu trả lời sai hoặc loại nhầm câu tốt. 8.000–10.000 mẫu chỉ là mục tiêu để thử nghiệm, **không phải cam kết**.
- Các nguồn ban đầu có dữ liệu tổng hợp hoặc giả lập; cần đánh giá tính xác thực và phong phú trước khi kinh doanh.
- Mã thử nghiệm được kiểm tra bằng dữ liệu tái dựng từ bản `prepared_v1` do bạn gửi, **không phải chạy trực tiếp trên raw dataset nằm trên máy Windows của bạn**. Vì thế số lượng cuối cùng có thể khác.
- Việc chuyển từ đồ ăn sang quần áo bằng đổi database còn phụ thuộc retrieval, cách định tuyến tenant, prompt, mô hình và bộ kiểm thử; data v2 không tự hoàn thiện SaaS.
