# Project Status: AI QUANTUM Binance Auto-Trader

## Current Status
- **[v4.0.1] 대시보드 및 설정 내 하드코딩된 OKX 브랜드 명칭 및 환경변수 맵핑 Binance 동기화 (2026-05-29):**
  - [Core/UI/Config] `app.py` 에서 수집 및 참조하는 API 키 환경변수를 `OKX_` -> `BINANCE_` 로 수정하여 `.env` 내의 바이낸스 키가 정상적으로 연동되도록 하였습니다.
  - [Core/UI] 사이드바 및 탭 전반에 걸친 OKX 연결 안내 및 버튼 텍스트 레이블을 "Binance"로 수정 적용하였습니다.
  - [Config] `settings.json` 내의 `EXCHANGE_ID`를 `"binance"`, `BASE_URL`을 `"https://www.binance.com"`으로 설정 변경하여 최초 로드 시의 브랜드 명칭 캐싱 문제를 완전히 해결했습니다.
- **[v4.0.0] OKX 봇 최신 소스코드 복제 및 바이낸스 결합 완료 (2026-05-29):**
  - [Core/Migration] `8501_bnc` 내의 바이낸스 어댑터(`core/exchange.py`) 및 `.env` 등 필수 인증/설정 파일을 제외한 소스 코드를 전면 클리닝했습니다.
  - [Core/Migration] `8401_okx` 로부터 최신 전략, 엔진 구조, 대시보드 UI 및 테스트 스위트 폴더를 그대로 복제하여 이식했습니다.
  - [Core/Migration] 이식 후 바이낸스 연결 환경에서 필요로 하는 `TradingConfig.USE_LIMIT_ORDER` 및 `__getattr__` 헬퍼 메서드를 `core/config.py`에 복원하였습니다.
  - [Test] `tests/test_liquidation.py` 내 모의 주문 객체 누락 필드(`status`, `filled`)를 채워 넣는 테스트 코드를 보정 완료하였습니다.
  - [Test] 전체 123개 단위 및 통합 테스트가 100% 정상적으로 통과함을 최종 확인하였습니다.
- **[v3.2.0] 실전 감사 6대 핵심 취약점 일괄 개선 및 패치 (2026-05-29):**
  - [Core/Exchange] 바이낸스 선물 거래소 연동 시 `setPositionMode(hedged=False)` API를 호출하여 Hedge Mode로 인한 주문 Reject 현상을 원천 방지하는 원웨이 모드 강제 설정 완료.
  - [Core/Trader] 동일 캔들 내 휩소 재진입 방지 가드(`Signal.timestamp` 및 `AutoTrader.last_entered_candle_ts`)를 탑재하여 15분 완성 캔들 주기 내 중복 진입 손실 위험 제거.
  - [Core/Engine] 서킷 브레이커 가동 및 `ERROR` 상태 전이 시 Stale 포지션 추적 찌꺼기 방지를 위해 `_prev_position_symbols`를 세트로 초기화하는 복구 로직 보강.
  - [Core/Exchange] `cancel_algo_orders` 호환 레이어에 실제 CCXT API 연동 및 3회 재시도 루프를 적용하여 미체결 Stop/TakeProfit 주문 정리 강건화.
  - [Core/Engine] 포지션 청산 완료 감지(`closed`) 즉시 거래소의 잔류 SL/TP 주문을 지연 없이 소멸시키는 OCO 클린업 처리 보강.
  - [Core/Exchange] `get_trade_history` 기본 조회 한도(`limit`)를 100건으로 늘려 고빈도/분할 체결 매칭 누락을 방지.
