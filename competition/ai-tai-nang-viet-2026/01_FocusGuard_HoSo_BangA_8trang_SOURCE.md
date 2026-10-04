# FOCUSGUARD
## Hồ sơ dự án – AI Tài Năng Việt 2026 • Bảng A THCS

> **Thông điệp chính:** FocusGuard không thay giáo viên và không “chấm” học sinh bằng AI. Hệ thống dùng camera để ghi nhận các tín hiệu quan sát được theo thời gian, sau đó hỗ trợ giáo viên nhận biết những trường hợp cần chú ý một cách minh bạch và có thể kiểm chứng.

| Thông tin | Nội dung |
|---|---|
| Tên đội | [ĐIỀN TÊN ĐỘI ĐÃ ĐĂNG KÝ] |
| Thành viên | [ĐIỀN HỌ TÊN 1–3 THÍ SINH] |
| Trường/Lớp | [ĐIỀN ĐÚNG THÔNG TIN ĐÃ ĐĂNG KÝ] |
| Giáo viên hướng dẫn | [ĐIỀN NẾU CÓ] |
| Bảng thi | Bảng A – Học sinh THCS |
| Sản phẩm | FocusGuard – Hệ thống hỗ trợ giáo viên nhận biết tín hiệu mất tập trung bằng camera |

# 1. Vấn đề thực tế

Trong một lớp học, giáo viên phải vừa giảng bài, vừa quan sát nhiều học sinh cùng lúc. Những hành vi như dùng điện thoại, nhắm mắt kéo dài, quay đầu lâu hoặc rời vị trí có thể khó được phát hiện kịp thời, nhất là khi lớp đông. FocusGuard được xây dựng để hỗ trợ quan sát, không thay thế đánh giá sư phạm của giáo viên.

## Mục tiêu
- Phát hiện các tín hiệu quan sát được bằng camera theo thời gian, hạn chế cảnh báo từ những khoảnh khắc rất ngắn.
- Hiển thị trạng thái và lịch sử cho đúng người dùng: giáo viên, học sinh, phụ huynh, quản trị viên.
- Tính điểm tập trung bằng quy tắc công khai, không giả vờ đây là mô hình AI dự đoán.
- Bảo vệ dữ liệu: không ghi video; không đo cảm xúc; không đo gaze; không tự động dùng kết quả để kỷ luật/chấm hạnh kiểm.

## Giá trị nổi bật
| Khía cạnh | FocusGuard |
|---|---|
| Bài toán | Hỗ trợ giáo viên quan sát lớp học |
| AI | YOLOv8, ByteTrack, MediaPipe, InsightFace |
| Phần đội xây dựng | Ổn định danh tính, phân tích hành vi theo thời gian, FocusEngine, runtime, realtime, phân quyền, analytics |
| Nguyên tắc | Minh bạch – kiểm chứng – không phóng đại năng lực AI |

# 2. Đối tượng sử dụng & hành trình sản phẩm

FocusGuard có bốn vai trò. Mỗi vai trò chỉ được xem dữ liệu phù hợp với quyền của mình.

| Vai trò | Nhu cầu chính | Phạm vi dữ liệu |
|---|---|---|
| Giáo viên | Theo dõi lớp trực tiếp, cảnh báo, điểm danh, lịch sử | Lớp giáo viên phụ trách |
| Học sinh | Xem trạng thái/lịch sử của bản thân | Chính học sinh đó |
| Phụ huynh | Theo dõi học sinh đã liên kết | Học sinh được liên kết |
| Quản trị viên | Quản lý lớp, tài khoản, đăng ký khuôn mặt | Phạm vi quản trị |

## Luồng giáo viên
1. Đăng nhập và chọn lớp.
2. Bắt đầu phiên học trực tiếp.
3. Camera nhận diện học sinh đã đăng ký và tạo trạng thái runtime.
4. Hành vi chỉ trở thành sự kiện khi kéo dài đủ ngưỡng thời gian.
5. Dashboard cập nhật realtime; giáo viên quyết định có cần can thiệp hay không.
6. Kết thúc phiên; hệ thống lưu tóm tắt và lịch sử từ dữ liệu thật.

**Tránh suy diễn sai:** “Mất kết nối”, “vắng mặt”, “tạm khuất khỏi camera” và “mất tập trung” là các trạng thái khác nhau trong hệ thống.

**Không có dữ liệu giả:** nếu chưa đủ dữ liệu, giao diện hiển thị “Không đủ dữ liệu” hoặc N/A.

