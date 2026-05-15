# Project Status: AI QUANTUM OKX Auto-Trader

## Current Status
- Initialized Streamlit dashboard with OKX API integration.
- Added auto-connect feature via `.env`.
- Fixed SL/TP sliders display logic.
- Fixed the empty keys bug that caused balance to show as 0 upon clicking "OKX ?곌껐".
- Fixed MDD Limit slider UI to show accurate percentage scale (5% ~ 50%).
- Added "?렞 ?ъ???吏꾩엯" tab between "留ㅻℓ ?대젰" and "?ㅼ젙" to display and adjust MACD, BB, and EMA entry conditions.
- Fixed an issue where `load_dotenv()` failed to hot-reload `.env` edits and UI inputs cached empty values.
- Fixed scanner yielding empty results because OKX's `quoteVolume` returned None, by manually calculating `baseVolume * last_price`.
- Fixed backtest "?곗씠???놁쓬" error by implementing pagination in `get_ohlcv` to fetch up to 1500+ candles and rewriting the backtest loop to be fully vectorized instead of losing history through sliced indicator calculations.
- Wrote a comprehensive operational manual (`4ref.md`) detailing the Triple-Indicator strategy, risk management logic, and dashboard features.
- Added "利됱떆泥?궛" buttons for individual positions and a "紐⑤뱺 醫낅ぉ ?쇨큵泥?궛" button for bulk liquidation.
- Adjusted liquidation buttons' font size and height to 77% of standard size for a more compact UI.
- Fixed `ModuleNotFoundError: plotly` by reinstalling dependencies in the correct Python environment.
- Restored and verified dashboard functionality on port 8502.
- Updated Trade History to display the latest trades at the top.
- Updated Backtest Trade List to display the latest trades at the top.
- **Implemented Orchestration Engine (`QuantumEngine`):** Centralized module management for Exchange, Scanner, and Trader.
- **Implemented Test Harness (`harness.py`):** Independent verification environment for core trading logic without UI dependency.

















- **[v1.2.27] Enhanced Trade History:** Added 'Type' (Entry/Exit), 'PnL', and 'PnL %' fields with Red/Blue color styling for closed trades.
















- **[v1.2.27] Enhanced Trade History:** Added 'Type' (Entry/Exit), 'PnL', and 'PnL %' fields with Red/Blue color styling for closed trades.

## Active Issues
- None.

## Next Steps
- Implement advanced risk management features (e.g., dynamic TP/SL).
- Enhance the Test Harness with mock exchange capabilities for CI/CD.

## v1.1.10 (2026-05-10)
- [Feature] ?숈쟻 ?먭툑 愿由?1% Rule) ?곸슜: 怨좎젙 吏꾩엯湲덉븸???먯??섍퀬 ?꾩껜 ?붽퀬??1%瑜?利앷굅湲덉쑝濡??ъ슜?섎룄濡?蹂寃?
- [Feature] One-Shot Rule: ?숈씪 醫낅ぉ 以묐났 吏꾩엯 諛⑹? 濡쒖쭅 ?먭? 諛??좎?.
- [UI] ?ы듃?대━??諛곕텇???ㅼ쟾 ?ъ엯 100%濡?蹂寃?(v1.1.9) 諛??ㅼ젙 UI??吏꾩엯 湲덉븸 ?낅젰??鍮꾩쑉(%) ?낅젰?쇰줈 援먯껜.

## v1.1.11 (2026-05-11)
- [Feature] 利앷굅湲??ㅼ젙 諛⑹떇 濡ㅻ갚: 1% ?먮룞 鍮꾩쨷?먯꽌 ?ъ슜?먭? 吏곸젒 吏꾩엯 利앷굅湲?USDT)??怨좎젙媛믪쑝濡??낅젰?섎룄濡?蹂寃?(UI ?ы븿).

## v1.1.12 (2026-05-11)
- [Fix] 留ㅻℓ?대젰(Trade History) 諛??먯껜 嫄곕옒 濡쒓렇(Trade Log)????꾩뒪?ы봽瑜??쒓뎅 ?쒓컙(KST, UTC+9)?쇰줈 媛뺤젣 蹂댁젙.

## v1.1.13 (2026-05-11)
- [UI] ??쒕낫???곷떒(LIVE/STOPPED 諭껋? ?꾨옒)???꾩뿭 **[?봽 ?덈줈怨좎묠]** 踰꾪듉 異붽?.

## v1.1.14 (2026-05-11)
- [UI] 硫붿씤 ?붾㈃ 諛??ъ씠?쒕컮 ??댄? 蹂寃? AI QUANTUM 愿???띿뒪?몃? 紐⑤몢 ??젣?섍퀬 ?꾨줈?앺듃 蹂몄쭏??留욊쾶 MACD-BB-EMA v1.1.14 濡?援먯껜.

