import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import akshare as ak
import os
import time
from io import BytesIO # 新增：用于图片流处理

# ================= 1. 页面配置 =================
st.set_page_config(
    page_title="Universal Alpha Terminal | 全球全资产策略终端",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= 2. UI 深度定制 =================
st.markdown("""
<style>
    /* 1. 全局背景色与字体适配 */
    .stApp {
        background-color: #12141C; 
        font-family: -apple-system, Helvetica, Arial, sans-serif;
    }
    
    /* 2. 强制所有基础文字颜色为亮白 */
    h1, h2, h3, h4, p, div, span, label, li, b, td, th {
        color: #E0E0E0 !important;
    }
    
    /* 3. 侧边栏 */
    [data-testid="stSidebar"] {
        background-color: #161920; 
        border-right: 1px solid #333;
    }
    
    /* 输入框和下拉框 */
    .stTextInput > div > div > input {
        color: #E0E0E0 !important;
        background-color: #252A38 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #252A38 !important;
        border-color: #444 !important;
        color: #E0E0E0 !important;
    }
    div[data-baseweb="popover"], ul[data-testid="stSelectboxVirtualDropdown"] {
        background-color: #1E222D !important;
    }
    li[role="option"] {
        color: #E0E0E0 !important;
        background-color: #1E222D !important;
    }
    
    /* 4. 卡片样式 */
    .metric-card {
        background-color: #1E222D; border: 1px solid #3A3F50; padding: 24px;
        border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    
    /* 5. 结论框 */
    .conclusion-box {
        background: #252A38; border-left: 4px solid #00E396; padding: 16px; 
        margin-top: 15px; border-radius: 4px;
    }

    /* 6. 状态标签 */
    .status-tag {
        display: inline-block; padding: 4px 10px; border-radius: 4px; 
        font-weight: 700; font-size: 13px; color: #000 !important;
    }
    .tag-green {background: #00E396;}
    .tag-red {background: #FF4560;}
    .tag-yellow {background: #F0B90B;}
    
    /* 7. 下载按钮美化 */
    .stDownloadButton button {
        background-color: #2B303B !important;
        color: #00E396 !important;
        border: 1px solid #00E396 !important;
    }

    /* 隐藏默认元素 */
    #MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ================= 3. 图片生成引擎 (新增功能) =================
def generate_high_res_image(fig):
    """将Plotly图表转换为3倍高清PNG字节流"""
    try:
        # scale=3 意味着图片清晰度是默认的3倍，非常适合小红书
        img_bytes = fig.to_image(format="png", width=1000, height=600, scale=3)
        return BytesIO(img_bytes)
    except Exception as e:
        # 如果Kaleido引擎失败，返回None
        return None

# ================= 4. 数据引擎 =================

def get_yfinance_data(symbol, interval):
    try:
        yf_interval = {"日线 (1D)": "1d", "周线 (1W)": "1wk", "月线 (1M)": "1mo"}[interval]
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2y", interval=yf_interval)
        if df.empty: return None
        df = df.reset_index()
        df = df.rename(columns={"Date": "Time"})
        return df
    except:
        return None

@st.cache_data(ttl=60) 
def get_market_data(asset_type, symbol, interval, use_proxy_setting, proxy_url_setting):
    df = pd.DataFrame()
    
    is_cn_stock = "A-Shares" in asset_type or "Liquor" in asset_type 
    
    if not is_cn_stock and use_proxy_setting and proxy_url_setting:
        os.environ["http_proxy"] = proxy_url_setting
        os.environ["https_proxy"] = proxy_url_setting
    else:
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)

    try:
        if asset_type == "Crypto (币安)":
            limit = 300
            binance_interval = {"日线 (1D)": "1d", "周线 (1W)": "1w", "月线 (1M)": "1M"}[interval]
            headers = {'User-Agent': 'Mozilla/5.0'}
            try:
                url = "https://api.binance.com/api/v3/klines"
                params = {"symbol": symbol, "interval": binance_interval, "limit": limit}
                r = requests.get(url, params=params, headers=headers, timeout=5)
                if r.status_code != 200: raise Exception("Error")
                data = r.json()
                df = pd.DataFrame(data, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'x', 'y', 'z', 'a', 'b', 'c'])
                df['Time'] = pd.to_datetime(df['Time'], unit='ms')
            except:
                try:
                    url_us = "https://api.binance.us/api/v3/klines"
                    r = requests.get(url_us, params=params, headers=headers, timeout=5)
                    r.raise_for_status()
                    data = r.json()
                    df = pd.DataFrame(data, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'x', 'y', 'z', 'a', 'b', 'c'])
                    df['Time'] = pd.to_datetime(df['Time'], unit='ms')
                except:
                    yf_symbol = symbol.replace("USDT", "-USD")
                    df = get_yfinance_data(yf_symbol, interval)
                    if df is None:
                        st.error("数据连接失败")
                        return None

        elif asset_type in ["US Stocks (美股)", "Commodities (大宗)"]:
            df = get_yfinance_data(symbol, interval)
            if df is None:
                st.error("无法获取数据")
                return None
            
        elif asset_type in ["A-Shares (A股)", "A-Share Liquor (白酒精选)"]:
            ak_period = {"日线 (1D)": "daily", "周线 (1W)": "weekly", "月线 (1M)": "monthly"}[interval]
            try:
                df = ak.stock_zh_a_hist(symbol=symbol, period=ak_period, adjust="qfq")
                df = df.rename(columns={"日期": "Time", "开盘": "Open", "最高": "High", "最低": "Low", "收盘": "Close", "成交量": "Volume"})
                df['Time'] = pd.to_datetime(df['Time'])
            except:
                if symbol.startswith("6") or symbol.startswith("5"): 
                    yf_symbol = f"{symbol}.SS"
                else: 
                    yf_symbol = f"{symbol}.SZ"
                df = get_yfinance_data(yf_symbol, interval)
                if df is None:
                    st.error("无法获取A股数据")
                    return None
            
        if not df.empty:
            cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna()
            return df
        else:
            return None

    except Exception:
        st.error("系统错误")
        return None

# ================= 5. 逻辑计算 =================

def calculate_indicators(df):
    if df is None or len(df) < 120:
        st.warning("数据量不足")
        return None
    
    current_price = df['Close'].iloc[-1]
    ma200 = df['Close'].rolling(200).mean().iloc[-1]
    if pd.isna(ma200): ma200 = df['Close'].mean()
    lth_ratio = current_price / ma200 if ma200 > 0 else 0
    
    vol_short = df['Volume'].tail(7).mean()
    vol_long = df['Volume'].tail(90).mean()
    demand_score = vol_short / vol_long if vol_long > 0 else 0
    
    price_hist = df['Close'].tail(150)
    vol_hist = df['Volume'].tail(150)
    counts, bin_edges = np.histogram(price_hist, bins=60, weights=vol_hist)
    max_idx = np.argmax(counts)
    support_price = (bin_edges[max_idx] + bin_edges[max_idx+1]) / 2
    
    return {
        "price": current_price, "ma200": ma200, "ratio": lth_ratio,
        "demand": demand_score, "support": support_price, "history": df
    }

# ================= 6. 结论生成 =================

def generate_outlook(data):
    if data['ratio'] < 1.05:
        sell_status, sell_desc, sell_score = "🟢 极低抛压", "价格回踩长期成本线，获利盘清洗完毕，惜售明显。", 1
    elif data['ratio'] < 1.3:
        sell_status, sell_desc, sell_score = "🟡 正常换手", "趋势延续中。", 0
    else:
        sell_status, sell_desc, sell_score = "🔴 高位获利", "乖离率过大，有风险。", -1
        
    if data['demand'] > 1.3:
        buy_status, buy_desc, buy_score = "🟢 资金抢筹", "成交量异常放大。", 1
    elif data['demand'] > 0.8:
        buy_status, buy_desc, buy_score = "🟡 存量博弈", "成交量平稳。", 0
    else:
        buy_status, buy_desc, buy_score = "🔴 流动性枯竭", "成交量低迷。", -1
        
    if sell_score == 1 and buy_score == 1: outlook, color = "🚀 黄金坑 (底部放量)", "#00E396"
    elif sell_score == -1 and buy_score == -1: outlook, color = "🩸 顶部阴跌 (离场)", "#FF4560"
    elif sell_score == 1: outlook, color = "⚖️ 底部缩量 (左侧机会)", "#F0B90B"
    elif sell_score == -1 and buy_score == 1: outlook, color = "🔥 加速赶顶 (风险)", "#FF4560"
    else: outlook, color = "〰️ 震荡 (中继)", "#A0A0A0"
        
    return {
        "sell_st": sell_status, "sell_txt": sell_desc,
        "buy_st": buy_status, "buy_txt": buy_desc,
        "outlook": outlook, "color": color
    }

# ================= 7. 界面渲染 =================

# --- 侧边栏 ---
with st.sidebar:
    st.header("🔍 资产扫描")
    
    st.markdown("### 📶 智能网络设置")
    use_proxy = st.checkbox("自动代理加速 (本地需开启/云端需关闭)", value=False)
    proxy_port = st.text_input("代理地址", value="http://127.0.0.1:10809")
    
    st.divider()

    asset_class = st.selectbox(
        "1. 选择市场", 
        ["Crypto (币安)", "US Stocks (美股)", "A-Share Liquor (白酒精选)", "A-Shares (A股)", "Commodities (大宗)"]
    )
    
    if asset_class == "Crypto (币安)":
        symbol_map = {
            "Bitcoin (BTC)": "BTCUSDT", "Ethereum (ETH)": "ETHUSDT", "Solana (SOL)": "SOLUSDT", 
            "Chainlink (LINK)": "LINKUSDT", "Ondo (ONDO - RWA)": "ONDOUSDT", "Maker (MKR - RWA)": "MKRUSDT",
            "Dogecoin (DOGE)": "DOGEUSDT"
        }
    elif asset_class == "US Stocks (美股)":
        symbol_map = {
            "NVIDIA (英伟达)": "NVDA", "Tesla (特斯拉)": "TSLA", "Apple (苹果)": "AAPL", 
            "Microsoft (微软)": "MSFT", "Coinbase": "COIN", "MicroStrategy": "MSTR",
            "Google (GOOG)": "GOOG", "Amazon (AMZN)": "AMZN", "Meta (META)": "META"
        }
    elif asset_class == "Commodities (大宗)":
        symbol_map = {"Gold (黄金)": "GC=F", "Oil (原油)": "CL=F", "Silver (白银)": "SI=F"}
    
    elif asset_class == "A-Share Liquor (白酒精选)":
        symbol_map = {
            "贵州茅台 (老大)": "600519", "五粮液 (老二)": "000858", "泸州老窖 (高端)": "000568",
            "山西汾酒 (清香龙头)": "600809", "洋河股份 (低估值)": "002304", "古井贡酒 (徽酒龙头)": "000596",
            "今世缘 (苏酒)": "603369", "舍得酒业 (次高端)": "600702", "迎驾贡酒 (洞藏)": "603198",
            "酒鬼酒 (馥郁香)": "000799"
        }
        
    else: # A-Shares (A股全市场)
        symbol_map = {
            # --- 热门ETF (A股) ---
            "【ETF】机器人ETF (562500)": "562500",
            "【ETF】半导体ETF (512480)": "512480",
            "【ETF】创新药ETF (512290)": "512290",

            # --- 核心资产 ---
            "【核心】贵州茅台": "600519", 
            "【核心】宁德时代": "300750", 
            "【核心】东方财富": "300059",
            
            # --- 科技/AI/算力 ---
            "【AI算力】鸿博股份 (算力龙头)": "002229",
            "【AI算力】梦网科技 (云通信)": "002123",
            "【半导体】江波龙 (存储芯片)": "301308",
            "【金融科技】赢时胜 (数字货币)": "300377",
            
            # --- 电子/制造/化工 ---
            "【消费电子】东山精密 (特斯拉链)": "002384",
            "【锂电化工】多氟多 (六氟磷酸锂)": "002407",
            "【游戏/充电】惠程科技": "002168",
            
            # --- 中字头/基建/能源 ---
            "【中字头】中国石油 (能源权重)": "601857",
            "【中字头】中国核建 (核电基建)": "601611",
            "【工程机械】山河智能 (低空经济)": "002097",
            
            # --- 消费/医药/传媒 ---
            "【影视传媒】博纳影业 (院线)": "001330",
            "【医药商业】开开实业": "600272",
            
            # --- 其他 ---
            "【券商】国联证券": "601456",
            "【银行】民生银行": "600016",
            "【自选】汇纳科技": "300609",
            "【自选】长春燃气": "600333",
            "【龙头】机器人": "300024",
            "【龙头】中航沈飞": "600760",
            "【龙头】科大讯飞": "002230",
            "【龙头】立讯精密": "002475"
        }
        
    selected_name = st.selectbox("2. 选择标的", list(symbol_map.keys()))
    ticker = symbol_map[selected_name]
    interval_ui = st.radio("3. 分析周期", ["日线 (1D)", "周线 (1W)", "月线 (1M)"])
    
# --- 主界面 ---
st.markdown(f"<h1 style='margin-bottom:0;'>🌍 Universal Alpha Terminal <span style='font-size:20px; color:#00E396;'>全球全资产策略终端</span> <span style='font-size:16px; color:#aaa;'>| {selected_name}</span></h1>", unsafe_allow_html=True)

with st.spinner(f"正在连接数据源 ({asset_class})..."):
    df_raw = get_market_data(asset_class, ticker, interval_ui, use_proxy, proxy_port)
    
if df_raw is not None:
    data = calculate_indicators(df_raw)
    
    if data:
        logic = generate_outlook(data)
        
        # 结论卡片
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, rgba(30,34,45,1) 0%, rgba(37,42,56,1) 100%); 
                    border-left: 6px solid {logic['color']}; padding: 25px; border-radius: 8px; margin: 20px 0; border: 1px solid #333;">
            <h2 style="margin:0; color:{logic['color']} !important; font-size: 28px;">🎯 核心结论：{logic['outlook']}</h2>
            <div style="margin-top:10px; font-size:16px; color:#E0E0E0;">
                分析逻辑：<span style="font-weight:bold; color:#fff">{logic['sell_st']}</span> + 
                <span style="font-weight:bold; color:#fff">{logic['buy_st']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        # 卖方分析 (增加下载按钮)
        with col1:
            st.markdown(f"### 🐢 长期成本趋势 (MA200)")
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("当前价格 (USD/CNY)", f"{data['price']:,.2f}")
            c2.metric("成本偏离度", f"{data['ratio']:.2f}", delta="< 1.05 安全", delta_color="inverse")
            
            fig_lth = go.Figure()
            hist = data['history']
            fig_lth.add_trace(go.Scatter(x=hist['Time'], y=hist['Close'], name="Price", line=dict(color='#fff', width=1.5)))
            fig_lth.add_trace(go.Scatter(x=hist['Time'], y=hist['Close'].rolling(200).mean(), name="MA200", line=dict(color='#FF4560', width=2)))
            
            fig_lth.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font={'color':'#ccc'}, xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#333'), showlegend=False)
            st.plotly_chart(fig_lth, use_container_width=True)
            
            # 🔥 高清图下载逻辑
            img = generate_high_res_image(fig_lth)
            if img:
                st.download_button("📥 下载成本分析图 (高清)", img, f"{ticker}_成本分析.png", "image/png", use_container_width=True)
            
            tag_cls = "tag-green" if "低" in logic['sell_st'] else ("tag-red" if "高" in logic['sell_st'] else "tag-yellow")
            st.markdown(f"""<div class="conclusion-box"><span class="status-tag {tag_cls}">{logic['sell_st']}</span> <span style="color:#ddd; margin-left:8px;">{logic['sell_txt']}</span></div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # 买方分析 (增加下载按钮)
        with col2:
            st.markdown(f"### 🐇 资金需求动量")
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            c3, c4 = st.columns(2)
            c3.metric("量能得分", f"{data['demand']:.2f}", delta="> 1.0 增量", delta_color="normal")
            
            fig_vol = go.Figure()
            colors = ['#00E396' if r.Open < r.Close else '#FF4560' for i, r in hist.tail(60).iterrows()]
            fig_vol.add_trace(go.Bar(x=hist['Time'].tail(60), y=hist['Volume'].tail(60), marker_color=colors))
            
            fig_vol.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font={'color':'#ccc'}, xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#333'), showlegend=False)
            st.plotly_chart(fig_vol, use_container_width=True)
            
            # 🔥 高清图下载逻辑
            img_vol = generate_high_res_image(fig_vol)
            if img_vol:
                st.download_button("📥 下载量能分析图 (高清)", img_vol, f"{ticker}_量能分析.png", "image/png", use_container_width=True)
            
            tag_cls_buy = "tag-green" if "抢筹" in logic['buy_st'] else ("tag-red" if "枯竭" in logic['buy_st'] else "tag-yellow")
            st.markdown(f"""<div class="conclusion-box"><span class="status-tag {tag_cls_buy}">{logic['buy_st']}</span> <span style="color:#ddd; margin-left:8px;">{logic['buy_txt']}</span></div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # 筹码支撑 (增加下载按钮)
        st.markdown(f"### 🎯 筹码结构 (Chip Distribution)")
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        ca, cb = st.columns([1, 2])
        with ca:
            st.metric("最强支撑位", f"{data['support']:,.2f}")
            gap = ((data['price'] - data['support']) / data['price']) * 100
            st.metric("距离支撑", f"{gap:.2f}%", delta="回踩支撑" if 0 < gap < 5 else "远离", delta_color="inverse")
            if gap < 0: st.error("⚠️ 跌破主要支撑区！")
        with cb:
            price_hist = data['history']['Close'].tail(150)
            vol_hist = data['history']['Volume'].tail(150)
            counts, bin_edges = np.histogram(price_hist, bins=50, weights=vol_hist)
            
            fig_chip = go.Figure()
            fig_chip.add_trace(go.Bar(y=bin_edges[:-1], x=counts, orientation='h', marker_color='#4A5568'))
            fig_chip.add_hline(y=data['price'], line_color="#00E396", annotation_text="Price")
            fig_chip.add_hline(y=data['support'], line_color="#F0B90B", annotation_text="Support")
            
            fig_chip.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font={'color':'#ccc'}, xaxis=dict(showgrid=False, visible=False), yaxis=dict(gridcolor='#333'), showlegend=False)
            st.plotly_chart(fig_chip, use_container_width=True)
            
            # 🔥 高清图下载逻辑
            img_chip = generate_high_res_image(fig_chip)
            if img_chip:
                st.download_button("📥 下载筹码分析图 (高清)", img_chip, f"{ticker}_筹码分析.png", "image/png", use_container_width=True)
                
        st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.warning("数据量过少，无法进行分析。")
else:
    st.info("连接中...")
