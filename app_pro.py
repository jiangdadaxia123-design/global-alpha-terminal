import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import akshare as ak
import os
from datetime import datetime

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
    /* 1. 全局背景色 */
    .stApp {background-color: #12141C; font-family: 'Inter', sans-serif;}
    
    /* 2. 强制所有基础文字颜色为亮白 */
    h1, h2, h3, h4, p, div, span, label, li, b {
        color: #E0E0E0 !important;
    }
    
    /* 3. 侧边栏与下拉框深度定制 */
    [data-testid="stSidebar"] {
        background-color: #161920; 
        border-right: 1px solid #333;
    }
    
    /* 输入框和下拉框的主体背景 */
    .stTextInput > div > div > input {
        color: #E0E0E0 !important;
        background-color: #252A38 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #252A38 !important;
        border-color: #444 !important;
        color: #E0E0E0 !important;
    }
    
    /* 下拉弹出的菜单选项 */
    div[data-baseweb="popover"] {
        background-color: #1E222D !important;
    }
    ul[data-testid="stSelectboxVirtualDropdown"] {
        background-color: #1E222D !important;
    }
    li[role="option"] {
        color: #E0E0E0 !important;
        background-color: #1E222D !important;
    }
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {
        background-color: #2B303B !important;
        color: #00E396 !important;
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

    /* 隐藏默认元素 */
    #MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ================= 3. 数据获取引擎 (智能代理版) =================

@st.cache_data(ttl=60) 
def get_market_data(asset_type, symbol, interval, use_proxy_setting, proxy_url_setting):
    """
    智能数据适配器：自动处理代理逻辑
    """
    df = pd.DataFrame()
    
    # === 智能代理逻辑 ===
    # 1. 如果是 A股：强制关闭代理
    if asset_type == "A-Shares (A股)":
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
        
    # 2. 如果是 美股/大宗/币圈 且 用户开启了代理：强制注入代理
    elif use_proxy_setting and proxy_url_setting:
        os.environ["http_proxy"] = proxy_url_setting
        os.environ["https_proxy"] = proxy_url_setting
        
    try:
        # --- A. 币圈 (Binance) ---
        if asset_type == "Crypto (币安)":
            limit = 300
            binance_interval = {"日线 (1D)": "1d", "周线 (1W)": "1w", "月线 (1M)": "1M"}[interval]
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": binance_interval, "limit": limit}
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            # 发送请求
            r = requests.get(url, params=params, headers=headers, timeout=15)
            
            if r.status_code != 200:
                st.error(f"Binance 连接失败 (Code {r.status_code})。")
                return None
                
            data = r.json()
            df = pd.DataFrame(data, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'x', 'y', 'z', 'a', 'b', 'c'])
            df['Time'] = pd.to_datetime(df['Time'], unit='ms')
            
        # --- B. 美股/大宗 (Yahoo Finance) ---
        elif asset_type in ["US Stocks (美股)", "Commodities (大宗)"]:
            yf_interval = {"日线 (1D)": "1d", "周线 (1W)": "1wk", "月线 (1M)": "1mo"}[interval]
            
            ticker_obj = yf.Ticker(symbol)
            df = ticker_obj.history(period="2y", interval=yf_interval)
            
            if df.empty:
                st.error(f"无法获取数据 ({symbol})。请确认代理 {proxy_url_setting} 是否通畅。")
                return None
                
            df = df.reset_index()
            df = df.rename(columns={"Date": "Time"})
            
        # --- C. A股 (AkShare) ---
        elif asset_type == "A-Shares (A股)":
            ak_period = {"日线 (1D)": "daily", "周线 (1W)": "weekly", "月线 (1M)": "monthly"}[interval]
            try:
                df = ak.stock_zh_a_hist(symbol=symbol, period=ak_period, adjust="qfq")
            except Exception as e:
                st.error(f"AkShare 连接超时: {e}。")
                return None
                
            df = df.rename(columns={
                "日期": "Time", "开盘": "Open", "最高": "High", 
                "最低": "Low", "收盘": "Close", "成交量": "Volume"
            })
            df['Time'] = pd.to_datetime(df['Time'])
            
        # === 数据清洗 ===
        if not df.empty:
            cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna()
            return df
        else:
            return None

    except Exception as e:
        st.error(f"数据源报错: {e}")
        return None

# ================= 4. 逻辑计算引擎 =================

def calculate_indicators(df):
    if df is None or len(df) < 120:
        st.warning(f"数据量不足 (仅 {len(df) if df is not None else 0} 行)，无法计算 MA200。")
        return None
    
    current_price = df['Close'].iloc[-1]
    
    # 1. 长期成本
    ma200 = df['Close'].rolling(200).mean().iloc[-1]
    if pd.isna(ma200): ma200 = df['Close'].mean()
        
    lth_ratio = current_price / ma200 if ma200 > 0 else 0
    
    # 2. 资金动量
    vol_short = df['Volume'].tail(7).mean()
    vol_long = df['Volume'].tail(90).mean()
    demand_score = vol_short / vol_long if vol_long > 0 else 0
    
    # 3. 筹码支撑
    price_hist = df['Close'].tail(150)
    vol_hist = df['Volume'].tail(150)
    counts, bin_edges = np.histogram(price_hist, bins=60, weights=vol_hist)
    max_idx = np.argmax(counts)
    support_price = (bin_edges[max_idx] + bin_edges[max_idx+1]) / 2
    
    return {
        "price": current_price, "ma200": ma200, "ratio": lth_ratio,
        "demand": demand_score, "support": support_price, "history": df
    }

# ================= 5. 结论生成引擎 =================

def generate_outlook(data):
    # 卖方逻辑
    if data['ratio'] < 1.05:
        sell_status, sell_desc, sell_score = "🟢 极低抛压", "价格回踩长期成本线，获利盘清洗完毕，惜售明显。", 1
    elif data['ratio'] < 1.3:
        sell_status, sell_desc, sell_score = "🟡 正常换手", "偏离度适中，处于健康趋势中。", 0
    else:
        sell_status, sell_desc, sell_score = "🔴 高位获利", "乖离率过大，随时有回调风险。", -1
        
    # 买方逻辑
    if data['demand'] > 1.3:
        buy_status, buy_desc, buy_score = "🟢 资金抢筹", "成交量异常放大 (>130%)。", 1
    elif data['demand'] > 0.8:
        buy_status, buy_desc, buy_score = "🟡 存量博弈", "成交量平稳。", 0
    else:
        buy_status, buy_desc, buy_score = "🔴 流动性枯竭", "成交量低迷，市场缺乏关注。", -1
        
    # 综合结论
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

# ================= 6. 界面渲染 =================

# --- 侧边栏 ---
with st.sidebar:
    st.header("🔍 资产扫描")
    
    st.markdown("### 📶 智能网络设置")
    use_proxy = st.checkbox("自动代理加速 (美股/大宗/币圈)", value=True)
    proxy_port = st.text_input("代理地址", value="http://127.0.0.1:10809")
    
    st.divider()

    asset_class = st.selectbox(
        "1. 选择市场", 
        ["Crypto (币安)", "US Stocks (美股)", "A-Shares (A股)", "Commodities (大宗)"]
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
    else: 
        symbol_map = {
            "贵州茅台": "600519", "宁德时代": "300750", "东方财富": "300059", 
            "汇纳科技": "300609", "长春燃气": "600333", "机器人": "300024",
            "中航沈飞": "600760", "科大讯飞": "002230", "立讯精密": "002475"
        }
        
    selected_name = st.selectbox("2. 选择标的", list(symbol_map.keys()))
    ticker = symbol_map[selected_name]
    interval_ui = st.radio("3. 分析周期", ["日线 (1D)", "周线 (1W)", "月线 (1M)"])
    
# --- 主界面 ---
st.markdown(f"<h1 style='margin-bottom:0;'>🌍 Universal Alpha Terminal <span style='font-size:20px; color:#00E396;'>全球全资产策略终端</span> <span style='font-size:16px; color:#aaa;'>| {selected_name}</span></h1>", unsafe_allow_html=True)

# 获取数据
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
        
        # 卖方/成本分析
        with col1:
            st.markdown(f"### 🐢 长期成本趋势 (MA200)")
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("当前价格", f"{data['price']:,.2f}")
            c2.metric("成本偏离度", f"{data['ratio']:.2f}", delta="< 1.05 为安全", delta_color="inverse")
            
            fig_lth = go.Figure()
            hist = data['history']
            fig_lth.add_trace(go.Scatter(x=hist['Time'], y=hist['Close'], name="Price", line=dict(color='#fff', width=1.5)))
            fig_lth.add_trace(go.Scatter(x=hist['Time'], y=hist['Close'].rolling(200).mean(), name="MA200", line=dict(color='#FF4560', width=2)))
            
            fig_lth.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font={'color':'#ccc'}, xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#333'), showlegend=False)
            st.plotly_chart(fig_lth, use_container_width=True)
            
            tag_cls = "tag-green" if "低" in logic['sell_st'] else ("tag-red" if "高" in logic['sell_st'] else "tag-yellow")
            # --- 修复点：确保这里括号闭合 ---
            st.markdown(f"""<div class="conclusion-box"><span class="status-tag {tag_cls}">{logic['sell_st']}</span> <span style="color:#ddd; margin-left:8px;">{logic['sell_txt']}</span></div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # 买方/动量分析
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
            
            tag_cls_buy = "tag-green" if "抢筹" in logic['buy_st'] else ("tag-red" if "枯竭" in logic['buy_st'] else "tag-yellow")
            # --- 修复点：确保这里括号闭合 ---
            st.markdown(f"""<div class="conclusion-box"><span class="status-tag {tag_cls_buy}">{logic['buy_st']}</span> <span style="color:#ddd; margin-left:8px;">{logic['buy_txt']}</span></div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # 筹码支撑
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
        st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.warning("数据量过少，无法进行分析。")
else:
    st.info("若连接失败，请检查 VPN 端口是否正确。")