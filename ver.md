# 🚀 AI QUANTUM - Version History

| 버전 | 일시 | 내용 | 비고 |
| :--- | :--- | :--- | :--- |
| v4.0.6 | 2026-05-29 17:53:00 | [Core/Exchange] Binance Trailing Stop 주문 시 callbackRate 소수점 1자리(0.1% 단위) 정밀도 제한 대응 패치 추가 (Invalid callBack rate 에러로 인한 진입 즉시 롤백 현상 해결) | Core/Exchange |
| v4.0.5 | 2026-05-29 17:47:00 | [Core/Scanner] 실시간 웹소켓 선진입에 따른 OHLCV 캐시 1봉 조기 오염(지표 계산 먹통) 버그 수정: 캐시 150봉 미만 시 REST API 강제 리로딩 보장 | Core/Scanner |
| v4.0.4 | 2026-05-29 17:19:00 | [Docs/Config] PROJECT_STATUS.md 최신 릴리즈 히스토리 업데이트 및 settings.json 기본 마진/필터 옵션 바이낸스 실거래 최적화 세팅 반영 | Docs/Config |
| v4.0.3 | 2026-05-29 16:11:31 | [Core/UI] 매매이력 완전 초기화 및 재동기화 차단: 1) trade_history.csv/.bak 전체 삭제(헤더만 보존), 2) stats.json 통계 전체 리셋(perf_start_time=2026-05-29 16:09:59 기준), 3) engine.py _sync_trades_to_csv_async에 perf_start_time 이전 거래소 이력 재동기화 차단 컷오프 필터 추가, 4) app.py 매매이력 탭 렌더링 시 perf_start_time 이전 raw_trades 표시 제외 필터 추가, 5) app.py SINCE 표시 및 기준 시각 기본값 2026-05-29 16:09로 업데이트 | Core/UI |
| v4.0.2 | 2026-05-29 16:15:00 | [Core/QA] 코드 전수 검증 기반 7개 핵심 버그 수정: 1) trader.py — recently_entered TTL 120초→180초, 2) trader.py — on_signal 청산감지 쿨다운 복원, 3) trader.py — 동일캔들 중복진입 방지, 4) exchange.py — 시장가 FalseCancel 수정, 5) strategy.py — 스퀴즈윈도우 lookback+4, 6) harness.py — BINANCE env, 7) engine.py — 브랜드 수정. 전체 123테스트 100% 통과 | Core/QA |
| v4.0.1 | 2026-05-29 15:48:00 | [UI/Config] 대시보드 및 설정 내 하드코딩된 OKX 브랜드 명칭 및 환경변수 맵핑 Binance 동기화 완료: 1) app.py 내 API Key/Secret/Passphrase 환경변수를 BINANCE_ 로 변경, 2) 사이드바 및 탭 내 OKX 연결 안내 및 버튼 레이블을 Binance로 수정, 3) settings.json의 EXCHANGE_ID 및 BASE_URL을 바이낸스로 강제 패치 | UI/Config |
| v4.0.0 | 2026-05-29 15:42:00 | [Architecture/Migration] OKX 봇 최신 소스코드 복제 및 바이낸스 결합 완료 (v4.0.0 메이저 릴리즈): 1) 8501_bnc의 exchange.py 및 .env 제외 소스 전면 클리닝 후 8401_okx 소스 복제 이식, 2) core/config.py 에 바이낸스 전용 설정(USE_LIMIT_ORDER, LIMIT_TICK_OFFSET 등) 및 __getattr__ 헬퍼 복원 적용, 3) tests/test_liquidation.py 내 모킹 오류 보정 패치 반영, 4) 123개 단위/통합 테스트 100% 정상 통과 검증 완료 | Core/Migration |
| v3.2.0 | 2026-05-29 15:52:00 | [Core/Exchange/Trader/Engine] 실전 감사 결과 6대 취약점 일괄 개선 및 패치: 1) Binance Futures One-way Mode 강제 설정 API 연동, 2) 동일 캔들 내 중복 진입 방지 가드(Signal timestamp 및 last_entered_candle_ts) 탑재, 3) 서킷 브레이커 가동/에러 상태 전이 시 _prev_position_symbols 초기화 추가, 4) cancel_algo_orders 실제 CCXT API 연동 및 3회 재시도 루프 복구, 5) closed 포지션 감지 즉시 cancel_all_orders OCO 청소 보강, 6) get_trade_history limit 100 상향 | Core/Exchange/Trader/Engine |
| v3.1.5 | 2026-05-29 15:50:00 | [Core/Trader] 청산 후 쿨다운 즉시 동기화 및 무한 재진입(채터링) 방지 버그 수정: 스캐너 루프 종료 시점보다 신호 격발이 먼저 발생하여 쿨다운 가드가 무력화되던 버그를 trader.on_signal 초입 실시간 포지션 청산 감지 및 즉시 쿨다운(60초) 격발로 원천 차단 | Core/Trader |
| v3.1.4 | 2026-05-29 15:05:00 | [Core/History] 분할 체결(Split-Fill) 및 분할 진입 행 자동 병합 구현: 동일 청산 시각(exit_time)을 갖는 여러 개의 쪼개진 행들을 총 수량 및 가중평균 가격/수익률로 단일 행 통합하여 가독성 개선 | Core/History |
| v3.1.3 | 2026-05-29 15:20:00 | [Core/History] ADA/USDT 페어링 누락 및 '진입유실' 버그 근본 수정: 24시간 초과 Stale 진입 자동 만료 및 '청산 완료 (미기록)' 치환 로직 도입으로 FIFO 매칭 꼬임 원천 제거 | Core/History |
| v3.1.2 | 2026-05-29 12:12:00 | [Test] test_liquidation.py 내 test_no_rollback_when_algo_succeeds의 mock_order에 status='closed' 및 filled=5.0 모킹을 보강하여 v3.1.1의 place_order 미체결 즉시 취소 로직(None 리턴)과의 호환성 해결 | Test |
| v3.1.1 | 2026-05-29 11:53:00 | [Core/QA] 실전 감사(QA Audit) 기반 4개 핵심 버그 즉시 수정: 1) exchange.py — Limit 주문 완전 미체결 시 요청 수량으로 SL/TP 생성하던 유령 주문 버그 수정 → 주문 즉시 취소 후 None 반환으로 변경, 2) trader.py — recently_entered TTL 120초를 LIMIT_ORDER_TIMEOUT(180초)과 일치하도록 연장하여 Limit 주문 체결 전 동일 심볼 재진입 허용 버그 차단, 3) engine.py — 청산 timeout(15초) 후 _cached_positions/_cached_balance 즉시 무효화 추가로 Stale 캐시 상태 불일치 방지, 4) strategy.py — 스퀴즈 확장 윈도우 lookback*3(24봉) → lookback+4(12봉) 축소로 수십 봉 전 스퀴즈 이력 기반 과신호 진입 방지 | Core/QA |
| v3.1.0 | 2026-05-29 11:15:00 | [Core/Profitability] 수익성 극대화를 위한 변동성(ATR) 동적 SL/TP 및 Chandelier Exit, 모멘텀 기울기 가드 구현: 1) core/config.py에 관련 설정 탑재, 2) core/strategy.py에 모멘텀 가속도 기울기 필터 적용, 3) core/trader.py에 ATR 기반 동적 손익절 계산 연동, 4) core/engine.py에 샹들리에 엑시트(최고가/최저가 추적 기반 ATR 범위 후퇴 시 일괄 청산) 비동기 감시 추가, 5) 126개 단위 테스트 100% 정상 통과 검증 완료 | Core/Profitability |
| v3.0.0 | 2026-05-29 11:10:00 | [Architecture/Migration] OKX 봇 최신 엔터프라이즈 코드베이스 이식 및 바이낸스 API 결합: 1) D:\AI\project\8501_bnc 내 바이낸스 API 어댑터(core/exchange.py) 및 핵심 관리용 파일 제외 전원 클리닝, 2) OKX 봇(8401_okx)의 검증된 고성능 Orchestration Engine v2(FSM 상태머신, 쿨다운 가드 등), 최신 전략 및 UI 소스코드 복제 이식, 3) 바이낸스 API 어댑터에 OKXClient 에일리어스 및 cancel_algo_orders 호환 메소드 추가로 OKX 코드베이스 호환 레이어 결합, 4) 123개 단위/통합 테스트 100% 정상 통과 검증 완료 | Core/Migration |
| v2.8.2 | 2026-05-29 01:52:00 | [Core/Test] 서킷 브레이커 조기 종료 시 상태 정리 버그 수정 및 테스트 환경 격리: 1) 일일 손실 한도/MDD 초과로 조기 리턴 시 _prev_position_symbols 클린업(set())이 누락되는 런타임 버그 해결, 2) 테스트 환경용 헬퍼 _create_engine에서 mock trader의 enabled를 False로 고정하여 불필요한 서킷 브레이커 격발 차단 | Core/Test |
| v2.8.1 | 2026-05-29 01:50:00 | [Core/UI] 자동매매 가동 토글 기본값 ON 설정 및 새로고침 대응: 1) AutoTrader 초기 enabled 값을 True로 변경, 2) 브라우저 F5 새로고침 및 최초 실행 시 st.session_state 및 백엔드 엔진 가동을 항상 ON으로 자동 기동하는 refresh_initialized 세션 가드 구현 | Core/UI |
| v2.8.0 | 2026-05-28 16:45:00 | [Core/UI] 일 평균 수익률 기준 시각 보정 및 도움말 툴팁 전면 적용: 1) core/stats.py, app.py, data/stats.json의 수익률 시작 시점을 '2026-05-28 01:34:00'으로 일괄 수정, 2) UI 레이블 서브텍스트를 'SINCE 2026.05.28 01:34'로 변경, 3) 사이드바 및 설정 탭의 모든 파라미터 제어 위젯에 상세 한국어 도움말(help=) 탑재 및 1:1 동기화 | Core/UI |
| v2.7.0 | 2026-05-28 23:58:00 | [Architecture/Performance] 대시보드 비동기 캐시화 및 설정값 스냅샷 바인딩 적용: 1) Streamlit UI의 REST API 동기 블로킹 방지를 위한 백그라운드 텔레메트리 10초 주기 캐시 업데이트 구현, 2) 포지션 종료/주문 체결 등 이벤트 발생 시 즉각 캐시를 강제 갱신하여 UI 실시간 반응성 보장, 3) 런타임 경쟁 상태 및 스레드 안전성 확보를 위한 Scanner/AutoTrader 실행 주기별 config 스냅샷 바인딩 구현, 4) UI의 직접적인 엔진 서브모듈 config 가변 갱신 코드 제거 및 Decoupling 완료, 5) 신규 유닛 테스트 작성 및 검증 통과 | Core/Architecture |
| v2.6.1 | 2026-05-28 23:51:00 | [Core/Test] 포지션 청산 로직 강인성 보완: 1) 실수 표현 오차로 인한 절사 오류 방지차 8자리 반올림 적용, 2) 폴링 루프 내 get_positions 오류 발생 시 예외 처리 추가로 붕괴 방지, 3) bulk 청산 병렬 실행(asyncio.gather)으로 UI 프리징/타임아웃 해소, 4) UI/인자 side와 상관없이 실제 포지션 방향(target["side"]) 기반 close_side 판정, 5) 추가 보완 항목 테스트 코드 작성 완료 | Core/Test |
| v2.6.0 | 2026-05-28 23:37:00 | [Core/UI/Test] 5개 필수 수정 통합 릴리즈: [수정1] core/strategy.py - 완성 캔들(iloc[-2]) 기준 신호 판단 전환으로 리페인팅 완전 제거 / [수정2] core/exchange.py - Binance 네이티브 TRAILING_STOP_MARKET 주문 진입 시 전송 / [수정3] core/exchange.py - 부분 체결 대응 실시간 수량 조회 기반 SL/TP 생성 (fetch_order 폴링 + 잔여 취소) / [수정4] app.py - 일방적 UI 은폐 캐시(Fast Hide) 제거, st.spinner 추가로 API 성공 확정 후에만 포지션 카드 제거 / [수정5] core/engine.py - 서킷 브레이커(일일 손실 한도 + MDD 초과 시 일괄 청산 및 봇 정지) 연동, test_exit_circuit_breaker.py 신규 추가 | Core/UI/Test |
| v2.5.2 | 2026-05-28 19:04:00 | [Config] .vscode/settings.json 내의 python.defaultInterpreterPath 파이썬 가상환경 경로를 상대 경로로 변경하여 IDE 상의 경로 미확인 경고 해결 | Config |
| v2.5.1 | 2026-05-28 19:01:00 | [Security] 대시보드 로그인 패스워드 검증 화면 및 검증 로직 제거 (접속 편의성 향상) | Security |
| v2.5.0 | 2026-05-28 14:10:00 | [Core/UI/UX] 대시보드 및 매매 이력의 고스트/중복 '보유 중' 포지션 표기 버그 수정. active_positions_set을 실제 잔고 수량(coins) 매핑 딕셔너리로 고도화하고 최신 진입부터 역순 수량 매칭하여 과거 유실/중복 포지션을 '청산 완료 (미기록)'로 자동 판정되도록 개선 | Core/UI/UX |
| v2.4.9 | 2026-05-28 14:05:00 | [Security] 대시보드 로그인 패스워드 검증 화면(DASHBOARD_PASSWORD: COco@@5454) 복구 | Security |
| v2.4.8 | 2026-05-28 13:47:00 | [Security/Config] 1) 대시보드 로그인 패스워드 검증 화면 및 검증 로직 제거, 2) .env 내 USE_VOLUME_SURGE_FILTER=False 기본 비활성화로 포지션 진입 제한 해제 | Security/Config |
| v2.4.7 | 2026-05-28 09:05:00 | [Core] 1) core/exchange.py 내 모든 주문 작성/취소 및 레버리지/마진 설정 API 호출을 _execute_with_retry 지수 백오프 재시도 루프로 래핑하여 시간 비동기화 및 네트워크 타임아웃에 따른 청산/진입 실패 방지 | Core |
| v2.4.6 | 2026-05-28 01:36:00 | [UI] 1) 사이드바 로고 영역의 가동 시작 시각(SINCE)을 2026.05.28 01:34로 수정 및 app.py 버전 동기화 | UI |
| v2.4.5 | 2026-05-28 01:26:00 | [Config/UI] 1) 1회 진입 증거금(MARGIN_USDT) 기본값을 10 USDT에서 5 USDT로 하향 조정 및 .env 연동 | Config/UI |
| v2.4.4 | 2026-05-28 01:15:00 | [Config/UI/Test] 1) core/config.py 내 트레일링 스탑 설정(TRAILING_ACTIVATE_PCT, TRAILING_CALLBACK_PCT)을 정식 필드로 등록, 2) 사이드바 및 설정 탭에 트레일링 발동/콜백 조작 위젯 추가 및 .env 실시간 저장 연동, 3) tests/test_strategy.py 내 pandas(pd) 임포트 누락으로 인한 NameError 수정, 4) app.py 내 get_git_tag() 리턴 버전을 v2.4.4로 동기화 수정 | Config/UI/Test |
| v2.4.3 | 2026-05-28 01:10:00 | [Core/UI] 1) core/exchange.py 내 close_position 시 size에 amount_to_precision 적용하여 정밀도 불일치로 인한 청산 실패 원천 제거, 2) app.py 내 모든 종목 일괄 청산 버튼 클릭 시 active_positions를 즉각 closing_symbols에 등록하여 UI 상에서 지연 없이 바로 사라지도록 즉각 은폐 로직 보강 | Core/UI |
| v2.4.2 | 2026-05-28 01:05:00 | [Config/UI/Test] 1) core/config.py가 .env 파일 환경 변수값을 읽어 로드하도록 개선, 2) UI 위젯 및 프리셋 값 변경 시 실시간으로 .env 파일에 자동 저장/반영되도록 동기화 구현, 3) test_rotation.py의 로컬 독립성 강화를 위해 MAX_HOLDING_HOURS=4.0 명시적 격리 설정 | Config/UI/Test |
| v2.4.1 | 2026-05-28 00:49:00 | [Core/Test] 1) core/engine.py 내 포지션 로테이션 체크 로직 조건부 활성화(__getattr__ 호환성 확보), 2) test_rotation.py 및 전체 유닛 테스트 정상 통과 복구 | Core/Test |
| v2.4.0 | 2026-05-28 00:43:00 | [Config/Core/Test] 1) core/config.py 내 UI 비노출 설정 변수 제거 및 19개 핵심 변수 최소화, 2) 하위 호환성용 __getattr__ 구현, 3) 전체 비동기 테스트 케이스 수정 및 패키지 100% 통과 검증 | Config/Core/Test |
| v2.3.0 | 2026-05-28 00:32:15 | [Core/Strategy/UI] 거래량 서지 필터(Volume Surge Filter) 도입 및 대시보드 스캐너/설정 탭 연동, 유닛 테스트 보완 | Core/Strategy/UI |
| v2.2.3 | 2026-05-27 22:28:00 | [Security] 대시보드 로그인 패스워드 검증 화면 및 검증 로직 제거 (접속 편의성 향상) | Security |
| v2.2.2 | 2026-05-27 20:30:00 | [Config/UI] 1) RSI 필터 상/하한선을 75/25 황금 세팅으로 복구, 2) 멀티셀렉트 태그 배경색 다크그레이(#333) 변경, 3) SINCE 표기 시간 23:45로 수정 | Config/UI |
| v2.2.1 | 2026-05-27 15:35:00 | [UI/UX] 1) 수익률 차트에 실시간 현재 일 평균 수익률 위치를 가리키는 노란색 점선 및 라벨 추가, 2) 상단 '금일 실현 손익' 지표 계산식을 '총 잔고 * 일 평균 수익률'로 변경 | UI/UX |
| v2.2.0 | 2026-05-27 13:40:00 | [UI/UX] 대시보드 하단에 기간봉(1분, 5분, 15분, 1시간 등) 기준의 '초기화 이후 누적 수익률(%) 차트' 추가 (매매 엔진에 100% 무해한 Read-Only 로직) | UI/UX |
| v2.1.9 | 2026-05-27 12:31:00 | [UI/UX] 사이드바 로고 영역의 SINCE 시간을 10:34에서 13:45로 수정 | UI/UX |
| v2.1.8 | 2026-05-27 11:26:00 | [Security] 대시보드 보안(로그인) 접속 비밀번호를 사용자 지정 값으로 변경 적용 | Security |
| v2.1.7 | 2026-05-27 10:48:00 | [Security] 클라우드 서버 무중단 배포 대비, Streamlit 앱 접속 시 비밀번호(.env DASHBOARD_PASSWORD)를 묻는 로그인 보안 기능 추가로 무단 접속 방지 | Security |
| v2.1.6 | 2026-05-26 23:53:00 | [Config] 사용자 프롬프트 지시 및 디버깅 시작 시 에이전트의 이해 수준을 사전에 보고하고 사용자 승인(OK)을 득한 후 실행하도록 하는 글로벌 안전 워크플로우를 .antigravityrules에 추가 | Config |
| v2.1.5 | 2026-05-26 23:41:00 | [Config] 대시보드 기본값(Default)을 사용자 지정 최적 파라미터(레버리지 10x, 진입 증거금 10 USDT, 최대 포지션 4개, 일일 손실 한도 7 USDT, 스캔 주기 30초 등)로 재세팅 및 .env 설정 동기화 | Config |
| v2.1.4 | 2026-05-26 23:36:00 | [Core/Bugfix] 청산 감지 시 CCXT fetch_my_trades 시간순 정렬 오류로 과거 오래된 청산 거래가 매칭되어 오늘 청산 기록이 누락되고 통계가 오염되던 버그 수정 (reversed(recent_trades) 탐색 적용) | Core/Bugfix |
| v2.1.3 | 2026-05-26 19:54:00 | [Core/Bugfix] Streamlit 세션 리로드 시 config 모듈 재로드(importlib.reload)에 따른 백그라운드 엔진 설정 동기화 누락 버그 해결 및 기본 RSI 필터 제한 완화(75% / 25%) 적용 | Core/Bugfix |
| v2.1.2 | 2026-05-26 16:56:00 | [UI] SINCE 날짜 시간 표기 오타 수정 (10.34 -> 10:34) | UI/UX |

