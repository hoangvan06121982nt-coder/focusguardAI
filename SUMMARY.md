# 📋 FocusGuardAI – Tổng hợp chức năng & Kiến trúc hệ thống

FocusGuard AI là hệ thống giám sát học tập và hỗ trợ tập trung thời gian thực sử dụng trí tuệ nhân tạo (AI Camera) với sự kết hợp của YOLOv8 và MediaPipe. Ứng dụng hỗ trợ giao diện phân quyền chi tiết cho cả 4 vai trò: **Học sinh**, **Giáo viên**, **Phụ huynh**, và **Quản trị viên (Admin)**.

---

## 🏗️ Kiến trúc tổng quan

Kiến trúc phần mềm của dự án được triển khai phân tầng (Layered Architecture) rõ ràng, tăng hiệu năng truyền dữ liệu realtime:

| Tầng (Layer) | File & Module chính | Công nghệ & Thư viện sử dụng |
| :--- | :--- | :--- |
| **Backend** | [app.py](file:///Users/ikh/projects/FocusGuardAI/app.py), [session_manager.py](file:///Users/ikh/projects/FocusGuardAI/session_manager.py), [camera_ai.py](file:///Users/ikh/projects/FocusGuardAI/camera_ai.py), [repository.py](file:///Users/ikh/projects/FocusGuardAI/repository.py) | **Python 3.10+, Flask, Flask-SocketIO (Eventlet)** |
| **Frontend** | [main.js](file:///Users/ikh/projects/FocusGuardAI/static/js/main.js), [style.css](file:///Users/ikh/projects/FocusGuardAI/static/css/style.css), các templates HTML | **Vanilla JavaScript (ES6), Bootstrap 5.3 (Dark/Light theme), Chart.js** |
| **Database** | Cấu hình linh hoạt qua `.env` | **SQLite** (`focusguard.db`) hoặc **Firebase local (Firestore Emulator + Firebase Auth Emulator)** |
| **AI Models** | [camera_ai.py](file:///Users/ikh/projects/FocusGuardAI/camera_ai.py) | **MediaPipe FaceLandmarker + Facial Transformation Matrix**, **YOLOv8n (PyTorch / ONNX)** |

---

## 🤖 1. Module AI Camera – `camera_ai.py`

Module cốt lõi chạy trực tiếp dưới luồng camera học sinh để nhận diện hành vi, cử chỉ và biểu cảm thời gian thực:

* **📱 Phát hiện điện thoại**: Sử dụng mô hình YOLOv8n để phát hiện sự xuất hiện của điện thoại (class `67` = cell phone) trước camera.
* **😴 Phát hiện buồn ngủ**: Tính toán chỉ số EAR (Eye Aspect Ratio) từ các mốc điểm mắt của MediaPipe. Nếu chỉ số EAR hạ dưới ngưỡng `0.22` quá thời gian `1.5s` (DROWSY_TIME_THRESH), ghi nhận trạng thái **Buồn ngủ**.
* **🔍 Phát hiện mất tập trung (Ngoảnh mặt)**: Sử dụng Facial Transformation Matrix để tính toán yaw/pitch/roll của đầu học sinh. Nếu quay đầu quá góc $\pm20^\circ$ lâu hơn `2.0s` (DISTRACTION_TIME_THRESH), ghi nhận trạng thái **Ngoảnh mặt**.
* **🚫 Không thấy khuôn mặt**: Ghi nhận khi MediaPipe không tìm thấy bất kỳ khuôn mặt nào trước camera (học sinh rời khỏi chỗ).
* **👥 Phát hiện nhiều người (Multiple Person)**: Sử dụng YOLOv8 (class `0` = person) kết hợp MediaPipe để đếm số người trong khung hình. Nếu xuất hiện từ 2 người trở lên, phát cảnh báo bảo mật.
* **😊 Nhận diện cảm xúc (Emotion Detection)**: Phân tích các biểu cảm cơ mặt thời gian thực thành 4 loại cảm xúc:
  * 😐 **Neutral (Bình thường)** - Mặc định
  * 😊 **Happy (Vui vẻ)** - Trực quan hóa tương tác tích cực
  * 😴 **Tired (Mệt mỏi)** - Liên đới cảnh báo buồn ngủ
  * 😫 **Stressed (Căng thẳng)** - Cảnh báo stress khi học tập quá tải

---

## 📡 2. Hệ thống API Backend & Realtime WebSockets

Xử lý định tuyến RESTful APIs và truyền tải trạng thái thời gian thực thông qua WebSockets (Socket.IO).

### Auth & Roles (Phân quyền người dùng)
Hệ thống tự động chuyển hướng và quản lý phiên đăng nhập theo 4 vai trò:
1. **Admin**: Quản lý lớp học và tài khoản người dùng.
2. **Teacher**: Giám sát lớp học thời gian thực, xem analytics, báo cáo, điểm danh và điều phối lớp.
3. **Student**: Học tập, chạy camera AI giám sát cá nhân và nhận báo cáo học tập.
4. **Parent**: Giám sát tiến trình học tập của con, nhận khuyến nghị AI và biểu đồ nhiệt.

### Các API Endpoint chính

#### 👤 Student & AI APIs
* `GET /video_feed`: Stream MJPEG webcam realtime kèm các bounding boxes và text phủ trạng thái từ AI.
* `POST /api/start_session`: Bắt đầu phiên học tập cá nhân (Khởi tạo điểm tập trung ban đầu = 100).
* `POST /api/stop_session`: Kết thúc phiên học, tổng hợp dữ liệu lưu vào database.
* `GET /api/stats`: Lấy điểm số hiện tại, số lần vi phạm và trạng thái kết nối.
* `GET/POST /api/settings`: Đọc và cập nhật cấu hình ngưỡng nhận diện AI cá nhân.
* `GET /api/latest_session`: Lấy báo cáo phiên học gần nhất kèm đánh giá AI Coach.
* `GET /api/leaderboard`: Lấy danh sách bảng xếp hạng thi đua trong ngày của lớp.
* `GET /api/student/heatmap`: Dữ liệu biểu đồ nhiệt tập trung theo từng giờ (High/Med/Low).
* `GET /api/session/<id>/breakdown`: Lấy chi tiết lịch sử vi phạm của một phiên cụ thể.
* `GET /api/student/subject_analytics`: Phân tích điểm tập trung trung bình theo môn học.
* `GET /api/student/profile`: Lấy thống kê tổng hợp (tổng giờ tích lũy, điểm trung bình, xu hướng).
* `GET /api/student/session_comparison`: Lấy dữ liệu so sánh điểm tập trung giữa các phiên học gần nhất.
* `GET /api/student/recommendations`: AI tự động tạo gợi ý học tập cá nhân hóa.

#### 👨‍🏫 Teacher APIs
* `POST /api/teacher/start_class`: Giáo viên bắt đầu buổi học (phát tín hiệu bắt đầu đến học sinh).
* `POST /api/teacher/end_class`: Kết thúc buổi học (dừng tất cả phiên của học sinh).
* `GET /api/teacher/class_status`: Lấy trạng thái thời gian thực của toàn bộ học sinh.
* `GET /api/teacher/logs`: Lấy nhật ký cảnh báo thời gian thực của lớp học.
* `GET/POST /api/teacher/settings`: Cập nhật cấu hình hiển thị và ngưỡng cảnh báo của lớp.
* `GET /api/teacher/analytics_summary`: Thống kê điểm trung bình lớp, watchlist học sinh yếu, danger hour và phân tích nguyên nhân gốc rễ (root cause).
* `GET /api/teacher/class_summary`: Tạo tóm tắt thông minh kết quả cuối buổi học (AI Summary).
* `GET /api/teacher/interventions`: AI gợi ý cách điều phối lớp học khi chỉ số tập trung sụt giảm.

#### 🔑 Admin APIs
* `GET /api/admin/classes`: Lấy danh sách tất cả lớp học.
* `POST /api/admin/create_class` / `edit_class` / `delete_class`: Quản lý danh mục lớp học.
* `GET /api/admin/users`: Lấy danh sách tài khoản.
* `POST /api/admin/create_user` / `edit_user` / `delete_user`: Quản lý tài khoản (đồng bộ hóa tự động qua SQLite và Firebase Auth).

#### 🏠 Parent & Mobile Simulator APIs
* `GET /parent/dashboard`: Bảng điều khiển dành riêng cho phụ huynh để theo dõi tiến trình của con.
* `GET /mobile`: Giao diện ứng dụng di động (Mobile App Demo) dạng iframe 3D iPhone.

### WebSocket Events (Socket.IO)
* `join_teacher_room` / `join_student_room`: Đưa kết nối của giáo viên / học sinh vào các phòng sự kiện tương ứng.
* `request_class_snapshot`: Giáo viên yêu cầu chụp và gửi trạng thái hiện tại của toàn lớp.
* `class_snapshot`: Gửi trạng thái toàn lớp (broadcast mỗi 2s khi buổi học đang diễn ra).
* `student_update` / `student_frame`: Cập nhật trạng thái và ảnh chụp snapshot của học sinh gửi lên màn hình giáo viên (gửi mỗi 3s).
* `student_data_push` / `student_frame_push`: Luồng đẩy dữ liệu realtime từ phía client học sinh lên server.
* `class_started` / `class_ended`: Tín hiệu giáo viên bắt đầu/kết thúc lớp được gửi tự động xuống máy học sinh để mở/đóng camera AI.

---

## 🗄️ 3. Quản lý trạng thái học tập – `session_manager.py`

`SessionManager` chịu trách nhiệm quản lý logic điểm số học tập và mô phỏng lớp học:

### Thuật toán tính điểm tập trung (Focus Score Engine)
* Điểm số ban đầu khởi tạo là **100**.
* Trừ điểm theo thời gian thực khi có hành vi vi phạm:
  * 📱 Dùng điện thoại: **-0.2 điểm / frame**
  * 😴 Buồn ngủ / ngủ gật: **-0.3 điểm / frame**
  * 🔍 Ngoảnh mặt đi: **-0.1 điểm / frame**
* **Cơ chế hồi phục tự động (Auto-recovery)**: Tự động cộng lại **+0.1 điểm / giây** khi học sinh quay trở lại trạng thái tập trung tốt.
* **Chỉ số rủi ro học tập (Learning Risk Score)**:
  $$\text{Risk Score} = 40\% \times \text{Tỷ lệ dùng điện thoại} + 30\% \times \text{Tỷ lệ ngủ gật} + 20\% \times \text{Tỷ lệ ngoảnh mặt} + 10\% \times \text{Cảm xúc tiêu cực}$$

### Giả lập lớp học (Classroom Simulation)
* Hệ thống quản lý **28 học sinh giả lập (Mock Students)** trong RAM. Các học sinh giả lập này tự động sinh hành vi và điểm số ngẫu nhiên theo đồ thị phân phối chuẩn để giáo viên có thể trải nghiệm đầy đủ giao diện lớp học trực quan.
* Khi có học sinh thật kết nối (`hocsinh`), dữ liệu thật sẽ thay thế luồng giả lập tương ứng.

### Cơ sở dữ liệu Firestore Local Emulator
* Khi biến môi trường `.env` cấu hình `DATABASE_TYPE=firestore` và `USE_EMULATOR=true`, ứng dụng sẽ kết nối trực tiếp đến **Firebase Local Emulator Suite**.
* Tự động khởi tạo cấu trúc dữ liệu và đồng bộ hóa danh sách người dùng sang Firebase Auth Emulator khi chạy ứng dụng lần đầu tiên hoặc chạy script `scratch/reset_firestore.py`.

---

## 🎨 4. Tính năng Giao diện người dùng (Frontend)

Hệ thống sở hữu thiết kế giao diện hiện đại, trực quan, hỗ trợ Light/Dark mode tự động lưu cấu hình.

### 👤 Giao diện Học sinh (`index.html` & `main.js`)
* **Bảng điều khiển tập trung:** Đồng hồ đo điểm (Gauge SVG), đồng hồ đếm giờ học và 3 thẻ trạng thái nhanh (Focused, Sleepy, Phone).
* **AI Camera Feed:** Xem stream camera trực tiếp, chụp ảnh snapshot màn hình, bật/tắt toàn màn hình.
* **Nhật ký hoạt động (Activity Log):** Hiển thị danh sách cảnh báo vi phạm realtime có phân cấp màu sắc.
* **Chuông thông báo (Alert Bell):** Dropdown lưu trữ 5 cảnh báo gần nhất, có badge đếm số lượng chưa đọc.
* **Lịch sử học tập (Stats tab):** Xem danh sách tất cả phiên học đã qua, điểm trung bình toàn thời gian.
* **Biểu đồ nhiệt (Heatmap):** Hiển thị mức độ tập trung theo từng khung giờ trong ngày dưới dạng lưới ô màu sinh động.
* **Bảng xếp hạng (Leaderboard):** Bảng thi đua top 3 học sinh có điểm tập trung tốt nhất trong ngày.
* **Báo cáo thông minh (AI Coach):** Tạo báo cáo tổng kết phiên kèm phân tích nguyên nhân xao nhãng và lời khuyên hữu ích từ AI. Hỗ trợ in ấn và xuất báo cáo PDF/JSON chuyên nghiệp.
* **Cài đặt cá nhân:** Điều chỉnh độ nhạy AI (EAR, yaw/pitch), bật/tắt âm thanh cảnh báo và tùy chỉnh âm lượng.

### 👨‍🏫 Giao diện Giáo viên (`teacher_dashboard.html`)
* **Giám sát trực tiếp (Live Monitoring):**
  * Điều khiển buổi học (Start/End Class) kèm đồng hồ bấm giờ buổi học.
  * Hỗ trợ 4 chế độ hiển thị linh hoạt:
    * **Grid View**: Danh sách thẻ học sinh (ảnh webcam trực tiếp cập nhật mỗi 3s, thanh điểm focus, badge trạng thái).
    * **List View**: Dạng bảng tối ưu dữ liệu cho lớp đông.
    * **Bản đồ 2D (Classroom Seating Map)**: Sơ đồ vị trí chỗ ngồi 2D của học sinh.
    * **Bản đồ 3D Twin**: Mô phỏng lớp học 3D trực quan, các bàn học hiển thị dưới dạng khối 3D đổi màu động theo trạng thái tập trung của học sinh (Xanh = Tập trung, Vàng = Phân tâm, Đỏ = Vi phạm). Click vào bàn học để mở chi tiết học sinh đó.
* **Bảng điều khiển chi tiết (Detail Panel):** Xem chi tiết học sinh được chọn bao gồm: ảnh chụp vi phạm mới nhất, điểm số, chỉ số rủi ro học tập, biểu đồ mini xu hướng tập trung và lịch sử cảm xúc thời gian thực.
* **Bảng điểm danh lớp (AI Attendance):** Điểm danh tự động bằng nhận diện khuôn mặt khi học sinh bắt đầu phiên học. Hiển thị trạng thái (Có mặt / Đi muộn / Vắng mặt), thời gian vào lớp và phương thức xác minh.
* **Phân tích nâng cao (Analytics View):**
  * Biểu đồ tròn (Donut) phân bổ mức độ tập trung toàn lớp.
  * Biểu đồ đường (Line) xu hướng điểm trung bình lớp thời gian thực.
  * Thống kê nguyên nhân xao nhãng hàng đầu (Root Cause Analysis).
  * Danh sách học sinh cần lưu ý (Low Attention Watchlist).
  * Khung giờ mất tập trung nhiều nhất (Danger Hour).
* **AI Intervention (Gợi ý điều phối):** Hệ thống đề xuất hành động cho giáo viên dựa trên mức tập trung toàn lớp.
* **Tóm tắt cuối buổi (AI Summary):** Trình bày tổng điểm trung bình lớp, Top 3 học sinh xuất sắc, và tóm tắt gửi giáo viên.
* **Xuất dữ liệu:** Hỗ trợ xuất báo cáo lớp học ra định dạng file CSV tương thích tốt với Excel (UTF-8 BOM).

### 🏠 Giao diện Phụ huynh (`parent_dashboard.html`)
* **Thẻ thống kê nhanh:** Tổng số giờ tự học tích lũy của con, điểm tập trung trung bình tuần, số lần rời vị trí và tổng thời gian vắng mặt trước camera.
* **Smart Study Recommendation:** AI gợi ý khung giờ học tập tốt nhất của con và khuyến nghị thời gian nghỉ ngơi hợp lý.
* **Biểu đồ nhiệt độ (Heatmap):** Theo dõi mức độ tập trung từng khung giờ hàng ngày của con.
* **Biểu đồ xu hướng tuần:** Biểu đồ đường (Line Chart) theo dõi tiến trình tập trung của con qua các ngày.
* **Mobile Simulator Preview:** Mô phỏng ứng dụng di động trên khung hình 3D iPhone.

---

## 🚀 Tính năng đã hoàn thành (Checklist)

Tất cả các tính năng dưới đây đều đã được tích hợp và triển khai thành công vào hệ thống FocusGuard AI:

### 🟢 Giao diện & Tiện ích cá nhân (Đã xong)
- [x] **AI Coach cá nhân (Báo cáo thông minh)**: Đưa ra nhận xét và khuyến nghị học tập hữu ích.
- [x] **Focus Heatmap (Biểu đồ nhiệt tập trung)**: Trực quan hóa mức độ tập trung từng giờ của học sinh.
- [x] **Leaderboard (Bảng xếp hạng thi đua)**: Hiển thị top học sinh tập trung xuất sắc nhất trong ngày.
- [x] **PDF Report (Xuất báo cáo PDF chuyên nghiệp)**: Xuất file PDF đầy đủ dữ liệu phiên học và ảnh vi phạm.
- [x] **Daily / Weekly / Monthly Analytics**: So sánh xu hướng tập trung theo chu kỳ thời gian.
- [x] **Hồ sơ học sinh (Student Profile)**: Quản lý tổng hợp giờ học và tiến trình phát triển cá nhân.

### 🔵 Phân tích & Trợ lý học đường nâng cao (Đã xong)
- [x] **Classroom Analytics AI**: Phân tích tình hình lớp, cảnh báo và tìm khung giờ tập trung kém nhất (Danger Hour).
- [x] **Root Cause Analytics**: Phân tích tỷ lệ phần trăm nguyên nhân gây xao nhãng của học sinh.
- [x] **Session Comparison**: Đánh giá sự tiến bộ qua các buổi học khác nhau.
- [x] **Subject Analytics**: Theo dõi và phân tích độ tập trung theo từng môn học.
- [x] **Low Attention Watchlist**: Tự động liệt kê học sinh cần hỗ trợ gấp (điểm tập trung < 60).
- [x] **Emotion Detection (Nhận diện cảm xúc)**: Phân tích biểu cảm khuôn mặt (Vui, Bình thường, Mệt, Căng thẳng).

### 🟡 Công nghệ mô phỏng & Dự báo (Đã xong)
- [x] **AI Classroom Twin**: Sơ đồ vị trí lớp học 2D realtime.
- [x] **AI Prediction Engine**: Động cơ dự báo nguy cơ chuẩn bị có hành vi xao nhãng của học sinh.
- [x] **Early Warning System**: Cảnh báo sớm nguy cơ mất tập trung của học sinh trong vài phút tới.
- [x] **Attention Trend Forecast**: Vẽ đồ thị dự báo đường xu hướng tập trung tiếp theo.
- [x] **Learning Risk Score**: Chỉ số đánh giá mức độ rủi ro sa sút học tập của học sinh.
- [x] **AI Summary cuối buổi**: Tổng kết nhanh kết quả buổi học gửi cho giáo viên.

### 🔴 Chống gian lận & Giám sát thực tế (Đã xong)
- [x] **AI Attendance**: Điểm danh tự động qua nhận diện khuôn mặt khi bắt đầu học.
- [x] **Seat Leaving Detection**: Phát hiện rời vị trí camera, đếm số lần và tổng thời gian rời đi.
- [x] **Multiple Person Detection**: Phát hiện có từ 2 người trở lên trước camera để cảnh báo bảo mật.
- [x] **Anti-Cheating Mode**: Chế độ chống gian lận tổng hợp (phát hiện điện thoại, nhiều người, rời camera, lệch mắt).
- [x] **Screen Attention**: Theo dõi hướng nhìn để đánh giá tỷ lệ thời gian học sinh nhìn màn hình học tập.
- [x] **Teacher Intervention Recommendation**: AI gợi ý hoạt động điều phối lớp cho giáo viên.

### 🏆 Đột phá công nghệ & Mở rộng cổng kết nối (Đã xong)
- [x] **Dashboard Classroom Twin 3D**: Sơ đồ lớp học 3D realtime hỗ trợ đổi màu động theo trạng thái học sinh.
- [x] **AI Voice Assistant (Trợ lý giọng nói)**: Giáo viên tương tác hỏi đáp thông tin lớp bằng giọng nói.
- [x] **Parent Dashboard**: Cổng thông tin riêng cho phụ huynh theo dõi tiến trình của con.
- [x] **Mobile App Simulator**: Giả lập ứng dụng di động hiển thị trên giao diện iPhone.
- [x] **Multi-Class Monitoring**: Giám sát đồng thời nhiều lớp học khác nhau.
- [x] **Smart Recommendation Engine**: Đề xuất tối ưu hóa lịch trình học tập thông minh dựa trên thói quen cá nhân.