- **[v3.1.5] 청산 후 쿨다운 즉시 동기화 및 초단기 무한 재진입 차단 (2026-05-29):**
  - [Core/Trader] `trader.py`의 `on_signal` 초입에서 실시간으로 포지션을 확인하여, 스캐너 루프 진행 중 청산이 완료된 종목이 있을 경우 즉각 60초 쿨다운을 가동하는 자립형 감지 루프 구현.
  - 이를 통해 스캐너 종료 시점의 지연으로 쿨다운 가드가 무력화되어 수십 초 간격으로 진입과 시장가 청산이 무한 반복(채터링 현상)되던 치명적인 리스크 차단 완료.
- **[v3.1.4] 분할 체결 행 병합 구현 및 가독성 개선 (2026-05-29):**
  - [Core/History] 동일한 심볼, 방향, 청산 시각(exit_time) 및 상태(status)를 갖는 분할 진입/체결 행들에 대해 수량 및 PnL을 합산하고 가격/수익률을 가중 평균하여 하나의 행으로 대시보드에 노출되도록 개선 완료.
- **[v3.1.3] ADA/USDT '진입유실' 버그 해결 및 history_helper.py 보강 (2026-05-29):**
  - [Core/History] 24시간을 초과하여 페어링되지 않고 방치된 미청산(Stale) 진입 건들을 자동으로 만료하여 `청산 완료 (미기록)`으로 은폐 보정하는 유효시간 만료 시스템 도입.
  - 이를 통해 과거 누적된 가짜/유령 진입 건들이 오늘 새로 발생한 청산 건의 1대1 FIFO 매칭을 교란하여 유발되던 "진입유실" 문제를 완벽하게 예방하고 원상복구.
- **[v3.1.2] 신규 로직 반영에 따른 테스트 모킹 보강 (2026-05-29):**
  - [Test] `tests/test_liquidation.py` — `test_no_rollback_when_algo_succeeds` 내 `mock_order`에 `status='closed'`, `filled=5.0`을 보강하여 v3.1.1 미체결 자동 취소(None 반환) 로직에 따른 단위 테스트 실패 해결.
  - [Test] 로컬 패키지 의존성 (`pytest-asyncio`) 연동 정상화 및 126개 전체 테스트 스위트 100% 정상 패스 완료.
- **[v3.1.1] 실전 감사(QA Audit) 기반 4개 핵심 버그 즉시 수정 (2026-05-29):**
  - [Core/QA] `exchange.py` — Limit 주문 완전 미체결(filled=0, status=open) 시 원래 요청 수량으로 SL/TP 주문을 생성하던 유령 주문 버그 수정 → 즉시 주문 취소 후 `None` 반환으로 변경하여 포지션 없는 SL/TP 원천 차단.
  - [Core/QA] `trader.py` — `recently_entered` TTL을 120초에서 180초로 연장하여 `LIMIT_ORDER_TIMEOUT_MINUTES=3`(180초)과 일치. Limit 주문 체결 전 동일 심볼 재진입 허용 버그 차단.
  - [Core/QA] `engine.py` — 청산 timeout(15초 초과) 발생 시 `_cached_positions`/`_cached_balance`를 즉시 `None`으로 무효화. 타임아웃 후 Stale 캐시로 인한 UI 상태 불일치 방지.
  - [Core/QA] `strategy.py` — 스퀴즈 확장 윈도우를 `lookback*3`(24봉) → `lookback+4`(12봉)으로 축소. 수십 봉 전 스퀴즈 이력으로 인한 과신호(false positive) 진입 방지.
  - [Test] 18개 sync 테스트 100% 무오류 통과 검증 완료.