# 3. Kiến trúc hệ thống

```text
Camera
  ↓
YOLOv8 + ByteTrack
  ↓
MediaPipe + InsightFace
  ↓
IdentityManager → student_id chuẩn
  ↓
BehaviorAnalyzer → tín hiệu theo thời gian
  ↓
FocusEngine → điểm theo giây
  ↓
SessionRuntime → events + snapshots
  ↓
Socket.IO + SQLite/Firestore → dashboard & lịch sử
```

## Thiết kế danh tính
- ByteTrack chỉ cung cấp `track_id` tạm thời; không được coi là danh tính học sinh.
- InsightFace tạo embedding; IdentityManager yêu cầu ngưỡng, khoảng cách với lựa chọn thứ hai và xác nhận qua nhiều frame.
- Có cơ chế khóa/mở khóa danh tính, cooldown, phục hồi track và chống một học sinh bị gán cho hai track đang sống.

## Server authoritative
Client không được gửi điểm, danh tính hoặc trạng thái AI để server tin theo. Socket.IO dùng room theo lớp/học sinh và server quyết định dữ liệu nào được phát tới ai.

# 4. AI và cách tính “tập trung”

FocusGuard tách rõ phần mô hình AI có sẵn khỏi phần logic do đội xây dựng.

| Thành phần | Vai trò |
|---|---|
| YOLOv8 | Phát hiện người và điện thoại |
| ByteTrack | Theo dõi người qua các frame |
| MediaPipe Face Landmarker | Mốc khuôn mặt, tín hiệu mắt và góc đầu |
| InsightFace | Embedding khuôn mặt |
| BehaviorAnalyzer | Biến tín hiệu thô thành sự kiện theo thời gian |
| FocusEngine | Tích phân điểm theo thời gian bằng quy tắc công khai |

## Ngưỡng hành vi
| Hành vi | Điều kiện thời gian | Ý nghĩa |
|---|---|---|
| PHONE | > 1 giây | Dùng điện thoại đủ lâu mới cảnh báo |
| DROWSY | > 1,5 giây | Nhắm mắt kéo dài; bỏ qua chớp mắt |
| HEAD_AWAY | > 2 giây | Quay đầu lâu; bỏ qua liếc nhanh |
| AWAY | > 10 giây | Rời vị trí đủ lâu |
| Tạm khuất | Ngay | Không phạt điểm |

## FocusEngine
FOCUSED: +0,5 điểm/giây • PHONE: -2 • DROWSY: -1,5 • HEAD_AWAY: -1 • AWAY: -1 • tạm khuất/không rõ/mất camera: đóng băng điểm.

Điểm này là **heuristic theo thời gian**, không phải mô hình máy học dự đoán “mức độ tập trung thật”. FocusGuard không nhận diện cảm xúc và không đo gaze.

# 5. Sản phẩm & trải nghiệm người dùng

## Dashboard giáo viên
- Trạng thái phiên học và camera.
- Danh sách học sinh, điểm danh và trạng thái hiện tại.
- Các sự kiện cần chú ý kèm loại hành vi và thời lượng.
- Kết thúc phiên và xem tóm tắt/lịch sử từ dữ liệu thật.

## Camera lỗi
Camera ngắt không kết thúc runtime. Hệ thống chuyển sang `NO_CAMERA_SIGNAL` và đóng băng điểm; khi camera trở lại, runtime tiếp tục.

## Realtime và quyền
| Tình huống | Cách xử lý |
|---|---|
| Học sinh gửi điểm từ trình duyệt | Bị từ chối (`client_state_rejected`) |
| Giáo viên truy cập lớp khác | Bị chặn theo quyền sở hữu |
| Học sinh/phụ huynh | Chỉ nhận dữ liệu của học sinh được phép |
| Không đủ dữ liệu analytics | N/A / Không đủ dữ liệu |

Backend: Python + Flask + Flask-SocketIO. Lưu trữ: SQLite hoặc Firestore. Frontend: Flask templates, CSS/JavaScript.

# 6. Kiểm thử & bằng chứng

