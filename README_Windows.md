# Cài MyAI v0.3 trên Windows 10/11 (PowerShell, KHÔNG Ubuntu)

Giữ nguyên `.venv` Windows đang dùng. Mô tả xóa venv trong audit cũ là lịch sử.
Chỉ cài mới khi chưa có môi trường, theo [INSTALL_v2_4.md](INSTALL_v2_4.md).
Train Qwen3.5-9B theo [hướng dẫn Vast.ai](docs/VASTAI_DEPLOYMENT.md).
Các profile v0.3 phía dưới là lịch sử; không train 9B trên RTX 3050 4 GB.

Kiểm tra offline hiện tại, không cần model/GPU:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_offline_checks --output outputs/another_unique_check
```

## A. Chuẩn bị

- Windows 10 hoặc 11, Python **3.11 x64**, NVIDIA driver cập nhật, RAM 16 GB.
- Mở PowerShell trong thư mục đã giải nén. Không cần cài WSL, Ubuntu hay Docker.
- Kiểm tra GPU: `nvidia-smi`. Dòng **Memory-Usage** cung cấp tổng VRAM (ví dụ 8192 MiB = 8 GiB).
- Có khoảng trống đĩa đáng kể để lưu model, thư viện và checkpoints; 9B cần nhiều dung lượng hơn 4B.
- GPU <8 GiB VRAM: không nên kỳ vọng fine-tune 4B/9B local với cấu hình hiện tại; cần thay cách tiếp cận/phần cứng.

## B. Cài các thư viện Windows

Từ PowerShell tại thư mục MyAI:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
```

Script tạo `.venv`, cài bản CUDA PyTorch từ chỉ mục cu128, rồi cài dependencies. Nếu driver không hỗ trợ cu128 hoặc máy có phần cứng/driver khác, xem [PyTorch official Windows selector](https://pytorch.org/get-started/locally/) và chạy script với `-CudaIndex` tương ứng (ví dụ một chỉ mục CUDA khác đang được PyTorch hỗ trợ). Không có yêu cầu cài CUDA Toolkit đầy đủ khi dùng wheel PyTorch có CUDA.

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\check.ps1
```

Phải thấy `CUDA available: True`. Nếu False, **không train** cho đến khi sửa driver/torch.

## C. Chọn mô hình MẠNH, không còn dùng Qwen3-1.7B

`high` = Qwen3.5-9B (ưu tiên chất lượng); `balanced` = Qwen3.5-4B (ít VRAM hơn).

**Nếu GPU có >=16 GiB VRAM**, bắt đầu với `high`:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\download.ps1 -Profile high
powershell -ExecutionPolicy Bypass -File .\windows\train.ps1 -Profile high
```

**Nếu GPU có khoảng 8–15 GiB VRAM**, chọn `balanced` (8 GiB có thể OOM):

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\download.ps1 -Profile balanced
powershell -ExecutionPolicy Bypass -File .\windows\train.ps1 -Profile balanced
```

Không thay `high` thành `balanced` mà không báo. Đây là hai cấu hình do bạn chủ động chọn. Trong giai đoạn huấn luyện, adapter được lưu ở `adapters/myai-sales-v0.3-9B` hoặc `...-4B`. Dữ liệu tổng hợp là khởi đầu, **chưa phải dataset chất lượng thương mại**.

## D. Cài cửa hàng và chạy API thật

```powershell
.\.venv\Scripts\python.exe -m scripts.store_admin create-store shop01 "Shop của tôi" "Quần áo"
.\.venv\Scripts\python.exe -m scripts.store_admin import-products shop01 data/catalog_format.csv
.\.venv\Scripts\python.exe -m scripts.store_admin new-key shop01
```

Giữ API key ở nơi an toàn, không nhúng nó vào JavaScript công khai. Sau khi model và adapter đã có:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1 -Profile high
```

Nếu bạn đã train `balanced` thì `-Profile balanced`. Sau đó truy cập `http://127.0.0.1:8000`.

## E. Đánh giá kết quả

Trước fine-tune, chạy kiểm tra offline (không tải model, không thuê GPU):

```powershell
.\.venv\Scripts\python.exe -m scripts.run_offline_checks --output outputs/offline_review_01
```

Chọn tên output mới mỗi lần. Xem [AUDIT_v2_2.md](docs/AUDIT_v2_2.md) cho kết quả
thực tế, giới hạn môi trường hiện tại và các mục review còn tồn đọng.

Tìm kiếm catalog không cần model: `windows/start.ps1 -SearchOnly` và dùng
[`POST /search`](docs/SEARCH_API.md). Thao tác này vẫn yêu cầu Python/dependencies
hoạt động và API key hợp lệ của cửa hàng. `/chat` cần model/adapter khi sinh câu trả lời.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File .\windows\evaluate.ps1 -Profile high
```

Chuyển sang `balanced` nếu đúng profile đã train. Kiểm tra câu trả lời mới, giá/tồn kho, các câu hỏi trái ngành và những câu hỏi không có thông tin. Kết quả huấn luyện không được khẳng định thành công cho tới khi quá trình trên thực thi xong.

## F. Lưu ý kỹ thuật

- Qwen3.5 là kiến trúc mới; các phiên bản PyTorch/Transformers/PEFT/TRL cụ thể vẫn cần thử trên GPU của bạn.
- `bitsandbytes` đã hỗ trợ CUDA trên Windows, nhưng GPU/driver cũ vẫn có thể không tương thích.
- Những thành phần SaaS production (TLS, dashboard, đăng ký thuê bao, rate limit, giám sát, thanh toán) chưa hoàn thiện.
- Mô hình được chạy trên hạ tầng của bạn; việc tải trọng số và giấy phép từ Qwen vẫn là sự phụ thuộc nguồn gốc một lần, không phải thuê API để chạy inference.
