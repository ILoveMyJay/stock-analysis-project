from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import akshare as ak
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import sqlite3
import json
from typing import List, Dict, Any
from pydantic import BaseModel
import time
from functools import lru_cache

app = FastAPI()

# 数据模型
class StockInfo(BaseModel):
    stock_code: str
    stock_name: str
    added_time: str
    highlight: bool = False
    strategies: Dict[str, Any] = {}

# 数据库初始化
def init_database():
    """初始化SQLite数据库"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    # 创建股票信息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT UNIQUE NOT NULL,
        stock_name TEXT NOT NULL,
        added_time TEXT NOT NULL,
        highlight BOOLEAN DEFAULT FALSE,
        strategies TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建基本面数据缓存表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fundamental_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT UNIQUE NOT NULL,
        data TEXT NOT NULL,
        data_source TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL
    )
    ''')
    
    # 创建错误日志表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT,
        error_type TEXT NOT NULL,
        error_message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# 缓存相关函数
def save_fundamental_cache(stock_code: str, data: dict, expires_hours: int = 24):
    """保存基本面数据到缓存"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        from datetime import datetime, timedelta
        expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
        
        cursor.execute('''
        INSERT OR REPLACE INTO fundamental_cache 
        (stock_code, data, data_source, updated_at, expires_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (
            stock_code,
            json.dumps(data, ensure_ascii=False),
            data.get('data_source', 'unknown'),
            expires_at
        ))
        conn.commit()
    finally:
        conn.close()

def get_fundamental_cache(stock_code: str):
    """从缓存获取基本面数据"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT data, data_source, expires_at FROM fundamental_cache 
        WHERE stock_code = ? AND expires_at > CURRENT_TIMESTAMP
        ''', (stock_code,))
        
        result = cursor.fetchone()
        if result:
            data = json.loads(result[0])
            data['cache_source'] = result[1]
            data['cache_hit'] = True
            return data
        return None
    finally:
        conn.close()

def log_error(stock_code: str, error_type: str, error_message: str):
    """记录错误日志"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO error_logs (stock_code, error_type, error_message)
        VALUES (?, ?, ?)
        ''', (stock_code, error_type, str(error_message)[:500]))  # 限制错误消息长度
        conn.commit()
    except:
        pass  # 避免日志记录失败影响主要功能
    finally:
        conn.close()

def clean_expired_cache():
    """清理过期的缓存数据"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM fundamental_cache WHERE expires_at < CURRENT_TIMESTAMP')
        cursor.execute('DELETE FROM error_logs WHERE created_at < datetime("now", "-7 days")')  # 保留7天错误日志
        conn.commit()
    finally:
        conn.close()

