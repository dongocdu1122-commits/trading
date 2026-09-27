"""
=============================================================================
WEB APPLICATION: KIỂM ĐỊNH CHIẾN LƯỢC GIAO DỊCH KẾT HỢP EMA VÀ OBV (ACB STOCK)
Nền tảng: Streamlit
Tác giả: Chuyên gia Định lượng & Phát triển Web App
=============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os

# -----------------------------------------------------------------------------
# 1. CẤU HÌNH TRANG WEB & GIAO DIỆN
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Hệ thống Kiểm định Chiến lược EMA + OBV | ACB Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho giao diện hiện đại, chuyên nghiệp
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F172A;
        margin: 0.3rem 0;
    }
    .metric-sub {
        font-size: 0.8rem;
    }
    .positive { color: #16A34A; }
    .negative { color: #DC2626; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 6px 6px 0 0;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. HÀM TÍNH TOÁN CHỈ BÁO KỸ THUẬT (INDICATORS)
# -----------------------------------------------------------------------------
def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Tính Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Tính On-Balance Volume (OBV)."""
    price_diff = close.diff()
    direction = np.where(price_diff > 0, 1, np.where(price_diff < 0, -1, 0))
    direction[0] = 0
    obv = (pd.Series(direction, index=close.index) * volume).cumsum()
    return obv

def calculate_obv_slope(obv: pd.Series, period: int) -> pd.Series:
    """Tính độ dốc OBV qua N phiên: OBV(t) - OBV(t-N)."""
    return obv.diff(period)


# -----------------------------------------------------------------------------
# 3. HÀM TẠO TÍN HIỆU GIAO DỊCH (SIGNAL GENERATION - KHÔNG LOOK-AHEAD BIAS)
# -----------------------------------------------------------------------------
def get_ema_signals(data: pd.DataFrame, ema_period: int):
    """Chiến lược 1: EMA Riêng lẻ."""
    close = data['Close']
    ema = calculate_ema(close, int(ema_period))
    raw_entries = (close > ema)
    raw_exits = (close < ema)
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, ema

def get_obv_signals(data: pd.DataFrame, obv_slope_period: int = 3):
    """Chiến lược 2: OBV Riêng lẻ."""
    close = data['Close']
    volume = data['Volume']
    obv = calculate_obv(close, volume)
    obv_slope = calculate_obv_slope(obv, int(obv_slope_period))
    raw_entries = (obv_slope > 0)
    raw_exits = (obv_slope < 0)
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, obv, obv_slope

def get_combined_signals(data: pd.DataFrame, ema_period: int, obv_slope_period: int = 3):
    """Chiến lược 3: Kết hợp EMA + OBV Slope."""
    close = data['Close']
    volume = data['Volume']
    ema = calculate_ema(close, int(ema_period))
    obv = calculate_obv(close, volume)
    obv_slope = calculate_obv_slope(obv, int(obv_slope_period))
    
    # Mua: Giá vượt trên EMA VÀ Độ dốc OBV dương
    raw_entries = (close > ema) & (obv_slope > 0)
    # Bán: Giá đóng cửa giảm xuống dưới EMA
    raw_exits = (close < ema)
    
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, ema, obv, obv_slope


