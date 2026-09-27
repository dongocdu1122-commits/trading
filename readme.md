# 📈 Hệ thống Kiểm định Chiến lược Giao dịch EMA & OBV Fusion (ACB Stock)

Ứng dụng Web tương tác chuyên sâu xây dựng trên nền tảng **Streamlit**, dùng để kiểm định định lượng (Backtesting), hạch toán vị thế giao dịch (Position Accounting), và đánh giá hiện tượng quá khớp (Overfitting) của chiến lược kết hợp chỉ báo **Đường trung bình hàm mũ (EMA)** và **Chỉ báo Khối lượng Cân bằng (OBV)** trên cổ phiếu **Ngân hàng Á Châu (ACB)**.

---

## 🌟 Tính Năng Nổi Bật của Web App

1. **Khử hoàn toàn Thiên lệch Tương lai (No Look-Ahead Bias):**
   - Tín hiệu Mua/Bán được dịch trễ 1 phiên (`shift(1)`), đảm bảo chỉ sử dụng dữ liệu giá đóng cửa phiên trước để ra quyết định mua/bán trong phiên hiện tại.
2. **Hạch toán Vị thế Chuẩn mực (Strict Position Accounting):**
   - Mô hình vị thế **Long-Only** (Mua hoặc Tiền mặt).
   - Tránh việc giải ngân dồn dập (No Accumulation) khi đang nắm giữ cổ phiếu.
   - Chỉ kích hoạt lệnh Bán khi tài khoản thực sự đang nắm giữ vị thế.
3. **Mô phỏng Quản trị Rủi ro & Chi phí Ma sát Thực tế:**
   - **Phí giao dịch (Fees):** 0.2% mỗi chiều (chuẩn thị trường chứng khoán Việt Nam).
   - **Trượt giá (Slippage):** 0.1% mỗi chiều khi khớp lệnh.
   - **Cắt lỗ tự động (Stop Loss):** Ngưỡng bảo vệ vốn 7% khi thị trường biến động ngược chiều.
4. **Phân chia Tập Dữ liệu Huấn luyện & Kiểm thử (Train / Test Split):**
   - **Tập Train (2014 - 2020):** Gồm 1,743 phiên, phục vụ tối ưu hóa tham số.
   - **Tập Test (2021 - 2023):** Gồm 748 phiên Out-of-Sample "chưa từng thấy", kiểm tra độ bền vững của chiến lược.
5. **Đồ thị Tương tác Đa Tầng (Interactive Plotly Visualizations):**
   - Biểu đồ nến Nhật OHLC kèm chỉ báo EMA và điểm vào/ra lệnh trực quan.
   - Biểu đồ đo độ dốc khối lượng dòng tiền OBV Slope (`OBV.diff(N)`).
   - Biểu đồ trạng thái vị thế (Tiền mặt / Cổ phiếu).
   - Biểu đồ đường cong tích lũy vốn (Equity Curve) và biểu đồ sụt giảm tài sản (Underwater Drawdown Chart).
6. **Đối chiếu Kiểm định Quá khớp (Overfitting Analysis):**
   - Bảng tổng hợp so sánh trực tiếp 3 chiến lược: **EMA riêng lẻ**, **OBV riêng lẻ**, và **EMA + OBV kết hợp** trên cả 2 giai đoạn Train và Test.
7. **Công cụ Quét Lưới Tham số Tối ưu (Grid Search & Heatmap):**
   - Tự động quét dải tham số EMA và chu kỳ độ dốc OBV, trực quan hóa bằng Bản đồ nhiệt 2D (Heatmap) với ràng buộc tối thiểu 5 lệnh đóng để tránh tín hiệu ảo.
8. **Sổ Lệnh Chi Tiết (Trade Log):**
   - Thống kê chi tiết từng lệnh (Ngày vào, Giá vào, Ngày thoát, Giá thoát, Lãi/Lỗ %, Số ngày nắm giữ, Lý do thoát).
   - Cho phép xuất dữ liệu ra file `.csv` ngay trên giao diện web.

---

## 📁 Cấu Trúc Thư Mục

```plaintext
Tao app trading/
│
├── ACB.csv                                  # Tệp dữ liệu lịch sử giá và khối lượng cổ phiếu ACB (2014 - 2023)
├── ACB_Strategy_EMA_OBV_Nhom3_Adjusted.ipynb # Jupyter Notebook nghiên cứu gốc (tối ưu hóa Hyperopt)
├── app.py                                   # Mã nguồn chính của ứng dụng Streamlit Web App
├── requirements.txt                         # Danh sách các thư viện Python cần thiết để triển khai
└── readme.md                                # Tài liệu hướng dẫn sử dụng và triển khai dự án
```

---

## 🛠️ Hướng Dẫn Cài Đặt & Chạy Cục Bộ (Local Machine)

### Bước 1: Yêu cầu môi trường
Đảm bảo máy tính đã cài đặt Python phiên bản 3.9 trở lên (Khuyến nghị 3.10 hoặc 3.11).

### Bước 2: Cài đặt các thư viện cần thiết
Mở Terminal (hoặc PowerShell / Command Prompt) tại thư mục dự án và chạy lệnh:

```bash
pip install -r requirements.txt
```

### Bước 3: Khởi chạy ứng dụng Web
Chạy lệnh sau để khởi động Streamlit:

```bash
streamlit run app.py
```

