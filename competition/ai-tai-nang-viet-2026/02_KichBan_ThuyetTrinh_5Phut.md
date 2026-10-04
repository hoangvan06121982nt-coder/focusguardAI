**KỊCH BẢN THUYẾT TRÌNH 5 PHÚT**

FocusGuard • Bảng A THCS

> **Mục tiêu:** Học sinh nói tự nhiên, hiểu ý; không đọc như thuộc lòng. Tổng thời lượng mục tiêu: 4:30–4:50 để có biên an toàn.

## 0:00–0:35 • Mở bài

“Trong một lớp học, giáo viên phải vừa giảng vừa quan sát rất nhiều học sinh. Có những lúc một bạn dùng điện thoại, ngủ gật hoặc rời chỗ nhưng giáo viên khó phát hiện ngay. Nhóm em xây dựng FocusGuard để hỗ trợ giáo viên nhận biết những tín hiệu đó bằng camera, nhưng không thay giáo viên đưa ra kết luận.”

## 0:35–1:20 • Giải pháp

“Camera phát hiện người và điện thoại. Sau đó hệ thống dùng đặc trưng khuôn mặt để xác định học sinh đã đăng ký. Chúng em không lấy một khung hình để kết luận ngay mà theo dõi tín hiệu theo thời gian: điện thoại phải đủ lâu, nhắm mắt phải kéo dài, quay đầu phải kéo dài; còn tạm khuất camera thì chưa bị trừ điểm.”

## 1:20–2:10 • Phần AI và phần nhóm xây dựng

“Chúng em sử dụng YOLOv8, ByteTrack, MediaPipe và InsightFace là các công nghệ có sẵn. Phần nhóm tập trung xây dựng là cách ổn định danh tính, ghép tín hiệu theo từng học sinh, BehaviorAnalyzer theo thời gian, FocusEngine duy nhất, SessionRuntime, phân quyền và dashboard. Điểm tập trung là công thức minh bạch chứ không phải AI đo được suy nghĩ của học sinh.”

## 2:10–3:05 • Sản phẩm

“Giáo viên đăng nhập, chọn lớp và bắt đầu phiên học. Khi có hành vi đủ điều kiện, sự kiện xuất hiện theo thời gian thực. Học sinh chỉ xem dữ liệu của mình; phụ huynh chỉ xem học sinh được liên kết. Nếu camera mất tín hiệu, hệ thống đóng băng điểm chứ không giả rằng học sinh mất tập trung.”

## 3:05–4:05 • Kiểm thử

“Hiện hệ thống có 184 test pass. Firestore emulator có 6/6 test hợp đồng và hardware tests 3/3 pass. Nhóm đã chạy camera thật trên MacBook Air M3, khoảng 7,5 FPS. Các tình huống như điện thoại, rời chỗ, ngắt camera đã chạy được. Tuy nhiên chúng em chưa có dataset lớp học thật đủ lớn để tuyên bố accuracy, nên hồ sơ ghi rõ NOT_EVALUATED.”

## 4:05–4:45 • An toàn & kết

“FocusGuard không nhận diện cảm xúc, không đo gaze và không ghi video. Hệ thống chỉ là tín hiệu hỗ trợ giáo viên, không dùng để tự động kỷ luật hoặc chấm hạnh kiểm. Mục tiêu tiếp theo của nhóm là cải thiện UI/UX và đánh giá trên dữ liệu có sự đồng ý, có ground truth. Chúng em muốn AI trong lớp học phải hữu ích, minh bạch và có trách nhiệm.”

# Ba câu tuyệt đối không nói

- “AI của em đo chính xác mức độ tập trung của học sinh.”
- “Nhóm em tự xây YOLO/InsightFace.”
- “Hệ thống đã đạt accuracy X%” khi chưa có bộ dữ liệu thật gán nhãn.

# Mẹo trình bày

- Mỗi thành viên nói một phần nếu đội có 2–3 người.
- Khi nói công nghệ, luôn nối với “dùng để làm gì”, không đọc danh sách tên model.
- Nếu giám khảo hỏi sâu, trả lời phần đã kiểm chứng trước, hạn chế nói suy đoán.