# -----------------------------------------------------------------------------
# 4. ĐỘNG CƠ KIỂM ĐỊNH HIỆU SUẤT & QUẢN LÝ VỊ THẾ (BACKTEST ENGINE)
# -----------------------------------------------------------------------------
def run_backtest_simulation(
    data: pd.DataFrame,
    entries: pd.Series,
    exits: pd.Series,
    initial_capital: float = 100_000_000.0,
    fee_rate: float = 0.002,      # Phí 0.2%
    slippage_rate: float = 0.001, # Trượt giá 0.1%
    stop_loss_pct: float = 0.07   # Cắt lỗ 7%
):
    """
    Mô phỏng giao dịch vị thế Long-Only chính xác:
    - Quản lý vị thế: Không mở lệnh lặp lại khi đang nắm giữ (Accumulate=False).
    - Hạch toán chi phí trượt giá và phí giao dịch cả hai chiều mua/bán.
    - Cơ chế Stop Loss bảo vệ vốn (Cắt lỗ khi giá giảm >= 7% so với giá vào).
    """
    n = len(data)
    close_prices = data['Close'].values
    dates = data.index

    # Mảng theo dõi
    positions = np.zeros(n, dtype=int)       # 0: Tiền mặt, 1: Nắm giữ cổ phiếu
    cash = np.zeros(n, dtype=float)
    shares = np.zeros(n, dtype=float)
    portfolio_value = np.zeros(n, dtype=float)
    
    buy_signals = np.zeros(n, dtype=bool)
    sell_signals = np.zeros(n, dtype=bool)
    stop_loss_signals = np.zeros(n, dtype=bool)

    current_cash = initial_capital
    current_shares = 0.0
    current_position = 0
    entry_price = 0.0
    entry_idx = 0

    trades_list = []

    for i in range(n):
        curr_price = close_prices[i]
        curr_date = dates[i]
        is_entry = bool(entries.iloc[i])
        is_exit = bool(exits.iloc[i])

        # 1. Nếu đang nắm giữ vị thế (Position = 1) -> Kiểm tra thoát lệnh
        if current_position == 1:
            # Kiểm tra điều kiện Cắt lỗ Stop Loss (7%)
            pct_change = (curr_price - entry_price) / entry_price
            hit_stop_loss = (stop_loss_pct > 0) and (pct_change <= -stop_loss_pct)

            if hit_stop_loss or is_exit:
                # Thực hiện Bán
                if hit_stop_loss:
                    stop_loss_signals[i] = True
                    reason = "Cắt lỗ (Stop Loss 7%)"
                    exec_price = entry_price * (1.0 - stop_loss_pct) * (1.0 - slippage_rate)
                else:
                    sell_signals[i] = True
                    reason = "Tín hiệu Bán (Exit Signal)"
                    exec_price = curr_price * (1.0 - slippage_rate)

                gross_proceeds = current_shares * exec_price
                fee = gross_proceeds * fee_rate
                net_proceeds = gross_proceeds - fee
                current_cash += net_proceeds

                # Ghi nhận sổ lệnh
                trade_return = (exec_price / entry_price - 1.0) - (2 * fee_rate + 2 * slippage_rate)
                pnl_vnd = net_proceeds - (current_shares * entry_price * (1.0 + slippage_rate + fee_rate))
                holding_days = (curr_date - dates[entry_idx]).days

                trades_list.append({
                    'Lệnh #': len(trades_list) + 1,
                    'Ngày Mua': dates[entry_idx].strftime('%Y-%m-%d'),
                    'Giá Mua': round(entry_price, 2),
                    'Ngày Bán': curr_date.strftime('%Y-%m-%d'),
                    'Giá Bán': round(exec_price, 2),
                    'Lợi nhuận (%)': round(trade_return * 100, 2),
                    'Lãi/Lỗ (VNĐ)': round(pnl_vnd, 0),
                    'Số ngày giữ': holding_days,
                    'Lý do Bán': reason
                })

                current_shares = 0.0
                current_position = 0
                entry_price = 0.0

        # 2. Nếu đang giữ tiền mặt (Position = 0) -> Kiểm tra vào lệnh
        elif current_position == 0:
            if is_entry:
                # Thực hiện Mua
                exec_price = curr_price * (1.0 + slippage_rate)
                cost_per_share = exec_price * (1.0 + fee_rate)
                
                # Mua tối đa số lượng cổ phiếu với vốn hiện có
                available_shares = current_cash / cost_per_share
                if available_shares > 0:
                    current_shares = available_shares
                    total_cost = current_shares * cost_per_share
                    current_cash -= total_cost
                    current_position = 1
                    entry_price = curr_price
                    entry_idx = i
                    buy_signals[i] = True

        # Ghi nhận giá trị tài sản ròng cuối ngày
        positions[i] = current_position
        cash[i] = current_cash
        shares[i] = current_shares
        portfolio_value[i] = current_cash + (current_shares * curr_price)

    # DataFrame tài sản qua các ngày
    equity_df = pd.DataFrame({
        'Portfolio_Value': portfolio_value,
        'Position': positions,
        'Buy_Signal': buy_signals,
        'Sell_Signal': sell_signals,
        'StopLoss_Signal': stop_loss_signals
    }, index=dates)

    # 3. Tính toán các chỉ số đo lường hiệu suất (Performance Metrics)
    equity = equity_df['Portfolio_Value']
    daily_returns = equity.pct_change().fillna(0)
    
    total_return_pct = (equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0
    
    # Sharpe Ratio thường niên (252 ngày giao dịch)
    std_ret = daily_returns.std()
    if std_ret > 0:
        sharpe_ratio = (daily_returns.mean() / std_ret) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    # Max Drawdown
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_drawdown_pct = drawdown.min() * 100.0

    # Thống kê giao dịch
    trades_df = pd.DataFrame(trades_list)
    closed_trades_count = len(trades_df)

    if closed_trades_count > 0:
        win_trades = trades_df[trades_df['Lợi nhuận (%)'] > 0]
        win_rate = (len(win_trades) / closed_trades_count) * 100.0
        
        gross_profits = trades_df.loc[trades_df['Lãi/Lỗ (VNĐ)'] > 0, 'Lãi/Lỗ (VNĐ)'].sum()
        gross_losses = abs(trades_df.loc[trades_df['Lãi/Lỗ (VNĐ)'] < 0, 'Lãi/Lỗ (VNĐ)'].sum())
        profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)
        avg_holding_days = trades_df['Số ngày giữ'].mean()
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_holding_days = 0.0

    position_coverage = (positions.sum() / n) * 100.0

    metrics = {
        'total_return_pct': total_return_pct,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown_pct': max_drawdown_pct,
        'closed_trades': closed_trades_count,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_holding_days': avg_holding_days,
        'position_coverage': position_coverage,
        'final_value': equity.iloc[-1]
    }

    return metrics, equity_df, trades_df, drawdown


# -----------------------------------------------------------------------------
# 5. TẢI DỮ LIỆU ĐẦU VÀO (DATA LOADER)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data(file_path: str = None, uploaded_file = None) -> pd.DataFrame:
    """Tải và chuẩn hóa dữ liệu OHLCV."""
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    elif file_path and os.path.exists(file_path):
        df = pd.read_csv(file_path)
    else:
        return None

    # Tìm và chuẩn hóa cột ngày
    date_col = None
    for col in df.columns:
        if col.lower() in ['date', 'time', 'ngay', 'ngày', '<date>']:
            date_col = col
            break
    
    if date_col:
        df['Date'] = pd.to_datetime(df[date_col])
        df.set_index('Date', inplace=True)
    elif 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
    else:
        df.index = pd.to_datetime(df.index)

    df.sort_index(inplace=True)

    # Chuẩn hóa tên cột
    rename_dict = {}
    for col in df.columns:
        cl = col.strip().lower().replace('<', '').replace('>', '')
        if cl == 'close': rename_dict[col] = 'Close'
        elif cl == 'open': rename_dict[col] = 'Open'
        elif cl == 'high': rename_dict[col] = 'High'
        elif cl == 'low': rename_dict[col] = 'Low'
        elif cl in ['volume', 'vol']: rename_dict[col] = 'Volume'
    
    df.rename(columns=rename_dict, inplace=True)

    if 'Close' not in df.columns:
        raise ValueError("Không tìm thấy cột giá đóng cửa 'Close' trong tệp dữ liệu!")
    if 'Volume' not in df.columns:
        df['Volume'] = 1_000_000  # Giả định nếu thiếu

    return df