Sau khi chạy lệnh, trình duyệt web sẽ tự động mở trang web tại địa chỉ: `http://localhost:8501`.

---

## 🚀 Hướng Dẫn Đẩy Lên GitHub & Triển Khai Miễn Phí Trên Streamlit Cloud

Để đưa ứng dụng lên mạng internet cho mọi người cùng truy cập, bạn có thể triển khai miễn phí 100% qua **Streamlit Community Cloud** theo các bước sau:

### Bước 1: Đẩy mã nguồn lên kho lưu trữ GitHub (GitHub Repository)
1. Truy cập [GitHub](https://github.com/) và tạo một Repository mới (ví dụ đặt tên: `acb-trading-strategy`).
2. Mở Terminal / PowerShell tại thư mục dự án trên máy tính của bạn và chạy các lệnh sau:

```bash
# Khởi tạo git
git init

# Thêm tất cả các file vào git
git add app.py requirements.txt readme.md ACB.csv

# Lưu commit
git commit -m "Khoi tao web app kiem dinh chien luoc EMA va OBV tren Streamlit"

# Đổi nhánh sang main
git branch -M main

# Liên kết với repository GitHub của bạn (thay URL bằng repo của bạn)
git remote add origin https://github.com/<TEN_GITHUB_CUA_BAN>/acb-trading-strategy.git

# Đẩy code lên GitHub
git push -u origin main
```

### Bước 2: Triển khai trên Streamlit Community Cloud
1. Truy cập vào trang quản lý: [share.streamlit.io](https://share.streamlit.io/) và đăng nhập bằng tài khoản GitHub của bạn.
2. Nhấn vào nút **"New app"** (hoặc **"Create app"**).
3. Điền thông tin kết nối:
   - **Repository:** Chọn repository vừa tạo (ví dụ: `<TEN_GITHUB_CUA_BAN>/acb-trading-strategy`).
   - **Branch:** Chọn `main`.
   - **Main file path:** Nhập `app.py`.
4. Nhấn **"Deploy!"**.
5. Đợi khoảng 1-2 phút để hệ thống tự động cài đặt các thư viện từ `requirements.txt`. Sau khi hoàn tất, bạn sẽ nhận được một đường link web công khai (ví dụ: `https://acb-trading-strategy.streamlit.app`) có thể chia sẻ cho giảng viên và bạn bè xem trực tiếp trên mọi thiết bị!

---

## 📊 Tóm Tắt Kết Quả Kiểm Định Từ Notebook

Dưới đây là kết quả kiểm định chuẩn được trích xuất từ mô hình tối ưu hóa trong Notebook:

| Chiến Lược | Tập Dữ Liệu | Tham Số Tối Ưu | Tỷ Số Sharpe | Tổng Lợi Nhuận (%) | Max Drawdown (%) | Số Giao Dịch Đã Đóng |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **EMA Riêng Lẻ** | Train (2014-2020) | `EMA = 36` | **1.0797** | **+211.97%** | -28.69% | 70 |
| **EMA Riêng Lẻ** | Test (2021-2023) | `EMA = 36` | -0.8601 | -37.69% | -59.19% | 41 |
| **OBV Riêng Lẻ** | Train (2014-2020) | `OBV_Slope = 19` | **1.1735** | **+277.80%** | -30.46% | 51 |
| **OBV Riêng Lẻ** | Test (2021-2023) | `OBV_Slope = 19` | -0.6135 | -38.73% | -62.50% | 38 |
| **EMA + OBV Kết Hợp** | Train (2014-2020) | `EMA = 36, OBV = 20` | **1.1514** | **+236.56%** | **-23.87%** | 64 |
| **EMA + OBV Kết Hợp** | Test (2021-2023) | `EMA = 36, OBV = 20` | -0.8298 | **-36.47%** | -60.14% | 37 |

### 💡 Nhận Xét Chuyên Môn & Bài Học Thực Chiến:
1. **Giá trị của việc tích hợp OBV:** Khi kết hợp độ dốc khối lượng dòng tiền OBV cùng đường EMA, mức sụt giảm tài sản tối đa (**Max Drawdown**) trong giai đoạn Train giảm từ **-28.69%** xuống chỉ còn **-23.87%**, đồng thời trên giai đoạn Test cũng giảm bớt mức lỗ so với chỉ dùng OBV đơn lẻ. Khối lượng đóng vai trò như một màng lọc xác nhận lực cầu thực tế.
2. **Cảnh báo về Hiện tượng Quá khớp (Overfitting):** Lợi nhuận rất cao trên tập Train (trên 200%) nhưng lại sụt giảm mạnh trên tập Test phản ánh sự chuyển đổi trạng thái thị trường (**Regime Shift**): Giai đoạn 2014-2020 là xu thế đi lên bền vững của cổ phiếu ngân hàng, trong khi giai đoạn 2022 là đợt suy thoái mạnh (Bear Market) của toàn thị trường chứng khoán Việt Nam.
3. **Giải pháp nâng cao:** Để triển khai giao dịch tiền thật, nhà đầu tư nên bổ sung thêm bộ lọc xu hướng vĩ mô (chẳng hạn như đường SMA 200 ngày) và áp dụng phương pháp tái tối ưu hóa định kỳ (Walk-Forward Analysis).

---

## 📜 Giấy Phép (License)
Dự án được phát triển phục vụ mục đích nghiên cứu học thuật và kiểm định chiến lược định lượng. Mã nguồn mở tự do theo giấy phép MIT.
