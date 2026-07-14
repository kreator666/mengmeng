
# SOXL_USDT 9:00 抄底做多因子 - 可复用代码

import pandas as pd
import numpy as np

def calculate_panic_bottom_factors(df):
    """
    计算恐慌性抄底因子
    适用于：连续暴跌后的抄底做多场景
    """
    factors = pd.DataFrame(index=df.index)

    # 1. 基础价格行为
    factors['body'] = df['close'] - df['open']
    factors['range'] = df['high'] - df['low']
    factors['lower_shadow'] = np.minimum(df['open'], df['close']) - df['low']
    factors['lower_shadow_pct'] = factors['lower_shadow'] / factors['range'] * 100
    factors['upper_shadow'] = df['high'] - np.maximum(df['open'], df['close'])
    factors['upper_shadow_pct'] = factors['upper_shadow'] / factors['range'] * 100
    factors['body_pct'] = abs(factors['body']) / factors['range'] * 100
    factors['rebound_strength'] = (df['close'] - df['low']) / factors['range'] * 100

    # 2. 连续下跌统计
    factors['is_down'] = df['close'] < df['open']
    factors['consecutive_down'] = factors['is_down'].astype(int).groupby((~factors['is_down']).astype(int).cumsum()).cumsum()

    # 3. 短期跌幅
    factors['return_1'] = df['close'].pct_change(1) * 100
    factors['return_2'] = df['close'].pct_change(2) * 100
    factors['return_3'] = df['close'].pct_change(3) * 100
    factors['return_5'] = df['close'].pct_change(5) * 100

    # 4. 新低判断
    factors['new_low_5'] = df['low'] == df['low'].rolling(5).min()
    factors['new_low_10'] = df['low'] == df['low'].rolling(10).min()
    factors['new_low_20'] = df['low'] == df['low'].rolling(20).min()

    # 5. RSI超卖
    def rsi(prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    factors['rsi_3'] = rsi(df['close'], 3)
    factors['rsi_7'] = rsi(df['close'], 7)
    factors['rsi_14'] = rsi(df['close'], 14)

    # 6. 成交量
    factors['volume_ma5'] = df['volume'].rolling(5).mean()
    factors['volume_ratio'] = df['volume'] / factors['volume_ma5']
    factors['volume_ma10'] = df['volume'].rolling(10).mean()
    factors['volume_ratio_10'] = df['volume'] / factors['volume_ma10']

    # 7. 均线状态
    factors['ma5'] = df['close'].rolling(5).mean()
    factors['ma10'] = df['close'].rolling(10).mean()
    factors['ma20'] = df['close'].rolling(20).mean()
    factors['close_below_ma5'] = df['close'] < factors['ma5']
    factors['close_below_ma10'] = df['close'] < factors['ma10']
    factors['close_below_ma20'] = df['close'] < factors['ma20']
    factors['bearish_alignment'] = (factors['ma5'] < factors['ma10']) & (factors['ma10'] < factors['ma20'])

    # 8. MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    factors['macd_hist'] = macd_hist
    factors['macd_hist_prev'] = macd_hist.shift(1)
    factors['macd_hist_change'] = macd_hist - factors['macd_hist_prev']

    # 9. 布林带
    bb_middle = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    bb_lower = bb_middle - 2 * bb_std
    factors['bb_position'] = (df['close'] - bb_lower) / (4 * bb_std)

    # 10. 破底翻结构
    factors['lower_than_prev'] = df['low'] < df['low'].shift(1)
    factors['close_higher_than_prev'] = df['close'] > df['close'].shift(1)
    factors['break_bottom_reverse'] = factors['lower_than_prev'] & factors['close_higher_than_prev']

    # 11. 恐慌放量后缩量
    factors['panic_volume'] = df['volume'] > df['volume'].rolling(10).mean() * 2
    factors['volume_decrease'] = df['volume'] < df['volume'].shift(1)
    factors['panic_then_calm'] = factors['panic_volume'].shift(1) & factors['volume_decrease']

    return factors


def panic_bottom_signal(factors, idx):
    """
    判断是否为恐慌抄底信号
    返回: (是否信号, 信号强度0-100, 理由)
    """
    score = 0
    reasons = []

    # 1. 长下影线 (>40%)
    if factors.loc[idx, 'lower_shadow_pct'] > 40:
        score += 25
        reasons.append("长下影线%.1f%%" % factors.loc[idx, 'lower_shadow_pct'])
    elif factors.loc[idx, 'lower_shadow_pct'] > 30:
        score += 15
        reasons.append("下影线%.1f%%" % factors.loc[idx, 'lower_shadow_pct'])

    # 2. 连续下跌 (>=2)
    if factors.loc[idx, 'consecutive_down'] >= 3:
        score += 20
        reasons.append("连续下跌%.0f根" % factors.loc[idx, 'consecutive_down'])
    elif factors.loc[idx, 'consecutive_down'] >= 2:
        score += 10
        reasons.append(f"连续下跌{factors.loc[idx, 'consecutive_down']:.0f}根")

    # 3. 短期超跌 (<-5%)
    if factors.loc[idx, 'return_2'] < -10:
        score += 20
        reasons.append("2期跌幅%.1f%%" % factors.loc[idx, 'return_2'])
    elif factors.loc[idx, 'return_2'] < -5:
        score += 10
        reasons.append(f"2期跌幅{factors.loc[idx, 'return_2']:.1f}%")

    # 4. RSI超卖
    if factors.loc[idx, 'rsi_3'] < 10:
        score += 15
        reasons.append("RSI(3)=%.1f极度超卖" % factors.loc[idx, 'rsi_3'])
    elif factors.loc[idx, 'rsi_14'] < 30:
        score += 10
        reasons.append("RSI(14)=%.1f超卖" % factors.loc[idx, 'rsi_14'])

    # 5. 新低
    if factors.loc[idx, 'new_low_10']:
        score += 10
        reasons.append("10期新低")

    # 6. 破底翻
    if factors.loc[idx, 'break_bottom_reverse']:
        score += 10
        reasons.append("破底翻结构")

    # 7. 放量恐慌后承接
    if factors.loc[idx, 'volume_ratio'] > 1.5:
        score += 5
        reasons.append("量比%.2f" % factors.loc[idx, 'volume_ratio'])

    is_signal = score >= 50
    return is_signal, min(score, 100), reasons


def factor(df):
    """
    系统回测接口：接收 OHLCV DataFrame，返回信号 Series
    正值 = 恐慌抄底信号触发，0 = 无信号
    """
    import numpy as np

    factors = calculate_panic_bottom_factors(df)
    signal_values = np.zeros(len(df))

    for i in range(len(df)):
        idx = df.index[i]
        is_signal, score, _ = panic_bottom_signal(factors, idx)
        if is_signal:
            signal_values[i] = score

    return pd.Series(signal_values, index=df.index)


# 使用示例
# signal = factor(df)
# factors = calculate_panic_bottom_factors(df)
# is_signal, score, reasons = panic_bottom_signal(factors, idx)
