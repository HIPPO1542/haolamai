# MyAI v2.1 — Kiểm tra dữ liệu trước khi thuê GPU

**Mục tiêu:** rà soát chất lượng đầu vào v2, không thay đổi bất kỳ file gốc nào. Không cần GPU, không cần mạng, không cần thư viện ngoài Python.

## Cài trên Windows
Giải nén `MyAI_Quality_Gate_v2_1` vào thư mục gốc dự án, ngang hàng `windows`, `data` và `MyAI_Prepare_Datasets_v2`.

Trong PowerShell tại thư mục gốc dự án:

```powershell
py -3.11 .\MyAI_Quality_Gate_v2_1\quality_gate.py --project-root .
```

Kết quả: `data\prepared_v2_1_review\` gồm:
- `train.jsonl`, `validation.jsonl`, `test_external.jsonl`: **ứng viên** đã cách ly thêm các dòng có cảnh báo nguy cơ cao; vẫn cần kiểm tra thủ công và đánh giá mô hình.
- `myai_eval_cases.jsonl`: 126 ca gốc giữ nguyên, tuyệt đối không trộn vào train.
- `high_risk_review.csv`: mẫu bị cách ly vì nghi xác nhận hành động chưa có kết quả hệ thống hoặc lộ tên chatbot gốc.
- `medium_risk_review.csv`: mẫu nên rà soát thêm: dữ liệu số liệu/PII/ngành nhạy cảm...; **vẫn nằm trong bộ ứng viên** trừ khi đồng thời bị gắn cờ cao.
- `audit_report.json`: thống kê và giới hạn kiểm tra.

Bản v2.2 đã bỏ bước tự tạo dataset khỏi `windows/train.ps1`. Vẫn chỉ dùng đường
dẫn train/validation đã được duyệt; candidate hiện tại chưa được phê duyệt để train.

## Sau khi rà soát
1. Đọc `high_risk_review.csv` và `medium_risk_review.csv` bằng Excel, lọc cột `reasons`.
2. Sửa hoặc loại các mẫu sai, không phục hồi hàng loạt chỉ để đạt số lượng.
3. Trước khi thuê Vast.ai, thử mô hình và tokenizer với một tập nhỏ bằng GPU thuê trong thời gian ngắn. Mọi lệnh fine-tune phải chỉ rõ đường dẫn `--train` và `--valid` đến dữ liệu đã duyệt.
4. Chỉ đưa file đã kiểm tra quyền sử dụng và dữ liệu riêng tư lên máy thuê. **Không tải `review_queue.csv` hoặc các mẫu đang chờ xử lý có PII lên cloud.**

## Giới hạn
Bộ lọc dựa trên biểu thức và quy tắc, không xác nhận đúng/sai ngữ nghĩa. Các lỗi như 'cửa hàng túi vải trả lời máy sấy tóc' có thể lọt qua và phải kiểm tra thủ công. Đánh giá độc lập cần gồm các cửa hàng và sản phẩm chưa thấy khi train.