# 数据库操作函数
def save_stock_to_db(stock_data: dict):
    """保存股票信息到数据库"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO stocks 
        (stock_code, stock_name, added_time, highlight, strategies, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            stock_data['stock_code'],
            stock_data['stock_name'],
            stock_data.get('added_time', datetime.now().isoformat()),
            stock_data.get('highlight', False),
            json.dumps(stock_data.get('strategies', {}))
        ))
        conn.commit()
    finally:
        conn.close()

def get_saved_stocks() -> List[Dict]:
    """获取所有保存的股票信息"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        SELECT stock_code, stock_name, added_time, highlight, strategies
        FROM stocks
        ORDER BY updated_at DESC
        ''')
        
        stocks = []
        for row in cursor.fetchall():
            stock = {
                'stock_code': row[0],
                'stock_name': row[1],
                'added_time': row[2],
                'highlight': bool(row[3]),
                'strategies': json.loads(row[4] if row[4] else '{}')
            }
            stocks.append(stock)
        return stocks
    finally:
        conn.close()

def delete_stock_from_db(stock_code: str):
    """从数据库删除股票"""
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM stocks WHERE stock_code = ?', (stock_code,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

# 配置 CORS 中间件，允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源的请求，为了方便本地开发
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def analyze_stock_highlight_strategy(df: pd.DataFrame):
    """
    分析股票是否符合高亮策略
    策略：最近半个月价格变化不大，并且交易量比之前是缩量状态
    """
    if len(df) < 30:  # 需要至少30天的数据来比较
        return False

    # 1. 定义时间周期
    recent_period = df.tail(15)  # 最近半个月（约15个交易日）
    previous_period = df.iloc[-30:-15] # 再之前半个月

    # 2. 分析价格变化
    # 我们使用收盘价的标准差来衡量价格波动
    recent_price_std = recent_period['收盘'].std()
    previous_price_std = previous_period['收盘'].std()
    
    # 策略：近期波动率小于或等于前期波动率的1.1倍（允许小幅增加）
    price_volatility_condition = recent_price_std <= (previous_price_std * 1.1)

    # 3. 分析交易量
    recent_avg_volume = recent_period['成交量'].mean()
    previous_avg_volume = previous_period['成交量'].mean()

    # 策略：近期平均交易量小于前期平均交易量的 0.8 倍（明显缩量）
    volume_condition = recent_avg_volume < (previous_avg_volume * 0.8)
    
    # 4. 结合两个条件
    if price_volatility_condition and volume_condition:
        return True
    
    return False


def analyze_ma_crossover_strategy(df: pd.DataFrame, short_period=5, long_period=20):
    """
    双均线策略分析
    短期均线上穿长期均线为买入信号，下穿为卖出信号
    """
    if len(df) < max(short_period, long_period):
        return {
            "signal": "insufficient_data",
            "current_trend": "unknown",
            "ma_short": None,
            "ma_long": None
        }
    
    # 计算移动平均线
    df['MA_short'] = df['收盘'].rolling(window=short_period).mean()
    df['MA_long'] = df['收盘'].rolling(window=long_period).mean()
    
    # 获取最新值
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else latest
    
    current_short = latest['MA_short']
    current_long = latest['MA_long']
    prev_short = previous['MA_short']
    prev_long = previous['MA_long']
    
    # 判断信号
    signal = "hold"
    if pd.notna(current_short) and pd.notna(current_long) and pd.notna(prev_short) and pd.notna(prev_long):
        # 金叉：短期均线上穿长期均线
        if prev_short <= prev_long and current_short > current_long:
            signal = "buy"
        # 死叉：短期均线下穿长期均线
        elif prev_short >= prev_long and current_short < current_long:
            signal = "sell"
    
    # 当前趋势
    current_trend = "bullish" if current_short > current_long else "bearish"
    
    return {
        "signal": signal,
        "current_trend": current_trend,
        "ma_short": float(current_short) if pd.notna(current_short) else None,
        "ma_long": float(current_long) if pd.notna(current_long) else None,
        "short_period": short_period,
        "long_period": long_period
    }


def calculate_macd(df: pd.DataFrame, fast_period=12, slow_period=26, signal_period=9):
    """
    计算MACD指标
    """
    if len(df) < slow_period:
        return None, None, None
    
    # 计算EMA
    ema_fast = df['收盘'].ewm(span=fast_period).mean()
    ema_slow = df['收盘'].ewm(span=slow_period).mean()
    
    # MACD线 = 快线EMA - 慢线EMA
    macd_line = ema_fast - ema_slow
    
    # 信号线 = MACD的EMA
    signal_line = macd_line.ewm(span=signal_period).mean()
    
    # 柱状图 = MACD - 信号线
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def analyze_macd_strategy(df: pd.DataFrame):
    """
    MACD策略分析
    MACD上穿信号线为买入信号，下穿为卖出信号
    """
    macd_line, signal_line, histogram = calculate_macd(df)
    
    if macd_line is None or signal_line is None or histogram is None:
        return {
            "signal": "insufficient_data",
            "current_trend": "unknown",
            "macd": None,
            "signal_line": None,
            "histogram": None
        }
    
    # 获取最新值
    latest_macd = macd_line.iloc[-1]
    latest_signal = signal_line.iloc[-1]
    latest_histogram = histogram.iloc[-1]
    
    # 获取前一个值用于判断交叉
    if len(macd_line) > 1:
        prev_macd = macd_line.iloc[-2]
        prev_signal = signal_line.iloc[-2]
    else:
        prev_macd = latest_macd
        prev_signal = latest_signal
    
    # 判断信号
    signal = "hold"
    if pd.notna(latest_macd) and pd.notna(latest_signal) and pd.notna(prev_macd) and pd.notna(prev_signal):
        # 金叉：MACD上穿信号线
        if prev_macd <= prev_signal and latest_macd > latest_signal:
            signal = "buy"
        # 死叉：MACD下穿信号线
        elif prev_macd >= prev_signal and latest_macd < latest_signal:
            signal = "sell"
    
    # 当前趋势
    current_trend = "bullish" if latest_macd > latest_signal else "bearish"
    
    return {
        "signal": signal,
        "current_trend": current_trend,
        "macd": float(latest_macd) if pd.notna(latest_macd) else None,
        "signal_line": float(latest_signal) if pd.notna(latest_signal) else None,
        "histogram": float(latest_histogram) if pd.notna(latest_histogram) else None
    }


def calculate_rsi(df: pd.DataFrame, period=14):
    """
    计算RSI指标
    """
    if len(df) < period + 1:
        return None
    
    # 计算价格变化
    delta = df['收盘'].diff()
    
    # 分离上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 计算平均涨幅和平均跌幅
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # 计算RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def analyze_rsi_strategy(df: pd.DataFrame, period=14, oversold=30, overbought=70):
    """
    RSI策略分析
    RSI < 30 超卖，买入信号
    RSI > 70 超买，卖出信号
    """
    rsi = calculate_rsi(df, period)
    
    if rsi is None or len(rsi) == 0:
        return {
            "signal": "insufficient_data",
            "current_level": "unknown",
            "rsi": None,
            "oversold_threshold": oversold,
            "overbought_threshold": overbought
        }
    
    # 获取最新RSI值
    latest_rsi = rsi.iloc[-1] if hasattr(rsi, 'iloc') else rsi
    
    if pd.isna(latest_rsi):
        return {
            "signal": "insufficient_data",
            "current_level": "unknown",
            "rsi": None,
            "oversold_threshold": oversold,
            "overbought_threshold": overbought
        }
    
    # 判断信号
    signal = "hold"
    current_level = "normal"
    
    if latest_rsi <= oversold:
        signal = "buy"
        current_level = "oversold"
    elif latest_rsi >= overbought:
        signal = "sell"
        current_level = "overbought"
    
    return {
        "signal": signal,
        "current_level": current_level,
        "rsi": float(latest_rsi),
        "oversold_threshold": oversold,
        "overbought_threshold": overbought
    }


def calculate_bollinger_bands(df: pd.DataFrame, period=20, std_dev=2):
    """
    计算布林带
    """
    if len(df) < period:
        return None, None, None
    
    # 中轨：移动平均线
    middle_band = df['收盘'].rolling(window=period).mean()
    
    # 标准差
    std = df['收盘'].rolling(window=period).std()
    
    # 上轨和下轨
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def analyze_bollinger_strategy(df: pd.DataFrame, period=20, std_dev=2):
    """
    布林带策略分析
    价格触及下轨买入，触及上轨卖出
    """
    upper_band, middle_band, lower_band = calculate_bollinger_bands(df, period, std_dev)
    
    if upper_band is None or middle_band is None or lower_band is None:
        return {
            "signal": "insufficient_data",
            "current_position": "unknown",
            "price": None,
            "upper_band": None,
            "middle_band": None,
            "lower_band": None
        }
    
    # 获取最新值
    latest_price = df['收盘'].iloc[-1]
    latest_upper = upper_band.iloc[-1] if hasattr(upper_band, 'iloc') else upper_band
    latest_middle = middle_band.iloc[-1] if hasattr(middle_band, 'iloc') else middle_band
    latest_lower = lower_band.iloc[-1] if hasattr(lower_band, 'iloc') else lower_band
    
    if pd.isna(latest_upper) or pd.isna(latest_lower):
        return {
            "signal": "insufficient_data",
            "current_position": "unknown",
            "price": float(latest_price),
            "upper_band": None,
            "middle_band": None,
            "lower_band": None
        }
    
    # 判断信号
    signal = "hold"
    current_position = "middle"
    
    # 价格相对于布林带的位置
    if latest_price <= latest_lower:
        signal = "buy"
        current_position = "lower"
    elif latest_price >= latest_upper:
        signal = "sell"
        current_position = "upper"
    elif latest_price > latest_middle:
        current_position = "upper_middle"
    else:
        current_position = "lower_middle"
    
    return {
        "signal": signal,
        "current_position": current_position,
        "price": float(latest_price),
        "upper_band": float(latest_upper),
        "middle_band": float(latest_middle),
        "lower_band": float(latest_lower),
        "band_width": float(latest_upper - latest_lower)
    }


def analyze_momentum_strategy(df: pd.DataFrame, lookback_period=20, percentile_threshold=0.8):
    """
    相对强弱动量策略分析
    计算过去N天的价格动量，排名前20%的为强势
    """
    if len(df) < lookback_period + 1:
        return {
            "signal": "insufficient_data",
            "momentum_strength": "unknown",
            "momentum_value": None,
            "lookback_period": lookback_period
        }
    
    # 计算动量：现价/N天前价格 - 1
    current_price = df['收盘'].iloc[-1]
    past_price = df['收盘'].iloc[-(lookback_period + 1)]
    
    momentum = (current_price / past_price) - 1
    
    # 判断动量强度
    signal = "hold"
    momentum_strength = "normal"
    
    # 简化版本：直接根据动量值判断
    if momentum > 0.15:  # 15%以上为强势
        signal = "buy"
        momentum_strength = "strong"
    elif momentum > 0.05:  # 5%-15%为中等
        signal = "hold"
        momentum_strength = "moderate"
    elif momentum > -0.05:  # -5%到5%为正常
        signal = "hold"
        momentum_strength = "normal"
    elif momentum > -0.15:  # -15%到-5%为弱势
        signal = "hold"
        momentum_strength = "weak"
    else:  # -15%以下为极弱
        signal = "sell"
        momentum_strength = "very_weak"
    
    return {
        "signal": signal,
        "momentum_strength": momentum_strength,
        "momentum_value": float(momentum),
        "momentum_percentage": float(momentum * 100),
        "lookback_period": lookback_period
    }


def analyze_breakout_strategy(df: pd.DataFrame, period=20, volume_factor=1.5):
    """
    突破策略分析
    价格突破N日最高价且成交量放大为买入信号
    """
    if len(df) < period + 1:
        return {
            "signal": "insufficient_data",
            "breakout_type": "unknown",
            "current_price": None,
            "resistance_level": None,
            "support_level": None,
            "volume_ratio": None
        }
    
    # 获取最新数据
    current_price = df['收盘'].iloc[-1]
    current_volume = df['成交量'].iloc[-1]
    
    # 计算支撑和阻力位
    historical_data = df.iloc[-(period + 1):-1]  # 排除当天
    resistance_level = historical_data['最高'].max()  # N日最高价
    support_level = historical_data['最低'].min()    # N日最低价
    avg_volume = historical_data['成交量'].mean()  # 平均成交量
    
    # 计算成交量比值
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
    
    # 判断突破类型
    signal = "hold"
    breakout_type = "none"
    
    # 上方突破
    if current_price > resistance_level and volume_ratio >= volume_factor:
        signal = "buy"
        breakout_type = "upward_breakout"
    # 下方突破
    elif current_price < support_level and volume_ratio >= volume_factor:
        signal = "sell"
        breakout_type = "downward_breakout"
    # 接近突破但成交量不足
    elif current_price > resistance_level * 0.98 or current_price < support_level * 1.02:
        signal = "hold"
        breakout_type = "potential_breakout"
    
    return {
        "signal": signal,
        "breakout_type": breakout_type,
        "current_price": float(current_price),
        "resistance_level": float(resistance_level),
        "support_level": float(support_level),
        "volume_ratio": float(volume_ratio),
        "volume_threshold": volume_factor
    }


def get_real_fundamental_data_with_cache(stock_code: str):
    """
    获取真实的基本面数据（集成缓存机制）
    优先使用缓存，缓存未命中时才请求新数据
    """
    # 1. 先尝试从缓存获取
    cached_data = get_fundamental_cache(stock_code)
    if cached_data:
        print(f"使用缓存数据: {stock_code}")
        return cached_data
    
    # 2. 缓存未命中，获取新数据
    try:
        print(f"获取新数据: {stock_code}")
        data = get_real_fundamental_data(stock_code)
        
        # 3. 保存到缓存
        save_fundamental_cache(stock_code, data, expires_hours=6)  # 6小时过期
        
        return data
        
    except Exception as e:
        # 4. 记录错误并返回后备数据
        log_error(stock_code, "fundamental_data_fetch", str(e))
        print(f"获取真实数据失败，使用后备数据: {stock_code}, 错误: {e}")
        
        fallback_data = get_fundamental_data_fallback(stock_code)
        # 也缓存后备数据，但过期时间较短
        save_fundamental_cache(stock_code, fallback_data, expires_hours=1)
        
        return fallback_data

def get_real_fundamental_data(stock_code: str):
    try:
        # 1. 获取个股基本信息
        basic_info = ak.stock_individual_info_em(symbol=stock_code)
        basic_dict = dict(zip(basic_info['item'], basic_info['value']))
        
        # 2. 获取估值数据（市盈率、市净率等）
        try:
            # 获取实时估值数据
            valuation_data = ak.stock_zh_valuation_baidu(symbol=stock_code)
            if not valuation_data.empty:
                latest_valuation = valuation_data.iloc[-1]
                pe_ratio = float(latest_valuation.get('市盈率', 0)) if pd.notna(latest_valuation.get('市盈率')) else None
                pb_ratio = float(latest_valuation.get('市净率', 0)) if pd.notna(latest_valuation.get('市净率')) else None
            else:
                pe_ratio = None
                pb_ratio = None
        except:
            # 如果获取实时估值失败，尝试从基本信息中获取
            pe_ratio = None
            pb_ratio = None
        
        # 3. 获取更及时的财务数据（季度+半年度）
        quarterly_growth, semi_annual_growth, roe, debt_ratio = get_timely_financial_data(stock_code)
        
        # 4. 尝试获取财务指标数据（作为后备）
        try:
            # 使用新的财务摘要接口获取财务指标
            financial_abstract = ak.stock_financial_abstract(symbol=stock_code)
            if not financial_abstract.empty:
                # 查找PE、PB、ROE等数据
                pe_data = financial_abstract[financial_abstract['指标'].str.contains('P/E', na=False)]
                pb_data = financial_abstract[financial_abstract['指标'].str.contains('市净率', na=False)]
                roe_data = financial_abstract[financial_abstract['指标'].str.contains('ROE|\u51c0资产收益率', na=False)]
                debt_data = financial_abstract[financial_abstract['指标'].str.contains('资产负债率', na=False)]
                
                # 提取最新一季度数据（通常是第三列）
                if len(financial_abstract.columns) > 2:
                    latest_col = financial_abstract.columns[2]  # 最新一期数据
                    
                    # 如果季度数据获取失败，使用财务摘要数据作为后备
                    if pe_ratio is None and not pe_data.empty:
                        try:
                            pe_value = pe_data.iloc[0][latest_col]
                            if isinstance(pe_value, str) and pe_value.replace('.', '').replace('-', '').isdigit():
                                pe_ratio = float(pe_value)
                        except:
                            pass
                    
                    if pb_ratio is None and not pb_data.empty:
                        try:
                            pb_value = pb_data.iloc[0][latest_col]
                            if isinstance(pb_value, str) and pb_value.replace('.', '').replace('-', '').isdigit():
                                pb_ratio = float(pb_value)
                        except:
                            pass
                    
                    if roe is None and not roe_data.empty:
                        try:
                            roe_value = roe_data.iloc[0][latest_col]
                            if isinstance(roe_value, str):
                                roe_value = roe_value.replace('%', '')
                                if roe_value.replace('.', '').replace('-', '').isdigit():
                                    roe = float(roe_value)
                        except:
                            pass
                    
                    if debt_ratio is None and not debt_data.empty:
                        try:
                            debt_value = debt_data.iloc[0][latest_col]
                            if isinstance(debt_value, str):
                                debt_value = debt_value.replace('%', '')
                                if debt_value.replace('.', '').replace('-', '').isdigit():
                                    debt_ratio = float(debt_value)
                        except:
                            pass
                    
        except Exception as e:
            print(f"获取财务摘要失败: {e}")
            # 如果都失败了，使用默认值
            if quarterly_growth is None:
                quarterly_growth = 10.0
            if roe is None:
                roe = 15.0
            if debt_ratio is None:
                debt_ratio = 40.0
        
        # 5. 计算股息率（如果有分红数据）
        try:
            # 获取分红数据
            dividend_data = ak.stock_zh_a_gdhs_detail_em(symbol=stock_code)
            if not dividend_data.empty:
                # 计算最近一年的股息率
                recent_dividend = dividend_data.head(1)
                dividend_per_share = float(recent_dividend.iloc[0].get('每股派息', 0)) if not recent_dividend.empty else 0
                current_price = float(basic_dict.get('最新', 1))
                dividend_yield = (dividend_per_share / current_price * 100) if current_price > 0 else 0
            else:
                dividend_yield = 0
        except:
            dividend_yield = 0
        
        # 6. 整理数据，提供默认值
        current_price = float(basic_dict.get('最新', 0))
        market_cap = float(basic_dict.get('总市值', 0)) / 100000000  # 转换为亿元
        
        return {
            "stock_code": stock_code,
            "stock_name": basic_dict.get('股票简称', ''),
            "current_price": current_price,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio or 20.0,  # 默认值
            "pb_ratio": pb_ratio or 2.0,   # 默认值
            "dividend_yield": dividend_yield,
            "roe": roe or 15.0,  # 默认值
            "revenue_growth": quarterly_growth or 10.0,  # 优先使用季度数据
            "semi_annual_growth": semi_annual_growth,  # 新增半年度数据
            "debt_ratio": debt_ratio or 40.0,  # 默认值
            "industry": basic_dict.get('行业', '未知'),
            "list_date": basic_dict.get('上市时间', ''),
            "data_source": "akshare_real_timely",
            "data_period": "quarterly_and_semi_annual",
            "last_update": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"获取真实基本面数据失败 {stock_code}: {e}")
        # 如果获取真实数据失败，返回默认数据结构
        return get_fundamental_data_fallback(stock_code)


def get_timely_financial_data(stock_code: str):
    """
    获取更及时的财务数据（季度和半年度）
    返回: (quarterly_growth, semi_annual_growth, roe, debt_ratio)
    """
    quarterly_growth = None
    semi_annual_growth = None
    roe = None
    debt_ratio = None
    
    try:
        # 1. 使用财务摘要接口获取ROE和资产负债率
        financial_abstract = ak.stock_financial_abstract(symbol=stock_code)
        if not financial_abstract.empty and len(financial_abstract.columns) > 2:
            latest_col = financial_abstract.columns[2]  # 最新一期数据
            
            # 获取ROE
            roe_data = financial_abstract[financial_abstract['指标'].str.contains('ROE|净资产收益率', na=False)]
            if not roe_data.empty:
                try:
                    roe_value = roe_data.iloc[0][latest_col]
                    if pd.notna(roe_value) and roe_value != '' and str(roe_value) != 'NaN':
                        roe = float(roe_value)
                        print(f"ROE获取成功: {roe}%")
                except Exception as e:
                    print(f"ROE解析失败: {e}")
            
            # 获取资产负债率
            debt_data = financial_abstract[financial_abstract['指标'].str.contains('资产负债率', na=False)]
            if not debt_data.empty:
                try:
                    debt_value = debt_data.iloc[0][latest_col]
                    if pd.notna(debt_value) and debt_value != '' and str(debt_value) != 'NaN':
                        debt_ratio = float(debt_value)
                        print(f"资产负债率获取成功: {debt_ratio}%")
                except Exception as e:
                    print(f"资产负债率解析失败: {e}")
            
            # 获取营业收入数据计算增长率
            revenue_data = financial_abstract[financial_abstract['指标'].str.contains('营业总收入', na=False)]
            if not revenue_data.empty and len(financial_abstract.columns) > 6:  # 至少有6季数据
                try:
                    # 获取最新两季和同期两季数据
                    latest_revenue = revenue_data.iloc[0][financial_abstract.columns[2]]  # 最新一季
                    year_ago_revenue = revenue_data.iloc[0][financial_abstract.columns[6]]  # 同期一季
                    
                    if pd.notna(latest_revenue) and pd.notna(year_ago_revenue) and str(latest_revenue) != 'NaN' and str(year_ago_revenue) != 'NaN':
                        latest_revenue = float(latest_revenue)
                        year_ago_revenue = float(year_ago_revenue)
                        
                        if year_ago_revenue > 0:
                            quarterly_growth = ((latest_revenue - year_ago_revenue) / year_ago_revenue) * 100
                            print(f"季度数据: 最新 {latest_revenue}, 同期 {year_ago_revenue}, 增长率 {quarterly_growth:.2f}%")
                except Exception as e:
                    print(f"计算营收增长率失败: {e}")
    
    except Exception as e:
        print(f"获取财务摘要数据失败: {e}")
    
    # 如果没有获取到季度数据，尝试其他方法
    if quarterly_growth is None:
        try:
            # 使用东财接口获取季报数据
            quarterly_report = ak.stock_financial_abstract_ths(symbol=stock_code, indicator="营业收入")
            if not quarterly_report.empty and len(quarterly_report) >= 4:
                quarterly_report = quarterly_report.sort_values('报告期', ascending=False)
                
                latest_q = quarterly_report.iloc[0]['值'] if '值' in quarterly_report.columns else quarterly_report.iloc[0].iloc[-1]
                year_ago_q = quarterly_report.iloc[4]['值'] if len(quarterly_report) > 4 and '值' in quarterly_report.columns else quarterly_report.iloc[-1].iloc[-1]
                
                # 处理数值格式（可能包含万、亿等单位）
                def parse_financial_value(value):
                    if pd.isna(value) or value == '':
                        return 0
                    value_str = str(value)
                    if '万' in value_str:
                        return float(value_str.replace('万', '')) * 10000
                    elif '亿' in value_str:
                        return float(value_str.replace('亿', '')) * 100000000
                    else:
                        return float(value_str)
                
                latest_val = parse_financial_value(latest_q)
                year_ago_val = parse_financial_value(year_ago_q)
                
                if year_ago_val > 0:
                    quarterly_growth = ((latest_val - year_ago_val) / year_ago_val) * 100
                    print(f"东财季度数据: 增长率 {quarterly_growth:.2f}%")
        except Exception as e2:
            print(f"东财季度数据也失败: {e2}")
    
    return quarterly_growth, semi_annual_growth, roe, debt_ratio


def get_fundamental_data_fallback(stock_code: str):
    """
    当真实数据获取失败时的后备方案
    提供基于股票代码的一致性模拟数据（包含季度数据）
    """
    import random
    random.seed(hash(stock_code) % (2**32))
    
    # 模拟季度和半年度数据（通常比年度数据波动更大）
    annual_growth = round(random.uniform(-20, 50), 2)
    quarterly_growth = round(annual_growth + random.uniform(-10, 15), 2)  # 季度数据有一定随机性
    semi_annual_growth = round(annual_growth + random.uniform(-5, 8), 2)   # 半年度数据相对稳定
    
    return {
        "stock_code": stock_code,
        "stock_name": f"股票{stock_code}",
        "current_price": round(random.uniform(5, 50), 2),
        "market_cap": round(random.uniform(50, 5000), 2),
        "pe_ratio": round(random.uniform(8, 50), 2),
        "pb_ratio": round(random.uniform(0.8, 8), 2),
        "dividend_yield": round(random.uniform(0, 8), 2),
        "roe": round(random.uniform(5, 25), 2),
        "revenue_growth": quarterly_growth,  # 优先使用季度数据
        "semi_annual_growth": semi_annual_growth,
        "debt_ratio": round(random.uniform(10, 80), 2),
        "industry": "模拟行业",
        "list_date": "20100101",
        "data_source": "fallback_simulation",
        "data_period": "quarterly_and_semi_annual",
        "last_update": time.strftime('%Y-%m-%d %H:%M:%S')
    }


def analyze_peg_strategy(stock_code: str):
    """
    PEG策略分析（使用真实数据）
    PEG = PE / 增长率，PEG < 1 被低估，PEG > 1 被高估
    """
    try:
        # 使用真实基本面数据
        fundamental_data = get_real_fundamental_data_with_cache(stock_code)
        
        pe_ratio = fundamental_data['pe_ratio']
        growth_rate = fundamental_data['revenue_growth']
        data_source = fundamental_data.get('data_source', 'unknown')
        
        if growth_rate <= 0:
            return {
                "signal": "sell",
                "peg_value": None,
                "pe_ratio": pe_ratio,
                "growth_rate": growth_rate,
                "valuation": "negative_growth",
                "reason": "增长率为负或零",
                "data_source": data_source,
                "stock_name": fundamental_data.get('stock_name', '')
            }
        
        peg_value = pe_ratio / growth_rate
        
        # 判断信号（优化阈值）
        signal = "hold"
        valuation = "fair"
        
        if peg_value < 0.5:
            signal = "buy"
            valuation = "very_undervalued"
        elif peg_value < 1.0:
            signal = "buy" 
            valuation = "undervalued"
        elif peg_value < 1.5:
            signal = "hold"
            valuation = "fair"
        elif peg_value < 2.0:
            signal = "sell"
            valuation = "overvalued"
        else:
            signal = "sell"
            valuation = "very_overvalued"
        
        return {
            "signal": signal,
            "peg_value": round(peg_value, 2),
            "pe_ratio": pe_ratio,
            "growth_rate": growth_rate,
            "valuation": valuation,
            "reason": f"PEG={peg_value:.2f}",
            "data_source": data_source,
            "stock_name": fundamental_data.get('stock_name', ''),
            "market_cap": fundamental_data.get('market_cap', 0),
            "industry": fundamental_data.get('industry', ''),
            "current_price": fundamental_data.get('current_price', 0),
            "calculation_detail": {
                "formula": "PEG = PE率 ÷ 增长率",
                "pe_explanation": "市盈率，反映市场对公司的估值水平",
                "growth_explanation": "营业收入增长率，反映公司的成长性",
                "peg_interpretation": "综合考虑估值和成长性的指标"
            },
            "last_update": fundamental_data.get('last_update', '')
        }
        
    except Exception as e:
        log_error(stock_code, "peg_analysis", str(e))
        return {
            "signal": "insufficient_data",
            "peg_value": None,
            "pe_ratio": None,
            "growth_rate": None,
            "valuation": "unknown",
            "reason": "数据不足",
            "data_source": "error",
            "stock_name": "",
            "error": str(e)
        }


def analyze_value_factor_strategy(stock_code: str):
    """
    价值因子策略分析（使用真实数据）
    综合PE、PB、股息率、ROE等指标进行评分
    """
    try:
        # 使用真实基本面数据
        fundamental_data = get_real_fundamental_data_with_cache(stock_code)
        
        pe_ratio = fundamental_data['pe_ratio']
        pb_ratio = fundamental_data['pb_ratio']
        dividend_yield = fundamental_data['dividend_yield']
        roe = fundamental_data['roe']
        debt_ratio = fundamental_data['debt_ratio']
        data_source = fundamental_data.get('data_source', 'unknown')
        
        # 计算各项评分（优化评分算法）
        # PE评分：低 PE 更好，最伸25%权重
        pe_score = max(0, min(25, (50 - pe_ratio) / 50 * 25)) if pe_ratio > 0 else 0
        
        # PB评分：低 PB 更好，最伸20%权重  
        pb_score = max(0, min(20, (10 - pb_ratio) / 10 * 20)) if pb_ratio > 0 else 0
        
        # 股息率评分：高股息率更好，最伸15%权重
        dividend_score = min(15, dividend_yield / 8 * 15) if dividend_yield >= 0 else 0
        
        # ROE评分：高ROE更好，最伸25%权重
        roe_score = min(25, roe / 25 * 25) if roe > 0 else 0
        
        # 资产负债率评分：低负债率更好，最伸15%权重
        debt_score = max(0, min(15, (100 - debt_ratio) / 100 * 15)) if debt_ratio >= 0 else 0
        
        total_score = pe_score + pb_score + dividend_score + roe_score + debt_score
        
        # 判断信号（优化阈值）
        signal = "hold"
        value_level = "fair"
        
        if total_score >= 85:
            signal = "buy"
            value_level = "excellent"
        elif total_score >= 70:
            signal = "buy"
            value_level = "good"
        elif total_score >= 50:
            signal = "hold"
            value_level = "fair"
        elif total_score >= 30:
            signal = "sell"
            value_level = "poor"
        else:
            signal = "sell"
            value_level = "very_poor"
        
        return {
            "signal": signal,
            "total_score": round(total_score, 1),
            "value_level": value_level,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "dividend_yield": dividend_yield,
            "roe": roe,
            "debt_ratio": debt_ratio,
            "sub_scores": {
                "pe_score": round(pe_score, 1),
                "pb_score": round(pb_score, 1),
                "dividend_score": round(dividend_score, 1),
                "roe_score": round(roe_score, 1),
                "debt_score": round(debt_score, 1)
            },
            "data_source": data_source,
            "stock_name": fundamental_data.get('stock_name', ''),
            "market_cap": fundamental_data.get('market_cap', 0),
            "industry": fundamental_data.get('industry', ''),
            "current_price": fundamental_data.get('current_price', 0)
        }
        
    except Exception as e:
        log_error(stock_code, "value_factor_analysis", str(e))
        return {
            "signal": "insufficient_data",
            "total_score": None,
            "value_level": "unknown",
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "roe": None,
            "debt_ratio": None,
            "sub_scores": {},
            "data_source": "error",
            "stock_name": "",
            "error": str(e)
        }



@app.get("/api/stock/{stock_code}")
async def get_stock_data(stock_code: str):
    """
    根据股票代码获取股票日线数据和策略分析结果
    """
    try:
        # 获取股票历史数据
        # 我们获取最近一年的数据用于分析和展示
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

        if stock_zh_a_hist_df.empty:
            raise HTTPException(status_code=404, detail="未找到该股票代码的数据")
            
        # 获取股票名称
        stock_info = ak.stock_individual_info_em(symbol=stock_code)
        stock_name = stock_info.value[stock_info['item'] == '股票简称'].iloc[0]

        # 分析是否需要高亮
        should_highlight = analyze_stock_highlight_strategy(stock_zh_a_hist_df)
        
        # 运行所有策略分析
        strategies_result = {
            "highlight_strategy": {
                "result": should_highlight,
                "description": "价格稳定性分析和缩量分析"
            },
            # 趋势跟踪策略
            "ma_crossover": analyze_ma_crossover_strategy(stock_zh_a_hist_df.copy()),
            "macd": analyze_macd_strategy(stock_zh_a_hist_df.copy()),
            # 均值回归策略
            "rsi": analyze_rsi_strategy(stock_zh_a_hist_df.copy()),
            "bollinger_bands": analyze_bollinger_strategy(stock_zh_a_hist_df.copy()),
            # 动量策略
            "momentum": analyze_momentum_strategy(stock_zh_a_hist_df.copy()),
            "breakout": analyze_breakout_strategy(stock_zh_a_hist_df.copy()),
            # 基本面量化策略
            "peg": analyze_peg_strategy(stock_code),
            "value_factor": analyze_value_factor_strategy(stock_code),
            # 新增基本面分析维度
            "financial_health": analyze_financial_health_strategy(stock_code)

        }

        # 准备 K 线图数据
        # ECharts 需要的数据格式是 [日期, 开盘, 收盘, 最低, 最高]
        k_line_data = stock_zh_a_hist_df[['日期', '开盘', '收盘', '最低', '最高']].values.tolist()
        
        # 准备成交量数据
        volume_data = stock_zh_a_hist_df[['日期', '成交量']].values.tolist()

        # 保存到数据库
        stock_result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "highlight": should_highlight,
            "k_line_data": k_line_data,
            "volume_data": volume_data,
            "added_time": datetime.now().isoformat(),
            "strategies": strategies_result
        }
        
        save_stock_to_db(stock_result)

        return stock_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{stock_code}/strategies")
async def get_stock_strategies(stock_code: str):
    """
    获取指定股票的所有策略分析结果
    """
    try:
        # 获取股票历史数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

        if stock_zh_a_hist_df.empty:
            raise HTTPException(status_code=404, detail="未找到该股票代码的数据")
        
        # 运行所有策略分析
        strategies_result = {
            "highlight_strategy": {
                "result": analyze_stock_highlight_strategy(stock_zh_a_hist_df.copy()),
                "description": "价格稳定性分析和缩量分析"
            },
            # 趋势跟踪策略
            "ma_crossover": analyze_ma_crossover_strategy(stock_zh_a_hist_df.copy()),
            "macd": analyze_macd_strategy(stock_zh_a_hist_df.copy()),
            # 均值回归策略
            "rsi": analyze_rsi_strategy(stock_zh_a_hist_df.copy()),
            "bollinger_bands": analyze_bollinger_strategy(stock_zh_a_hist_df.copy()),
            # 动量策略
            "momentum": analyze_momentum_strategy(stock_zh_a_hist_df.copy()),
            "breakout": analyze_breakout_strategy(stock_zh_a_hist_df.copy()),
            # 基本面量化策略
            "peg": analyze_peg_strategy(stock_code),
            "value_factor": analyze_value_factor_strategy(stock_code),
            # 新增基本面分析维度
            "financial_health": analyze_financial_health_strategy(stock_code)
        }
        
        return {
            "stock_code": stock_code,
            "analysis_time": datetime.now().isoformat(),
            "strategies": strategies_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stocks")
async def get_all_stocks():
    """
    获取所有已保存的股票信息
    """
    try:
        saved_stocks = get_saved_stocks()
        return {"stocks": saved_stocks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/stock/{stock_code}")
async def delete_stock(stock_code: str):
    """
    删除指定的股票
    """
    try:
        success = delete_stock_from_db(stock_code)
        if success:
            return {"message": f"股票 {stock_code} 已删除"}
        else:
            raise HTTPException(status_code=404, detail="股票不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def analyze_financial_health_strategy(stock_code: str):
    """
    财务健康策略分析（使用更及时的季度数据）
    综合资产负债率、流动比率、盈利能力等指标评估财务健康状况
    """
    try:
        fundamental_data = get_real_fundamental_data_with_cache(stock_code)
        
        debt_ratio = fundamental_data['debt_ratio']
        roe = fundamental_data['roe']
        revenue_growth = fundamental_data['revenue_growth']  # 现在优先使用季度数据
        semi_annual_growth = fundamental_data.get('semi_annual_growth')  # 半年度数据
        market_cap = fundamental_data.get('market_cap', 0)
        data_period = fundamental_data.get('data_period', 'annual')
        
        # 财务健康评分系统（优化后的评分）
        health_score = 0
        
        # 1. 资产负债率评分 (30%权重)
        if debt_ratio < 30:
            debt_score = 30
        elif debt_ratio < 50:
            debt_score = 20
        elif debt_ratio < 70:
            debt_score = 10
        else:
            debt_score = 0
        
        # 2. ROE评分 (25%权重)
        if roe > 20:
            roe_score = 25
        elif roe > 15:
            roe_score = 20
        elif roe > 10:
            roe_score = 15
        elif roe > 5:
            roe_score = 10
        else:
            roe_score = 0
        
        # 3. 增长稳定性评分 (25%权重) - 优先使用季度数据
        growth_data = revenue_growth
        growth_period = '季度同比'
        
        # 如果有半年度数据，也考虑在内（作为参考）
        if semi_annual_growth is not None:
            # 使用加权平均，季度数据权重60%，半年度数据权重40%
            growth_data = revenue_growth * 0.6 + semi_annual_growth * 0.4
            growth_period = '综合同比(季度+半年)'
        
        if growth_data > 20:
            growth_score = 25
        elif growth_data > 10:
            growth_score = 20
        elif growth_data > 5:
            growth_score = 15
        elif growth_data > 0:
            growth_score = 10
        else:
            growth_score = 0
        
        # 4. 市值规模评分 (20%权重)
        if market_cap > 1000:
            size_score = 20
        elif market_cap > 500:
            size_score = 15
        elif market_cap > 100:
            size_score = 10
        elif market_cap > 50:
            size_score = 5
        else:
            size_score = 0
        
        health_score = debt_score + roe_score + growth_score + size_score
        
        # 判断财务健康等级
        if health_score >= 80:
            health_level = "excellent"
            signal = "buy"
        elif health_score >= 65:
            health_level = "good"
            signal = "buy"
        elif health_score >= 50:
            health_level = "fair"
            signal = "hold"
        elif health_score >= 30:
            health_level = "poor"
            signal = "sell"
        else:
            health_level = "very_poor"
            signal = "sell"
        
        return {
            "signal": signal,
            "health_score": round(health_score, 1),
            "health_level": health_level,
            "debt_ratio": debt_ratio,
            "roe": roe,
            "revenue_growth": revenue_growth,
            "semi_annual_growth": semi_annual_growth,
            "combined_growth": round(growth_data, 2) if growth_data != revenue_growth else None,
            "growth_period": growth_period,
            "market_cap": market_cap,
            "sub_scores": {
                "debt_score": debt_score,
                "roe_score": roe_score,
                "growth_score": growth_score,
                "size_score": size_score
            },
            "data_source": fundamental_data.get('data_source', 'unknown'),
            "data_period": data_period,
            "stock_name": fundamental_data.get('stock_name', ''),
            "last_update": fundamental_data.get('last_update', '')
        }
        
    except Exception as e:
        log_error(stock_code, "financial_health_analysis", str(e))
        return {
            "signal": "insufficient_data",
            "health_score": None,
            "health_level": "unknown",
            "growth_period": "data_unavailable",
            "error": str(e)
        }

if __name__ == "__main__":
    # 初始化数据库
    init_database()
    # 清理过期缓存
    clean_expired_cache()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)