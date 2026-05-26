# Project Status: AI QUANTUM OKX Auto-Trader

## Current Status
- **[v2.1.5] Strategy Parameter Defaults Re-setting:**
  - [Config] 대시보드 기본 전략 파라미터 설정을 사용자 지정 값(레버리지 10x, 증거금 10 USDT, 최대 포지션 4개, 스캔 주기 30초, 익절 1.5%, 손절 1.0%, 일일 손실 한도 7 USDT 등)으로 재정의 완료.
  - [Config] `.env` 설정 파일도 해당 사용자 지정 기본값과 완전히 일치하도록 동기화 수정 완료.
- **[v2.1.4] ICP/USDT Trade Sync & Old Trade Match Resolution:**
  - [Core/Bugfix] 청산 감지 시 CCXT fetch_my_trades 시간순 정렬 오류로 과거 오래된 청산 거래가 매칭되어 오늘 청산 기록이 누락되고 통계가 오염되던 버그 수정 (`reversed(recent_trades)` 탐색 적용).
  - [Core/Bugfix] 수동 동기화 스크립트 검증을 통하여 누락된 금일의 `ICP/USDT` 손실 거래 및 `RENDER/USDT` 등 거래소 실제 내역이 `trade_history.csv`에 성공적으로 기록됨을 검증 완료.
- **[v3.2.9] Ghost Holding Positions Resolution:**
  - [Core/UI] 실제 보유하지 않은 포지션이 로컬 기록 상의 미청산 상태로 인해 '보유 중'으로 계속 남아있던 심각한 데이터 불일치 버그 해결.
  - [Core/UI] `core/history_helper.py` 내 진입/청산 페어링 로직에 `active_positions_set` 크로스체크 프로세스 결합.
  - [Core/UI] 실시간 거래소 포지션 정보를 대조하여, 실제 보유하고 있지 않은 종목에 대해 가상으로 진입가와 동일한 청산가를 부여하고 손익 0.0의 `청산 완료 (미기록)` 상태로 자동 보정 처리.