## v1.1.15 (2026-05-11)
- [Fix] BacktestEngine compatibility: fallback to MARGIN_USDT when ORDER_USDT is missing, preventing AttributeError during backtest run.

## v1.1.16 (2026-05-11)
- [Config] 1??吏꾩엯 利앷굅湲?湲곕낯媛믪쓣 1 USDT?먯꽌 5 USDT濡??곹뼢 議곗젙.

## v1.1.17 (2026-05-11)
- [UI] SYSTEM LOG 理쒖떊 湲곕줉 媛뺤“ 湲곕뒫 異붽? (Bold, White, Blink).

## v1.1.17 (2026-05-11)
- [UI/UX] SYSTEM LOG??理쒖떊 湲곕줉???뺢킅 ?뱀깋 蹂쇰뱶泥?+ 源쒕묀???④낵 ?곸슜?섏뿬 媛?쒖꽦 媛뺥솕.

## v1.1.18 (2026-05-11)
- [Stability] OKX API 50011(Rate Limit) ?ㅻ쪟 諛⑹?瑜??꾪빐 ?ㅼ틦??吏???쒓컙??0.15珥덉뿉??0.3珥덈줈 ?곹뼢 議곗젙.

## v1.1.24 (2026-05-11)
- [UI] Changed ● LIVE badge to red color with blinking animation.

## v1.1.25 (2026-05-11)
- [UI] Applied attached design style to header status area: cyan outlined REFRESH button and LIVE STATUS badge with glowing green dot.

## v1.1.26 (2026-05-11)
- [Risk] Changed entry risk gate from 1.5x margin check to 1.0x (ree >= MARGIN_USDT).
- [Order] Changed TP order from reduce-only limit to stop(trigger) to reduce available-margin over-reservation risk when opening positions.

## v1.1.27 (2026-05-11)
- [UI] Applied stitch_trading_bot_ui_design.zip style system as app-wide override (Space Grotesk/Inter/JetBrains Mono, cyber dark palette, glass cards, neon green primary + cyan refresh accents).
- [UI] Updated header live badge label to 'LIVE CONNECTION' and sidebar version label to v1.1.27.

## v1.1.28 (2026-05-15)
- [UI/UX] Overhauled dashboard UI to "Wall Street Professional Terminal" style.
- [UI/UX] Applied deep black background (#050505) and Bloomberg-inspired color palette (#FF9900).
- [UI/UX] Switched numerical fonts to JetBrains Mono for enhanced terminal readability.
- [UI/UX] Replaced rounded glassmorphism cards with sharp-edged grid containers.
- [UI/UX] Optimized information density for high-end financial dashboard feel.

## v1.2.11 (2026-05-15)
- [UI] Replaced Allocation/Risk Metrics row with high-density 'Wall Street' metric bar (Image 1 Style).
- [Fix] Added total_pnl_usdt tracking to core/stats.py to ensure cumulative returns are correctly displayed.
- [UI] Restored and optimized liquidation buttons' sharp-edged terminal styling.



## v1.2.12 (2026-05-15)
- [UI] Added position duration display ([00시간 00분]) above the 'Close Now' button.

## v1.2.13 (2026-05-15)
- [UI] Added 'Used Margin' metric to the dashboard header.

## v1.2.14 (2026-05-15)
- [UI] Enhanced position duration display with larger font and 3h+ red alert background.

## v1.2.15 (2026-05-15)
- [UI] Added 'Amount' (Notional Entry Value) to active position cards.

## v1.2.16 (2026-05-15)
- [UI] Minimized liquidation buttons and font sizes to 66% of previous scale.

## v1.2.17 (2026-05-15)
- [Fix] Enhanced CSS selector specificity for liquidation buttons using marker div technique.

## v1.2.18 (2026-05-15)
- [UI] Enhanced visibility of position details with larger, brighter font.

## v1.2.19 (2026-05-15)
- [UI] Further enlarged position duration text to 0.98rem.

## v1.2.20 (2026-05-15)
- [UI] Switched PnL color scheme to Profit: Red / Loss: Blue.

## v1.2.21 (2026-05-15)
- [Core] Deleted Backtest module (core/backtest.py and UI tab).

## v1.2.22 (2026-05-15)
- [UI] Standardized Red (+) and Blue (-) colors across all metrics and tables.

## v1.2.23 (2026-05-15)
- [UI] Implemented custom HTML metrics in the header to allow full color control (Red/Blue).

## v1.2.24 (2026-05-15)
- [UI] Reverted colors for balance and margin metrics to neutral white.

## v1.2.25 (2026-05-15)
- [Trade] Implemented dynamic leverage sizing based on ticker-specific exchange policy.

## v1.2.26 (2026-05-15)
- [UI] Enlarged top metrics (133%) and brightened labels. [Fix] Accurate PnL % calculation based on actual leverage.

## v1.2.27 (2026-05-15)
- [UI] Enhanced Trade History with Type, PnL, and PnL % fields and color styling.