| v2.1.1 | 2026-05-26 10:41:00 | [Core/UI] 목표 익절 잠금 및 일일 익절 잠금 기능/대시보드 UI 완전 제거 | Core/UI |

| v2.1.0 | 2026-05-26 10:34:00 | [Core/UI] v2.0.0 기반 복원 및 로고 표시 정보 최적화 | Core/UI |

| v3.0.0 | 2026-05-26 09:47:00 | [Core/Strategy/UI] AKMCD-SSL-RSI 정식 릴리즈 및 대시보드 로고 무지개 텍스트 애니메이션 적용 | Core/Strategy/UI |

| v2.0.8 | 2026-05-26 02:01:49 | [Core/Scanner] OHLCV 캐시 구현(최초 300봉, 이후 3봉 증분 업데이트) 및 거래대금 상위 80개 스캔 제한으로 REST API 호출 95% 절감 / Binance IP 차단 근본 방지 | Core/Scanner |

| v2.0.7 | 2026-05-26 01:45:32 | [Core/Scanner/UI] Tickers 키 매핑 보정, 스캐너 개별 API 호출 차단, 대시보드 조회 실패 시 Fallback 사전 예방(KeyError 방지) | Core/Scanner/UI |

| v2.0.6 | 2026-05-26 01:35:50 | [Core/Engine] Streamlit 다중 탭 접속 시 중복 스캔 스레드 실행 방지를 위한 Singleton 패턴 및 초기화 가드 구현 | Core/Engine |

