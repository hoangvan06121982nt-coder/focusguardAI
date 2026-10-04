# Hồ sơ AI Tài Năng Việt 2026 – FocusGuard (Bảng A THCS)

Thư mục này chứa **bản nguồn để review và cập nhật hồ sơ dự thi**. Mọi claim kỹ thuật phải đối chiếu với source/test hiện tại của repository.

## Nội dung
- `01_FocusGuard_HoSo_BangA_8trang_SOURCE.md` – nguồn nội dung hồ sơ chính.
- `02_KichBan_ThuyetTrinh_5Phut.md` – kịch bản thuyết trình.
- `03_KichBan_Video_Demo_3Phut.md` – kịch bản video demo.
- `04_PromptLog_MinhChung_HuongDan.md` – hướng dẫn Prompt Log & evidence.
- `05_Bo_CauHoi_PhanBien.md` – bộ câu hỏi luyện phản biện.
- `CLAUDE_REVIEW_AND_SCREENSHOT_PROMPT.md` – prompt dùng cho Claude Code để audit claim, chạy test và chụp UI thật.
- `screenshots/README.md` – quy ước ảnh giao diện thật dùng trong hồ sơ.

## Nguyên tắc
1. Không sửa claim kỹ thuật chỉ để hồ sơ “đẹp” hơn.
2. Không đưa accuracy thực tế khi chưa có dataset gán nhãn hợp lệ.
3. Không dùng screenshot giả, mock data hoặc dashboard dựng riêng cho hồ sơ.
4. Screenshot phải lấy từ phiên bản code thực tế đang đề xuất nộp.
5. Prompt Log phải là lịch sử thật; không dựng lại.
6. Không commit secret, token, cookie, ảnh khuôn mặt riêng tư hoặc dữ liệu học sinh.

## Nguồn đối chiếu bắt buộc
- `README.md`
- `SUMMARY.md`
- `docs/COMPETITION_ARCHITECTURE.md`
- `docs/PRIVACY_AND_AI_SAFETY.md`
- `docs/REAL_CAMERA_RESULTS.md`
- `.github/workflows/ci.yml`
- test suite và commit history hiện tại

## Trạng thái
Bản nguồn hiện vẫn có placeholder cho tên đội/thành viên/trường/lớp/giáo viên hướng dẫn. Chỉ điền bằng thông tin đăng ký thật.

Bản PDF/DOCX có thể được sinh lại sau khi:
- claim audit PASS;
- UI branch cuối cùng được xác nhận;
- screenshot thật được cập nhật;
- thông tin đội được điền.
