# MyAI Search Integration v2.2

Trạng thái v2.4: [audit](../AUDIT_v2_4.md). Bộ 42 ca v2.3 đã chuyển thành hồi quy
qua `--regression` và đạt 42/42. Holdout mới tại `evaluations/search_holdout_v24`
đã khóa trước đánh giá, đạt 63/65; không sửa thuật toán theo hai ca chưa đạt.
`benchmark_retrieval_v24.py` đo chi phí so với snapshot v2.3;
`evaluate_router_v24.py` chọn k theo validation rồi đo test một lần.

Cập nhật v2.3: [audit mới](../docs/AUDIT_v2_3.md).
`prepare_search_benchmarks.py` tách nguồn intent/ranking, cách ly nhãn mâu thuẫn
và đo baseline cố định; output phải nằm trong thư mục mới dưới `outputs`.
`evaluate_frozen_holdout.py` dùng bộ 42 ca mới trong `evaluations/search_holdout_v23`.
Thuật toán đã khóa trước lần chạy đầu; kết quả 37/42 và 5 finding được giữ nguyên.
Không dùng suite này để chỉnh v2.3 rồi tuyên bố vẫn là holdout mới.

Thư mục này chưa có ở đầu phiên kiểm tra; được tạo mới cho công cụ đánh giá và
tài liệu tích hợp. Runtime nằm trong `myai/retrieval.py`, `myai/db.py`, `myai/api.py`.

- [Hợp đồng API](../docs/SEARCH_API.md): `/search`, API key xác định tenant,
  lọc thuộc tính/giá/tồn kho, không cần Qwen để tìm kiếm.
- `evaluate_search.py`: chạy 126 ca có sẵn với SQLite trong RAM, nạp catalog mẫu
  riêng cho từng ca; cập nhật giá/tồn kho/inactive/SKU mới chỉ trong fixture.
- [Báo cáo](../docs/AUDIT_v2_2.md): kiểm thử và các giới hạn còn lại.

```powershell
python MyAI_Search_Integration_v2_2/evaluate_search.py --output outputs/search_run_01.json
```

Thư mục cha của output phải tồn tại và tệp chưa tồn tại. Công cụ từ chối ghi vào
`data`, `datasets`, `models`, `adapters`. Không kết nối database sản xuất.
126 ca là hồi quy cho truy xuất dữ liệu; các ca yêu cầu hành vi của mô hình mới chỉ
kiểm tra được nguồn liên quan/phạm vi cửa hàng. Kết quả không xác nhận chất lượng
câu trả lời, an toàn ngữ nghĩa hoặc khả năng khái quát của Qwen.

Hai nguồn `vi_ecommerce_intent` và WANDS giữ nguyên ở `datasets/raw`, chưa đưa vào
SFT. Nguồn intent có nhãn mâu thuẫn; WANDS có phán xét lặp và mâu thuẫn. Cần cách ly
nhãn mâu thuẫn, tách theo nhóm câu hỏi chuẩn hóa trước khi dùng cho router/ranker.
Không dùng WANDS làm dữ liệu giá/tồn kho hoặc trộn benchmark vào train chatbot.