| v2.0.5 | 2026-05-26 01:22:22 | [Core/Scanner] Scanner Ticker 일괄 조회(fetch_tickers) 도입으로 REST API 호출 횟수 최적화 및 API Ban(Rate Limit 418) 차단 | Core/Scanner |

| v2.0.4 | 2026-05-26 01:18:18 | [Core/Risk] 거래소 API 에러 발생 시 리스크 게이트 우회 방지 (예외 전파 및 Trader 예외 처리 적용), API 백오프 재시도 추가 | Core/Risk |

| v2.0.3 | 2026-05-26 01:15:22 | [UI/UX] AKMCD-SSL-HYBRID 고정 매매기법에 맞추어 불필요한 '🚀 TP/SL 최적화기' 탭 삭제 및 탭 인덱스 조정 | UI/UX |

| v2.0.0 | 2026-05-26 00:55:27 | [UI/UX] 보유 중인 포지션 카드 하단의 5분봉 가격/거래량 추이 그래프(Plotly Popover) 제거 | UI/UX |

| v1.0.19 | 2026-05-25 22:25:13 | [Core/Cleanup] 봇에서 무용지물인 추세강도 자동 스위칭 잔재를 완전 제거. config/app/session/strategy 지표 계산/테스트/스크래치 최적화 코드에서 관련 설정과 계산을 삭제하고, 전용 백테스트 스크립트 제거 | Core/Cleanup |

