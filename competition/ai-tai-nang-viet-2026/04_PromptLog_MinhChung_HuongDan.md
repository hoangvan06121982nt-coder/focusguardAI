# PROMPT LOG & MINH CHỨNG PHÁT TRIỂN

> **Bắt buộc:** Prompt Log phải là lịch sử thật. Không dựng lại prompt “cho đẹp”, không sửa timestamp và không khai nội dung tạo sau là lịch sử gốc.

## Cần nộp
1. Export/ảnh/PDF lịch sử ChatGPT, Claude Code, Copilot hoặc công cụ AI đã thực sự dùng.
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
| Git history | Quá trình sửa lỗi dựa trên kiểm thử thực tế |

## Kê khai công nghệ
- YOLOv8 / Ultralytics: mô hình/thư viện có sẵn; đội tích hợp và kiểm thử.
- ByteTrack: tracker có sẵn; track_id chỉ là tạm thời.
- MediaPipe Face Landmarker: landmark khuôn mặt.
- InsightFace: embedding khuôn mặt.
- Flask / Socket.IO: backend/realtime.
- Firebase Admin / Firestore: backend tùy chọn.
- AI coding assistant: **điền đúng công cụ thật và đính kèm Prompt Log gốc**.

## Trước khi nộp
- Xóa/redact API key, token, cookie, mật khẩu.
- Không đưa dữ liệu khuôn mặt riêng tư.
- Mọi claim trong hồ sơ phải đối chiếu được với repo/test/video.
