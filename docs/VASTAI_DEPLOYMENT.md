# Train Qwen3.5-9B trên Vast.ai

Quy trình: **clone → cài thư viện → chuyển hai split đã duyệt → tải model → train**.
Không cần WANDS, dataset thô, database cửa hàng hoặc `.venv` Windows trên GPU.
Chưa thuê máy hay chạy train trong đợt dọn repository này.

## 1. Clone và cài thư viện trên Linux

Chọn Ubuntu 22.04/24.04 x86_64, Python 3.11/3.12, một GPU NVIDIA **24 GB VRAM
trở lên**, RAM ít nhất 32 GiB (nên 64 GiB), khoảng 100–150 GB disk. Đây là mức
dự trù, chưa phải peak memory đã đo của Qwen 9B. Chọn image PyTorch/CUDA có
driver tương thích; kiểm tra `nvidia-smi` trước. Không copy môi trường Windows.

```bash
git clone https://github.com/HIPPO1542/haolamai.git MyAI
cd MyAI
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Nếu repository private, dùng SSH/deploy key có quyền đọc đã được chủ dự án cấp:
`git clone git@github.com:HIPPO1542/haolamai.git MyAI`. Không nhúng token vào URL
hoặc lưu token trong repository. Không cần submodule WANDS sau khi dọn index.

Cài `torch`/`torchvision` theo [bộ chọn PyTorch chính thức](https://pytorch.org/get-started/locally/)
cho **Linux và driver/image đang thuê**, rồi cài file chung:

```bash
# Chạy lệnh torch/torchvision từ bộ chọn chính thức cho image trước lệnh dưới.
python -m pip install -r requirements.txt
python -m pip check
python -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'
python -m scripts.diagnose_environment --output outputs/linux_imports_01.json
```

Không mặc định cu132 trên Windows dùng được trên Linux. `requirements.txt` là
dải phiên bản, chưa phải lockfile Linux đã kiểm chứng. Nếu resolver không tìm
được wheel phù hợp, import lỗi hoặc CUDA=False, dừng và sửa môi trường trước.

## 2. Chuyển dữ liệu đã duyệt, giữ riêng khỏi GitHub

Candidate Windows hiện tại nằm ở `outputs/v2_4/sft_candidate_final`:
**3.866 train / 263 validation**. Chưa có bằng chứng duyệt đầy đủ về nội dung,
quyền riêng tư và quyền sử dụng nguồn. Chủ dự án cần duyệt trước khi chuyển/train.
Không đổi cờ xác nhận để bỏ qua việc duyệt. Không đưa external test/benchmark lên train.

Sau khi được duyệt, trên Windows đóng gói **đúng hai file**, không thêm test:

```powershell
New-Item -ItemType Directory -Force private_releases | Out-Null
# Chọn tên mới nếu archive đã tồn tại.
tar -czf private_releases/myai-v24-approved.tar.gz -C outputs/v2_4/sft_candidate_final train.jsonl validation.jsonl
Get-FileHash private_releases/myai-v24-approved.tar.gz -Algorithm SHA256
scp -P <SSH_PORT> private_releases/myai-v24-approved.tar.gz <USER>@<HOST>:/workspace/
```

Dùng host/port/user trong phần Connect của Vast.ai. Không log nội dung mẫu.
Trên Linux, đối chiếu SHA-256 của archive với Windows rồi giải nén vào thư mục mới:

```bash
sha256sum /workspace/myai-v24-approved.tar.gz
mkdir -p private_data
mkdir private_data/myai-v24
tar -xzf /workspace/myai-v24-approved.tar.gz -C private_data/myai-v24
sha256sum private_data/myai-v24/{train,validation}.jsonl
python -c 'from scripts.training_data_guard import validate_training_inputs; validate_training_inputs("private_data/myai-v24/train.jsonl", "private_data/myai-v24/validation.jsonl")'
```

SHA-256 candidate đã kiểm tra (nếu thay nội dung phải duyệt và kiểm tra lại):

```text
train       f59f58742189f7f3f4cc00671d091de08813ead0c19b4f64a372644e6cb7b402
validation  b817b0aa19a8787432eacae00c0649607f3eaf488ee57837da8973d69b6c1dec
```

`configs/training_release_v24.json` chỉ chứa metadata, không chứa nội dung SFT.
Không có split thì script dừng; không tự sinh dataset thay thế. Kiểm tra lexical
leakage và near-duplicate đầy đủ được giữ trong báo cáo Windows, không được suy
diễn rằng guard hai file trên GPU đã thay thế toàn bộ audit đó.

## 3. Tải model trực tiếp trên máy GPU

```bash
python -m scripts.download_model --model Qwen/Qwen3.5-9B --output models/Qwen3.5-9B --revision main
```

Script phân giải `main` thành commit SHA trước khi tải, lưu revision vào manifest
và giữ LICENSE. Để tái tạo, truyền lại SHA trong manifest thay `main`. Nếu tải lỗi,
giữ output dở để kiểm tra và chọn thư mục mới khi thử lại; script không ghi đè.
Không tải trọng số 9B về laptop.

## 4. Train thật, preflight ở đầu cùng lần chạy

Chỉ chạy khi đã duyệt dữ liệu và sẵn sàng huấn luyện trên chính instance này:

```bash
mkdir -p outputs
set -o pipefail
python -m scripts.finetune \
  --model models/Qwen3.5-9B \
  --train private_data/myai-v24/train.jsonl \
  --valid private_data/myai-v24/validation.jsonl \
  --output adapters/myai-v24-run01 \
  --run-preflight --preflight-output outputs/gpu-preflight-01 \
  --accept-reviewed-candidate \
  --method qlora --max-length 2048 --batch-size 1 --accumulation 8 --epochs 2 \
  2>&1 | tee outputs/train-run01.log