| v1.0.18 | 2026-05-25 22:05:42 | [Core/Bugfix] 매매 이력 청산 중복 기록 및 진입/청산 동일시각 표시 문제 수정. CSV 체결ID 기준 중복 제거, sync_trades_to_csv 비동기 엔진 복구, 청산 감지 중복 기록 방지, 미기록 청산의 임시 동일가/동일시각 표시 제거, 0손익 reduceOnly 청산 분류 보강 및 회귀 테스트 추가 | Core/Bugfix |

| v3.5.4 | 2026-05-25 16:01:47 | [UI/UX] 앱 배경 스타일을 우상향 글로우에서 중앙 방사형 딥블루 글로우로 변경, 사이드바 'API 연결 설정' 라벨 및 대시보드 'STRATEGY ENGINE PARAMETERS' 라벨 문구 삭제 | UI/UX |

| v3.5.3 | 2026-05-24 23:46:25 | v3.5.3 | UI |

| v3.5.2 | 2026-05-24 23:41:32 | [Config] Git Pre-commit 훅(.pre-commit-config.yaml) 설정 및 자동화 릴리즈 툴(release.py) 스크립트 추가 | Config |

| v3.5.1 | 2026-05-24 23:32:32 | [UI] 사이드바 버전(v1.0.0) 텍스트 폰트 크기 122% 확대 적용, 모든 슬라이더/인풋/선택 위젯 값 변경 시 실시간 st.toast 팝업 알림 구현 및 requirements.txt 버전 관리 반영 | UI |

