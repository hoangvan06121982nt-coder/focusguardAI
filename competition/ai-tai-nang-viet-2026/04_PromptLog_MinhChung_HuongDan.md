# PROMPT LOG & MINH CHỨNG PHÁT TRIỂN

> **Bắt buộc:** Prompt Log phải là lịch sử thật. Không dựng lại prompt “cho đẹp”, không sửa timestamp và không khai nội dung tạo sau là lịch sử gốc.

## Trạng thái: USER_ACTION_REQUIRED
Thư mục này **chưa có** Prompt Log gốc. Không ai được viết lại hay dựng lịch sử thay cho bản xuất thật.

Bằng chứng trong repo cho thấy trợ lý lập trình AI đã được dùng: 29 trên 33 commit của nhánh `main` (tại `950f8f5`) ghi `Co-Authored-By: Claude` (kiểm tra bằng `git log --format=%B | grep -c "Co-Authored-By: Claude"`). Vì vậy hồ sơ phải kê khai Claude Code và nộp lịch sử thật của các phiên đó.

Nơi lấy lịch sử thật:
- Claude Code lưu bản ghi từng phiên trên máy đã chạy, trong `~/.claude/projects/<tên-thư-mục-dự-án>/*.jsonl`; có thể xuất bằng chức năng xuất hội thoại của ứng dụng.
- ChatGPT, Copilot hoặc công cụ khác: chỉ nộp nếu thực sự đã dùng, bằng chức năng xuất của chính công cụ đó.
- Trước khi nộp phải đọc lại và che mật khẩu, token, cookie, đường dẫn riêng tư. Không commit bản ghi thô vào repo công khai.

## Cần nộp
1. Bản xuất/ảnh/PDF lịch sử của công cụ AI đã thực sự dùng (xem trên).
2. System prompt/custom instructions liên quan nếu nền tảng cho phép xuất.
3. Prompt tạo/sửa code, debug, test, tài liệu, UI/UX.
4. Minh chứng GitHub: commits, PR, CI, test, real-camera results, security.

## Manifest minh chứng trong repo
| Minh chứng | Nội dung |
|---|---|
| README.md | Kiến trúc, trạng thái test, hạn chế, cách chạy |
| SUMMARY.md | Competition hardening |
| docs/COMPETITION_ARCHITECTURE.md | Identity, behavior, FocusEngine, runtime, realtime, authz |
| docs/REAL_CAMERA_RESULTS.md | Camera thật, kịch bản PASS, lỗi đã sửa |
| docs/PRIVACY_AND_AI_SAFETY.md | Sinh trắc, không ghi video, phạm vi sử dụng |
| .github/workflows/ci.yml | CI compile/import/pytest/JS/security/evaluation |
| docs/UI_UX.md | Rà soát màn hình, hệ thống thiết kế, trạng thái hiển thị, hạn chế |
| tests/ (184 bài, trong đó tests/test_ui_contract.py 41 bài) | Kiểm thử logic, phân quyền, giao diện |
| competition/ai-tai-nang-viet-2026/screenshots/ | 5 ảnh giao diện thật kèm nguồn gốc (nhánh, commit, trạng thái) |
| Git history | Quá trình sửa lỗi dựa trên kiểm thử thực tế; ghi rõ commit nào có trợ lý AI đồng tác giả |

## Kê khai công nghệ
- YOLOv8 / Ultralytics: mô hình/thư viện có sẵn; đội tích hợp và kiểm thử.
- ByteTrack: tracker có sẵn; track_id chỉ là tạm thời.
- MediaPipe Face Landmarker: landmark khuôn mặt.
- InsightFace: embedding khuôn mặt.
- Flask / Socket.IO: backend/realtime.
- Firebase Admin / Firestore: backend tùy chọn.
- Trợ lý lập trình AI: Claude Code (theo lịch sử commit). **Đội xác nhận lại, bổ sung công cụ khác nếu có dùng, và đính kèm Prompt Log gốc.**
- Đóng góp của từng thành viên: **đội tự kê khai trung thực** (ý tưởng, yêu cầu, kiểm thử, phần mã tự viết, phần mã do AI viết và đội đã đọc hiểu).

## Trước khi nộp
- Xóa/redact API key, token, cookie, mật khẩu.
- Không đưa dữ liệu khuôn mặt riêng tư.
- Mọi claim trong hồ sơ phải đối chiếu được với repo/test/video.
