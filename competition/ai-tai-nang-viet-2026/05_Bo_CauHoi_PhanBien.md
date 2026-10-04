# BỘ CÂU HỎI PHẢN BIỆN – FOCUSGUARD

## 1. FocusGuard có thật sự đo được “tập trung” không?
Không đo trực tiếp suy nghĩ. Hệ thống ghi nhận hành vi quan sát được và tính một chỉ số heuristic theo thời gian để hỗ trợ giáo viên.

## 2. Vì sao không dùng model AI dự đoán focus?
Nhóm ưu tiên kết quả giải thích được và tránh tuyên bố quá khả năng dữ liệu. Khi chưa có dataset thật gán nhãn, mô hình dự đoán sẽ khó kiểm chứng.

## 3. YOLOv8 do nhóm tự làm không?
Không. YOLOv8 là mô hình có sẵn. Nhóm tích hợp nó vào pipeline và xây phần identity/runtime/behavior/focus/realtime/test.

## 4. ByteTrack và InsightFace khác nhau thế nào?
ByteTrack theo dõi người qua frame bằng track_id tạm; InsightFace tạo embedding khuôn mặt. IdentityManager mới quyết định student_id chuẩn.

## 5. Nếu hai học sinh đi cắt nhau thì sao?
IdentityManager có khóa danh tính, xác nhận theo thời gian, chống trùng và conflict/recovery. Kịch bản hai người thật vẫn cần thêm volunteer để đánh giá đầy đủ.

## 6. Tại sao chớp mắt không bị báo ngủ?
DROWSY chỉ mở episode khi tín hiệu mắt thấp kéo dài đủ thời gian; chớp ngắn bị bỏ qua.

## 7. Điện thoại lóe qua camera có bị phạt không?
Không; behavior dùng ngưỡng thời gian và gap tolerance để giảm event do vài frame nhiễu.

## 8. Camera mất thì điểm có giảm không?
Không. NO_CAMERA_SIGNAL làm FocusEngine đóng băng điểm.

## 9. Người lạ vào lớp thì sao?
Nếu không đủ bằng chứng nhận dạng, giữ UNKNOWN thay vì đoán.

## 10. Có lưu ảnh/video học sinh không?
Thiết kế hiện không ghi video; ảnh đăng ký chỉ dùng để trích embedding trong bộ nhớ. Hệ thống lưu vector đặc trưng khuôn mặt.

## 11. Embedding có nhạy cảm không?
Có. Vì vậy cần consent phù hợp, kiểm soát quyền truy cập và khả năng xóa.

## 12. Accuracy hiện bao nhiêu?
Chưa có số accuracy thực tế đáng tin cậy. Hồ sơ ghi NOT_EVALUATED vì chưa có dataset thật gán nhãn đủ điều kiện.

## 13. 184 test chứng minh gì?
Chứng minh code/contract/logic đã kiểm thử; không chứng minh accuracy ngoài thực tế.

## 14. Camera thật đã thử chưa?
Có. Một buổi với một volunteer trên MacBook Air M3, khoảng 7,5 FPS; nhiều kịch bản tích hợp đã PASS, nhưng không dùng để suy ra accuracy.

## 15. Focus score tính thế nào?
Tăng khi FOCUSED; giảm với PHONE/DROWSY/HEAD_AWAY/AWAY; trạng thái không chắc hoặc mất camera thì đóng băng.

## 16. Tại sao PHONE bị trừ nhiều hơn HEAD_AWAY?
Đây là quyết định heuristic hiện tại, không phải chân lý khoa học; có thể hiệu chỉnh khi có dữ liệu thật.

## 17. Giáo viên có thể xem lớp khác không?
Không theo thiết kế; authz kiểm tra quyền sở hữu lớp ở server.

## 18. Client có thể hack điểm 100 không?
Không theo contract; client push trạng thái AI bị server từ chối.

## 19. Tại sao có cả Firestore và SQLite?
SQLite thuận tiện local/demo; Firestore là backend tùy chọn. Repository layer tách persistence khỏi business logic.

## 20. Sản phẩm có thay giáo viên không?
Không. Giáo viên luôn là người quyết định.

## 21. Điểm mới của nhóm là gì?
Sự kết hợp identity ổn định, behavior theo thời gian, FocusEngine duy nhất, server-authoritative realtime, phân quyền và nguyên tắc không fake dữ liệu.

## 22. Nếu BTC yêu cầu đổi UX trong thời gian ngắn?
Hiểu change-request → xác định screen/contract → sửa bounded → test regression → demo lại.

## 23. Hạn chế lớn nhất?
Chưa có evaluation thực tế có ground truth; multi-person/stranger camera thật chưa đủ; privacy sinh trắc cần quản trị nghiêm túc.

## 24. Bước tiếp theo quan trọng nhất?
Hoàn thiện UI/UX và xây evaluation nhỏ có consent/ground truth để báo cáo precision/recall/false alerts trung thực.

## Cách luyện
- Trả lời 15–30 giây/câu.
- Hiểu ý, không học thuộc chữ.
- Nếu chưa biết hoặc chưa kiểm chứng, nói rõ thay vì đoán.