| v3.5.0 | 2026-05-24 23:22:23 | [Core/UI] TTM Squeeze 전략 도입에 따른 대시보드 UI 연동 고도화 (로고 TTM-Squeeze-EMA 변경, 스캐너 컬럼 '추세 방향 일치'/'스퀴즈 돌파'/'모멘텀 방향'/'EMA 200 가드'/'EMA 200 가격' 재매핑), 거래소 체결(Fill) ID 수집 및 로컬 CSV 영구 기록을 통한 분할 체결 누락 해결, 진입 시점 레버리지 역추적 및 수익률(%) 왜곡 방지, M:N FIFO 가중평균 비율 매칭 구현, 자동매매 오프(OFF) 시 오버라이드 정지 보장 가드 구현 | Core/UI |

| v3.4.2 | 2026-05-24 15:45:38 | [UI/UX] 앱 실행 시 사이드바 자동매매가동(auto_trading) 토글 상태가 항상 ON(True)을 디폴트로 하도록 설정 세션 상태 초기화 방식 개선 | UI/UX |

| v3.4.1 | 2026-05-24 14:52:06 | [Core/Bugfix] 거래소 포지션 정보에서 레버리지 값이 None으로 들어오는 경우 Dashboard에서 'Nonex'로 잘못 렌더링되던 현상을 수정 (None일 시 CFG.LEVERAGE로 Fallback 처리) | Core/Bugfix |

| v3.4.0 | 2026-05-24 14:29:00 | [Core/Safety] 쿨다운 시스템 도입 — 일괄청산 후 1분 글로벌 쿨다운 + 개별 청산(수동 즉시청산, 거래소 TP/SL 청산, 타임아웃 강제청산, 로테이션 청산 등 모든 청산 케이스) 후 1분 종목별 쿨다운 도입 및 단위 테스트 구현 | Core/Safety |

| v3.3.5 | 2026-05-24 09:31:23 | [UI/UX] 앱 최초 로드 및 화면 너비/브라우저 캐시 여부에 상관없이 앱 기동 시 사이드바 강제 열림(확장) 보장을 위해 data-testid="collapsedControl" 자동 클릭 JS 스크립트 추가 | UI/UX |

| v3.3.4 | 2026-05-23 23:33:57 | [Core/Bugfix] 매매 이력 페어링 로직 고도화 및 캐싱 방지. 동일 분(minute)에 속한 분할 체결(Split-Fill) 건의 단일 행 병합, 1개 청산 주문에 대한 N개 진입 주문 가중평균 FIFO 매칭(1:N) 적용으로 수익률/손익의 거래소 일치성 확보. Streamlit의 모듈 캐싱에 따른 구버전 렌더링 방지를 위해 `importlib.reload` 구문 적용 | Core/Bugfix |

