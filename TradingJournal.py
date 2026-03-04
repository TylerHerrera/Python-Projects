import json
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

DATA_FILE = "data/trades.json"

def main():
    trades = load_trades(DATA_FILE)

    while True:
        print("\n--- TRADING JOURNAL & PORTFOLIO (CLI) ---")
        print("1. Add trade")
        print("2. View journal")
        print("3. View portfolio")
        print("4. Show P/L chart")
        print("5. Save & exit")

        choice = input("Choose an option (number): ").strip()
        if choice == "1":
            symbol = input("Symbol: ").strip().upper()
            date = input("Date (YYYY-MM-DD): ").strip()
            side = input("Side (BUY/SELL): ").strip()
            if side not in {"BUY", "SELL"}: raise ValueError("side must be BUY or SELL")
            qty = int(input("Quantity: ").strip())
            price = float(input("Price: ").strip())
            if qty <= 0 or price <= 0: raise ValueError("qty and price must be positive")
            fees = float(input("Fees (0 if none or as default): ").strip() or 0)
            strategy = input("Strategy (optional): ").strip()
            notes = input("Notes (optional): ").strip()
            try:
                trades = add_trade(trades, symbol, date, side, qty, price, fees, strategy, notes)
                print("Trade added.")
            except ValueError as e: print(f"Error: {e}")

        elif choice == "2": print_journal(trades)

        elif choice == "3": print_portfolio(trades)

        elif choice == "4": show_unrealized_pl_chart(trades)

        elif choice == "5":
            save_trades(trades, DATA_FILE)
            print("Saved. Goodbye!")
            break

        else: print("Invalid choice.")

def load_trades(path: str = DATA_FILE) -> list:
    # load trades from a JSON file
    # return empty list if file missing or invalid
    try:
        with open(path, "r", encoding="utf-8") as db:
            data = json.load(db)
            if isinstance(data, list):
                return data
            return []
    except (FileNotFoundError, json.JSONDecodeError): return []

def save_trades(trades: list, path: str = DATA_FILE) -> None:
    with open(path, "w", encoding="utf-8") as db: json.dump(trades, db, indent=4, ensure_ascii=False)

def add_trade(trades: list, symbol: str, date_str: str, side: str,
              qty: float, price: float, fees_in_percentage: float = 0.0,
              strategy: str = "", notes: str = "") -> list:
    symbol = symbol.upper().strip()
    side = side.upper().strip()

    # ensure valid date format
    try: dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError: raise ValueError("date must be in format YYYY-MM-DD")

    # create new id from previous entry
    next_id = max((t["id"] for t in trades), default=0) + 1

    trade = {
        "id": next_id,
        "date": dt.isoformat(),
        "symbol": symbol,
        "side": side,
        "qty": float(qty),
        "price": float(price),
        "fees_in_percentage": float(fees_in_percentage),
        "strategy": strategy,
        "notes": notes,
    }

    # add a trade to the list and return a new list
    new_trades = trades.copy()
    new_trades.append(trade)
    return new_trades

def fetch_current_price(symbol: str) -> float:
    # fetch current price using yfinance.
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")
    if data.empty:
        raise ValueError(f"No price data for symbol {symbol}")
    return float(data["Close"].iloc[-1])

def build_portfolio(trades: list) -> dict:
    # use simple average-cost method
    # internal dictionary to track avg cost and shares
    positions: dict[str, dict] = {} # {symbol: {"shares", "avg_cost"}}

    for t in trades:
        symbol = t["symbol"]
        side = t["side"]
        qty = float(t["qty"])
        price = float(t["price"])
        fees = float(t["fees_in_percentage"])

        if symbol not in positions: positions[symbol] = {"shares": 0.0, "avg_cost": 0.0}

        filler = positions[symbol]
        shares = filler["shares"]
        avg_cost = filler["avg_cost"]


        total_cost_before = shares * avg_cost
        if side == "BUY":
            total_cost_after = total_cost_before + qty * price * (1 + fees)
            new_shares = shares + qty
        elif side == "SELL":
            total_cost_after = total_cost_before - qty * price * (1 + fees)
            new_shares = shares - qty
        if new_shares > 0:
            new_avg_cost = total_cost_after / new_shares
        else:
            new_avg_cost = 0.0
        filler["shares"] = new_shares
        filler["avg_cost"] = new_avg_cost

    # remove zero-share symbols
    return {s: p for s, p in positions.items() if p["shares"] != 0} # {symbol: {"shares", "avg_cost"}}

