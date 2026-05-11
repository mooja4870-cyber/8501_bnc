# Project Status: AI QUANTUM OKX Auto-Trader

## Current Status
- Initialized Streamlit dashboard with OKX API integration.
- Added QuantumEngine Orchestration layer.
- Fixed Margin & PnL display logic (v1.1.34).

## v1.1.52 (2026-05-11)
- [Performance] **스캔 속도 300% 향상**: 종목당 스캔 대기 시간을 0.3초에서 0.1초로 단축하여 신호 포착 지연 대폭 감소.
- [UI] **시간 표시 스타일 최적화**: KST 시간 표시 폰트 색상을 흰색으로 변경 및 가독성 개선.
- [Logic] **증거금 우선 매매 로직**: 설정된 증거금(Margin)을 고정하고 레버리지를 가변적으로 적용하는 실전형 로직으로 전환.

## v1.1.45 (2026-05-11)
- [Critical] **중복 진입(Duplicate Entry) 버그 해결**: 기존 스캐너 스레드가 중첩되어 실행되던 문제 해결 (엔진 초기화 시 기존 스레드 강제 종료 로직 추가).
- [Stability] **AutoTrader 보호막 강화**: 펜딩 상태 관리 및 락(Lock) 로직 고도화로 이중 주문 원천 차단.
- [UI] **초기 자본금 수정 로직 개선**: 입력 즉시 수익률이 반영되며, 성공 메시지가 딱 한 번만 뜨도록 최적화.
- [UI] **무지개 로고 스타일 업데이트**: 참조 프로젝트(d_brief4vc)의 7색 그라데이션 및 6초 애니메이션 반영.
- [UI] **매매 이력 상세화**: 체결 이력에 '수량' 및 '거래금액(USDT)' 컬럼 추가.

## v1.1.44 (2026-05-11)
- [Fix] 설정(초기 자본금 등) 수정 시 UI 무한 루프 및 팝업 깜빡임 현상 해결.
- [Fix] `app.py`와 `core/config.py` 간의 설정 인스턴스 동기화 최적화.
- [Feature] 설정 탭에 '모든 설정 영구 저장' 버튼 추가 및 `.env` 연동 강화.

## v1.1.35 (2026-05-11)
- [Feature] 초기 자본금 기반 수익률 관리 및 24시간 성과 추적 대시보드 적용.

## v1.1.34 (2026-05-11)
- [Fix] 증거금 계산 최적화 및 매매 이력 고도화.

## v1.1.30 ~ v1.1.33 (2026-05-11)
- [UI/Flow] 로고 애니메이션, 자동 백테스트 강제화, 중복 진입 가드 기초 구현.
