"""
백테스트 엔진
과거 OHLCV 데이터 기반 전략 성과 시뮬레이션
기간별 (1Y / 2Y / 3Y) 상세 리포트 생성
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from core.strategy import StrategyEngine
from core.config import CFG
import logging

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str          # "long" | "short"
    entry_price: float
    exit_price: float
    pnl_pct: float          # 레버리지 적용 수익률 (%)
    pnl_usdt: float
    exit_reason: str        # "tp" | "sl" | "signal"


@dataclass
class BacktestReport:
    symbol: str
    period_label: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl_pct: float
    total_pnl_usdt: float
    max_drawdown_pct: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    sharpe_ratio: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)


class BacktestEngine:
    """
    벡터화 백테스트 엔진
    ccxt를 통해 받은 OHLCV DataFrame으로 전략을 시뮬레이션
    """

    def __init__(self):
        self.strategy = StrategyEngine()
        self.cfg = CFG

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        period_label: str = "1년",
        initial_capital: float = 100.0,
    ) -> BacktestReport:
        """
        백테스트 실행

        Parameters
        ----------
        df : OHLCV DataFrame (timestamp index)
        symbol : 심볼 이름
        period_label : 표시용 기간 레이블
        initial_capital : 초기 자금 (USDT)
        """
        if df.empty or len(df) < 250:
            return self._empty_report(symbol, period_label)

        # 지표 계산
        df = self.strategy.calculate_indicators(df)
        if df.empty:
            return self._empty_report(symbol, period_label)

        capital = initial_capital
        equity_curve = [capital]
        trades: List[Trade] = []

        in_position = False
        entry_idx = 0
        direction = "none"
        entry_price = 0.0

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        times = df.index
        
        ema200 = df["ema200"].values
        bb_upper = df["bb_upper"].values
        bb_lower = df["bb_lower"].values
        macd_hist = df["macd_hist"].values
        rsi = df["rsi"].values

        sl_pct = self.cfg.STOP_LOSS_PCT
        tp_pct = self.cfg.TAKE_PROFIT_PCT
        commission = self.cfg.BT_COMMISSION
        slippage = self.cfg.BT_SLIPPAGE

        for i in range(2, len(df)):
            price = closes[i]

            # 신호 평가
            sig_dir = "none"
            if not in_position:
                prev_close = closes[i-1]
                prev2_close = closes[i-2]
                prev_lower = bb_lower[i-1]
                prev2_lower = bb_lower[i-2]
                prev_upper = bb_upper[i-1]
                prev2_upper = bb_upper[i-2]
                prev_hist = macd_hist[i-1]
                cur_hist = macd_hist[i]

                long_ema = price > ema200[i]
                long_bb = (prev_close <= prev_lower or prev2_close <= prev2_lower) and price > bb_lower[i]
                long_macd = prev_hist < 0 and cur_hist > prev_hist
                long_rsi = rsi[i] < 60

                short_ema = price < ema200[i]
                short_bb = (prev_close >= prev_upper or prev2_close >= prev2_upper) and price < bb_upper[i]
                short_macd = prev_hist > 0 and cur_hist < prev_hist
                short_rsi = rsi[i] > 40

                if long_ema and long_bb and long_macd and long_rsi and self.cfg.ALLOW_LONG:
                    sig_dir = "long"
                elif short_ema and short_bb and short_macd and short_rsi and self.cfg.ALLOW_SHORT:
                    sig_dir = "short"

                if sig_dir in ("long", "short"):
                    adjusted_entry = price * (
                        1 + slippage + commission
                        if sig_dir == "long"
                        else 1 - slippage - commission
                    )
                    in_position = True
                    direction = sig_dir
                    entry_price = adjusted_entry
                    entry_idx = i

            else:
                # SL / TP 체크 (고가/저가 기준)
                sl_hit = tp_hit = False
                exit_price = price
                exit_reason = "signal"

                if direction == "long":
                    sl_level = entry_price * (1 - sl_pct)
                    tp_level = entry_price * (1 + tp_pct)
                    if lows[i] <= sl_level:
                        sl_hit = True
                        exit_price = sl_level
                        exit_reason = "sl"
                    elif highs[i] >= tp_level:
                        tp_hit = True
                        exit_price = tp_level
                        exit_reason = "tp"
                    elif sig_dir == "short":
                        exit_reason = "signal"
                else:
                    sl_level = entry_price * (1 + sl_pct)
                    tp_level = entry_price * (1 - tp_pct)
                    if highs[i] >= sl_level:
                        sl_hit = True
                        exit_price = sl_level
                        exit_reason = "sl"
                    elif lows[i] <= tp_level:
                        tp_hit = True
                        exit_price = tp_level
                        exit_reason = "tp"
                    elif sig_dir == "long":
                        exit_reason = "signal"

                if sl_hit or tp_hit or (sig_dir != direction and sig_dir != "none"):
                    # 청산 수수료 적용
                    adj_exit = exit_price * (
                        1 - commission - slippage
                        if direction == "long"
                        else 1 + commission + slippage
                    )
                    if direction == "long":
                        raw_return = (adj_exit - entry_price) / entry_price
                    else:
                        raw_return = (entry_price - adj_exit) / entry_price

                    leveraged_return = raw_return * self.cfg.LEVERAGE
                    pnl_usdt = capital * (getattr(self.cfg, 'MARGIN_USDT', 1.0) / initial_capital) * leveraged_return
                    capital += pnl_usdt

                    trade = Trade(
                        symbol=symbol,
                        entry_time=times[entry_idx],
                        exit_time=times[i],
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=adj_exit,
                        pnl_pct=round(leveraged_return * 100, 2),
                        pnl_usdt=round(pnl_usdt, 4),
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)
                    equity_curve.append(round(capital, 4))

                    in_position = False
                    direction = "none"
                    entry_price = 0.0

        return self._compile_report(
            symbol=symbol,
            period_label=period_label,
            start_date=str(df.index[0].date()),
            end_date=str(df.index[-1].date()),
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=initial_capital,
            df=df,
        )

    def _compile_report(
        self,
        symbol: str,
        period_label: str,
        start_date: str,
        end_date: str,
        trades: List[Trade],
        equity_curve: List[float],
        initial_capital: float,
        df: pd.DataFrame,
    ) -> BacktestReport:
        if not trades:
            return self._empty_report(symbol, period_label)

        wins = [t for t in trades if t.pnl_usdt > 0]
        losses = [t for t in trades if t.pnl_usdt <= 0]

        total_win = sum(t.pnl_usdt for t in wins)
        total_loss = abs(sum(t.pnl_usdt for t in losses))
        profit_factor = round(total_win / total_loss, 2) if total_loss > 0 else 999.0

        # 최대 낙폭 (MDD)
        eq = np.array(equity_curve)
        peak = np.maximum.accumulate(eq)
        drawdown = (eq - peak) / peak
        mdd = round(float(drawdown.min()) * 100, 2)

        # 샤프 비율 (간략 계산)
        returns = np.diff(eq) / eq[:-1]
        sharpe = (
            round(float(np.mean(returns) / np.std(returns) * np.sqrt(252)), 2)
            if np.std(returns) > 0 else 0.0
        )

        # 월별 수익률
        monthly: Dict[str, float] = {}
        for t in trades:
            key = t.entry_time.strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0) + t.pnl_pct

        final_capital = equity_curve[-1] if equity_curve else initial_capital
        total_pnl_pct = round((final_capital - initial_capital) / initial_capital * 100, 2)

        return BacktestReport(
            symbol=symbol,
            period_label=period_label,
            start_date=start_date,
            end_date=end_date,
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=round(len(wins) / len(trades) * 100, 1) if trades else 0,
            total_pnl_pct=total_pnl_pct,
            total_pnl_usdt=round(final_capital - initial_capital, 2),
            max_drawdown_pct=mdd,
            profit_factor=profit_factor,
            avg_win_pct=round(np.mean([t.pnl_pct for t in wins]), 2) if wins else 0,
            avg_loss_pct=round(np.mean([t.pnl_pct for t in losses]), 2) if losses else 0,
            sharpe_ratio=sharpe,
            trades=trades,
            equity_curve=equity_curve,
            monthly_returns=dict(sorted(monthly.items())),
        )

    def _empty_report(self, symbol: str, period_label: str) -> BacktestReport:
        return BacktestReport(
            symbol=symbol, period_label=period_label,
            start_date="", end_date="",
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0, total_pnl_pct=0, total_pnl_usdt=0,
            max_drawdown_pct=0, profit_factor=0,
            avg_win_pct=0, avg_loss_pct=0, sharpe_ratio=0,
        )
