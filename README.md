# Stock Monitoring GUI (Python)

주가지수/종목 코드를 등록하고, 실시간(주기 갱신) 매매 체결값을 모니터링하는 Tkinter GUI 프로그램입니다.

## 주요 기능
- 기본 제공 코드(KOSPI, KOSDAQ, NASDAQ, S&P500, 삼성전자 등) 로드
- 사용자 종목코드 직접 등록
- 선택 코드 다중 추적
- 약 2초 간격으로 현재가/전일 대비/거래량 갱신
- 종목코드 목록을 `stock_codes.json`으로 저장

## 실행 방법 (소스 실행)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 실행파일(.exe) 빌드 (Windows)
로컬 PC에서 아래 배치 파일만 실행하면 exe를 만들 수 있습니다.

```bat
build_exe.bat
```

빌드 결과:
- `dist/stock-monitor.exe`

## 사용 방법
1. 상단 콤보에서 종목/지수를 선택 후 `추가`
2. `새 코드 입력`에 심볼 입력 후 `코드 등록`
   - 예: `005930.KS`, `AAPL`, `^IXIC`
3. 목록에서 선택 후 `삭제`
4. 코드 목록 확정 시 `저장` 버튼으로 `stock_codes.json` 반영

## 참고
- 데이터 소스: `yfinance`
- 엄밀한 체결 틱 단위 실시간이 아니라, 공개 데이터 기반의 **주기적 실시간 모니터링**입니다.
