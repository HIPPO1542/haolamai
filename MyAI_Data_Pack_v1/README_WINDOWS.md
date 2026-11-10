# MyAI Data Pack v1.0 — dữ liệu chuẩn bị trước khi thuê Vast.ai

**Dùng cùng:** MyAI v0.3 trên Windows 10/11 (Python 3.11).

> ⚠️ **Toàn bộ sản phẩm, giá, tồn kho, chính sách và đoạn hội thoại trong Data Pack này đều là dữ liệu giả lập để kiểm thử.** Không công bố là giá/chính sách của cửa hàng có thật. Bộ dữ liệu không chứa dữ liệu khách hàng cá nhân.

## 1. Có gì trong pack?

| Đường dẫn | Nội dung |
|---|---|
| `01_database/snacks_products.csv` | 30 sản phẩm/SKU đồ ăn vặt, đúng định dạng nhập CSV của MyAI v0.3 |
| `01_database/fashion_products.csv` | 30 SKU quần áo, có size/màu và số lượng theo từng SKU |
| `01_database/stores.csv` | 2 cửa hàng mẫu: `food01`, `fashion01` |
| `01_database/MyAI_DanhMuc_va_ChinhSach.xlsx` | Excel để xem và chỉnh sửa thủ công (không tự đồng bộ CSV) |
| `02_policies/policies.jsonl` | 12 mục chính sách giả lập: giao hàng, thanh toán, đổi trả, giờ hỗ trợ... |
| `02_policies/policies.csv` / `*.md` | Chính sách ở dạng dễ đọc |
| `03_sft_addon/myai_sft_addon_train.jsonl` | **884** mẫu SFT train bổ sung (`prompt`/`completion`) |
| `03_sft_addon/myai_sft_addon_validation.jsonl` | **143** mẫu validation, tách sản phẩm khỏi train |
| `04_evaluation/myai_eval_cases.jsonl` / `.csv` | **126** ca test độc lập, có tiêu chí kỳ vọng; tuyệt đối KHÔNG trộn vào train |
| `tools/validate_pack.py` | Kiểm tra CSV, JSONL, SKU trùng, train/validation leak, tính đầy đủ |
| `tools/preflight_db_test.py` | Tạo database tạm, kiểm tra tách cửa hàng và cập nhật giá/tồn kho mà không train |
| `tools/import_to_myai.py` | Nhập dữ liệu mẫu vào SQLite MyAI v0.3, chế độ xem trước mặc định |
| `tools/train_prepared.ps1` | Script PowerShell train bằng data bổ sung, **KHÔNG** gọi `make_train_data.py` |
| `tools/inspect_downloaded.py` | Đọc cấu trúc hai bộ dataset bạn đã tải; không tự gộp hoặc chỉnh sửa |

## 2. Giải nén & kiểm thử KHÔNG tốn tiền GPU

Trong PowerShell, chuyển đến thư mục gốc dự án `MyAI_v0_3_Windows` rồi giải nén file ZIP ngay tại đó:

```powershell
Expand-Archive -Path "H:\duong_dan_tai_ve\MyAI_Data_Pack_v1.zip" -DestinationPath "." -Force
```

Đường dẫn `H:\duong_dan_tai_ve\...` chỉ là **ví dụ**; thay bằng vị trí file bạn đã tải.

Sau đó chạy:

```powershell
py -3.11 .\MyAI_Data_Pack_v1\tools\validate_pack.py
py -3.11 .\MyAI_Data_Pack_v1\tools\preflight_db_test.py --project-root .
```

Hai lệnh trên chỉ đọc dữ liệu hoặc tạo DB tạm (tự xóa). Chúng không fine-tune hoặc gọi API.

## 3. Nhập dữ liệu mẫu vào SQLite thật của dự án (chỉ khi bạn muốn)

Chạy xem trước trước khi ghi:

```powershell
py -3.11 .\MyAI_Data_Pack_v1\tools\import_to_myai.py --project-root .
```

Nếu đúng tên dự án/cửa hàng thì mới thực hiện:

```powershell
py -3.11 .\MyAI_Data_Pack_v1\tools\import_to_myai.py --project-root . --apply
```

**Bảo vệ dữ liệu cũ:** Nếu database đã có các cửa hàng `food01` hoặc `fashion01`, script sẽ **dừng** để tránh ghi đè. Không nên dùng `--allow-overwrite` khi chưa sao lưu.

Nhập CSV trực tiếp bằng lệnh gốc của dự án cũng được, nhưng phải tạo store trước:

```powershell
.\.venv\Scripts\python.exe -m scripts.store_admin create-store food01 "Cửa hàng Ăn Vặt Mẫu" "Đồ ăn vặt"
.\.venv\Scripts\python.exe -m scripts.store_admin import-products food01 .\MyAI_Data_Pack_v1\01_database\snacks_products.csv
```

## 4. Huấn luyện SFT bổ sung nhưng KHÔNG ghi đè dữ liệu cũ

Bản v2.2 đã bỏ bước gọi `scripts.make_train_data` khỏi `windows/train.ps1`.
Chọn rõ tập đã được duyệt qua `-TrainPath`/`-ValidationPath`; bộ sinh scaffold
cũng từ chối ghi đè dữ liệu có sẵn. Chưa bắt đầu fine-tune khi candidate còn chờ duyệt.

Khi đã thuê GPU và tải model `models/Qwen3.5-9B`, dùng:

```powershell
powershell -ExecutionPolicy Bypass -File .\MyAI_Data_Pack_v1\tools\train_prepared.ps1 -Profile high -Epochs 1
```

Chạy từ **thư mục gốc dự án**; lệnh trên chỉ dùng 884+143 mẫu addon và lưu adapter vào `adapters/myai-sales-prepared-9B`, không đụng vào hai dataset bạn tải trước đó.

Nếu sử dụng hai dataset đã tải, **chưa được gộp mù**: cần mở cấu trúc, kiểm tra license, chuyển chúng về đúng schema `prompt`/`completion`, lọc trùng/lỗi, tạo split độc lập, rồi truyền đường dẫn mới qua `scripts.finetune --train ... --valid ...`. Dataset bên ngoài không có trong ZIP này vì chưa được bạn gửi, nên chúng **chưa được hợp nhất**.

## 5. Kiểm tra cấu trúc dataset bên ngoài (không thay đổi dữ liệu)

Ví dụ:

```powershell
py -3.11 .\MyAI_Data_Pack_v1\tools\inspect_downloaded.py ".\datasets\raw\saas_chatbot" ".\datasets\raw\empath_ai"
```

Lệnh sẽ liệt kê tên tệp, cột dữ liệu và kiểu dữ liệu; không tự động huấn luyện.

## 6. Nguyên tắc để đổi database mà không train lại

- **SFT:** AI học cách đọc dữ liệu và trả lời theo thông tin được cung cấp. Không cho AI học thuộc giá/tồn kho.
- **Backend:** Mỗi request chỉ truy vấn sản phẩm/chính sách thuộc cửa hàng đang được xác thực bằng API key.
- **Giá và số lượng tồn:** Lấy trực tiếp từ SQL ở thời điểm trả lời; đơn hàng phải kiểm tra lại tồn kho trước khi xác nhận.
- **Khi đổi cửa hàng:** Chỉ đổi cấu hình store, dữ liệu SKU và chính sách. Có thể cần bổ sung parser/retrieval cho thuộc tính mới (ví dụ kích thước hoặc cấu hình điện thoại).
- **Độ chính xác:** Không chỉ dựa vào prompt. Backend phải đưa ra câu trả lời an toàn khi không xác nhận được thông tin; phần kiểm tra giá hiện tại chỉ là kiểm tra cơ bản, **chưa chứng minh loại bỏ được mọi hallucination**.

## 7. Đánh giá đúng cách

- `04_evaluation` chỉ được dùng **sau** train để đánh giá; không gộp vào train hay validation.
- Bộ test có ca cần thay đổi DB trước khi hỏi (giá F009 từ 22000 thành 27000, tồn kho A005 thành 0), không có nghĩa CSV gốc sai.
- `preflight_db_test.py` xác nhận logic SQL cơ bản; **không chấm điểm mô hình Qwen**, vì chưa nạp trọng số/adapter.
- Trước khi công khai sản phẩm SaaS cần kiểm thử thêm jailbreak, lọt dữ liệu chéo cửa hàng, phân quyền, bảo mật API key, hạn mức truy vấn và độ chính xác thực tế bằng kiểm duyệt của người dùng.

## 8. Giấy phép và nguồn gốc

Dữ liệu trong pack tự tạo và giả lập. Hai dataset từ Hugging Face mà bạn đã tải có nguồn gốc/giấy phép riêng, cần kiểm tra rõ trước khi dùng để kinh doanh. Không đưa log chứa thông tin cá nhân khách hàng thật vào dataset nếu chưa có cơ sở xử lý hợp lệ.