| Hạng mục | Kết quả đã ghi nhận |
|---|---|
| CI / unit & integration | 184 test pass, 0 fail, 9 skip theo điều kiện hardware/emulator |
| Firestore emulator | 6/6 test hợp đồng PASS |
| Hardware tests | 3/3 PASS |
| Camera thật | MacBook Air M3, FaceTime HD, khoảng 7,5 FPS trên CPU |
| Kịch bản camera | 1–5, 8, 9 PASS; 6–7 cần thêm tình nguyện viên |
| Độ chính xác lớp học thật | **NOT_EVALUATED** – chưa có bộ dữ liệu gán nhãn có đồng ý |

## Ví dụ camera thật
- Danh tính một người: xác nhận sau khoảng 0,85 giây; sau đó giữ CONFIRMED.
- Chớp mắt: các chớp ngắn bị bỏ qua; nhắm kéo dài được báo theo thiết kế.
- Điện thoại: ghi nhận một episode PHONE 14,7 giây đúng student_id.
- Rời chỗ/quay lại: một episode AWAY 18,7 giây; track mới nhận lại đúng học sinh; điểm không reset.
- Ngắt camera: điểm đóng băng; camera mở lại có frame sau khoảng 0,33 giây.

Các lần chạy camera thật đã phát hiện lỗi ghép khuôn mặt khi quay cận, mất danh tính khi điện thoại che mặt, EAR cố định gây báo buồn ngủ sai, duplicate track và tín hiệu điện thoại bị đứt. Các lỗi này đã được sửa và có regression test.

# 7. Quyền riêng tư, đạo đức AI & tính minh bạch

## Dữ liệu sinh trắc
- Chỉ lưu vector đặc trưng khuôn mặt; ảnh đăng ký chỉ dùng trong bộ nhớ để trích xuất.
- Không ghi video lớp học.
- Người không đăng ký hoặc nhận dạng không chắc chắn giữ trạng thái UNKNOWN.
- Admin có thể xóa vector đặc trưng.

## AI có trách nhiệm
FocusGuard là tín hiệu hỗ trợ giáo viên, không phải hệ thống tự động kỷ luật, xếp hạng hạnh kiểm hay chẩn đoán học sinh.

## Phần kế thừa & phần đội làm chủ
YOLOv8, ByteTrack, MediaPipe, InsightFace là công nghệ có sẵn. Phần đội xây dựng/kiểm chứng gồm pipeline ghép người–khuôn mặt, IdentityManager, BehaviorAnalyzer theo thời gian, FocusEngine duy nhất, SessionRuntime, realtime server-authoritative, phân quyền, analytics, regression tests và hardening camera thật.

## Điểm chưa hoàn thiện
- Chưa có đánh giá độ chính xác trên bộ dữ liệu lớp học thật có gán nhãn và đồng ý.
- Kịch bản hai người cắt nhau và người lạ cần thêm tình nguyện viên.
- Firestore production chưa kiểm thử; emulator đã kiểm thử.
- Lịch sử git cũ từng có tài sản nhạy cảm; current tree đã có security check nhưng lịch sử cần xử lý nếu công bố lâu dài.

# 8. Tác động, hướng phát triển & cam kết

FocusGuard hướng tới giảm tải quan sát đồng thời cho giáo viên, phát hiện sớm tín hiệu cần chú ý và tạo dữ liệu để trao đổi với học sinh/phụ huynh. Giá trị chính là hỗ trợ phản hồi kịp thời, không thay thế quan hệ thầy–trò.

## Ưu tiên tiếp theo
1. Xác nhận lại luồng camera thật trên UI/UX mới và chụp screenshot cuối cho hồ sơ.
2. Tổ chức evaluation nhỏ có sự đồng ý, ground truth thủ công và báo cáo precision/recall/false alerts.
3. Kiểm thử nhiều người, người lạ, ánh sáng/góc camera khác nhau và phần cứng thi.
4. Luyện đội thi giải thích kiến trúc và sửa change-request nhỏ có kiểm thử.

## Cam kết trung thực
Nhóm không tuyên bố accuracy khi chưa có dữ liệu thật, không gọi heuristic là mô hình AI dự đoán và không tuyên bố tự xây các mô hình nguồn mở.

## Nguồn đối chiếu
- `README.md`
- `SUMMARY.md`
- `docs/COMPETITION_ARCHITECTURE.md`
- `docs/PRIVACY_AND_AI_SAFETY.md`
- `docs/REAL_CAMERA_RESULTS.md`
- `.github/workflows/ci.yml`

> Trước khi nộp: điền đúng thông tin đội đã đăng ký và thay ảnh giao diện trong bản PDF bằng screenshot thật từ phiên bản cuối đã xác minh.