```

Preflight kiểm tra import thực, GPU/RAM/disk, model/config/đủ shard, tokenizer,
completion bị cắt, loss mask/collator và QLoRA. Bất kỳ launch check nào lỗi đều
dừng trước train. `--accept-reviewed-candidate` là xác nhận của người vận hành đã
duyệt dữ liệu, không phải chứng nhận tự động. Không có fallback sang model nhỏ.

`technical_launch_checks_pass` chỉ là đủ điều kiện **thử tải/train**. Báo cáo vẫn
ghi BLOCKED cho thực thi 9B và resume chưa xảy ra. Tải 9B/forward/backward thật
diễn ra trong train; chưa thử thành công trên GPU lớn trong workspace này.
Adapter roundtrip mô hình chẩn đoán không được coi là Qwen3.5-9B PASS.

Theo dõi bằng `tail -f outputs/train-run01.log`, `watch -n 2 nvidia-smi` và `df -h`.
Checkpoint đầy đủ được lưu mỗi epoch, không tự xóa checkpoint cũ. Với 3.866 mẫu,
epoch đầu có thể dài; Ctrl+C trước checkpoint đầu có thể chưa có state để resume.
Đặt `--output` trực tiếp trên volume đã mount nếu có; vẫn sao lưu ra ngoài host.

## 5. Sao lưu, resume và kết thúc

Sao chép adapter **và toàn bộ checkpoint**, cùng preflight report, log và
`pip freeze` về Windows hoặc kho riêng có xác thực. Không chỉ copy adapter nếu
cần resume: phải có optimizer/scheduler/RNG/trainer state. Đối chiếu checksum
bản sao; checkpoint trong container không phải backup bền vững.

Resume: dùng lại lệnh train với output và preflight-output **mới**, thêm
`--resume-from-checkpoint /duong/dan/checkpoint-N`. Giữ đúng model revision,
split, hyperparameters và môi trường; script kiểm tra state nhưng khả năng
resume thật vẫn cần xác minh khi checkpoint QLoRA đầu tiên tồn tại.

Kết thúc: Ctrl+C/đợi tiến trình thoát → kiểm tra và sao lưu → dùng Stop trong
Vast Console nếu cần giữ máy. Stop vẫn tính tiền storage; Destroy xóa container
và dữ liệu trong đó. Chỉ Destroy sau khi xác minh backup. Volume có vòng đời/
phí riêng và gắn với host; không xem nó là bản sao ngoài host.
Xem [Vast quản lý instance](https://docs.vast.ai/guides/instances/manage-instances)
và [storage](https://docs.vast.ai/guides/instances/storage/types).