# -----------------------------------------------------------------------------
# 6. SIDEBAR - ĐIỀU KHIỂN & CẤU HÌNH THAM SỐ
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/bullish.png", width=64)
    st.title("⚙️ Thiết lập Hệ thống")

    st.subheader("1. Nguồn dữ liệu")
    data_source_mode = st.radio(
        "Chọn dữ liệu:",
        ["Mặc định (ACB.csv)", "Tải lên tệp CSV riêng"],
        index=0
    )

    df_raw = None
    if data_source_mode == "Mặc định (ACB.csv)":
        default_file = "ACB.csv"
        if os.path.exists(default_file):
            df_raw = load_data(file_path=default_file)
            st.success("✅ Đã kết nối ACB.csv")
        else:
            st.warning("⚠️ Không tìm thấy tệp ACB.csv cục bộ. Vui lòng tải file lên.")
    else:
        uploaded_file = st.file_uploader("Tải lên file CSV:", type=['csv'])
        if uploaded_file:
            df_raw = load_data(uploaded_file=uploaded_file)
            st.success("✅ Đã tải file thành công!")

    if df_raw is None:
        st.stop()

    min_date = df_raw.index.min().date()
    max_date = df_raw.index.max().date()

    st.divider()
    st.subheader("2. Phân chia Tập Dữ liệu")
    split_preset = st.selectbox(
        "Khung thời gian kiểm định:",
        [
            "Theo Notebook (Train: 2014-2020 | Test: 2021-2023)",
            "Chỉ kiểm định Train (2014 - 2020)",
            "Chỉ kiểm định Test (2021 - 2023)",
            "Toàn bộ dữ liệu (2014 - 2023)",
            "Tùy chỉnh khoảng thời gian"
        ],
        index=0
    )

    if split_preset == "Theo Notebook (Train: 2014-2020 | Test: 2021-2023)":
        start_date = min_date
        end_date = max_date
        current_data = df_raw.copy()
        eval_phase_name = "Toàn bộ chuỗi (Có phân đoạn Train / Test)"
    elif split_preset == "Chỉ kiểm định Train (2014 - 2020)":
        current_data = df_raw.loc['2014':'2020'].copy()
        start_date = current_data.index.min().date()
        end_date = current_data.index.max().date()
        eval_phase_name = "Tập Huấn luyện (Train: 2014-2020)"
    elif split_preset == "Chỉ kiểm định Test (2021 - 2023)":
        current_data = df_raw.loc['2021':'2023'].copy()
        start_date = current_data.index.min().date()
        end_date = current_data.index.max().date()
        eval_phase_name = "Tập Kiểm thử Độc lập (Test: 2021-2023)"
    elif split_preset == "Toàn bộ dữ liệu (2014 - 2023)":
        current_data = df_raw.copy()
        start_date = min_date
        end_date = max_date
        eval_phase_name = "Toàn bộ lịch sử (Full: 2014-2023)"
    else:
        date_range = st.date_input(
            "Chọn khoảng ngày kiểm định:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            current_data = df_raw.loc[str(start_date):str(end_date)].copy()
            eval_phase_name = f"Tùy chỉnh ({start_date} -> {end_date})"
        else:
            current_data = df_raw.copy()
            eval_phase_name = "Tùy chỉnh"

    st.divider()
    st.subheader("3. Tham số Chiến lược")
    param_preset = st.radio(
        "Bộ tham số mẫu từ Notebook:",
        ["Mặc định (EMA=20, OBV=3)", "Tối ưu hóa Train (EMA=36, OBV=20)", "Tự điều chỉnh thủ công"],
        index=1
    )

    if param_preset == "Mặc định (EMA=20, OBV=3)":
        init_ema = 20
        init_obv = 3
    elif param_preset == "Tối ưu hóa Train (EMA=36, OBV=20)":
        init_ema = 36
        init_obv = 20
    else:
        init_ema = 36
        init_obv = 20

    ema_param = st.slider("Chu kỳ EMA (EMA Period):", min_value=5, max_value=100, value=init_ema, step=1)
    obv_slope_param = st.slider("Độ dốc OBV qua N phiên (OBV Slope):", min_value=2, max_value=40, value=init_obv, step=1)

    st.divider()
    st.subheader("4. Quản lý Rủi ro & Chi phí")
    initial_cap = st.number_input("Vốn ban đầu (VNĐ):", min_value=1_000_000, value=100_000_000, step=10_000_000)
    stop_loss_pct = st.slider("Mức Cắt lỗ Stop Loss (%):", min_value=0.0, max_value=15.0, value=7.0, step=0.5) / 100.0
    fee_pct = st.number_input("Phí giao dịch mỗi chiều (%):", min_value=0.0, max_value=1.0, value=0.2, step=0.05) / 100.0
    slippage_pct = st.number_input("Trượt giá ước tính (%):", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0


# -----------------------------------------------------------------------------
# 7. KHỞI CHẠY TÍNH TOÁN DỮ LIỆU & CHIẾN LƯỢC
# -----------------------------------------------------------------------------
# Tạo tín hiệu cho tập đang chọn
ent_ema, ext_ema, line_ema = get_ema_signals(current_data, ema_param)
ent_obv, ext_obv, line_obv, line_obv_slope = get_obv_signals(current_data, obv_slope_param)
ent_comb, ext_comb, line_c_ema, line_c_obv, line_c_obv_slope = get_combined_signals(current_data, ema_param, obv_slope_param)

# Chạy mô phỏng 3 chiến lược
m_ema, eq_ema, tr_ema, dd_ema = run_backtest_simulation(current_data, ent_ema, ext_ema, initial_cap, fee_pct, slippage_pct, stop_loss_pct)
m_obv, eq_obv, tr_obv, dd_obv = run_backtest_simulation(current_data, ent_obv, ext_obv, initial_cap, fee_pct, slippage_pct, stop_loss_pct)
m_comb, eq_comb, tr_comb, dd_comb = run_backtest_simulation(current_data, ent_comb, ext_comb, initial_cap, fee_pct, slippage_pct, stop_loss_pct)

# Benchmark Buy & Hold
bh_return_pct = (current_data['Close'].iloc[-1] / current_data['Close'].iloc[0] - 1.0) * 100.0
bh_equity = initial_cap * (current_data['Close'] / current_data['Close'].iloc[0])
bh_daily_ret = bh_equity.pct_change().fillna(0)
bh_sharpe = (bh_daily_ret.mean() / bh_daily_ret.std()) * np.sqrt(252) if bh_daily_ret.std() > 0 else 0.0
bh_max_dd = ((bh_equity - bh_equity.cummax()) / bh_equity.cummax()).min() * 100.0


# -----------------------------------------------------------------------------
# 8. HEADER CHÍNH CỦA TRANG WEB
# -----------------------------------------------------------------------------
st.markdown('<div class="main-header">📈 Hệ thống Kiểm định Chiến lược EMA & OBV Fusion</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Phân tích định lượng, kiểm định Overfitting và hạch toán vị thế cho Cổ phiếu <b>ACB</b> | Giai đoạn: <b>{eval_phase_name}</b></div>',
    unsafe_allow_html=True
)

# 4 Metric tóm tắt nhanh trên đỉnh trang
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Tổng Lợi Nhuận (EMA + OBV)</div>
        <div class="metric-value {'positive' if m_comb['total_return_pct'] >= 0 else 'negative'}">{m_comb['total_return_pct']:+.2f}%</div>
        <div class="metric-sub">Thị trường B&H: {bh_return_pct:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Sharpe Ratio (Thường niên)</div>
        <div class="metric-value {'positive' if m_comb['sharpe_ratio'] >= 1.0 else ('negative' if m_comb['sharpe_ratio'] < 0 else '')}">{m_comb['sharpe_ratio']:.2f}</div>
        <div class="metric-sub">Thị trường B&H: {bh_sharpe:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Max Drawdown (Sụt giảm tối đa)</div>
        <div class="metric-value negative">{m_comb['max_drawdown_pct']:.2f}%</div>
        <div class="metric-sub">Thị trường B&H: {bh_max_dd:.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Số Lệnh Đóng / Win Rate</div>
        <div class="metric-value">{m_comb['closed_trades']} <span style="font-size:1.1rem; color:#64748B;">lệnh</span></div>
        <div class="metric-sub">Tỷ lệ thắng: <b>{m_comb['win_rate']:.1f}%</b> | Profit Factor: <b>{m_comb['profit_factor']:.2f}</b></div>
    </div>
    """, unsafe_allow_html=True)

st.write("")


# -----------------------------------------------------------------------------
# 9. CÁC TABS NỘI DUNG CHÍNH CỦA ỨNG DỤNG
# -----------------------------------------------------------------------------
tab_overview, tab_signals, tab_backtest, tab_comparison, tab_optimization = st.tabs([
    "📊 1. Khám phá Dữ liệu",
    "🎯 2. Tín hiệu & Vị thế",
    "🚀 3. Hiệu suất & Sổ lệnh",
    "⚖️ 4. Kiểm định Train vs Test",
    "🔍 5. Quét & Tối ưu Tham số"
])


# =============================================================================
# TAB 1: KHÁM PHÁ DỮ LIỆU (EXPLORATORY DATA ANALYSIS)
# =============================================================================
with tab_overview:
    st.subheader("📌 Tổng quan Chuỗi Thời gian & Phân chia Dữ liệu")
    
    st.markdown("""
    Theo thiết kế phương pháp luận nghiên cứu từ giảng viên:
    - **Tập Huấn luyện (Train 2014 - 2020)**: Gồm 1,743 phiên giao dịch, dùng để tối ưu hóa tham số tín hiệu.
    - **Tập Kiểm định Độc lập (Test 2021 - 2023)**: Gồm 748 phiên giao dịch "chưa từng thấy", kiểm tra khả năng sống sót của chiến lược trong thực tế.
    """)

    # Biểu đồ giá ACB với vùng màu Train / Test
    fig_eda = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=("Biểu đồ Nến & Khung Phân chia Dữ liệu (Train: 2014-2020 | Test: 2021-2023)", "Khối lượng Giao dịch (Volume)"),
        row_heights=[0.75, 0.25]
    )

    fig_eda.add_trace(
        go.Candlestick(
            x=df_raw.index,
            open=df_raw['Open'],
            high=df_raw['High'],
            low=df_raw['Low'],
            close=df_raw['Close'],
            name="ACB OHLC",
            increasing_line_color='#10B981',
            decreasing_line_color='#EF4444'
        ),
        row=1, col=1
    )

    # Thêm đường EMA 200 làm chuẩn xu hướng dài hạn
    ema200 = calculate_ema(df_raw['Close'], 200)
    fig_eda.add_trace(
        go.Scatter(x=df_raw.index, y=ema200, name="EMA 200 (Xu hướng dài hạn)", line=dict(color='#F59E0B', width=1.5)),
        row=1, col=1
    )

    # Tô màu phân chia Train và Test
    fig_eda.add_vrect(
        x0="2014-01-01", x1="2020-12-31",
        fillcolor="#3B82F6", opacity=0.08,
        annotation_text="VÙNG TRAIN (2014 - 2020)<br>1,743 phiên",
        annotation_position="top left",
        row=1, col=1
    )

    fig_eda.add_vrect(
        x0="2021-01-01", x1="2023-12-31",
        fillcolor="#EF4444", opacity=0.08,
        annotation_text="VÙNG TEST (2021 - 2023)<br>748 phiên",
        annotation_position="top left",
        row=1, col=1
    )

    # Volume bar
    vol_colors = ['#10B981' if c >= o else '#EF4444' for c, o in zip(df_raw['Close'], df_raw['Open'])]
    fig_eda.add_trace(
        go.Bar(x=df_raw.index, y=df_raw['Volume'], name="Khối lượng", marker_color=vol_colors, opacity=0.7),
        row=2, col=1
    )

    fig_eda.update_layout(
        height=550,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig_eda, use_container_width=True)

    # Bảng xem trước dữ liệu 5 phiên đầu và cuối
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**5 Phiên đầu tiên:**")
        st.dataframe(df_raw.head(5).style.format('{:.1f}'), use_container_width=True)
    with c2:
        st.markdown("**5 Phiên gần nhất:**")
        st.dataframe(df_raw.tail(5).style.format('{:.1f}'), use_container_width=True)


# =============================================================================
# TAB 2: TÍN HIỆU & VỊ THẾ (SIGNALS & POSITIONS)
# =============================================================================
with tab_signals:
    st.subheader("🎯 Cơ chế Tín hiệu & Quản trị Vị thế Tránh Look-Ahead Bias")

    st.markdown("""
    > [!IMPORTANT]
    > **Nguyên tắc cốt lõi đã được hiệu chỉnh:**
    > 1. **Khử thiên lệch dự đoán tương lai (Look-ahead bias):** Tín hiệu Mua/Bán được dịch trễ 1 phiên (`shift(1)`), đảm bảo chỉ dùng dữ liệu đóng cửa phiên trước để ra quyết định mua/bán tại giá phiên sau.
    > 2. **Hạch toán vị thế (Position Accounting):** Không phát lệnh mua dồn dập khi đã full cổ phiếu. Khi đang cầm hàng thì chỉ lắng nghe lệnh Bán hoặc Cắt lỗ.
    """)

    strat_choice = st.radio(
        "Chọn chiến lược để hiển thị trực quan tín hiệu:",
        ["1. EMA Riêng lẻ", "2. OBV Riêng lẻ", "3. Kết hợp EMA + OBV Slope"],
        index=2,
        horizontal=True
    )

    if strat_choice.startswith("1"):
        active_eq = eq_ema
        active_line = line_ema
        line_label = f"EMA ({ema_param})"
        active_sub_title = "Đường EMA"
    elif strat_choice.startswith("2"):
        active_eq = eq_obv
        active_line = line_obv_slope
        line_label = f"Độ dốc OBV ({obv_slope_param} phiên)"
        active_sub_title = "Độ dốc OBV Slope"
    else:
        active_eq = eq_comb
        active_line = line_c_ema
        line_label = f"EMA ({ema_param})"
        active_sub_title = "Chỉ báo EMA & OBV Slope"

    # Trích xuất các điểm mua và bán
    buy_dates = active_eq[active_eq['Buy_Signal']].index
    buy_prices = current_data.loc[buy_dates, 'Close']

    sell_dates = active_eq[active_eq['Sell_Signal']].index
    sell_prices = current_data.loc[sell_dates, 'Close']

    sl_dates = active_eq[active_eq['StopLoss_Signal']].index
    sl_prices = current_data.loc[sl_dates, 'Close']

    # Vẽ biểu đồ tín hiệu
    fig_sig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(
            f"Giá Cổ phiếu ACB, {line_label} & Các Điểm Vào/Thoát lệnh",
            "Độ dốc OBV Slope (OBV.diff)",
            "Trạng thái Vị thế (1: Đang giữ Cổ phiếu | 0: Tiền mặt)"
        ),
        row_heights=[0.55, 0.25, 0.20]
    )

    # 1. Nến & Tín hiệu
    fig_sig.add_trace(
        go.Scatter(x=current_data.index, y=current_data['Close'], name="Giá ACB (Close)", line=dict(color="#2563EB", width=1.5)),
        row=1, col=1
    )
    fig_sig.add_trace(
        go.Scatter(x=current_data.index, y=line_c_ema, name=f"EMA ({ema_param})", line=dict(color="#F59E0B", width=1.5)),
        row=1, col=1
    )

    # Điểm MUA (Mũi tên Xanh tam giác hướng lên)
    fig_sig.add_trace(
        go.Scatter(
            x=buy_dates, y=buy_prices * 0.98,
            mode='markers',
            marker=dict(symbol='triangle-up', size=11, color='#10B981', line=dict(width=1, color='#047857')),
            name="Lệnh MUA (Entry)"
        ),
        row=1, col=1
    )

    # Điểm BÁN thường (Mũi tên Đỏ tam giác hướng xuống)
    fig_sig.add_trace(
        go.Scatter(
            x=sell_dates, y=sell_prices * 1.02,
            mode='markers',
            marker=dict(symbol='triangle-down', size=11, color='#EF4444', line=dict(width=1, color='#B91C1C')),
            name="Lệnh BÁN (Exit)"
        ),
        row=1, col=1
    )

    # Điểm CẮT LỖ (Hình chữ X màu tím)
    if len(sl_dates) > 0:
        fig_sig.add_trace(
            go.Scatter(
                x=sl_dates, y=sl_prices * 1.02,
                mode='markers',
                marker=dict(symbol='x', size=10, color='#8B5CF6', line=dict(width=2)),
                name="Lệnh CẮT LỖ (Stop Loss 7%)"
            ),
            row=1, col=1
        )

    # 2. OBV Slope
    slope_colors = ['#10B981' if s > 0 else '#EF4444' for s in line_c_obv_slope]
    fig_sig.add_trace(
        go.Bar(x=current_data.index, y=line_c_obv_slope, name="OBV Slope", marker_color=slope_colors),
        row=2, col=1
    )
    fig_sig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # 3. Trạng thái vị thế (0 hoặc 1)
    fig_sig.add_trace(
        go.Scatter(
            x=active_eq.index, y=active_eq['Position'],
            name="Trạng thái Vị thế",
            fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.2)',
            line=dict(color="#3B82F6", width=1.5, shape='hv')
        ),
        row=3, col=1
    )

    fig_sig.update_layout(
        height=680,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        xaxis3_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig_sig, use_container_width=True)

    # Thống kê số lượng lệnh phát sinh
    st.markdown(f"**Bảng Thống kê Tín hiệu Giao dịch Thực tế:**")
    cs1, cs2, cs3, cs4 = st.columns(4)
    cs1.metric("Tổng số lệnh MUA", f"{active_eq['Buy_Signal'].sum()} lệnh")
    cs2.metric("Số lệnh BÁN thông thường", f"{active_eq['Sell_Signal'].sum()} lệnh")
    cs3.metric("Số lần chạm Cắt lỗ (SL 7%)", f"{active_eq['StopLoss_Signal'].sum()} lần")
    cs4.metric("Tỷ lệ thời gian có vị thế", f"{(active_eq['Position'].sum()/len(active_eq))*100:.1f}%")


# =============================================================================
# TAB 3: HIỆU SUẤT & SỔ LỆNH (BACKTEST PERFORMANCE & TRADE LOG)
# =============================================================================
with tab_backtest:
    st.subheader(f"🚀 Đường cong Vốn (Equity Curve) & Hiệu suất Chiến lược")

    # So sánh đường vốn của 3 chiến lược và Buy & Hold
    fig_eq = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=("Tăng trưởng Giá trị Danh mục (Khởi điểm: 100 Triệu VNĐ)", "Mức độ Sụt giảm Tài sản (Underwater Drawdown %)"),
        row_heights=[0.70, 0.30]
    )

    # Đường vốn
    fig_eq.add_trace(
        go.Scatter(x=eq_comb.index, y=eq_comb['Portfolio_Value'], name=f"EMA ({ema_param}) + OBV ({obv_slope_param})", line=dict(color="#2563EB", width=2.5)),
        row=1, col=1
    )
    fig_eq.add_trace(
        go.Scatter(x=eq_ema.index, y=eq_ema['Portfolio_Value'], name=f"EMA ({ema_param}) Riêng lẻ", line=dict(color="#F59E0B", width=1.5, dash="dot")),
        row=1, col=1
    )
    fig_eq.add_trace(
        go.Scatter(x=eq_obv.index, y=eq_obv['Portfolio_Value'], name=f"OBV ({obv_slope_param}) Riêng lẻ", line=dict(color="#8B5CF6", width=1.5, dash="dash")),
        row=1, col=1
    )
    fig_eq.add_trace(
        go.Scatter(x=current_data.index, y=bh_equity, name="Thị trường (Buy & Hold ACB)", line=dict(color="#6B7280", width=1.5, dash="dashdot")),
        row=1, col=1
    )

    # Drawdown
    fig_eq.add_trace(
        go.Scatter(x=dd_comb.index, y=dd_comb * 100, name="Drawdown EMA+OBV", fill='tozeroy', fillcolor='rgba(239, 68, 68, 0.25)', line=dict(color="#EF4444", width=1)),
        row=2, col=1
    )

    fig_eq.update_layout(
        height=600,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        xaxis2_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig_eq, use_container_width=True)

    # Bảng số liệu chi tiết
    st.markdown("### 📋 Bảng So sánh Chỉ số Định lượng Chi tiết:")
    metrics_summary = pd.DataFrame({
        'Chỉ số Đánh giá': [
            'Tổng Lợi nhuận (%)',
            'Lợi nhuận Tuyệt đối (VNĐ)',
            'Tỷ số Sharpe (Annualized)',
            'Max Drawdown (%)',
            'Số Lệnh Đã đóng',
            'Tỷ lệ Thắng - Win Rate (%)',
            'Hệ số Lãi/Lỗ (Profit Factor)',
            'Thời gian Giữ vị thế TB (Phiên)',
            'Tỷ lệ Tham gia Thị trường (%)'
        ],
        'Chiến lược EMA + OBV': [
            f"{m_comb['total_return_pct']:+.2f}%",
            f"{m_comb['final_value'] - initial_cap:+,.0f} đ",
            f"{m_comb['sharpe_ratio']:.4f}",
            f"{m_comb['max_drawdown_pct']:.2f}%",
            f"{m_comb['closed_trades']}",
            f"{m_comb['win_rate']:.1f}%",
            f"{m_comb['profit_factor']:.2f}",
            f"{m_comb['avg_holding_days']:.1f} ngày",
            f"{m_comb['position_coverage']:.1f}%"
        ],
        'Chiến lược EMA Riêng lẻ': [
            f"{m_ema['total_return_pct']:+.2f}%",
            f"{m_ema['final_value'] - initial_cap:+,.0f} đ",
            f"{m_ema['sharpe_ratio']:.4f}",
            f"{m_ema['max_drawdown_pct']:.2f}%",
            f"{m_ema['closed_trades']}",
            f"{m_ema['win_rate']:.1f}%",
            f"{m_ema['profit_factor']:.2f}",
            f"{m_ema['avg_holding_days']:.1f} ngày",
            f"{m_ema['position_coverage']:.1f}%"
        ],
        'Chiến lược OBV Riêng lẻ': [
            f"{m_obv['total_return_pct']:+.2f}%",
            f"{m_obv['final_value'] - initial_cap:+,.0f} đ",
            f"{m_obv['sharpe_ratio']:.4f}",
            f"{m_obv['max_drawdown_pct']:.2f}%",
            f"{m_obv['closed_trades']}",
            f"{m_obv['win_rate']:.1f}%",
            f"{m_obv['profit_factor']:.2f}",
            f"{m_obv['avg_holding_days']:.1f} ngày",
            f"{m_obv['position_coverage']:.1f}%"
        ],
        'Buy & Hold ACB (Chuẩn)': [
            f"{bh_return_pct:+.2f}%",
            f"{(current_data['Close'].iloc[-1]/current_data['Close'].iloc[0] - 1)*initial_cap:+,.0f} đ",
            f"{bh_sharpe:.4f}",
            f"{bh_max_dd:.2f}%",
            "1",
            "100.0%" if bh_return_pct > 0 else "0.0%",
            "N/A",
            f"{(current_data.index[-1] - current_data.index[0]).days} ngày",
            "100.0%"
        ]
    })

    st.dataframe(metrics_summary.set_index('Chỉ số Đánh giá'), use_container_width=True)

    # Sổ lệnh giao dịch chi tiết (Trade Log)
    st.markdown("### 📑 Sổ Lệnh Giao Dịch Chi Tiết (Trade Log - EMA + OBV):")
    if len(tr_comb) > 0:
        # Tô màu cột lãi/lỗ
        def style_pnl(val):
            color = '#10B981' if val > 0 else '#EF4444'
            return f'color: {color}; font-weight: bold;'

        styled_trades = tr_comb.style.map(style_pnl, subset=['Lợi nhuận (%)', 'Lãi/Lỗ (VNĐ)']) if hasattr(tr_comb.style, 'map') else tr_comb.style.applymap(style_pnl, subset=['Lợi nhuận (%)', 'Lãi/Lỗ (VNĐ)'])
        st.dataframe(
            styled_trades,
            use_container_width=True,
            height=300
        )

        csv_trades = tr_comb.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Tải xuống Sổ lệnh (CSV)",
            data=csv_trades,
            file_name=f"ACB_TradeLog_EMA{ema_param}_OBV{obv_slope_param}.csv",
            mime="text/csv"
        )
    else:
        st.info("Không có lệnh giao dịch nào được hoàn tất trong khoảng thời gian này.")


# =============================================================================
# TAB 4: SO SÁNH TRAIN VS TEST (KIỂM ĐỊNH HIỆN TƯỢNG OVERFITTING)
# =============================================================================
with tab_comparison:
    st.subheader("⚖️ Kiểm định Hiện tượng Quá khớp (Overfitting) & Đánh giá Out-of-Sample")

    st.markdown("""
    Trong học máy tài chính và kiểm định định lượng, việc một chiến lược đạt kết quả rực rỡ trên tập huấn luyện (**In-sample Train**) nhưng thất bại nặng nề trên tập kiểm thử độc lập (**Out-of-sample Test**) là bằng chứng kinh điển của **hiện tượng quá khớp (Overfitting)**.
    """)

    # Tính toán chính xác trên cả 2 tập Train & Test để so sánh
    train_data = df_raw.loc['2014':'2020'].copy()
    test_data = df_raw.loc['2021':'2023'].copy()

    # Tín hiệu Train & Test
    # EMA = 36, OBV = 19/20 (Tham số tối ưu từ Notebook)
    opt_ema = 36
    opt_obv = 19
    opt_comb_obv = 20

    # Backtest Train
    _, _, line_ema_tr = get_ema_signals(train_data, opt_ema)
    ent_e_tr, ext_e_tr, _ = get_ema_signals(train_data, opt_ema)
    ent_o_tr, ext_o_tr, _, _ = get_obv_signals(train_data, opt_obv)
    ent_c_tr, ext_c_tr, _, _, _ = get_combined_signals(train_data, opt_ema, opt_comb_obv)

    m_e_tr, _, _, _ = run_backtest_simulation(train_data, ent_e_tr, ext_e_tr, initial_cap, fee_pct, slippage_pct, stop_loss_pct)
    m_o_tr, _, _, _ = run_backtest_simulation(train_data, ent_o_tr, ext_o_tr, initial_cap, fee_pct, slippage_pct, stop_loss_pct)
    m_c_tr, _, _, _ = run_backtest_simulation(train_data, ent_c_tr, ext_c_tr, initial_cap, fee_pct, slippage_pct, stop_loss_pct)

    # Backtest Test
    ent_e_te, ext_e_te, _ = get_ema_signals(test_data, opt_ema)
    ent_o_te, ext_o_te, _, _ = get_obv_signals(test_data, opt_obv)
    ent_c_te, ext_c_te, _, _, _ = get_combined_signals(test_data, opt_ema, opt_comb_obv)

    m_e_te, _, _, _ = run_backtest_simulation(test_data, ent_e_te, ext_e_te, initial_cap, fee_pct, slippage_pct, stop_loss_pct)
    m_o_te, _, _, _ = run_backtest_simulation(test_data, ent_o_te, ext_o_te, initial_cap, fee_pct, slippage_pct, stop_loss_pct)
    m_c_te, _, _, _ = run_backtest_simulation(test_data, ent_c_te, ext_c_te, initial_cap, fee_pct, slippage_pct, stop_loss_pct)

    # Bảng kết quả so sánh đối chiếu chuẩn như Cell 23 Notebook
    comp_df = pd.DataFrame({
        'Chiến lược': [
            'EMA Riêng lẻ', 'EMA Riêng lẻ',
            'OBV Riêng lẻ', 'OBV Riêng lẻ',
            'EMA + OBV Kết hợp', 'EMA + OBV Kết hợp'
        ],
        'Tập dữ liệu': ['Train (2014-2020)', 'Test (2021-2023)', 'Train (2014-2020)', 'Test (2021-2023)', 'Train (2014-2020)', 'Test (2021-2023)'],
        'Tham số Tối ưu': [f'EMA={opt_ema}', f'EMA={opt_ema}', f'OBV_Slope={opt_obv}', f'OBV_Slope={opt_obv}', f'EMA={opt_ema}, OBV_Slope={opt_comb_obv}', f'EMA={opt_ema}, OBV_Slope={opt_comb_obv}'],
        'Sharpe Ratio': [m_e_tr['sharpe_ratio'], m_e_te['sharpe_ratio'], m_o_tr['sharpe_ratio'], m_o_te['sharpe_ratio'], m_c_tr['sharpe_ratio'], m_c_te['sharpe_ratio']],
        'Tổng Lợi nhuận (%)': [m_e_tr['total_return_pct'], m_e_te['total_return_pct'], m_o_tr['total_return_pct'], m_o_te['total_return_pct'], m_c_tr['total_return_pct'], m_c_te['total_return_pct']],
        'Max Drawdown (%)': [m_e_tr['max_drawdown_pct'], m_e_te['max_drawdown_pct'], m_o_tr['max_drawdown_pct'], m_o_te['max_drawdown_pct'], m_c_tr['max_drawdown_pct'], m_c_te['max_drawdown_pct']],
        'Số Giao dịch Đã đóng': [m_e_tr['closed_trades'], m_e_te['closed_trades'], m_o_tr['closed_trades'], m_o_te['closed_trades'], m_c_tr['closed_trades'], m_c_te['closed_trades']]
    })

    st.markdown("#### 📊 Bảng Đối Chiếu Hiệu Suất Train vs Test:")
    st.dataframe(
        comp_df.style.format({
            'Sharpe Ratio': '{:.4f}',
            'Tổng Lợi nhuận (%)': '{:+.2f}%',
            'Max Drawdown (%)': '{:.2f}%',
            'Số Giao dịch Đã đóng': '{:d}'
        }),
        use_container_width=True
    )

    # Biểu đồ so sánh 3 thước đo chính
    fig_comp = make_subplots(
        rows=1, cols=3,
        subplot_titles=("1. Tỷ số Sharpe", "2. Tổng Lợi Nhuận (%)", "3. Max Drawdown (%)")
    )

    strats = ['EMA Riêng', 'OBV Riêng', 'EMA+OBV Kết hợp']
    
    # 1. Sharpe
    fig_comp.add_trace(go.Bar(name='Train', x=strats, y=[m_e_tr['sharpe_ratio'], m_o_tr['sharpe_ratio'], m_c_tr['sharpe_ratio']], marker_color='#3B82F6'), row=1, col=1)
    fig_comp.add_trace(go.Bar(name='Test', x=strats, y=[m_e_te['sharpe_ratio'], m_o_te['sharpe_ratio'], m_c_te['sharpe_ratio']], marker_color='#EF4444'), row=1, col=1)

    # 2. Return
    fig_comp.add_trace(go.Bar(name='Train', x=strats, y=[m_e_tr['total_return_pct'], m_o_tr['total_return_pct'], m_c_tr['total_return_pct']], marker_color='#3B82F6', showlegend=False), row=1, col=2)
    fig_comp.add_trace(go.Bar(name='Test', x=strats, y=[m_e_te['total_return_pct'], m_o_te['total_return_pct'], m_c_te['total_return_pct']], marker_color='#EF4444', showlegend=False), row=1, col=2)

    # 3. Drawdown
    fig_comp.add_trace(go.Bar(name='Train', x=strats, y=[m_e_tr['max_drawdown_pct'], m_o_tr['max_drawdown_pct'], m_c_tr['max_drawdown_pct']], marker_color='#3B82F6', showlegend=False), row=1, col=3)
    fig_comp.add_trace(go.Bar(name='Test', x=strats, y=[m_e_te['max_drawdown_pct'], m_o_te['max_drawdown_pct'], m_c_te['max_drawdown_pct']], marker_color='#EF4444', showlegend=False), row=1, col=3)

    fig_comp.update_layout(
        barmode='group',
        height=420,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
    )

    st.plotly_chart(fig_comp, use_container_width=True)

    # Nhận định chuyên gia (Diagnostic Insights)
    st.markdown("""
    ### 🧠 Báo cáo Phân tích Chuyên sâu & Giải pháp Thực chiến:
    
    1. **Tại sao hiệu suất suy giảm nghiêm trọng trên tập Test (2021-2023)?**
       - **Sự thay đổi chế độ thị trường (Regime Shift):** Giai đoạn 2014-2020 là xu hướng tăng trưởng bền vững (Secular Bull Market) của ngành ngân hàng và cổ phiếu ACB. Ngược lại, giai đoạn 2022-2023 thị trường chứng khoán Việt Nam trải qua đợt sụt giảm khốc liệt (Bear Market) do thắt chặt tiền tệ toàn cầu và khủng hoảng trái phiếu doanh nghiệp.
       - **Bản chất của chiến lược Theo xu hướng (Trend-Following):** Các chỉ báo như EMA và OBV phát huy hiệu quả tối đa khi giá có xu hướng rõ ràng. Trong giai đoạn thị trường đi ngang (Sideway) hoặc giảm sâu có sóng hồi giả (Bear Trap), chiến lược liên tục bị dính "whipsaw" (cắt lỗ nhiều lần liên tiếp).
    
    2. **Giá trị cốt lõi của việc kết hợp OBV với EMA:**
       - Trên tập Train: Chiến lược kết hợp giúp giảm thiểu Max Drawdown từ **-28.69%** (EMA) và **-30.46%** (OBV) xuống chỉ còn **-23.87%**.
       - Trên tập Test: Chiến lược kết hợp giảm số lượng lệnh thua và giảm tổn thất vốn (-36.47% so với -38.73% của OBV). Khối lượng OBV đóng vai trò như một **bộ lọc dòng tiền xác thực**, loại bỏ bớt các nhịp phá vỡ giả (Fake Breakout) khi thanh khoản yếu.
    
    3. **Khuyến nghị nâng cấp mô hình cho nhà đầu tư:**
       - Tích hợp thêm **Bộ lọc Xu hướng Vĩ mô (ví dụ: Đường SMA 200 ngày)**: Chỉ cho phép mở vị thế Mua khi giá nằm trên đường SMA 200 ngày.
       - Áp dụng **Walk-Forward Analysis (WFA)**: Tối ưu lại chu kỳ EMA/OBV định kỳ (ví dụ mỗi 6 tháng) thay vì cố định một tham số qua cả thập kỷ.
    """)


# =============================================================================
# TAB 5: QUÉT & TỐI ƯU THAM SỐ (PARAMETER OPTIMIZATION & HEATMAP)
# =============================================================================
with tab_optimization:
    st.subheader("🔍 Quét Lưới Tham số Tối ưu (Grid Search) & Bản đồ Nhiệt Sharpe")

    st.markdown("""
    Công cụ cho phép bạn quét đồng thời nhiều cặp giá trị `(EMA, OBV_Slope)` trên tập dữ liệu đang chọn để tìm ra "vùng ổn định" (Robust Parameter Island), tránh hiện tượng chọn phải đỉnh nhọn (Overfitted Spikes).
    """)

    co1, co2, co3 = st.columns(3)
    with co1:
        ema_test_range = st.select_slider(
            "Dải quét chu kỳ EMA:",
            options=[10, 15, 20, 25, 30, 35, 40, 45, 50],
            value=(15, 45)
        )
    with co2:
        obv_test_range = st.select_slider(
            "Dải quét chu kỳ Độ dốc OBV:",
            options=[2, 4, 6, 8, 10, 12, 15, 20],
            value=(4, 15)
        )
    with co3:
        opt_criterion = st.selectbox(
            "Tiêu chí Xếp hạng Tối ưu:",
            ["Sharpe Ratio cao nhất", "Tổng Lợi Nhuận cao nhất", "Max Drawdown thấp nhất"]
        )

    if st.button("🚀 Bắt đầu Quét Tham số (Run Grid Search)", type="primary"):
        all_ema_vals = [e for e in [10, 15, 20, 25, 30, 35, 40, 45, 50] if ema_test_range[0] <= e <= ema_test_range[1]]
        all_obv_vals = [o for o in [2, 4, 6, 8, 10, 12, 15, 20] if obv_test_range[0] <= o <= obv_test_range[1]]

        progress_bar = st.progress(0.0)
        status_text = st.empty()

        grid_results = []
        total_combos = len(all_ema_vals) * len(all_obv_vals)
        counter = 0

        for e_val in all_ema_vals:
            for o_val in all_obv_vals:
                counter += 1
                status_text.text(f"Đang kiểm định cặp: EMA={e_val}, OBV_Slope={o_val} ({counter}/{total_combos})...")
                
                # Tín hiệu
                e_ent, e_ext, _, _, _ = get_combined_signals(current_data, e_val, o_val)
                res_m, _, _, _ = run_backtest_simulation(
                    current_data, e_ent, e_ext, initial_cap, fee_pct, slippage_pct, stop_loss_pct
                )

                # Ràng buộc tối thiểu 5 giao dịch để có ý nghĩa thống kê (như trong Notebook)
                if res_m['closed_trades'] >= 5:
                    grid_results.append({
                        'EMA': e_val,
                        'OBV_Slope': o_val,
                        'Sharpe Ratio': round(res_m['sharpe_ratio'], 4),
                        'Lợi nhuận (%)': round(res_m['total_return_pct'], 2),
                        'Max Drawdown (%)': round(res_m['max_drawdown_pct'], 2),
                        'Số Lệnh': res_m['closed_trades'],
                        'Win Rate (%)': round(res_m['win_rate'], 1)
                    })
                progress_bar.progress(counter / total_combos)

        status_text.success("✅ Đã hoàn thành quét lưới tham số!")
        progress_bar.empty()

        if grid_results:
            grid_df = pd.DataFrame(grid_results)

            # Bản đồ nhiệt Heatmap
            pivot_metric = 'Sharpe Ratio' if "Sharpe" in opt_criterion else ('Lợi nhuận (%)' if "Lợi Nhuận" in opt_criterion else 'Max Drawdown (%)')
            pivot_table = grid_df.pivot(index='EMA', columns='OBV_Slope', values=pivot_metric)

            fig_hm = go.Figure(data=go.Heatmap(
                z=pivot_table.values,
                x=pivot_table.columns,
                y=pivot_table.index,
                colorscale='Viridis',
                colorbar=dict(title=pivot_metric),
                hoverongaps=False
            ))

            fig_hm.update_layout(
                title=f"Bản đồ nhiệt {pivot_metric} theo Cặp Tham số (EMA vs OBV Slope)",
                xaxis_title="Chu kỳ Độ dốc OBV (Phiên)",
                yaxis_title="Chu kỳ EMA (Phiên)",
                height=450
            )

            st.plotly_chart(fig_hm, use_container_width=True)

            # Bảng Top 5 cấu hình tốt nhất
            st.markdown(f"#### 🏆 Top 5 Cấu hình Tham số Tốt nhất theo {opt_criterion}:")
            if "Sharpe" in opt_criterion:
                top_grid = grid_df.sort_values(by='Sharpe Ratio', ascending=False).head(5)
            elif "Lợi Nhuận" in opt_criterion:
                top_grid = grid_df.sort_values(by='Lợi nhuận (%)', ascending=False).head(5)
            else:
                top_grid = grid_df.sort_values(by='Max Drawdown (%)', ascending=True).head(5)

            st.dataframe(top_grid.reset_index(drop=True), use_container_width=True)
        else:
            st.warning("Không tìm thấy bộ tham số nào đáp ứng điều kiện tối thiểu 5 giao dịch.")

# -----------------------------------------------------------------------------
# CHÂN TRANG (FOOTER)
# -----------------------------------------------------------------------------
st.divider()
st.markdown("""
<div style="text-align: center; color: #94A3B8; font-size: 0.85rem; padding: 1rem 0;">
    Phát triển bởi Chuyên gia Lập trình Web Định lượng | Sẵn sàng triển khai trên GitHub & Streamlit Cloud 🚀<br>
    Lưu ý: Kết quả backtest quá khứ không phải là lời khuyên đầu tư tài chính và không đảm bảo lợi nhuận tương lai.
</div>
""", unsafe_allow_html=True)
