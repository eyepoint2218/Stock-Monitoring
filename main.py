import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Dict, List

import tkinter as tk
from tkinter import messagebox, ttk

import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
CODES_FILE = BASE_DIR / "stock_codes.json"
REFRESH_SECONDS = 2


@dataclass
class TickerSnapshot:
    symbol: str
    price: float
    change: float
    volume: int
    timestamp: str


class StockMonitorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("주가지수/종목 실시간 모니터")
        self.root.geometry("1000x540")

        self.ticker_map: Dict[str, str] = {}
        self.tracked_symbols: List[str] = []
        self.queue: Queue[TickerSnapshot] = Queue()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None

        self._load_codes()
        self._build_ui()
        self._apply_default_symbols()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(200, self.process_queue)

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root, padding=12)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="등록된 종목/지수 선택").grid(row=0, column=0, sticky=tk.W)

        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(
            top_frame,
            textvariable=self.symbol_var,
            width=32,
            state="readonly",
            values=sorted(self.ticker_map.keys()),
        )
        self.symbol_combo.grid(row=0, column=1, padx=8)

        ttk.Button(top_frame, text="추가", command=self.add_symbol).grid(row=0, column=2, padx=4)
        ttk.Button(top_frame, text="삭제", command=self.remove_selected).grid(row=0, column=3, padx=4)
        ttk.Button(top_frame, text="저장", command=self.save_codes).grid(row=0, column=4, padx=4)

        ttk.Label(top_frame, text="새 코드 입력 (예: AAPL, ^KS11)").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.new_symbol_var = tk.StringVar()
        self.new_symbol_entry = ttk.Entry(top_frame, textvariable=self.new_symbol_var, width=34)
        self.new_symbol_entry.grid(row=1, column=1, padx=8, pady=(8, 0))
        ttk.Button(top_frame, text="코드 등록", command=self.register_code).grid(row=1, column=2, padx=4, pady=(8, 0))

        middle_frame = ttk.Frame(self.root, padding=12)
        middle_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("symbol", "price", "change", "volume", "timestamp")
        self.tree = ttk.Treeview(middle_frame, columns=columns, show="headings", height=16)
        self.tree.heading("symbol", text="심볼")
        self.tree.heading("price", text="현재가")
        self.tree.heading("change", text="전일대비")
        self.tree.heading("volume", text="거래량")
        self.tree.heading("timestamp", text="갱신시각")

        self.tree.column("symbol", width=200, anchor=tk.W)
        self.tree.column("price", width=140, anchor=tk.E)
        self.tree.column("change", width=140, anchor=tk.E)
        self.tree.column("volume", width=140, anchor=tk.E)
        self.tree.column("timestamp", width=180, anchor=tk.CENTER)

        scroll = ttk.Scrollbar(middle_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="대기 중")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, padding=6)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _load_codes(self) -> None:
        if not CODES_FILE.exists():
            self.ticker_map = {
                "KOSPI (^KS11)": "^KS11",
                "KOSDAQ (^KQ11)": "^KQ11",
                "NASDAQ (^IXIC)": "^IXIC",
                "S&P500 (^GSPC)": "^GSPC",
                "삼성전자 (005930.KS)": "005930.KS",
                "Apple (AAPL)": "AAPL",
            }
            return

        with CODES_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        self.ticker_map = {item["name"]: item["symbol"] for item in raw if "name" in item and "symbol" in item}

    def _apply_default_symbols(self) -> None:
        defaults = ["KOSPI (^KS11)", "NASDAQ (^IXIC)", "삼성전자 (005930.KS)"]
        for name in defaults:
            if name in self.ticker_map:
                self.tracked_symbols.append(self.ticker_map[name])
                self.tree.insert("", tk.END, iid=self.ticker_map[name], values=(name, "-", "-", "-", "-"))

        self.start_worker()

    def start_worker(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.worker_thread.start()

    def _poll_loop(self) -> None:
        while not self.stop_event.is_set():
            symbols = list(self.tracked_symbols)
            if not symbols:
                time.sleep(REFRESH_SECONDS)
                continue

            for symbol in symbols:
                if self.stop_event.is_set():
                    break

                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1d", interval="1m")
                    if hist.empty:
                        continue

                    close_series = hist["Close"].dropna()
                    volume_series = hist["Volume"].dropna()
                    if close_series.empty:
                        continue

                    latest_price = float(close_series.iloc[-1])
                    open_price = float(close_series.iloc[0])
                    change = latest_price - open_price
                    latest_volume = int(volume_series.iloc[-1]) if not volume_series.empty else 0

                    snapshot = TickerSnapshot(
                        symbol=symbol,
                        price=latest_price,
                        change=change,
                        volume=latest_volume,
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    self.queue.put(snapshot)
                except Exception as exc:
                    self.status_var.set(f"{symbol} 조회 실패: {exc}")

            time.sleep(REFRESH_SECONDS)

    def process_queue(self) -> None:
        while True:
            try:
                snapshot = self.queue.get_nowait()
            except Empty:
                break

            name = self.name_for_symbol(snapshot.symbol)
            price_text = f"{snapshot.price:,.2f}"
            change_text = f"{snapshot.change:+,.2f}"
            volume_text = f"{snapshot.volume:,}"

            if snapshot.symbol in self.tree.get_children():
                self.tree.item(snapshot.symbol, values=(name, price_text, change_text, volume_text, snapshot.timestamp))

            self.status_var.set(f"마지막 업데이트: {snapshot.symbol} {snapshot.timestamp}")

        self.root.after(250, self.process_queue)

    def name_for_symbol(self, symbol: str) -> str:
        for name, value in self.ticker_map.items():
            if value == symbol:
                return name
        return symbol

    def add_symbol(self) -> None:
        selected = self.symbol_var.get()
        if not selected:
            messagebox.showinfo("안내", "추가할 종목을 선택하세요.")
            return

        symbol = self.ticker_map[selected]
        if symbol in self.tracked_symbols:
            return

        self.tracked_symbols.append(symbol)
        self.tree.insert("", tk.END, iid=symbol, values=(selected, "-", "-", "-", "-"))
        self.status_var.set(f"추적 목록에 추가: {selected}")

    def remove_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("안내", "삭제할 항목을 선택하세요.")
            return

        for iid in selected:
            if iid in self.tracked_symbols:
                self.tracked_symbols.remove(iid)
            self.tree.delete(iid)

        self.status_var.set("선택 종목 삭제 완료")

    def register_code(self) -> None:
        symbol = self.new_symbol_var.get().strip().upper()
        if not symbol:
            messagebox.showwarning("경고", "종목코드를 입력하세요.")
            return

        name = f"사용자 등록 ({symbol})"
        if name in self.ticker_map:
            messagebox.showinfo("안내", "이미 등록된 코드입니다.")
            return

        self.ticker_map[name] = symbol
        self.symbol_combo["values"] = sorted(self.ticker_map.keys())
        self.symbol_var.set(name)
        self.new_symbol_var.set("")
        self.status_var.set(f"코드 등록: {symbol}")

    def save_codes(self) -> None:
        records = [{"name": name, "symbol": symbol} for name, symbol in sorted(self.ticker_map.items())]
        with CODES_FILE.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        messagebox.showinfo("저장 완료", f"{CODES_FILE.name}에 저장했습니다.")
        self.status_var.set("종목코드 저장 완료")

    def on_close(self) -> None:
        self.stop_event.set()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    app = StockMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