- **[v3.1.0] 수익성 극대화를 위한 변동성(ATR) 동적 SL/TP 및 Chandelier Exit, 모멘텀 기울기 가드 구현:**
  - [Core/Profitability] `core/config.py` 에 ATR 기반 손익절 및 Chandelier Exit, 모멘텀 임계치 설정을 이식하고 `.env` 로더와 연동하였습니다.
  - [Core/Profitability] `core/strategy.py` 에 TTM Momentum 가속도(기울기) 필터를 추가하여 미미한 변화율을 갖는 휩소 신호를 차단하도록 개선했습니다.
  - [Core/Profitability] `core/trader.py` 에 포지션 진입 시점의 ATR에 비례한 동적 TP/SL 수량/가격 연동을 구현했습니다.
  - [Core/Profitability] `core/engine.py` 에 Chandelier Exit 트레일링 스탑 루틴을 탑재하여 포지션 진입 이후 최고가/최저가 대비 ATR 배수 후퇴 시 시장가 강제 청산이 비동기로 자동 격발되도록 보강했습니다.
  - [Test] `tests/test_atr_strategy.py` 에 유닛 및 통합 검증 코드를 작성하고, 전체 126개 테스트 슈트 100% 정상 통과를 검증하였습니다.
- **[v3.0.0] OKX 봇 최신 엔터프라이즈 코드베이스 이식 및 바이낸스 API 결합:**
  - [Core/Migration] `8501_bnc` 내 바이낸스 API 어댑터(`core/exchange.py`) 및 핵심 설정 파일을 제외한 구버전 소스코드를 전면 클리닝했습니다.
  - [Core/Migration] OKX 봇(`8401_okx`)의 검증된 고성능 `QuantumEngine` v2(FSM 상태머신, 쿨다운 가드 등), 최신 전략 및 UI 소스코드를 완벽하게 이식했습니다.
  - [Core/Migration] 바이낸스 API 어댑터 하단에 `OKXClient = BinanceClient` 에일리어스를 추가하고, `cancel_algo_orders` 등 호환 메소드를 정의하여 OKX 엔터프라이즈 코드와의 호환 레이어를 구축했습니다.
  - [Test] 123개 단위/통합 테스트 슈트를 100% 정상 통과함을 검증 완료했습니다.
- **[v2.8.2] 서킷 브레이커 상태 정리 누락 버그 해결 및 테스트 가상 환경 격리:**
  - [Core/Test] 일일 손실 한도 또는 MDD 초과로 인한 서킷 브레이커 가동 중단 시, 기존 포지션 목록의 흔적을 비우는 `_prev_position_symbols` 초기화(`set()`) 처리가 조기 리턴으로 인해 누락되는 런타임 버그를 해결했습니다.
  - [Core/Test] 테스트 헬퍼 `_create_engine` 실행 시 생성되는 `AutoTrader`의 `enabled` 상태를 기본 `False`로 고정하여, 가짜 데이터의 모의 손실로 인해 테스트 수행 도중 엉뚱하게 서킷브레이커가 작동해 검증 흐름을 차단하지 않도록 수정했습니다.
- **[v2.8.1] 자동매매 가동 스위치 기본값 ON 적용 및 새로고침 대응:**
  - [Core/UI] AutoTrader의 기동 시 기본 `enabled` 값을 `True`로 수정하였습니다.
  - [Core/UI] 브라우저 F5 새로고침 또는 웹 앱 최초 실행 시 st.session_state 및 백엔드 엔진 가동을 항상 `ON`으로 강제 초기화하여 자동 기동되도록 보장하는 `refresh_initialized` 세션 가드를 구현했습니다.
- **[v2.8.0] 일 평균 수익률 산출 기준 시간 보정 및 한국어 상세 툴팁 전면 적용:**
  - [Core/UI] 일 평균 수익률 계산의 기준 시점을 기존 5월 15일에서 `2026-05-28 01:34:00`로 변경하였습니다 (`core/stats.py`, `app.py`, `data/stats.json` 일괄 적용).
  - [Core/UI] 대시보드 화면상에 노출되는 서브텍스트 표기를 `SINCE 2026.05.28 01:34`로 직관적이고 깔끔하게 수정하였습니다.
  - [Core/UI] 사이드바와 설정 탭의 모든 파라미터(레버리지, 증거금, 포지션 수, 지표 주기 등) 입력 위젯에 설명형+개조식 한국어 도움말(`help=`)을 전면 탑재하고 완전히 동기화했습니다.
