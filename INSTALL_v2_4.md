**Cài MyAI bằng một môi trường Python**

Máy Windows đã có `.venv`; giữ nguyên, không tạo môi trường đè lên nó. Chỉ dùng
các lệnh dưới khi cài mới trong thư mục chưa có `.venv`, với Python 3.11/3.12 x64.
Linux: [hướng dẫn Vast.ai](docs/VASTAI_DEPLOYMENT.md).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` có PyTorch, torchvision, backend và các thư viện Qwen/QLoRA.
File dùng PyPI mặc định; cài Torch/torchvision từ nguồn CUDA phù hợp trước.
Đây là dải phiên bản cho resolver, chưa phải lockfile Linux đã nghiệm thu trên GPU.

Nếu muốn chỉ định riêng nguồn Torch trước khi cài phần còn lại:

```powershell
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Sau cài, kiểm tra thực tế:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import torch, torchvision; print(torch.__version__, torchvision.__version__); print(torch.version.cuda, torch.cuda.is_available())"
.\.venv\Scripts\python.exe -m scripts.diagnose_environment --output outputs/my_import_check.json
```

Chọn đường dẫn output mới nếu tệp báo cáo đã tồn tại. Nếu gặp `WinError 10013`,
kết nối đang bị chặn; lỗi này không tự chứng minh wheel cu132 không tương thích.
Lần cài trong phiên Codex đã bị chặn như vậy. Không đổi tên/copy package nhị phân
từ Python khác để khắc phục.

Launcher Windows hiện chỉ tìm `.venv`, hoặc interpreter bạn chỉ định qua
`MYAI_PYTHON`. Chưa chạy fine-tune: máy RTX 3050 4 GB hiện tại không đáp ứng ngưỡng
9B của dự án, và các mục preflight còn BLOCKED.
