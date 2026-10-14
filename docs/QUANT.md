# Quant desk — đọc trong một phút

| Số trên màn hình | Ý nghĩa | Cách dùng |
|---|---|---|
| Dự báo nến kế tiếp | Giá đóng cửa nến phút tiếp theo, từ dữ liệu đã biết | So chênh lệch với giá đang giao dịch; chưa đủ để đặt lệnh một mình |
| RMSE (điểm) | Độ lớn sai số dự báo trên các nến kiểm định về sau | Biên dự báo nhỏ so với RMSE → ưu tiên Chờ |
| Sai số giảm so với baseline | So với cách đoán giá kế tiếp giữ nguyên | Mô hình phải giảm sai số ít nhất 5% mới đưa gợi ý có hướng |
| Biên còn sau phí | Độ lớn dự báo trừ 0,24 điểm phí và trượt giá khứ hồi mỗi HĐ trong game | Âm hoặc bằng 0 → chưa vượt chi phí; không phải lợi nhuận chắc chắn |
| Z-score | (Giá đóng cửa − trung bình tối đa 40 nến) / độ lệch chuẩn | +2: đang cao hơn trung bình khoảng hai độ lệch chuẩn; không tự suy ra Short |
| Quay về trung bình | Kiểm tra mô hình mean reversion riêng | Chỉ có hỗ trợ khi hệ số quay về hợp lệ và sai số tốt hơn baseline ít nhất 5% |
| Ước lượng tăng / vùng 80% | Phân bố sai số gần đây áp vào dự báo hiện tại | Cho biết độ bất định; chưa hiệu chỉnh thành xác suất thắng hay bảo đảm bao phủ |

**Trình tự đọc:** xem Long/Short/Chờ → so biên với RMSE và phí → xem mức bằng chứng → tự chọn lệnh. Mở phần “Hiểu các con số” ngay trong game để đọc thêm. Gợi ý không tự đặt lệnh. “Thấp/Vừa” là mức bằng chứng trong cửa sổ kiểm định, không phải cam kết hiệu quả thị trường.

## Mô hình nhẹ

- **AR(2):** dự báo thay đổi giá từ hai thay đổi gần nhất, hồi quy ridge nhẹ.
- **ARX(2):** thử thêm log(1 + khối lượng) đã quan sát tại nến dự báo. Chỉ giữ khi cửa sổ chọn mô hình giảm RMSE ít nhất 5%. “X” là biến dự báo trễ; không khẳng định khối lượng ngoại sinh về mặt kinh tế lượng.
- **Mean reversion:** hồi quy thay đổi giá theo mức giá hiện tại. Chỉ chọn khi hệ số nằm giữa −1 và 0 và sai số chọn mô hình tốt hơn ứng viên trước ít nhất 5%.

Mỗi dự báo lịch sử chỉ huấn luyện bằng dữ liệu trước nó, tối đa 96 mẫu. Dùng 12 dự báo đầu để chọn mô hình; báo RMSE và vùng sai số trên 20–40 dự báo **sau** cửa sổ chọn. Sau đó khớp lại mô hình được chọn bằng dữ liệu hiện đã biết để dự báo nến tiếp theo. Không chọn mô hình bằng sai số của cửa sổ báo cáo. Cách đánh giá tham khảo [time-series cross-validation](https://otexts.com/fpp3/toolbox.html).

Gợi ý Chờ khi sai số không vượt baseline, biên chưa vượt chi phí, biên dưới nửa RMSE, tỷ lệ một chiều dưới 60%, hoặc sai số vừa rồi vượt hai lần RMSE. Không nâng mức bằng chứng lên “cao”. Chỉ số có thể xấu đi khi thị trường đổi trạng thái.

## Dữ liệu và nhịp cập nhật

Chỉ dùng giá đóng cửa và khối lượng từ bộ nến có sẵn; không gọi thêm API. Chuỗi đầu vào tối đa 180 nến. Các mẫu huấn luyện vượt khoảng nghỉ trưa, qua đêm, trùng thời gian hoặc ATC bị loại khỏi bài toán nến phút. Sau khoảng nghỉ cần đủ nến liên tục trở lại.

Trong replay, tối đa 120 nến trước lúc bắt đầu được dùng làm warmup; các nến tương lai chưa mở tuyệt đối không tham gia phân tích. Trong live, xác định nến đã đóng theo thời điểm nguồn được lấy, để cache không biến nến chưa hoàn thành thành nến đã đóng. Chênh lệch dự báo và gợi ý được so với giá hiện đang giao dịch.

Kết quả mô hình được cache theo bộ nến. Chỉ tính lại khi đầu vào thay đổi; replay mở một nến mỗi 3 giây, nguồn live cache 60 giây. Không phải dữ liệu tick. Mô hình không cần thêm thư viện tính toán.

Luyện tập được ghi rõ **dữ liệu mẫu**; kiểm thử với chuỗi tổng hợp chỉ xác nhận thuật toán, không chứng minh hiệu quả VN30F1M. Nếu vnstock lỗi, chế độ dữ liệu thật báo lỗi và không thay bằng giá ngẫu nhiên. Thiếu ít nhất 52 mẫu huấn luyện/kiểm định hợp lệ thì hiển thị Chờ dữ liệu.