- **[v2.7.0] 대시보드 비동기 캐시화 및 설정값 스냅샷 바인딩 적용:**
  - [Config] `.vscode/settings.json` 내의 `python.defaultInterpreterPath` 파이썬 가상환경(venv) 경로 지정을 변수 치환 오류가 발생하는 `${workspaceFolder}` 형태에서 상대 경로(`venv/Scripts/python.exe`)로 변경하여 IDE 경고창을 완전히 해결했습니다.
- **[v2.5.1] 대시보드 로그인 패스워드 검증 제거:**
  - [Security] `app.py` 내 `check_password()` 메서드가 즉시 `True`를 반환하도록 하여, 초기 실행 시의 비밀번호 입력 단계를 완전 배제하고 접속 편의성을 향상했습니다.
- **[v2.5.0] 대시보드 및 매매 이력 포지션 표시 버그 수정:**
  - [Core/UI/UX] active_positions_set을 실제 잔고 수량(coins) 매핑 딕셔너리로 고도화하고 최신 진입부터 역순 수량 매칭하여 과거 유실/중복 포지션을 '청산 완료 (미기록)'로 자동 판정되도록 개선했습니다.
- **[v2.4.9] 대시보드 로그인 패스워드 검증 화면 복구:**
  - [Security] 대시보드 로그인 패스워드 검증 화면(DASHBOARD_PASSWORD: COco@@5454)을 임시 복구했습니다.
- **[v2.4.8] 대시보드 로그인 패스워드 검증 화면 제거 및 볼륨 서지 기본값 변경:**
  - [Security/Config] 1) 대시보드 로그인 패스워드 검증 화면 및 검증 로직 제거, 2) .env 내 USE_VOLUME_SURGE_FILTER=False 기본 비활성화로 포지션 진입 제한을 해제했습니다.
- **[v2.4.7] API 주문 및 설정에 대한 강건성 재시도 래핑:**
  - [Core] `core/exchange.py` 내의 모든 주문 생성(`create_order`), 취소(`cancel_all_orders`), 마진 및 레버리지 설정 메서드를 지수 백오프 기반 재시도 루프(`_execute_with_retry`)로 래핑하여 시간 비동기화 및 네트워크 타임아웃으로 인한 즉시/일괄 청산 및 진입 오류를 원천 차단했습니다.
- **[v2.4.6] 사이드바 가동 시작 시각(SINCE) 수정:**
  - [UI] 사이드바 로고 영역에 노출되는 봇 가동 시작 시각(SINCE) 문자열을 `2026.05.28 01:34`로 수정 및 앱 메타 버전을 `v2.4.6`으로 업데이트 완료했습니다.
- **[v2.4.5] 1회 진입 증거금 기본값 하향 조정:**
  - [Config/UI] `core/config.py` 및 `.env` 파일의 `MARGIN_USDT` 기본값을 10 USDT에서 5 USDT로 하향 조정하여, 대시보드 로드 시 초기 1회 진입 기본 부담을 경감했습니다.
- **[v2.4.4] 트레일링 스탑 설정 UI 추가 및 연동:**
  - [Config/UI] `core/config.py` 내의 `TRAILING_ACTIVATE_PCT` (기본 1.5%) 및 `TRAILING_CALLBACK_PCT` (기본 0.43%) 변수를 정식 필드로 등재하고, `.env` 로더에 연동 완료했습니다.
  - [UI] 사이드바 "🛡️ 리스크 및 한도 설정" 및 설정 탭의 우측 손익 설정 컬럼에 트레일링 스탑 발동 조건 및 콜백 비율 조정 위젯을 신설하고 실시간 `.env` 저장 프로세스와 동기화했습니다.
  - [Test] 97개 유닛 테스트의 무오류 통과를 정상 재확인 완료했습니다.
