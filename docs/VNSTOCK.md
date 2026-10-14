# Ghi chú đối chiếu vnstock cho demo VN30F1M

Đối chiếu ngày 14/10/2026 giữa hướng dẫn do người dùng cung cấp, tài liệu hiện hành và source công khai. Những mô tả dưới đây phục vụ quyết định adapter; kết nối thật trong môi trường này chưa xác minh được do giới hạn mạng.

## Các lớp trong source

| Lớp | Nhiệm vụ | Liên quan demo |
| --- | --- | --- |
| Unified UI `Market` | Chọn domain và phương thức | `Market().futures("VN30F1M").ohlcv(...)` |
| Registry / adapter `api.Quote` | Ánh xạ lời gọi tới provider | Nhận source và chuyển tham số nến |
| Explorer VCI/KBS | Gửi HTTP và chuẩn hóa DataFrame | Lấy nến và xử lý alias mã hợp đồng |
| Parser / transform | Mã KRX, timezone, đơn vị giá | Giá phái sinh giữ đơn vị điểm, giờ Việt Nam |
| `vnai` | Thiết lập khóa/cấp quyền và runtime của thư viện | Khóa nằm ở backend; không mặc định coi mọi chức năng là miễn phí |

Source công khai được đọc tại [thinh-vu/vnstock, commit 71b853f](https://github.com/thinh-vu/vnstock/tree/71b853f0db18c0d783c2b9eeafaedbcbf4d05fba). `pyproject.toml` của checkout khai báo 4.0.9. Đã đọc `ui/domains/market/futures.py`, `ui/_registry.py`, `api/quote.py`, `explorer/vci/quote.py`, `explorer/kbs/quote.py`, `core/utils/parser.py`, `core/utils/transform.py`.

VCI/KBS đều gọi chuyển đổi alias phái sinh qua `convert_derivative_symbol`. Transform OHLC chỉ chia 1.000 đối với tài sản không phải index/derivative; vì vậy demo không áp dụng quy đổi giá cổ phiếu cho VN30F1M. Adapter lấy mã thực tế từ metadata khi nguồn có cung cấp, không tự hard-code mã tháng.

## Nguồn dữ liệu cần chọn

| Nhu cầu | Nguồn / API nên đối chiếu | Lựa chọn demo |
| --- | --- | --- |
| Nến phút VN30F1M | VCI hoặc KBS, tùy phiên bản/cấp quyền | Mặc định VCI, `interval="1m"`, `length=500` |
| Nến ngày phái sinh | KBS | Không thay nến phút bằng nến ngày khi nguồn lỗi |
| Quote, OI, basis phái sinh | KBS / `futures().quote()` | Chưa dùng; close nến là giá của mini game |
| Tick khớp lệnh | `futures().trades()` | Chưa dùng; không gọi app là tick realtime |
| Sổ lệnh / độ sâu | `futures().order_book()` | Chưa dùng; không tạo bid/ask giả |

[Tài liệu thị trường hiện hành](https://vnstocks.com/docs/vnstock/thi-truong-market) mô tả OHLCV, quote và trades cho futures; nến trong phiên dùng VCI mặc định ở thế hệ mới, còn nến ngày dùng KBS. [Bảng nguồn](https://vnstocks.com/docs/vnstock/tham-khao/data-sources) cho thấy nguồn và quyền được phân theo domain/phương thức, nên không lấy bảng tính năng cổ phiếu để suy ra tính năng phái sinh.

## Vì sao không chép nguyên ví dụ từ hướng dẫn

[03-market-layer.md do người dùng gửi](https://github.com/vnstock-hq/vnstock-agent-guide/blob/main/docs/vnstock-data/03-market-layer.md) dùng `from vnstock_data import Market`, mô tả futures với KBS và liệt kê cả chức năng mở rộng. Ví dụ `VN30F2503` là mã có tháng cố định; demo tháng gần nhất dùng `VN30F1M` để thư viện xử lý mã thay đổi.

[Schema đi kèm](https://github.com/vnstock-hq/vnstock-agent-guide/blob/main/docs/vnstock-data/schema/02-market.md) cần được đọc cho từng phương thức. Không suy đoán cùng đơn vị cho `quote`, `ohlcv`, `trades`, hay giữa cổ phiếu và phái sinh. Adapter game chỉ nhận `time/open/high/low/close/volume`, kiểm tra OHLC và giá hữu hạn, chuẩn hóa timestamp về epoch dựa trên giờ Việt Nam.

[06-quote-price-api.md](https://github.com/vnstock-hq/vnstock-agent-guide/blob/main/docs/vnstock/advanced-usage/06-quote-price-api.md) vẫn ghi phiên bản 3.4.0 ở cuối trang và có các ví dụ tham số khác tài liệu hiện hành. Demo khóa một phiên bản cụ thể và đã đối chiếu chữ ký hàm trong source: `length=500` được `FuturesMarket.ohlcv` chuyển thành `count_back=500`. Không dùng giả định “500 ngày” cho 500 nến phút.

## Lỗi khoảng lùi được tái hiện trong source 4.0.9

Ngày 14/10/2026, chạy riêng hàm `get_start_date_from_lookback` từ checkout source công khai 4.0.9 cho kết quả:

```text
bars=500, interval='1m', end_date='2026-10-14' -> start='2024-10-14'
bars=500, interval='1D', end_date='2026-10-14' -> start='2024-10-14'
```

Nguyên nhân: nhánh phút nằm bên trong `elif "M" in interval`, rồi lại kiểm tra `"M" not in interval`. Với `1m`, nhánh không được vào; tỷ lệ mặc định 1,5 ngày/nến bị dùng. [Source hàm tính khoảng lùi](https://github.com/thinh-vu/vnstock/blob/71b853f0db18c0d783c2b9eeafaedbcbf4d05fba/vnstock/core/utils/lookback.py#L163).

Demo đã đổi sang `start/end` rõ ràng trong 14 ngày gần nhất theo giờ Việt Nam, vẫn yêu cầu 500 nến phút và giữ tối đa 500 nến nguồn trả. Cách này bỏ qua nhánh tự ước lượng sai, áp dụng cả VCI và KBS. Khoảng truy vấn sai là lỗi được tái hiện trong source; chưa có log máy người dùng để khẳng định nó là nguyên nhân duy nhất của lỗi tải dữ liệu. API VCI còn có `count_back`, nên khoảng start quá xa không đồng nghĩa chắc chắn mọi truy vấn VCI sẽ thất bại.

Ngoài ra, bản trước bỏ qua kết quả `False` từ `vnai.setup_api_key`. Nay xác thực thất bại được báo rõ; nếu thư viện có `login` của thế hệ 5 thì dùng API đó. Tiến trình fetch đánh dấu bước `import`, `authenticate`, `history`, `serialize`, giúp nhận biết lỗi thay vì gom chung. Không nâng cấp gói tự động lên v5 trong thay đổi này.

## Kiểm chứng còn thiếu

Kho `https://vnstocks.com/api/simple` bị proxy môi trường trả 403. Việc tải source từ GitHub thành công không chứng minh các endpoint dữ liệu VCI/KBS đã truy cập được. Vì vậy unit test dùng fixture riêng, giao diện luyện tập có nhãn mẫu, và không báo đã chạy thật VN30F1M.

Khi chạy trên máy có quyền mạng, cài đủ `requirements.txt`, chạy `python -m tests.live_smoke`, kiểm tra nguồn, mã hợp đồng, thời điểm và số nến rồi chọn Chơi lại. Nếu dùng `vnstock_data`, cài đúng gói/quyền của tài khoản trước, đặt `VNSTOCK_PACKAGE=vnstock_data`, chọn source tương ứng và kiểm thử lại. Không thay đổi hoặc bỏ qua chính sách mạng để ép gọi nguồn.