def compute_unrealized_pl(trades: list, symbol: str | None = None):
    portfolio = build_portfolio(trades)
    # filter if symbol provided
    if symbol is not None: filtered = {s: p for s, p in portfolio.items() if s == symbol}
    else: filtered = portfolio

    result = {"symbols": {}, "total_unrealized_pl": 0.0, "total_market_value": 0.0}

    for sym, pos in filtered.items():
        shares = pos["shares"]
        avg_cost = pos["avg_cost"]
        current = fetch_current_price(sym)

        if current is None: continue

        market_value = shares * current
        unreal = (current - avg_cost) * shares

        result["symbols"][sym] = {
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": current,
            "market_value": market_value,
            "unrealized_pl": unreal,
        }

        result["total_unrealized_pl"] += unreal
        result["total_market_value"] += market_value

    return result

# CLI
def print_journal(trades: list) -> None:
    if not trades:
        print("No trades yet.")
        return
    df = pd.DataFrame(trades)
    print(df)

def print_portfolio(trades: list) -> None:
    # build dataframe
    portfolio = build_portfolio(trades)
    table = []
    if not portfolio:
        print("No open positions.")
        return
    for sym, pos in portfolio.items():
        if pos["shares"] == 0:
            continue

        current_price = fetch_current_price(sym)
        qty = pos["shares"]
        avg_entry_price = pos["avg_cost"]
        capital = qty * avg_entry_price
        market_value = qty * current_price
        pnl = market_value - capital
        pct_diff = (pnl / capital * 100) if capital > 0 else 0.0

        table.append({
            "symbol": sym,
            "qty": qty,
            "avg_entry price": avg_entry_price,
            "current price": current_price,
            "capital": capital,
            "market value": market_value,
            "profit/loss": pnl,
            "percentage difference": pct_diff
        })

    
    portfolio_df = pd.DataFrame(table)
    portfolio_df.loc[len(portfolio_df)]={
            "symbol": "Total",
            "qty": "N/A",
            "avg_entry price": "N/A",
            "current price": "N/A",
            "capital": portfolio_df["capital"].sum(),
            "market value": portfolio_df["market value"].sum(),
            "profit/loss": portfolio_df["profit/loss"].sum(),
            "percentage difference": (portfolio_df["profit/loss"].sum() / portfolio_df["capital"].sum() * 100)
        }
    print(portfolio_df)

def show_unrealized_pl_chart(trades: list) -> None:
    choice = input("Symbol for P/L chart (leave empty for entire portfolio): ").strip()
    symbol = choice if choice else None
    data = compute_unrealized_pl(trades, symbol)

    if not data["symbols"]:
        print("No open position to plot.")
        return

    labels = list(data["symbols"].keys()) + ["TOTAL"]
    values = [info["unrealized_pl"] for info in data["symbols"].values()]
    values.append(data["total_unrealized_pl"])

    plt.figure()
    plt.bar(labels, values)
    for i, txt in enumerate(values):
        plt.annotate(txt, (labels[i], values[i]), textcoords="offset points", xytext=(0,10), ha='center',
                 arrowprops=dict(facecolor='black', shrink=0.05, width=0.5, headwidth=5))
    title = f"Unrealized P/L - {symbol}" if symbol else "Unrealized P/L - Portfolio"
    plt.title(title)
    plt.xlabel("Symbol")
    plt.ylabel("Unrealized P/L")
    plt.grid(True, axis="y")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
