"""Trade-log analysis. Research only."""
import pandas as pd


def analyze_trading_patterns(portfolio, transactions, ticker):
    """Enhanced trading pattern analysis with risk management insights"""
    if not transactions:
        return
    
    print(f"\n=== Enhanced Trading Analysis for {ticker} ===")
    
    # Basic trading stats
    total_days = (transactions[-1]['Date'] - transactions[0]['Date']).days
    avg_trades_per_day = len(transactions) / total_days if total_days > 0 else 0
    
    # Categorize transactions
    buys = [t for t in transactions if t['Action'] == 'BUY']
    sells = [t for t in transactions if t['Action'] in ['SELL', 'EXIT_LONG', 'EXIT_SHORT']]
    shorts = [t for t in transactions if t['Action'] == 'SHORT']
    covers = [t for t in transactions if t['Action'] == 'COVER']
    stop_losses = [t for t in transactions if 'STOP_LOSS' in t['Action']]
    take_profits = [t for t in transactions if 'TAKE_PROFIT' in t['Action']]
    trailing_stops = [t for t in transactions if 'TRAILING_STOP' in t['Action']]
    
    print(f"Trading Frequency: {len(transactions)} transactions over {total_days} days ({avg_trades_per_day:.2f}/day)")
    entries = len(buys) + len(shorts)
    exits = len(sells)
    print(f"Entries: {entries} | Normal Exits: {exits}")
    print(f"Stop Losses: {len(stop_losses)} | Take Profits: {len(take_profits)} | Trailing Stops: {len(trailing_stops)}")
    
    # Risk management effectiveness
    risk_exits = stop_losses + take_profits + trailing_stops
    if risk_exits:
        avg_risk_return = sum(t['Return'] for t in risk_exits) / len(risk_exits)
        print(f"Risk Management Exits: {len(risk_exits)} (avg return: {avg_risk_return:.2f}%)")
    
    # Performance analysis
    if len(transactions) >= 2:
        returns = [t['Return'] for t in transactions if t['Action'] not in ['BUY', 'SHORT']]
        if returns:
            best_return = max(returns)
            worst_return = min(returns)
            avg_return = sum(returns) / len(returns)
            print(f"Best trade: {best_return:.2f}% | Worst trade: {worst_return:.2f}% | Average: {avg_return:.2f}%")
    
    # Recent activity
    recent_cutoff = transactions[-1]['Date'] - pd.Timedelta(days=7)
    recent_trades = [t for t in transactions if t['Date'] >= recent_cutoff]
    print(f"Recent activity (last 7 days): {len(recent_trades)} transactions")
