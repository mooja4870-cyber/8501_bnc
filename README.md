# ⚡ AI QUANTUM — OKX Auto-Trading System

**10x 레버리지 · Triple-Indicator · Streamlit 대시보드**

---

## 📁 프로젝트 구조

```
okx_quantum/
├── app.py                  ← Streamlit 메인 대시보드 (실행 진입점)
├── requirements.txt        ← 패키지 목록
├── .env.example            ← API 키 환경변수 예시
├── .env                    ← ★ 실제 API 키 (직접 생성)
└── core/
    ├── config.py           ← 전체 파라미터 설정
    ├── exchange.py         ← OKX API v5 클라이언트
    ├── strategy.py         ← Triple-Indicator 전략 엔진
    ├── backtest.py         ← 백테스트 엔진 (1Y/2Y/3Y)
    ├── scanner.py          ← 전종목 실시간 스캐너
    └── trader.py           ← 자동매매 실행 + 리스크 관리
```

---

## 🚀 설치 및 실행

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 OKX API 키를 입력하세요:

```
OKX_API_KEY=실제_API_키
OKX_SECRET_KEY=실제_시크릿_키
OKX_PASSPHRASE=실제_패스프레이즈
```

> **OKX API 키 발급 방법**
> OKX → 계정 → API 관리 → API 생성
> 권한: 거래 ✅ / 출금 ❌ (출금 권한은 절대 부여 금지)
> IP 화이트리스트 설정 권장

### 3. Streamlit 앱 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 🧠 매매 전략 (Triple-Indicator)

| 지표 | 역할 | 설정 |
|------|------|------|
| EMA 200 | 추세 필터 | 가격이 EMA200 위 → 롱만 허용 |
| Bollinger Bands | 진입 타점 | 하단 터치 후 회귀 시 진입 |
| MACD | 모멘텀 확인 | 히스토그램 방향 전환 시 실행 |

**손익비 모델**: 손절 2% / 익절 5% → 손익비 1:2.5
승률 50% 미만에서도 전체 수익 우상향 구조

---

## ⚠️ 리스크 경고

- 레버리지 10배는 증거금의 10배 손실 위험 있음
- Stop-Loss는 자동 설정되나 급격한 변동성(펀딩비·청산)에는 100% 보호 불가
- 백테스트 과거 수익률은 미래를 보장하지 않음
- 소액(10 USDT)으로 충분한 검증 후 증액 권장
- 자동매매 실행 중 인터넷 단절 시 포지션 관리 불가 → 서버(VPS) 운용 권장

---

## 🖥️ VPS 운용 가이드 (24/7 자동매매)

```bash
# 백그라운드 실행
nohup streamlit run app.py --server.port 8501 &

# 또는 systemd 서비스 등록
# /etc/systemd/system/quantum.service 생성 후:
sudo systemctl start quantum
sudo systemctl enable quantum
```

---

## 📞 문의

설계 기준: OKX API v5 / 2026년 5월
