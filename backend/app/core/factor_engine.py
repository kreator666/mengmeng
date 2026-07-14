import ast
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


class FactorEngineError(Exception):
    """因子引擎错误"""


class SafePythonExecutor:
    """
    使用 AST 白名单执行的 Python 代码沙箱
    """

    ALLOWED_NODES = (
        ast.Module,
        ast.Expression,
        ast.FunctionDef,
        ast.Return,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Param,
        ast.Constant,
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,
        ast.IfExp,
        ast.Subscript,
        ast.Attribute,
        ast.Slice,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Expr,
        ast.Assign,
        ast.AnnAssign,
        ast.arguments,
        ast.arg,
        ast.keyword,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Not,
        ast.And,
        ast.Or,
        ast.BitAnd,
        ast.BitOr,
        ast.Invert,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
    )

    @classmethod
    def validate(cls, code: str):
        tree = ast.parse(code, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, cls.ALLOWED_NODES):
                raise FactorEngineError(f"不允许的语法: {type(node).__name__}")

    @classmethod
    def execute(cls, code: str, namespace: dict) -> Any:
        cls.validate(code)
        tree = ast.parse(code, mode="eval")
        compiled = compile(tree, filename="<factor>", mode="eval")
        return eval(compiled, {"__builtins__": {}}, namespace)