- **[v3.2.8] Binance API Time Synchronization & Stability Fix:**
  - [Core/API] 윈도우 로컬 시스템 시각 차이로 발생하는 바이낸스 `-1021` (Timestamp ahead of server's time) 오류 자동 동기화 대응.
  - [Core/API] CCXT 바이낸스 연동 옵션에 `recvWindow: 60000` 설정 적용으로 오차 허용 격차 범위 확장.
  - [Core/API] API 호출 중 시간 비동기화 오류 감지 시 백오프 단계에서 `load_time_difference()`를 강제 실행하여 동적으로 서버 시각과 로컬 시각 오차 재계산 후 자동 재시도 루프 탑재.
- **[v1.4.02] Auto-Tuning Persistence & Multi-Tab Layout Refresh:**
  - [Feature] 자동 피팅 이력 영구 기록 시스템 (`data/autotune_history.csv`) 구축 — 앱 업데이트, 서버 재시작 등에도 영구 보존.
  - [UI/UX] 대시보드 탭 레이아웃 재배치 — 7단 탭 구조 (`대시보드`, `스캐너`, `매매 이력`, `포지션 진입`, `TP/SL 최적화기`, `오토피팅 이력`, `설정`) 완성.
  - [UI/UX] 신설된 `📈 오토피팅 이력` 독립 탭을 통해 언제든지 봇의 수학적 퀀트 손익비 피팅 역사를 확인 가능.
  - [Test] `harness.py` 테스트 러너 유니코드 인코딩 수정 — Windows 환경(CP949) 및 일반 환경에서 100% 무오류 통과 보장.
- **[v1.4.01] Critical SL/TP Bugfix — OCO 통합 + Stop-Market + 스프레드 필터:**
  - [Bugfix] SL/TP 주문이 Stop-**Limit**으로 걸려 급변동 시 미체결되던 치명적 버그 수정 → Stop-**Market** 전환.
  - [Architecture] 3개 분리 주문(진입+SL+TP) → 1개 통합 OCO 주문(`attachAlgoOrds`) — 한쪽 체결 시 반대쪽 자동 취소.
  - [Risk] 스프레드 필터 추가 (`MAX_SPREAD_PCT=0.3%`) — 호가 갭이 넓은 저유동성 종목 진입 원천 차단.
- **[v1.4.00] Harness & Orchestration Lv.4 Upgrade:**
  - [Architecture] `QuantumEngine` v2 — FSM 상태 머신(7개 상태 + 전이 맵), Health Check, 지수 백오프 자동 복구 추가.
  - [Test] `MockOKXClient` 구현 — 6개 시나리오 프리셋(default, low_balance, no_margin, max_positions, with_positions, profitable/losing).
  - [Test] 30개 단위/통합 테스트 전체 통과 — 리스크 게이트(5), 포지션 가드(5), 주문 실행(3), 전략 신호(5), Mock 데이터(3), FSM(5), Health(2), E2E(2).
  - [Bugfix] `trader.py` — `timedelta` import 누락 수정.
  - [Test] `harness.py` v2 — `--mock` 플래그로 실 API 없이 전체 엔진 흐름 테스트 가능.
- **[v1.3.04] Agent Skills Configured:** Applied top 3 latest agentic coding skills via `.antigravityrules`. Configured Artifact-based verification guidelines, MCP local tool integration protocol, and Semantic Codebase Sanitization constraints to ensure safe, stable agent collaboration and hallucination prevention.
- **[v1.3.03] Streamlit Min-Value Hotfix:** Decreased the minimum allowed value for "익절 (%)" and "손절 (%)" number inputs to `0.1%` in all sidebar and settings widgets. This resolves the `StreamlitValueBelowMinError` crash when running fine-tuned day trading configurations.
- **[v1.3.02] Day Trading Optimization & Dynamic TIMEFRAME Widget:** Applied day trading optimized parameters (TIMEFRAME = 15m, SL = 0.8%, TP = 1.2%, MAX_HOLDING_HOURS = 4.0, BB_STD = 1.8, EMA_PERIOD = 100) to hit the daily 1%~2% return target. Added dynamic selectbox widgets in the sidebar and main entry tabs for remote timeframe adjustments.
- Initialized Streamlit dashboard with OKX API integration.
- Added auto-connect feature via `.env`.
- Fixed SL/TP sliders display logic.
- Fixed empty keys bug that caused balance to show as 0 upon clicking "OKX 연결".
- Fixed MDD Limit slider UI to show accurate percentage scale (5% ~ 50%).
- Added "지표 진입 조건" tab between "매매 이력" and "설정" to display and adjust MACD, BB, and EMA entry conditions.
- Fixed issue where `load_dotenv()` failed to hot-reload `.env` edits and UI inputs cached empty values.
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










































- **[v1.2.52] Anti-Ghosting Logic:** Implemented an immediate-hide cache and dual filtering system. Positions with < .1 value or those recently closed via UI are strictly hidden until API sync is confirmed.









































- **[v1.2.52] Anti-Ghosting Logic:** Implemented an immediate-hide cache and dual filtering system. Positions with < .1 value or those recently closed via UI are strictly hidden until API sync is confirmed.

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

## v1.2.28 (2026-05-15)
- [UI] Applied standard numerical formatting (comma + 2 decimal places) to Trade History.

## v1.2.29 (2026-05-15)
- [UI] Styled *진입 rows with bold yellow and hid PnL fields.

## v1.2.30 (2026-05-15)
- [UI] Reorganized setting items for better usability.

## v1.2.31 (2026-05-15)
- [UI] Enlarged and brightened the strategy summary text in Settings.

## v1.2.32 (2026-05-15)
- [UI] Updated Entry Conditions (TAB 4) with easy-to-understand explanations in yellow.

## v1.2.33 (2026-05-15)
- [UI] Added fun summary boxes for Entry Conditions with metaphors.

## v1.2.34 (2026-05-15)
- [UI] Enlarged (155%) and center-aligned Entry Condition summary boxes.

## v1.2.35 (2026-05-15)
- [UI] Moved Entry Condition summary boxes above the detailed list.

## v1.2.36 (2026-05-15)
- [UI] Applied global font policy (Min 14px, Bright Grey) to all UI elements.

## v1.2.37 (2026-05-15)
- [Core] Refined ROI calculation with .43 base capital and Daily Avg ROI logic.

## v1.2.37 (2026-05-15)
- [UI] Updated bottom metrics: Base capital .43, added Daily Average Return.

## v1.2.37 (2026-05-15)
- [Core] Updated ROI logic (.43 seed) and introduced Daily Avg ROI.

## v1.2.38 (2026-05-15)
- [Core] Reset win rate and order count tracking to start from 2026-05-15.

## v1.2.38 (2026-05-15)
- [Core] Reset all trading statistics to start fresh from May 15.

## v1.2.39 (2026-05-15)
- [Core] Aligned Daily Avg ROI logic with KST timezone.

## v1.2.39 (2026-05-15)
- [Core] Synchronized ROI calculation to KST timezone.

## v1.2.40 (2026-05-15)
- [UI] Added baseline date to Win Rate. 
- [Core] Conservative Daily ROI (min 1 day).

## v1.2.41 (2026-05-15)
- [UI] Changed MDD limit color to Bright Grey.

## v1.2.42 (2026-05-15)
- [Core] Implemented live history-based Win Rate calculation.

## v1.2.43 (2026-05-15)
- [Bugfix] Fixed method name in Win Rate calculation.

## v1.2.44 (2026-05-15)
- [Core] Implemented Trade Aggregation by Order ID for Win Rate.

## v1.2.45 (2026-05-15)
- [Core] Live unique order count for Orders Today metric.

## v1.2.46 (2026-05-15)
- [Core] Unified Orders Today metric with Win Rate (W+L only).

## v1.2.47 (2026-05-15)
- [UI] Tightened vertical spacing in position cards. 
- [Core] Refactored datetime for UTC-aware compliance.

## v1.2.48 (2026-05-15)
- [UI] Dynamic coloring for Win Rate (>50% Red, <=50% Blue).

## v1.2.49 (2026-05-15)
- [UI] Set ROI/Orders sub-text to White.

## v1.2.50 (2026-05-15)
- [UI] Applied negative margin to Close button for compact layout.

## v1.2.51 (2026-05-15)
- [Bugfix] Fixed system log line-break issue. 
- [UI] Enhanced log readability with row borders.

## v1.2.52 (2026-05-15)
- [Core] Implemented session-based immediate hide for closed positions to prevent ghosting.

## v1.3.00 (2026-05-19)
- [Architecture] Integrated background auto-scan with 'Auto-Trading ON' and completely removed the scanner tab.

## v1.3.01 (2026-05-19)
- [UI/UX] Restored the Scanner Monitoring tab without the manual Scan Start button to keep auto-trading integrity.

## v1.3.02 (2026-05-19)
- [Algorithm/UI] Optimized day trading parameters (15m TIMEFRAME, SL = 0.8%, TP = 1.2%, MAX_HOLDING_HOURS = 4.0, BB_STD = 1.8, EMA_PERIOD = 100) to target a daily 1%~2% return. Added dynamic selectbox widgets to both sidebar and main entry tabs for remote timeframe adjustments.

## v1.3.03 (2026-05-19)
- [Bugfix] Fixed `StreamlitValueBelowMinError` by lowering the minimum value for "익절 (%)" and "손절 (%)" number input widgets to `0.1%` in the sidebar and settings tabs.