| v3.3.3 | 2026-05-23 21:02:10 | [UI/UX] 툴팁(st.help)의 물음표(stTooltipIcon) 아이콘의 색상과 투명도가 어두운 테마에서 가독성이 떨어지는 문제를 해결하기 위해 흰색(#ffffff) 및 opacity 1 강제 적용 CSS 추가 | UI/UX |

| v3.3.2 | 2026-05-23 20:59:16 | [UI/UX] 사이드바 내 토글(st.toggle) 위젯 라벨의 글자 색상이 어두운 배경에 의해 묻히는 문제를 해결하기 위해 흰색(#ffffff) 강제 적용 CSS 룰 추가 | UI/UX |

| v3.3.1 | 2026-05-23 20:55:43 | [Core/Bugfix] 매매 이력 누락 및 유실 버그 수정. sync_trades_to_csv()의 파괴적인 CSV 삭제 및 덮어쓰기 방식을 폐지하고 중복 주문(order_id) 가드 기반 증분 추가(Append) 동기화로 변경. symbol=None 조회 시 바이낸스 API 예외 발생을 예방하는 안전 가드 추가 및 현재 활성 포지션 심볼과 로컬 이력 심볼 목록을 분석해 필요한 종목만 지능적으로 거래소 체결을 수집해 메우도록 보강 | Core/Bugfix |

| v3.3.0 | 2026-05-23 20:31:26 | [UI/UX] 대시보드 전반의 가시성 개선 (사이드바 및 설정 위젯 이모지 추가, 메인 헤더 배지 수평 정렬, 메트릭 카드 네온 글로우 적용, 포지션 카드 텍스트 가독성 및 TAB 4 캔들 색상 표기 모순 보정) | UI/UX |

| v3.2.9 | 2026-05-23 16:54:33 | [Core/UI] 매매 이력의 '상태' 필드 불일치 해결. 실제 보유하지 않은 포지션이 로컬 기록상 미청산 상태로 남아 '보유 중'으로 표시되는 현상을 실시간 거래소 데이터(get_positions)와의 크로스체크를 통해 '청산 완료 (미기록)' 상태로 자동 보정하도록 보완 | Core/UI |

| v3.2.8 | 2026-05-23 01:38:58 | [Core/API] Binance API 시간 오차 자동 복구 및 허용 격차 범위 확장(recvWindow: 60000) | Core/API |

| v3.2.7 | 2026-05-22 23:37:13 | [UI/UX] 모든 탭(대시보드, 스캐너, 매매 이력, 포지션 진입, 설정, 딥러닝 최적화)에 마우스 오버 시 표시되는 안내 툴팁 추가 | UI/UX |

| v3.2.6 | 2026-05-22 20:21:47 | [Config] 에이전트 인계 규칙(Vibe Coding 연속성, 웹 검색 최상위 룰, 자율 실행, Git 복구 지점 등)을 .antigravityrules에 추가하고 영문으로 번역하여 보완 완료 | Config |

| v3.2.5 | 2026-05-22 20:18:47 | [Config] 에이전트 지침 파일(.antigravityrules)에 UI-전략 일관성 및 실제 로직 코드(trader.py/config.py) 크로스 검증 강제 규칙(Rule 4) 추가 | Config |

| v3.2.4 | 2026-05-22 20:16:33 | [UI/UX] 사이드바 '자동매매 ON/OFF' 툴팁 내 RSI 필터 조건을 조건부 설명(하단 개별 스위칭 활성화 시 추가 적용)으로 바로잡아 로직 오해의 소지 교정 | UI/UX |

| v3.2.3 | 2026-05-22 20:13:38 | [UI/UX] 사이드바 '자동매매 ON/OFF' 툴팁 설명에 전략의 핵심 지표 중 하나인 EMA200 누락분을 보정하여 AKMCD+SSL+RSI+EMA200 하이브리드 명시 | UI/UX |

| v3.2.2 | 2026-05-22 20:11:35 | [UI/UX] 사이드바 '자동매매 ON/OFF' 토글 위젯에 마우스 오버 시 표시되는 상세 도움말(help 툴팁: 엔진 기동 상태 및 포지션 유지 여부 상세 설명) 추가 | UI/UX |

| v3.2.1 | 2026-05-22 20:10:25 | [UI/UX] 메인 헤더 배지 영역(KST 시간, 연결상태, 리프레시 버튼)을 탭바(st.tabs) 우측 영역에 오도록 음수 마진 및 미디어 쿼리 수평 정렬 적용. 버튼 높이 38px 매칭 완료 | UI/UX |

| v3.2.0 | 2026-05-22 20:02:15 | [UI/Core] 금융전문사이트 분위기의 영롱한 글래스모피즘 테마 및 1cm 격자무늬, 우상향 글로우 그라데이션 적용. Git Tag 정보를 subprocess를 통해 동적으로 읽어 로고 버전에 표기하도록 연동 완료 | UI/Core |

| v3.1.9 | 2026-05-22 19:55:20 | [UI/Core] 사이드바 로고 버전을 APP_VERSION 상수로 분리 (하드코딩 v3.0.8 제거), git tag와 자동 동기화 구조 적용 | UI/Core |

| v3.1.8 | 2026-05-22 19:40:27 | [Core/Risk] MAX_DRAWDOWN_PCT 실제 낙폭 체크 로직 구현 (seed_money 대비 잔고 낙폭 ≥ 10% 시 진입 차단), Dead Code 정리 (strength<60 → strength<100, 4대 조건 완전 충족 필수) | Core/Risk |

| v3.1.7 | 2026-05-22 19:27:07 | [Test] 포지션 진입 파라미터 개별 격리 검증 테스트 33개 추가 (전략 4대 조건, EMA200/RSI 필터, 리스크 게이트, 포지션 가드, MAX_POSITIONS 레이스컨디션) | Test |

| v3.1.6 | 2026-05-22 19:21:18 | [UI/UX] 사이드바 기본 상태를 expanded로 변경, STRATEGY ENGINE 하위 expander(RSI 필터/운용 및 포지션/리스크 및 한도) 기본 접힘(collapsed)으로 통일 | UI/UX |

| v3.1.5 | 2026-05-22 19:13:07 | [UI/UX] 대시보드 로고 'AKMCD-SSL-RSI' 텍스트 폰트를 Pretendard로 변경 (CDN: pretendard@v1.3.9) | UI/UX |

| v3.0.9 | 2026-05-22 17:17:33 | [Test] 테스트 환경 격리를 위해 conftest.py에서 stats.json 파일 경로 모킹 추가 (테스트 실행 시 실제 stats 데이터 오염 및 리스크 블락으로 인한 테스트 실패 차단) | Test |

| v3.0.8 | 2026-05-22 17:15:17 | [UI/UX] 사이드바 내 '지표 및 스캐너 설정' 안에 숨겨져 있던 RSI 필터 설정을 독립된 expander(⚡ RSI 필터 설정)로 분리 및 기본 펼침(expanded=True) 설정 | UI/UX |

| v3.0.7 | 2026-05-22 17:14:15 | [UI/UX] 통계 초기화 시점의 총 잔고 금액을 '누적 수익률' 항목의 툴팁에 표시(초기화 시점의 총 잔고: {seed_money} USDT) 하도록 개선 | UI/UX |

| v3.0.6 | 2026-05-22 17:11:06 | [Core/Test] 5대 진입 조건 및 RSI 과열/과매도 차단 조건 검증 단위 테스트(test_entry_conditions_and_rsi_blocking) 추가 및 검증 완료 | Core/Test |

| v3.0.5 | 2026-05-22 16:53:01 | [UI/UX] 스캐너 결과 테이블 내 'RSI 필터'와 'RSI 수치' 컬럼 순서 스왑 (필터 여부 컬럼 우선 노출) | UI/UX |

| v3.0.4 | 2026-05-22 16:48:59 | [UI/UX] 대시보드 메인 헤더의 KST 시간, 연결 상태, REFRESH 버튼을 동일한 크기 및 균등한 비율의 버튼 스타일 박스로 통합 배치 | UI/UX |

| v3.0.3 | 2026-05-22 16:44:48 | [UI/UX] 스캐너(Scanner) 탭 결과 테이블에 RSI 수치 및 RSI 필터(만족 여부) 컬럼 추가 | UI/UX |

| v3.0.2 | 2026-05-22 16:39:06 | [UI/UX] 설정(Settings) 탭에 RSI 필터 파라미터(기간, 상한선, 하한선) 노출 및 프리셋 동기화 개선 | UI/UX |

| v3.0.1 | 2026-05-22 16:36:48 | [UI/UX] 대시보드 로고 'AKMCD-SSL-RSI' 텍스트 폰트 두께 상향 (font-weight: 900) | UI/UX |

| v2.1.0 | 2026-05-22 16:31:56 | [Core/Strategy/UI] RSI 필터 도입 (Long < 60, Short > 40) 및 사이드바/설정 화면 위젯 제어 연동, 프리셋 최적화 | Core/Strategy/UI |

| v3.1.4 | 2026-05-22 00:00:00 | [Core/UI] 1회 진입 증거금 기본값 4.0 USDT로 하향 조정, 대시보드 내 '수익율' 오탈자를 '수익률'로 일괄 교정 및 누적 수익률 우측에 툴팁 아이콘(ℹ)을 추가하여 초기화 시점 잔고를 즉시 팝오버 렌더링하도록 개선 | Core/UI |

| v3.1.3 | 2026-05-22 00:00:00 | [UI/UX] '수익률,승률 초기화' 클릭 시 설정되는 초기 시점의 총 잔고 금액 툴팁을 '누적 수익률' 항목의 개별 레이블 외 카드 전체 영역(terminal-metric-item)으로 마우스 오버 시 표시되도록 확장 개선 | UI/UX |

| v3.1.2 | 2026-05-22 00:00:00 | [Core/Strategy/UI] 사이드바 매매 제어에 'RSI 자동 스위칭' 토글 추가, 해당 토글 오프 시 RSI 필터링 비활성화 및 스캐너 결과 테이블에서 RSI 관련 컬럼 동적 비노출 처리 | Core/Strategy/UI |

| v3.1.1 | 2026-05-22 00:00:00 | [UI/Scanner] 스캐너 결과 테이블에 EMA 200 필터(만족 여부) 및 EMA 200 수치 컬럼 추가 | UI |

| v3.1.0 | 2026-05-22 00:00:00 | [Core/Strategy/UI] RSI + EMA 200 전략을 기본 진입 필터로 설정하고, ADX 시장 체계 자동 스위칭(추세/횡보 동적 필터링) 기능 사이드바 토글 매매제어로 추가. 불필요해진 롱/숏 허용 토글은 매매제어에서 삭제 | Core/UI |

| v2.0.1 | 2026-05-21 22:58:44 | [Bugfix/FSM] ERROR 및 활성 상태에서 수동 API 연결 시도 시 EngineState.CONNECTING으로의 상태 전이 허용 | Core/Bugfix |

| v1.4.09 | 2026-05-19 23:54:03 | [UI/UX] 5분봉 추이 그래프(Popover)의 가로폭을 부모 컨테이너(100% 영역)로 레이아웃 이동하여 약 128% 확장 | UI/UX |

| v1.4.08 | 2026-05-19 23:24:33 | [UI/UX] 포지션 카드 내 추세 그래프 기준을 15분봉에서 5분봉(최근 24시간, 288개 캔들)으로 좀 더 촘촘하게 교체 | UI/UX |

| v1.4.06 | 2026-05-19 23:13:37 | [UI/UX] 보유 중인 포지션 카드 내부에 15분봉 기준 24시간 가격/거래량 추세 그래프(Plotly Sparkline) 렌더링 추가 | UI/UX |

| v1.4.05 | 2026-05-19 23:04:55 | [UI/UX] 로테이션 설정 및 통계 초기화 버튼에 중딩 레벨 쉬운 한국어 툴팁 추가, 사이드바 버전 표기 v1.4.04로 업데이트 | UI/UX |

| v1.4.04 | 2026-05-19 22:35:43 | [Feature/Strategy] 정체 포지션 로테이션(Stale Position Rotation) 기능 및 설정 UI 추가 (1안 기술적 모멘텀 역전 기본 적용) | Core/Strategy/UI |

| v1.4.03 | 2026-05-19 22:26:38 | [Config/UI] 실시간 오토피팅(Auto-Tuning) 및 시작시 자동매매 ON 기본 활성화, 통계 메트릭 시각 정보 표기 개선 | Config/UI |

| v1.3.04 | 2026-05-19 09:20:27 | [Config] 최신 AI 에이전트 협업 스킬 3종(.antigravityrules) 적용 및 시맨틱 저장소 관리 규정 셋업 | Config |

| v1.3.03 | 2026-05-19 07:32:13 | [Bugfix] 손/익절 최저 임계치 하향(0.1%)을 통한 StreamlitValueBelowMinError 에러 차단 | Bugfix |

| v1.3.02 | 2026-05-19 07:21:08 | [Algorithm/UI] 일일 1~2% 수익 실현을 위한 데이 트레이딩(15m) 최적화 파라미터 적용 및 TIMEFRAME 원격 조정 위젯 추가 | Core/UI |

| v1.4.07 | 2026-05-19 00:00:00 | [UI/UX] 포지션 카드 내 추세 그래프를 공간 절약형 Popover(클릭 팝업) 방식으로 변경 | UI/UX |

| v1.4.02 | 2026-05-19 00:00:00 | [Feature/UI] 자동 피팅 이력 영구 기록(`autotune_history.csv`) 및 대시보드 7단 탭 레이아웃 재배치 | Feature/UI |

| v1.4.01 | 2026-05-19 00:00:00 | [Bugfix/Risk] SL/TP Stop-Market OCO 통합 주문(`attachAlgoOrds`) 적용 및 저유동성 스프레드 필터 추가 | Core/Risk |

| v1.4.00 | 2026-05-19 00:00:00 | [Architecture/Test] QuantumEngine v2 (FSM, Health Check, 백오프 자동 복구) 및 30개 단위 테스트 / Mock하네스 완성 | Core/Test |

| v1.3.01 | 2026-05-16 23:11:51 | [UI/UX] 스캐너(Scanner) 모니터링 탭 부활 (수동 스캔 시작 버튼은 미포함하여 자동매매 통합성 유지) | UI/UX |

| v1.3.00 | 2026-05-16 23:10:54 | [Architecture] '자동매매 ON' 시 백그라운드 자동 스캔 통합 및 기존 스캐너 탭 완전 삭제 | Core |

| v1.2.52 | 2026-05-15 20:18:06 | 포지션 잔상 방지 로직 도입 (즉시 은폐 캐시 및 이중 필터링) | Core |

| v1.2.51 | 2026-05-15 20:14:06 | 시스템 로그 줄바꿈 오류 수정 및 가독성 개선 | Bugfix |

| v1.2.50 | 2026-05-15 20:02:39 | 포지션 카드 버튼 간격 극소화 (음수 마진 적용) | UI/UX |

| v1.2.49 | 2026-05-15 20:01:35 | 메트릭 바 서브 텍스트 색상 변경 (흰색 적용) | UI/UX |

| v1.2.48 | 2026-05-15 19:56:26 | 누적 승률 동적 색상 로직 적용 (>50% 빨강) | UI/UX |

| v1.2.47 | 2026-05-15 19:51:48 | 포지션 카드 경과 시간/버튼 간격 축소 및 로직 개선 | UI/UX |

| v1.2.46 | 2026-05-15 19:44:56 | 금일 주문 산출 기준 통일 (청산 거래 수 한정) | Core |

| v1.2.45 | 2026-05-15 17:40:03 | 금일 주문 건수 실시간 집계 로직 적용 | Core |

| v1.2.44 | 2026-05-15 17:37:48 | 분할 체결 통합 승률 계산 로직 적용 (OrderID 그룹화) | Core |

| v1.2.43 | 2026-05-15 17:34:51 | AttributeError 수정 (fetch_my_trades -> get_trade_history) | Bugfix |

| v1.2.42 | 2026-05-15 17:34:10 | 매매 이력 기반 실시간 승률 계산 로직 적용 | Core |

| v1.2.41 | 2026-05-15 17:32:44 | MDD 한도 섹션 색상 변경 (Bright Grey) | UI/UX |

| v1.2.40 | 2026-05-15 17:31:30 | 누적 승률 기준일 표기 및 일 평균 수익률 계산 보정 | UI/UX |

| v1.2.39 | 2026-05-15 16:41:52 | 일 평균 수익률 계산 기준 KST로 변경 | Core |

| v1.2.39 | 2026-05-15 16:41:52 | 수익률 계산 시간대 KST(한국 시간) 동기화 | Core |

| v1.2.38 | 2026-05-15 16:13:54 | 2026-05-15 기준 통계 데이터(승률/주문) 초기화 | Core |

| v1.2.38 | 2026-05-15 16:13:54 | 누적 승률 및 주문 건수 집계 기준 초기화 (2026-05-15) | Core |

| v1.2.37 | 2026-05-15 15:58:33 | 수익률 계산 기준 업데이트 (.43) 및 일 평균 수익률 도입 | Core |

| v1.2.37 | 2026-05-15 15:58:33 | 누적 수익률 기준 변경 (.43) 및 일 평균 수익률 도입 | Trade |

| v1.2.37 | 2026-05-15 15:58:33 | 수익률 계산 로직 고도화 (.43 기준 및 일 평균 수익률 적용) | Core |

| v1.2.36 | 2026-05-15 15:54:18 | 전역 폰트 최소 크기 상향 (14px) 및 색상 통일 (Bright Grey) | UI/UX |

| v1.2.35 | 2026-05-15 15:42:01 | 진입 요약 박스 위치 변경 (제목 바로 아래) | UI/UX |

| v1.2.34 | 2026-05-15 15:40:34 | 진입 요약 박스 폰트 확대 (155%) 및 중앙 정렬 | UI/UX |

| v1.2.33 | 2026-05-15 15:37:55 | 진입 조건 탭 재미있는 요약 박스 추가 | UI/UX |

| v1.2.32 | 2026-05-15 15:31:05 | 진입 조건 탭 설명 문구 업데이트 (중딩 버전 + 노란색) | UI/UX |

| v1.2.31 | 2026-05-15 15:24:03 | 설정 하단 요약 정보 폰트 확대 (122%) 및 색상 개선 | UI/UX |

| v1.2.30 | 2026-05-15 15:23:30 | 설정 항목 재배치 (스캔 주기, 손절 위치 변경) | UI/UX |

| v1.2.29 | 2026-05-15 15:17:59 | 진입 행 노란색 강조 및 손익 데이터 제거 | UI/UX |

| v1.2.28 | 2026-05-15 15:15:36 | 매매 이력 수치 포맷팅 (x,xxx.xx) | UI/UX |

| v1.2.27 | 2026-05-15 15:10:47 | 매매 이력 필드 확장 (구분, 손익, %) 및 스타일링 | UI/UX |

| v1.2.26 | 2026-05-15 15:05:48 | 상단 메트릭 폰트 확대 (133%) 및 색상 가독성 개선 | UI/UX |

| v1.2.25 | 2026-05-15 14:59:03 | 티커별 정책 레버리지 기반 가변 진입 로직 적용 | Trade |

| v1.2.24 | 2026-05-15 14:49:02 | 일반 잔고 지표 색상 원복 (Neutral White) | UI/UX |

| v1.2.23 | 2026-05-15 14:46:53 | 상단 메트릭 바 커스텀 렌더링 및 색상 적용 | UI/UX |

| v1.2.22 | 2026-05-15 14:45:27 | 전역 수치 색상 로직 통일 (빨강/파랑) | UI/UX |

| v1.2.21 | 2026-05-15 14:43:04 | 백테스트 모듈 완전 삭제 | Core |

| v1.2.20 | 2026-05-15 14:42:05 | PnL 색상 로직 변경 (수익: 빨강, 손실: 파랑) | UI/UX |

| v1.2.19 | 2026-05-15 14:40:33 | 포지션 경과 시간 폰트 추가 확대 (0.98rem) | UI/UX |

| v1.2.18 | 2026-05-15 14:39:55 | 포지션 상세 정보 폰트 확대 및 색상 변경 (Bright Grey) | UI/UX |

| v1.2.17 | 2026-05-15 14:38:31 | 버튼 스타일 적용 방식 변경 (Marker 방식) | UI/UX |

| v1.2.16 | 2026-05-15 14:31:57 | 청산 버튼 및 폰트 크기 축소 (66% 사이즈) | UI/UX |

| v1.2.15 | 2026-05-15 14:29:53 | 포지션 카드에 'Amount'(진입 가치) 표기 추가 | UI/UX |

| v1.2.14 | 2026-05-15 14:25:22 | 포지션 경과 시간 스타일 고도화 (폰트 확대 및 3시간 경고) | UI/UX |

| v1.2.13 | 2026-05-15 14:23:45 | 상단 메트릭 바 '사용 중 증거금' 추가 | UI/UX |

| v1.2.12 | 2026-05-15 14:22:58 | 포지션 진입 경과 시간 표기 추가 | UI/UX |

| v2.0.2 | 2026-05-12 12:27:26 | [UI/UX] 스캐너 탭의 지표 컬럼명(EMA200, MACD, BB)을 기법에 맞추어 SSL 추세, AKMCD 영선, AKMCD 점전환으로 변경 | UI/UX |

| Older History | - | Archived due to encoding corruption | Archive |