- **[v2.4.3] 청산 강건성 확보 및 일괄 청산 UI 지연 제거:**
  - [Core] `core/exchange.py` 내 `close_position` 실행 시 수량에 `amount_to_precision`을 적용하여 소수점 자릿수 불일치에 따른 API 청산 실패 위험을 완전히 해소했습니다.
  - [UI] 사이드바 상단 "모든 종목 일괄청산" 버튼을 클릭할 경우 즉시 활성 포지션 목록의 모든 심볼을 은폐 세션 리스트(`closing_symbols`)에 등록하도록 로직을 보강하여, 거래소 API 리프레시 지연과 무관하게 포지션 카드가 즉시 제거되도록 UI 반응성을 보장했습니다.
  - [Test] 전체 97개 단위/통합 테스트를 재구동하여 결함이 없음을 검증 완료했습니다.
- **[v2.4.2] UI 설정값 및 프리셋 .env 실시간 연동 보존 구현:**
  - [Config/UI] `core/config.py` 파일 내 설정 변수 초기 로드 시 `.env` 환경 변수 값을 우선 동적으로 파싱하여 연동하도록 개선했습니다.
  - [UI] 사이드바와 설정 탭의 모든 변수 조작(`sync_p` 호출) 및 다중기간 최적 프리셋 로딩 시 변경된 설정값을 `.env` 파일에 실시간 영구 기록/반영하도록 설계하였습니다. 이로써 세션 새로고침 및 서비스 재기동 시 조정한 기본값이 완벽하게 복원됩니다.
  - [Test] 로컬 `.env` 값 변경에 구애받지 않도록 `test_rotation.py` 내 `MAX_HOLDING_HOURS=4.0` 격리 명시 코드를 보강하여, 97개 전 유닛 테스트 패스를 정상적으로 재검증 완료하였습니다.
- **[v2.4.1] 포지션 로테이션 체크 로직 조건부 활성화 및 테스트 복구:**
  - [Core] `core/engine.py` 내 비활성화되어 있던 `_run_position_rotation_check_async` 메소드의 시작부에 `if not self.cfg.ROTATION_ENABLED: return` 조건을 추가하여 로테이션 검사를 복구했습니다.
  - [Test] `test_rotation.py`를 포함한 전체 97개 단위/통합 테스트 케이스가 100% 무오류 통과함을 완료했습니다.
- **[v2.4.0] 핵심 설정 변수 최소화 및 테스트 호환성 확보:**
  - [Config/Core] `core/config.py` 파일의 비노출 변수를 전면 정리하여 UI에 노출되는 19개 핵심 변수만 남겼습니다.
  - [Core] `TradingConfig`에 `__getattr__` 메소드를 구현하여 기존 핵심 로직 및 테스트가 정상 호환되도록 처리했습니다.
  - [Test] `test_risk.py`, `test_entry_params.py`, `test_regression.py`, `test_performance.py` 등 비동기 테스트 케이스에 `asyncio.run`을 적용하여 100% 완전 무오류 통과를 검증 완료했습니다.
- **[v2.3.0] 거래량 서지 필터(Volume Surge Filter) 기능 추가:**
  - [Core/Strategy] 진입 전략 지표 계산 시 최근 20봉(VOLUME_SURGE_PERIOD) 평균 대비 현재 봉의 거래량 배수(VOLUME_SURGE_MULTIPLIER = 1.5배) 필터 신설 및 롱/숏 진입 신호 차단 로직(`Signal.vol_surge_ok`) 구현.
  - [UI] 사이드바 및 설정 탭에 거래량 서지 필터 제어 위젯 추가, 스캐너 표에 필터 만족 여부(✅/❌) 열 추가, 포지션 진입 가이드 반영.
  - [Test] `test_volume_surge_blocking` 테스트 신설 및 async 클라이언트 연동 문제 완전 해결 완료.
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
