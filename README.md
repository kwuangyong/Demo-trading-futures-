# QuanTik Futures Arena

Mini game giao dịch VN30F1M bằng tiền ảo, tham chiếu màu sắc và bố cục terminal của [QuanTik-website](https://github.com/kwuangyong/QuanTik-website). Đây là codebase độc lập, không mang theo lịch sử Git, database, secret, worker/scheduler hay mô hình QUANT của repo gốc.

FastAPI phục vụ cả HTML/CSS/JS và API trên một cổng. Không cần Node, build frontend hay tài khoản broker để chơi. Dữ liệu thật được lấy bởi Python qua vnstock; mở HTML bằng `file://` sẽ không có backend giao dịch/dữ liệu.

## Chạy trên máy

Chuẩn bị Python **3.10 trở lên** và kết nối Internet khi cài dependencies.

- **Windows:** giải nén repo, nháy đúp `start-local.bat`.
- **macOS/Linux:** chạy `bash start-local.sh` trong thư mục repo.

Trình duyệt mở **http://localhost:8080**. Dừng server bằng `Ctrl+C`. Scripts tạo `.venv` riêng trong repo, không sửa môi trường Python dùng chung. Nếu cài vnstock lỗi, giao diện vẫn chạy với chế độ **Luyện tập · dữ liệu mẫu**; hai chế độ dữ liệu thật báo lỗi rõ ràng.

Chạy thủ công:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py --open
```

Windows dùng `.venv\Scripts\python.exe` thay cho `.venv/bin/python`. Nếu chỉ muốn thử game mẫu, cài `requirements-core.txt` rồi chạy `run.py`.

## Cách vào game

1. Chạy script local và mở `http://localhost:8080`, giữ cửa sổ server đang chạy.
2. Nhập tên, chọn **Luyện tập · dữ liệu mẫu** để thử ngay, rồi nhấn **Vào sân**.
3. Để chơi với giá thật, chọn **Chơi lại · dữ liệu thật** sau khi vnstock đã cài và lấy được dữ liệu.
4. Chọn số HĐ; **Long** nếu kỳ vọng tăng, **Short** nếu kỳ vọng giảm. **Đóng toàn bộ** để chốt vị thế.
5. Hết giờ hoặc nhấn **Kết thúc & chốt điểm** để xem bảng xếp hạng.

Nếu chỉ mở `web/index.html` trực tiếp, tài nguyên giao diện dùng đường dẫn tương đối nên vẫn hiển thị; trang sẽ hướng dẫn chạy server vì giao dịch và dữ liệu cần Python. Hãy giải nén cả repo, không chỉ tải riêng file HTML.

## Dữ liệu thật

Adapter mặc định:

```python
from vnstock import Market
df = Market().futures("VN30F1M").ohlcv(
    length=500, interval="1m", source="vci"
)
```

`requirements.txt` khóa `vnstock==4.0.9`; thư viện và các dependency của nó dùng kho chính thức `https://vnstocks.com/api/simple`. Cần cho phép truy cập kho này và các host nguồn giá. Gói nền tảng của game được khóa riêng trong `requirements-core.txt`.

Sao chép `.env.example` thành `.env` nếu cần cấu hình. Khóa vnstock, nếu có, chỉ đặt trong biến `VNSTOCK_API_KEY` ở backend. Không gửi khóa vào frontend hay commit `.env`.

- `VNSTOCK_PACKAGE=vnstock`: gói cộng đồng, mặc định.
- `VNSTOCK_SOURCE=vci`: nến phút, mặc định. Có thể đặt `kbs` nếu gói/nguồn trên máy hỗ trợ nến phút VN30F1M.
- `VNSTOCK_PACKAGE=vnstock_data`: tùy chọn dùng gói tài trợ **đã được cài và cấp quyền trên máy**. Repo không cài tự động gói này. API tương thích Unified UI; vẫn cần kiểm thử thật với phiên bản cụ thể của bạn.

Adapter không đổi sang nguồn khác khi lỗi, không đổi khung phút thành ngày, không sinh giá mẫu thay cho giá thật. Nguồn được giữ trong metadata. Nến thiếu, NaN, giá không hợp lệ hay OHLC sai đều bị từ chối.

Provider chạy trong subprocess có timeout 35 giây; cache chung 60 giây giảm số truy vấn khi nhiều người chơi. Đây là dữ liệu nến theo nguồn, **không cam kết tick realtime**. Giá phái sinh tính bằng **điểm**. VN30F1M là alias tháng gần nhất; vnstock tự xử lý mã KRX. Không tự nối các hợp đồng để backtest qua ngày đáo hạn.

Nghiên cứu API, schema, nguồn dữ liệu và khác biệt phiên bản: [docs/VNSTOCK.md](docs/VNSTOCK.md).

## Luật mini game

| Quy tắc | Giá trị |
| --- | --- |
| Vốn ban đầu | 100.000.000 ₫ |
| Giá trị 1 điểm / 1 HĐ | 100.000 ₫ |
| Trượt giá mỗi chiều | 0,1 điểm bất lợi |
| Phí mỗi HĐ / mỗi chiều | 2.000 ₫ |
| Ký quỹ game | 17% giá trị danh nghĩa |
| Tự đóng vị thế | Tài sản < 80% ký quỹ |
| Điểm | P&L ròng sau phí, đã đóng vị thế |

Long/Short cùng chiều tăng khối lượng; lệnh ngược chiều giảm, đóng hoặc đảo vị thế. Backend giữ toàn bộ sổ lệnh, kiểm tra ký quỹ trước khi khớp và dùng action ID để tránh tính phí hai lần khi gửi lại lệnh.

- **Chơi lại · dữ liệu thật:** dùng tối đa 90 nến gần nhất, hiển thị trước 30 nến rồi mở thêm 1 nến mỗi 3 giây. Đủ 90 nến thì lượt kéo dài 180 giây. Ít nến hơn thì ngắn hơn. API không trả nến tương lai. Đồng hồ thuộc server; tải lại trang không đặt lại thời gian.
- **Theo dõi · nến mới nhất:** lấy nến thật gần nhất, đóng băng lệnh khi dữ liệu quá 120 giây, nguồn lỗi hoặc nguồn chưa có giá. Không có điểm xếp hạng.
- **Luyện tập · dữ liệu mẫu:** người dùng chọn rõ ràng; nến tổng hợp có nhãn riêng, dùng cùng một scenario để dễ chơi nhiều lượt.

Game giản lược thanh khoản, thuế, lệnh LO/stop, thanh toán cuối ngày và quy định ký quỹ broker. Khớp ở close nến đang hiển thị ± trượt giá. Kiểm tra rủi ro tại close từng nến, không mô phỏng đường đi tick bên trong nến.

## Cho nhiều người chơi trên cùng Wi-Fi

Chạy server trên máy chủ:

```bash
.venv/bin/python run.py --host 0.0.0.0 --port 8080
```

Cho phép cổng 8080 trên firewall mạng nội bộ, tìm địa chỉ IP LAN của máy chủ rồi mở `http://<IP-LAN>:8080` trên điện thoại/máy khác cùng mạng. `localhost` chỉ trỏ tới thiết bị đang dùng; nó không phải link chia sẻ tới máy chủ. Chỉ dùng một process/worker.

Mỗi trình duyệt có cookie HttpOnly riêng; mở ẩn danh để tạo người chơi khác trên cùng máy. Một trình duyệt có một lượt đang chạy. Lượt mới sẽ chốt lượt trước. Vị thế, lệnh và điểm lưu tại `data/arena.sqlite`, tồn tại sau khi server khởi động lại. Bảng điểm chỉ so sánh **cùng hash bộ nến**; không gộp các thời điểm thị trường khác nhau.

Lượt hết giờ được đóng và ghi điểm ở request tiếp theo của trình duyệt. Không có scheduler nền chốt ngay lúc người chơi đóng trình duyệt; khi mở lại, backend chạy qua các close nến đã trôi qua rồi chốt kết quả. Bảng điểm của lượt bỏ dở chưa cập nhật cho tới khi lượt được truy cập lại hoặc người chơi bắt đầu lượt khác.

Có các nút đổi giao diện sáng/tối, luật chơi, bảng điểm và xuất nhật ký CSV.

## Repo và hosting

Repo đích độc lập: [kwuangyong/Demo-trading-futures-](https://github.com/kwuangyong/Demo-trading-futures-), nhánh `main`. Lấy source để chạy local:

```bash
git clone https://github.com/kwuangyong/Demo-trading-futures-.git
cd Demo-trading-futures-
```

Chạy local là lựa chọn đã triển khai. Có `render.yaml` nếu sau này muốn host Python trên Render. Chọn persistent disk và `ARENA_DATA_DIR` để giữ bảng điểm; ổ đĩa tạm của dịch vụ có thể mất dữ liệu khi redeploy. Không có deployment Render/Vercel công khai trong lần bàn giao này. Vercel/static hosting một mình không phục vụ backend vnstock và SQLite của app này; hãy dùng local hoặc một Python service.

## Kiểm thử

```bash
.venv/bin/python -m pip install -r tests/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
# Opt-in; cần cài vnstock và có quyền mạng tới nguồn thật:
.venv/bin/python -m tests.live_smoke
```

API docs tại `http://localhost:8080/api/docs`.

Trạng thái kiểm chứng trong môi trường bàn giao: **14 unit/API tests đạt**; Chromium kiểm tra vào game mẫu, Long, Short, đóng vị thế, khôi phục sau reload, chốt điểm, bảng xếp hạng, luật chơi, theme, mobile và thông báo lỗi nguồn thật; không có lỗi JavaScript. Luồng thật chưa được xác minh end-to-end: proxy mạng trả 403 với kho vnstock chính thức. Script live smoke cố ý thất bại nếu không lấy được nến thật.