def build_builtin_namespace(df: pd.DataFrame) -> dict:
    """
    构建内置因子函数命名空间
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    _open = df["open"]

    def MA(series, n):
        return series.rolling(window=n).mean()

    def EMA(series, n):
        return series.ewm(span=n, adjust=False).mean()

    def WMA(series, n):
        weights = pd.Series(range(1, n + 1))
        return series.rolling(window=n).apply(lambda x: (x * weights.values).sum() / weights.sum(), raw=True)

    def RSI(series, n=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=n).mean()
        avg_loss = loss.rolling(window=n).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def MOM(series, n=10):
        return series.diff(n)

    def ROC(series, n=10):
        return series.pct_change(n)

    def STD(series, n=20):
        return series.rolling(window=n).std()

    def VAR(series, n=20):
        return series.rolling(window=n).var()

    def ATR(high, low, close, n=14):
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=n).mean()

    def BOLL(series, n=20, std=2):
        ma = series.rolling(window=n).mean()
        s = series.rolling(window=n).std()
        return (series - ma) / (s * std).replace(0, np.nan)

    def ZSCORE(series, n=20):
        s = series.rolling(window=n).std().replace(0, np.nan)
        return (series - series.rolling(window=n).mean()) / s

    def PERCENTILE(series, n=20):
        return series.rolling(window=n).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)

    def VOL_MA(series, n=5):
        return series.rolling(window=n).mean()

    def OBV(close, volume):
        obv = [0.0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i - 1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i - 1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=close.index)

    def VWAP(high, low, close, volume):
        typical = (high + low + close) / 3
        return (typical * volume).cumsum() / volume.cumsum()

    def MACD(series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        return ema_fast - ema_slow

    def ADX(high, low, close, n=14):
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        plus_dm = (high - high.shift(1)).clip(lower=0)
        minus_dm = (low.shift(1) - low).clip(lower=0)
        atr_val = tr.rolling(window=n).mean().replace(0, np.nan)
        plus_di = 100 * plus_dm.rolling(window=n).mean() / atr_val
        minus_di = 100 * minus_dm.rolling(window=n).mean() / atr_val
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan) * 100
        return dx.rolling(window=n).mean()

    def STOCH(high, low, close, n=14):
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        denom = highest_high - lowest_low
        return 100 * (close - lowest_low) / denom.replace(0, np.nan)

    def CCI(high, low, close, n=20):
        typical = (high + low + close) / 3
        sma = typical.rolling(window=n).mean()
        mean_dev = typical.rolling(window=n).apply(lambda x: abs(x - x.mean()).mean(), raw=False)
        return (typical - sma) / (0.015 * mean_dev.replace(0, np.nan))

    def VOL_RATIO(volume, n=5):
        return volume.rolling(window=n).mean() / volume.rolling(window=20).mean().replace(0, np.nan)

    def SMA(series, n):
        return series.rolling(window=n).mean()

    def AND(a, b):
        return a.astype(bool) & b.astype(bool)

    def OR(a, b):
        return a.astype(bool) | b.astype(bool)

    def NOT(a):
        return ~a.astype(bool)

    namespace = {
        "MA": MA,
        "SMA": SMA,
        "EMA": EMA,
        "WMA": WMA,
        "RSI": RSI,
        "MOM": MOM,
        "ROC": ROC,
        "STD": STD,
        "VAR": VAR,
        "ATR": ATR,
        "BOLL": BOLL,
        "ZSCORE": ZSCORE,
        "PERCENTILE": PERCENTILE,
        "VOL_MA": VOL_MA,
        "OBV": OBV,
        "VWAP": VWAP,
        "MACD": MACD,
        "ADX": ADX,
        "STOCH": STOCH,
        "CCI": CCI,
        "VOL_RATIO": VOL_RATIO,
        "AND": AND,
        "OR": OR,
        "NOT": NOT,
        "close": close,
        "open": _open,
        "high": high,
        "low": low,
        "volume": volume,
        "np": np,
        "pd": pd,
        "int": int,
        "float": float,
        "bool": bool,
    }
    return namespace


def eval_formula(df: pd.DataFrame, expression: str) -> pd.Series:
    """
    解析并执行因子公式表达式
    """
    if not expression or not expression.strip():
        return pd.Series(0.0, index=df.index)

    ns = build_builtin_namespace(df)
    expr = expression

    try:
        result = SafePythonExecutor.execute(expr, ns)
    except Exception as e:
        raise FactorEngineError(f"公式执行失败: {e}")

    if isinstance(result, pd.Series):
        return result
    if isinstance(result, (int, float, bool, np.number)):
        return pd.Series(float(result), index=df.index)
    raise FactorEngineError(f"不支持的因子返回类型: {type(result)}")


def eval_python_code(df: pd.DataFrame, code: str) -> pd.Series:
    """
    执行用户自定义 Python 代码（沙箱环境）
    用户代码需定义 factor(df) 函数并返回 Series
    """
    if not code or not code.strip():
        return pd.Series(0.0, index=df.index)

    ns = build_builtin_namespace(df)
    ns["df"] = df

    # 验证 AST 安全性（exec 模式支持函数定义）
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if not isinstance(node, SafePythonExecutor.ALLOWED_NODES):
            raise FactorEngineError(f"不允许的语法: {type(node).__name__}")

    globals_ns = {**ns, "__builtins__": {}}
    exec(compile(tree, filename="<user_factor>", mode="exec"), globals_ns)

    if "factor" not in globals_ns or not callable(globals_ns["factor"]):
        raise FactorEngineError("用户代码必须定义 factor(df) 函数")

    result = globals_ns["factor"](df)
    if not isinstance(result, pd.Series):
        raise FactorEngineError("factor(df) 必须返回 pandas.Series")
    return result


def signal_to_position(signal: pd.Series, threshold: float = 0.0, allow_short: bool = False) -> pd.Series:
    """
    将连续信号转换为离散仓位
    """
    pos = pd.Series(0, index=signal.index, dtype=float)
    pos[signal > threshold] = 1.0
    if allow_short:
        pos[signal < -threshold] = -1.0
    return pos


def combine_factors_equal(factors: list[pd.Series]) -> pd.Series:
    """等权组合"""
    if not factors:
        return pd.Series()
    df = pd.concat(factors, axis=1)
    return df.mean(axis=1)


def combine_factors_weighted(factors: list[pd.Series], weights: list[float]) -> pd.Series:
    """加权组合"""
    if not factors or len(factors) != len(weights):
        raise FactorEngineError("因子数量与权重数量不匹配")
    df = pd.concat(factors, axis=1)
    w = np.array(weights)
    w = w / w.sum()
    return (df * w).sum(axis=1)


def calculate_ic(factor: pd.Series, returns: pd.Series, method: str = "spearman") -> float:
    """
    计算因子 IC 值（默认 Spearman 秩相关系数）
    """
    aligned = pd.concat([factor, returns.shift(-1)], axis=1).dropna()
    if len(aligned) < 10:
        return 0.0
    f, r = aligned.iloc[:, 0], aligned.iloc[:, 1]
    if method == "spearman":
        corr, _ = stats.spearmanr(f, r)
    else:
        corr, _ = stats.pearsonr(f, r)
    return float(corr) if not np.isnan(corr) else 0.0


def calculate_rolling_ic(factor: pd.Series, returns: pd.Series, window: int = 30) -> pd.Series:
    """
    计算滚动 IC 时间序列
    """
    aligned = pd.concat([factor, returns.shift(-1)], axis=1).dropna()
    f, r = aligned.iloc[:, 0], aligned.iloc[:, 1]
    return f.rolling(window=window).corr(r, method="spearman")


def get_builtin_factors() -> list[dict[str, Any]]:
    """获取内置因子列表"""
    return [
        {"name": "MA", "category": "趋势", "signature": "MA(close, n)", "description": "简单移动平均线"},
        {"name": "EMA", "category": "趋势", "signature": "EMA(close, n)", "description": "指数移动平均线"},
        {"name": "WMA", "category": "趋势", "signature": "WMA(close, n)", "description": "加权移动平均线"},
        {"name": "MACD", "category": "趋势", "signature": "MACD(close, fast, slow, signal)", "description": "MACD 指标"},
        {"name": "ADX", "category": "趋势", "signature": "ADX(high, low, close, n)", "description": "平均趋向指数"},
        {"name": "RSI", "category": "动量", "signature": "RSI(close, n)", "description": "相对强弱指标"},
        {"name": "MOM", "category": "动量", "signature": "MOM(close, n)", "description": "动量指标"},
        {"name": "ROC", "category": "动量", "signature": "ROC(close, n)", "description": "变化率指标"},
        {"name": "STOCH", "category": "动量", "signature": "STOCH(high, low, close, n)", "description": "随机指标"},
        {"name": "CCI", "category": "动量", "signature": "CCI(high, low, close, n)", "description": "顺势指标"},
        {"name": "ATR", "category": "波动", "signature": "ATR(high, low, close, n)", "description": "真实波动幅度均值"},
        {"name": "BOLL", "category": "波动", "signature": "BOLL(close, n, std)", "description": "布林带偏离"},
        {"name": "STD", "category": "波动", "signature": "STD(close, n)", "description": "标准差"},
        {"name": "VAR", "category": "波动", "signature": "VAR(close, n)", "description": "方差"},
        {"name": "OBV", "category": "成交量", "signature": "OBV(close, volume)", "description": "能量潮指标"},
        {"name": "VWAP", "category": "成交量", "signature": "VWAP(high, low, close, volume)", "description": "成交量加权平均价"},
        {"name": "VOL_MA", "category": "成交量", "signature": "VOL_MA(volume, n)", "description": "成交量均线"},
        {"name": "VOL_RATIO", "category": "成交量", "signature": "VOL_RATIO(volume, n)", "description": "成交量比率"},
        {"name": "ZSCORE", "category": "统计", "signature": "ZSCORE(close, n)", "description": "Z-Score 标准化"},
        {"name": "PERCENTILE", "category": "统计", "signature": "PERCENTILE(close, n)", "description": "滚动分位数"},
    ]
