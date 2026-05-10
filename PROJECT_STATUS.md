# Project Status: AI QUANTUM OKX Auto-Trader

## Current Status
- Initialized Streamlit dashboard with OKX API integration.
- Added auto-connect feature via `.env`.
- Fixed SL/TP sliders display logic.
- Fixed the empty keys bug that caused balance to show as 0 upon clicking "OKX 연결".
- Fixed MDD Limit slider UI to show accurate percentage scale (5% ~ 50%).
- Added "🎯 포지션 진입" tab between "매매 이력" and "설정" to display and adjust MACD, BB, and EMA entry conditions.
- Fixed an issue where `load_dotenv()` failed to hot-reload `.env` edits and UI inputs cached empty values.
- Fixed scanner yielding empty results because OKX's `quoteVolume` returned None, by manually calculating `baseVolume * last_price`.
- Fixed backtest "데이터 없음" error by implementing pagination in `get_ohlcv` to fetch up to 1500+ candles and rewriting the backtest loop to be fully vectorized instead of losing history through sliced indicator calculations.
- Wrote a comprehensive operational manual (`4ref.md`) detailing the Triple-Indicator strategy, risk management logic, and dashboard features.
- Added "즉시청산" buttons for individual positions and a "모든 종목 일괄청산" button for bulk liquidation.
- Adjusted liquidation buttons' font size and height to 77% of standard size for a more compact UI.
- Fixed `ModuleNotFoundError: plotly` by reinstalling dependencies in the correct Python environment.
- Restored and verified dashboard functionality on port 8502.
- Updated Trade History to display the latest trades at the top.
- Updated Backtest Trade List to display the latest trades at the top.
- **Implemented Orchestration Engine (`QuantumEngine`):** Centralized module management for Exchange, Scanner, and Trader.
- **Implemented Test Harness (`harness.py`):** Independent verification environment for core trading logic without UI dependency.
- **Refactored `app.py`:** Integrated the orchestration layer for improved stability and code cleanliness.

## Active Issues
- None.

## Next Steps
- Implement advanced risk management features (e.g., dynamic TP/SL).
- Enhance the Test Harness with mock exchange capabilities for CI/CD.

## v1.1.10 (2026-05-10)
- [Feature] 동적 자금 관리(1% Rule) 적용: 고정 진입금액을 폐지하고 전체 잔고의 1%를 증거금으로 사용하도록 변경.
- [Feature] One-Shot Rule: 동일 종목 중복 진입 방지 로직 점검 및 유지.
- [UI] 포트폴리오 배분을 실전 투입 100%로 변경 (v1.1.9) 및 설정 UI의 진입 금액 입력을 비율(%) 입력으로 교체.

## v1.1.11 (2026-05-11)
- [Feature] 증거금 설정 방식 롤백: 1% 자동 비중에서 사용자가 직접 진입 증거금(USDT)을 고정값으로 입력하도록 변경 (UI 포함).
