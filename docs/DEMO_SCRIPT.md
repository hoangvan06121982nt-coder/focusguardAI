# Kịch bản demo (≈ 8 phút)

Chuẩn bị: `cp .env.example .env`, điền `FLASK_SECRET_KEY`, `DEMO_ACCOUNT_PASSWORD`; `python app.py`;
đăng ký khuôn mặt cho 2–3 học sinh ở trang Admin (chỉ lưu vector đặc trưng, không lưu ảnh).

## 1. Chứng minh không có số liệu giả (1 phút)
1. Đăng nhập `teacher` → Analytics: khi chưa có buổi học, hiển thị **"Không đủ dữ liệu" / N/A**, không có
   biểu đồ nguyên nhân bịa.
2. Đăng nhập `hocsinh` → Thống kê: điểm TB là N/A, không có "cảm xúc", "dự báo" hay "chỉ số rủi ro AI".

## 2. Lớp học trực tiếp bằng camera (3 phút)
1. Giáo viên chọn lớp → chế độ **Trực tiếp** → **Bắt đầu**.
2. Học sinh bước vào khung hình: nhãn track xám `CANDIDATE` → sau ~0.6 s chuyển thành tên (xác nhận theo
   thời gian). Bảng điểm danh hiện giờ check-in thật; vào sau 5 phút là "Đi muộn".
3. Chớp mắt / liếc nhanh / giơ điện thoại 0.2 s → **không** cảnh báo.
4. Cầm điện thoại > 1 s → sự kiện "Dùng điện thoại", điểm giảm 2 điểm/giây; cất đi → hồi 0.5 điểm/giây.
5. Hai học sinh đi cắt ngang nhau → danh tính không bị đổi chéo.
6. Một học sinh rời khung hình 3 s → "Tạm khuất" (không trừ điểm); > 10 s → "Rời chỗ" (đếm 1 lần).
7. Người lạ vào khung hình → giữ "Track n: UNKNOWN", không bị gán vào học sinh nào.

## 3. Kết thúc & báo cáo (1 phút)
Bấm **Kết thúc** → tóm tắt buổi học từ `session_students`: có mặt x/y, đi muộn, điểm TB của những em đo được.
Học sinh không đến xuất hiện là **Vắng mặt** trong lịch sử của em đó và trên cổng phụ huynh.

## 4. Bảo mật & phân quyền (2 phút)
* Giáo viên lớp 10A1 mở `/api/teacher/class_status?class_id=2` → 403.
* Học sinh mở `/api/sessions?student_id=<người khác>` → chỉ nhận dữ liệu của chính mình.
* DevTools: `socket.emit('student_data_push', {focus_score: 100})` → lỗi `client_state_rejected`.
* `FOCUSGUARD_ENV=production python app.py` không có secret → từ chối khởi động.

## 5. Đánh giá trung thực (1 phút)
`python scripts/run_evaluation.py` → F1 hành vi, cảnh báo sai/giờ, độ trễ, danh tính, độ lệch theo FPS —
tất cả gắn nhãn **SYNTHETIC**; mục thực tế **NOT_EVALUATED**.
