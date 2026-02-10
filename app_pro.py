import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import akshare as ak
import os
import time
from io import BytesIO

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

# ================= 3. 图片生成引擎 =================
def generate_high_res_image(fig):
    """将Plotly图表转换为3倍高清PNG字节流"""
    try:
        img_bytes = fig.to_image(format="png", width=1000, height=600, scale=3)
        return BytesIO(img_bytes)
    except Exception as e:
        return None

# ================= 4. 数据引擎 (升级版) =================

def get_yfinance_data(symbol, interval):
    try:
        # 映射周期：支持 4h
        if "4小时" in interval: yf_interval = "1h" # Yahoo不直接支持4h, 用1h代替, 后续处理
        elif "日线" in interval: yf_interval = "1d"
        elif "周线" in interval: yf_interval = "1wk"
        else: yf_interval = "1mo"
        
        # 4H周期需要更短的整体时间范围，否则数据量太大
        period = "6mo" if "4小时" in interval else "2y"
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=yf_interval)
        
        if df.empty: return None
        
        # 简单的 4H 重采样逻辑 (如果需要)
        if "4小时" in interval:
            df = df.resample('4H').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()

        df = df.reset_index()
        df = df.rename(columns={"Date": "Time", "Datetime": "Time"}) # 兼容不同返回格式
        return df
    except:
        return None

@st.cache_data(ttl=60) 
def get_market_data(asset_type, symbol, interval, use_proxy_setting, proxy_url_setting):
    df = pd.DataFrame()
    
    is_cn_stock = "A-Shares" in asset_type or "Liquor" in asset_type 
    
    # 智能降级提示
    if is_cn_stock and "4小时" in interval:
        st.toast("⚠️ A股数据源暂不支持分时数据，已自动为您切换为【日线】模式。", icon="🔄")
        interval = "日线 (1D)" # 强制降级

    if not is_cn_stock and use_proxy_setting and proxy_url_setting:
        os.environ["http_proxy"] = proxy_url_setting
        os.environ["https_proxy"] = proxy_url_setting
    else:
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)

    try:
        # A. 币圈
        if asset_type == "Crypto (币安)":
            # 映射币安周期
            if "4小时" in interval: bin_interval = "4h"
            elif "周线" in interval: bin_interval = "1w"
            elif "月线" in interval: bin_interval = "1M"
            else: bin_interval = "1d"
            
            limit = 300
            headers = {'User-Agent': 'Mozilla/5.0'}
            try:
                url = "https://api.binance.com/api/v3/klines"
                params = {"symbol": symbol, "interval": bin_interval, "limit": limit}
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

        # B. 美股/大宗
        elif asset_type in ["US Stocks (美股)", "Commodities (大宗)"]:
            df = get_yfinance_data(symbol, interval)
            if df is None:
                st.error("无法获取数据")
                return None
            
        # C. A股 (含白酒)
        elif asset_type in ["A-Shares (A股)", "A-Share Liquor (白酒精选)"]:
            ak_period = {"
