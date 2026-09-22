# 🛡️ FocusGuard AI – Hệ thống giám sát học tập và hỗ trợ tập trung bằng AI

Hệ thống AI giám sát và phân tích độ tập trung của học sinh trong thời gian thực qua Webcam sử dụng YOLOv8 và MediaPipe. Ứng dụng hỗ trợ giao diện phân quyền chi tiết cho **Học sinh**, **Giáo viên**, **Phụ huynh** và **Quản trị viên (Admin)**.

---

## 🏗️ Yêu cầu hệ thống (Prerequisites)

Trước khi bắt đầu, hãy đảm bảo máy tính của bạn đã được cài đặt sẵn:
1. **Python 3.8 – 3.11** (Khuyên dùng Python 3.10 để tương thích tốt nhất với MediaPipe và PyTorch/YOLO).
2. **Node.js** (Phiên bản 16 trở lên để chạy Firebase Emulator cho cơ sở dữ liệu Firestore).
3. **Webcam** (Dành cho chức năng camera AI giám sát trực tiếp).

---

## 🚀 Hướng dẫn cài đặt chi tiết (Setup Instructions)

Hãy làm theo các bước dưới đây để cài đặt và chạy dự án FocusGuard AI trên máy của bạn:

### Bước 1: Thiết lập cấu hình môi trường (.env)
Tạo file cấu hình môi trường bằng cách sao chép từ file ví dụ `.env.example`:
```bash
cp .env.example .env
```
Mặc định cấu hình trong `.env` sẽ sử dụng cơ sở dữ liệu **Firestore (Emulator)**:
```env
DATABASE_TYPE=firestore
USE_EMULATOR=true
```
*(Nếu muốn chuyển sang SQLite, hãy đổi `DATABASE_TYPE=sqlite`)*.

---

### Bước 2: Cài đặt các gói thư viện Python (Backend & AI)
1. **Tạo môi trường ảo (Virtual Environment):**
   ```bash
   # MacOS / Linux
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Cài đặt các thư viện Python từ [requirements.txt](file:///Users/ikh/projects/FocusGuardAI/requirements.txt):**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

### Bước 3: Cài đặt Node Modules (Dành cho Firestore Emulator)
Dự án sử dụng cơ sở dữ liệu Firebase Firestore cục bộ thông qua Firebase Emulator. Để khởi chạy trình giả lập này, bạn cần cài đặt gói `firebase-tools`:

1. **Cài đặt các node packages:**
   ```bash
   npm install
   ```
   *Lệnh này sẽ tự động cài đặt `firebase-tools` được liệt kê trong [package.json](file:///Users/ikh/projects/FocusGuardAI/package.json) vào thư mục `node_modules`.*

---

## 🖥️ Hướng dẫn khởi chạy ứng dụng (Running the Application)

Để khởi chạy toàn bộ hệ thống, bạn cần mở **2 cửa sổ Terminal** riêng biệt:

### Terminal 1: Chạy Firebase Emulator (Giả lập Database & Auth)
Trình giả lập này giúp quản lý dữ liệu người dùng, điểm số và realtime đồng bộ hóa qua Firestore.
```bash
npx firebase emulators:start
```
> [!NOTE]
> * Giao diện quản lý Firebase Local Emulator Suite sẽ chạy tại địa chỉ: [http://127.0.0.1:4000](http://127.0.0.1:4000)
> * Firestore Emulator chạy tại cổng `8080` và Auth Emulator chạy tại cổng `9099`.

### Terminal 2: Chạy Flask Web Server (Backend & Realtime Web)
Kích hoạt môi trường ảo Python và khởi chạy server chính:
```bash
# Đảm bảo venv đã được active
source venv/bin/activate

# Chạy Flask Server
python app.py
```
> [!TIP]
> * Ứng dụng web chính sẽ chạy tại địa chỉ: [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## 🔑 Tài khoản đăng nhập mặc định (Default Accounts)

Hệ thống đã tự động seed sẵn dữ liệu mẫu sau khi cơ sở dữ liệu được khởi tạo:

| Tên đăng nhập (Username) | Mật khẩu (Password) | Vai trò (Role) | Mô tả |
| :--- | :--- | :--- | :--- |
| **`admin`** | `123` | **Quản trị viên** | Quản lý lớp học và danh sách tài khoản. |
| **`teacher`** | `123` | **Giáo viên** | Quản lý học sinh lớp 10A1, tạo buổi học và giám sát realtime. |
| **`hocsinh`** | `123` | **Học sinh** | Giao diện học tập thực tế, stream AI camera đo độ tập trung. |
| **`phuhuynh`** | `123` | **Phụ huynh** | Giám sát kết quả học tập và xem báo cáo của học sinh. |

---

## 📂 Danh mục cấu trúc các tệp tin quan trọng

* [app.py](file:///Users/ikh/projects/FocusGuardAI/app.py) – Máy chủ Flask chính xử lý API định tuyến, luồng webcam AI và WebSocket realtime.
* [camera_ai.py](file:///Users/ikh/projects/FocusGuardAI/camera_ai.py) – Xử lý luồng hình ảnh camera qua OpenCV, nhận diện đối tượng bằng YOLOv8n và theo dõi khuôn mặt bằng MediaPipe.
* [repository.py](file:///Users/ikh/projects/FocusGuardAI/repository.py) – Tầng truy xuất dữ liệu trừu tượng hỗ trợ cả SQLite và Firestore.
* [session_manager.py](file:///Users/ikh/projects/FocusGuardAI/session_manager.py) – Quản lý điểm tập trung, nhật ký hoạt động vi phạm và hệ thống chấm điểm / trừ điểm.
* [package.json](file:///Users/ikh/projects/FocusGuardAI/package.json) – Chứa các devDependencies dùng cho Firebase Emulator.
* [requirements.txt](file:///Users/ikh/projects/FocusGuardAI/requirements.txt) – Chứa danh sách các gói thư viện Python bắt buộc cài đặt.
