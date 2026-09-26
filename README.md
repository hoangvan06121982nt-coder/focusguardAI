# FocusGuard – Giám sát tập trung học tập bằng camera (bản thi)

FocusGuard dùng camera để ghi nhận **hành vi quan sát được** của học sinh (dùng điện thoại, nhắm mắt kéo dài,
quay đầu khỏi hướng học, rời chỗ) và tính **điểm tập trung theo thời gian** bằng một bộ quy tắc minh bạch.
Có bốn vai trò: **Học sinh**, **Giáo viên**, **Phụ huynh**, **Quản trị viên**.

> Trung thực về năng lực: các mô hình nhận dạng (YOLOv8, MediaPipe Face Landmarker, InsightFace) là mô hình
> có sẵn. Phần "đánh giá tập trung" là **heuristic theo thời gian**, không phải mô hình học máy dự đoán.
> Hệ thống **không** nhận diện cảm xúc và **không** đo hướng nhìn (gaze). Độ chính xác trên dữ liệu lớp học
> thật: **NOT_EVALUATED** (chưa có bộ dữ liệu có nhãn). Xem [docs/PRIVACY_AND_AI_SAFETY.md](docs/PRIVACY_AND_AI_SAFETY.md).

## Kiến trúc

```
Camera → YOLOv8 + ByteTrack (track_id tạm thời) → InsightFace → IdentityManager (student_id chuẩn)
      → StudentRuntimeState → BehaviorAnalyzer (theo thời gian) → FocusEngine (DUY NHẤT, theo giây)
      → SessionRuntime → focus_events / focus_snapshots / session_students
      → Socket.IO do máy chủ quyết định, cô lập theo lớp → Analytics chỉ từ dữ liệu thật
```

Chi tiết: [docs/COMPETITION_ARCHITECTURE.md](docs/COMPETITION_ARCHITECTURE.md). Kịch bản demo:
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

| Thành phần | File |
|---|---|
| Cấu hình ngưỡng tập trung | `focusguard/config.py` |
| IdentityManager | `focusguard/identity.py` |
| StudentRuntimeState | `focusguard/runtime_state.py` |
| BehaviorAnalyzer + BehaviorEpisode | `focusguard/behavior.py` |
| FocusEngine (duy nhất) | `focusguard/focus_engine.py` |
| SessionRuntime / RuntimeRegistry | `focusguard/session_runtime.py` |
| Phân quyền theo quyền sở hữu | `focusguard/authz.py` |
| Room realtime / chặn dữ liệu từ client | `focusguard/realtime.py` |
| Bảo mật (secret, cookie, CORS, mật khẩu) | `focusguard/security.py` |
| Analytics từ dữ liệu thật | `focusguard/analytics.py` |
| Đánh giá (metrics + dữ liệu SYNTHETIC) | `focusguard/evaluation/` |
| Pipeline camera lớp học / cá nhân | `classroom_ai.py`, `camera_ai.py` |
| Web + Socket.IO | `app.py` |
| Lưu trữ (SQLite / Firestore) | `repository.py` |

## Cài đặt

Yêu cầu: Python 3.10–3.12, webcam (cho pipeline camera), Node.js (chỉ để kiểm tra cú pháp JS / Firebase Emulator).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # đầy đủ: OpenCV, MediaPipe, YOLOv8, InsightFace
cp .env.example .env                      # rồi thay các giá trị <placeholder>
python tools/download_models.py           # tải InsightFace buffalo_sc (một lần)
python app.py                             # http://127.0.0.1:5001
```

Chỉ chạy kiểm thử / đánh giá (không cần camera):

```bash
pip install -r requirements-ci.txt
bash scripts/ci_check.sh
```

### Cấu hình quan trọng (`.env`)

| Biến | Ý nghĩa |
|---|---|
| `FOCUSGUARD_ENV` | `development` hoặc `production`. Production từ chối cấu hình không an toàn. |
| `FLASK_SECRET_KEY` | Bắt buộc ở production (≥ 32 ký tự ngẫu nhiên). Dev: tự sinh ngẫu nhiên mỗi lần chạy. |
| `ALLOWED_ORIGINS` | Danh sách origin cho Socket.IO. Rỗng = cùng origin. `*` bị cấm ở production. |
| `SEED_DEMO_ACCOUNTS` / `DEMO_ACCOUNT_PASSWORD` | Tài khoản demo chỉ tạo ở môi trường dev. |
| `DATABASE_TYPE` | `sqlite` (mặc định) hoặc `firestore` (chỉ truy cập từ máy chủ). |

Tài khoản demo (chỉ dev, mật khẩu = `DEMO_ACCOUNT_PASSWORD`, mặc định `123`): `admin`, `teacher`, `hocsinh`,
`phuhuynh`. Mật khẩu luôn được lưu dạng hash Werkzeug; mật khẩu cũ dạng plaintext được hash lại khi khởi động.

## Kiểm thử & CI

* `bash scripts/ci_check.sh`: compile → import → pytest → kiểm tra cú pháp JS → quét bảo mật/public repo → đánh giá SYNTHETIC.
* GitHub Actions: `.github/workflows/ci.yml` chạy cùng script.
* Test phần cứng (camera, model) nằm ở `tests/hardware/`, **SKIPPED: HARDWARE_REQUIRED** trừ khi đặt
  `FOCUSGUARD_HARDWARE_TESTS=1` trên máy có webcam.

## Đánh giá

```bash
python scripts/run_evaluation.py --output evaluation/reports/latest.json
```

Kết quả hiện có đều trên dữ liệu **SYNTHETIC** (tín hiệu sinh tự động để kiểm tra logic thời gian/danh tính).
Mục `real_world` là **NOT_EVALUATED** cho tới khi có bộ dữ liệu lớp học thật, có nhãn và có sự đồng ý.
