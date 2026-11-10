# MyAI — kiểm tra hai dataset chuyên tìm kiếm sản phẩm

Gói này chỉ **kiểm tra tệp** đã tải về máy Windows. Không cần GPU, không cần thư viện Python ngoài, không thay đổi source dataset, `data/prepared_v2`, `data/prepared_v2_1_review`, hay database SQLite.

## 1. Giải nén

Giải nén `MyAI_Search_Data_Preflight_v1.zip` vào thư mục gốc dự án `MyAI_v0_3_Windows` để có cấu trúc `MyAI_v0_3_Windows/MyAI_Search_Data_Preflight_v1/inspect_search_sources.py`.

## 2. Vị trí dữ liệu

- Bộ tiếng Việt: `datasets/raw/vi_ecommerce_intent/`, có một hoặc nhiều tệp CSV/JSONL chứa cột `text`, `label`.
- WANDS: `datasets/raw/wands/dataset/product.csv`, `query.csv`, `label.csv`.

Tên tệp CSV của bộ tiếng Việt có thể khác nhau. Script tự tìm trong tất cả thư mục con, bỏ qua `.cache` và `.git`.

## 3. Chạy PowerShell

```powershell
py -3.11 .\MyAI_Search_Data_Preflight_v1\inspect_search_sources.py --project-root .
```

Nếu hai bộ tải vào vị trí khác, có thể truyền thêm `--intent-dir "đường_dẫn" --wands-dir "đường_dẫn"`.

Script in ra số lượng, phân bố nhãn và tạo `data/search_data_preflight/report.json`. Gửi **nội dung report.json** để đối chiếu trước khi chọn mẫu tích hợp vào MyAI v2.2.

## 4. Sử dụng đúng mục đích

- Dataset tiếng Việt (`text`, `label`) giúp phân loại **ý định** (ví dụ `search_product`). Nó **không** chứa danh mục sản phẩm, giá hay tồn kho thật.
- WANDS có 42.994 sản phẩm, 480 câu tìm kiếm và 233.448 nhãn độ liên quan theo nguồn chính thức; dữ liệu chỉ phù hợp phát triển/đánh giá **retrieval/ranking**, không phải đưa hết vào phần trả lời chatbot. Không chứa giá hay tồn kho làm ground truth.
- Tách train/evaluation theo **câu tìm kiếm**, tránh rò rỉ các cặp query-product giống nhau. Cần kiểm tra tính đúng và giấy phép trước khi phát hành sản phẩm thương mại.

Nguồn: https://github.com/wayfair/WANDS và https://huggingface.co/datasets/duc004505/e-commerce-intent-classifier-dataset .
