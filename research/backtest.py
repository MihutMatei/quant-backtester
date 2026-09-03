"""Backtest simulation loop. No plotting dependencies."""
import pandas as pd


def backtest_strategy(df, signals, initial_capital=10000.0, log_transactions=True,
                     stop_loss_pct=None, take_profit_pct=None, 
                     use_trailing_stop=False, trailing_stop_pct=None,
                     enable_shorting=True, dedup_window_minutes=5, spread_pct=0.001):
    """
    Enhanced backtest with stop-loss, take-profit, and shorting functionality
    
    Args:
        df: Price data DataFrame
        signals: Trading signals DataFrame
        initial_capital: Starting capital
        log_transactions: Whether to log transactions
        stop_loss_pct: Stop loss percentage (e.g., 0.05 for 5%)
        take_profit_pct: Take profit percentage (e.g., 0.10 for 10%)
        use_trailing_stop: Enable trailing stop loss
        trailing_stop_pct: Trailing stop percentage
        enable_shorting: Enable short selling functionality
        dedup_window_minutes: Time window in minutes to prevent duplicate transactions
        spread_pct: Bid-ask spread percentage (e.g., 0.001 for 0.1%)
    """
    cash = initial_capital
    shares = 0.0  # Positive for long positions, negative for short positions
    portfolio = pd.DataFrame(index=df.index)
    portfolio['cash'] = cash
    portfolio['shares'] = shares
    portfolio['total'] = cash
    
    transactions = []
    
    # Deduplication tracking - prevent duplicate transactions within time window
    last_transaction_time = None
    last_transaction_type = None
    dedup_window = pd.Timedelta(minutes=dedup_window_minutes)
    
    # Risk management tracking
    position_entry_price = None
    position_entry_date = None
    trailing_stop_price = None
    position_type = None  # 'long' or 'short'
    
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    def should_allow_transaction(action_type, current_time):
        """Check if a transaction should be allowed based on deduplication window"""
        nonlocal last_transaction_time, last_transaction_type
        
        # Always allow risk management exits (stop loss, take profit, trailing stop)
        if any(risk_action in action_type for risk_action in ['STOP_LOSS', 'TAKE_PROFIT', 'TRAILING_STOP']):
            return True
            
        # Allow transaction if no previous transaction or enough time has passed
        if last_transaction_time is None or (current_time - last_transaction_time) >= dedup_window:
            return True
            
        # Block ANY transaction type if within the deduplication window
        return False
    
    def record_transaction(action_type, current_time):
        """Record the transaction time and type for deduplication"""
        nonlocal last_transaction_time, last_transaction_type
        last_transaction_time = current_time
        last_transaction_type = action_type

    def get_transaction_price(mid_price, action_type, spread_pct):
        """Calculate actual transaction price considering bid-ask spread"""
        spread = mid_price * spread_pct
        
        if action_type in ['BUY', 'COVER']:
            # Buying: pay ask price (mid + spread/2)
            return mid_price * (1 + spread_pct / 2)
        elif action_type in ['SELL', 'SHORT']:
            # Selling: receive bid price (mid - spread/2)
            return mid_price * (1 - spread_pct / 2)
        else:
            # Risk management exits: use mid price
            return mid_price

    for i, (date, row) in enumerate(df.iterrows()):
        current_price = row[price_col]
        current_signal = signals.iloc[i]['signal']
        prev_signal = signals.iloc[i-1]['signal'] if i > 0 else 0.0
        
        # Risk management checks for existing positions
        if shares != 0 and position_entry_price is not None:
            should_exit = False
            exit_reason = ""
            exit_price = current_price
            
            if position_type == 'long':
                # Long position risk management
                position_return = (current_price - position_entry_price) / position_entry_price
                
                # Stop loss check
                if stop_loss_pct and position_return <= -stop_loss_pct:
                    should_exit = True
                    exit_reason = "STOP_LOSS"
                    exit_price = position_entry_price * (1 - stop_loss_pct)
                
                # Take profit check
                elif take_profit_pct and position_return >= take_profit_pct:
                    should_exit = True
                    exit_reason = "TAKE_PROFIT"
                    exit_price = position_entry_price * (1 + take_profit_pct)
                
                # Trailing stop logic for long positions
                elif use_trailing_stop and trailing_stop_pct:
                    if trailing_stop_price is None:
                        trailing_stop_price = current_price * (1 - trailing_stop_pct)
                    else:
                        # Update trailing stop if price moved favorably (upward)
                        new_trailing_stop = current_price * (1 - trailing_stop_pct)
                        if new_trailing_stop > trailing_stop_price:
                            trailing_stop_price = new_trailing_stop
                    
                    # Check if trailing stop was hit
                    if current_price <= trailing_stop_price:
                        should_exit = True
                        exit_reason = "TRAILING_STOP"
                        exit_price = trailing_stop_price
                        
            elif position_type == 'short':
                # Short position risk management (inverse logic)
                position_return = (position_entry_price - current_price) / position_entry_price
                
                # Stop loss check for short (price goes up)
                if stop_loss_pct and position_return <= -stop_loss_pct:
                    should_exit = True
                    exit_reason = "STOP_LOSS"
                    exit_price = position_entry_price * (1 + stop_loss_pct)
                
                # Take profit check for short (price goes down)
                elif take_profit_pct and position_return >= take_profit_pct:
                    should_exit = True
                    exit_reason = "TAKE_PROFIT"
                    exit_price = position_entry_price * (1 - take_profit_pct)
                
                # Trailing stop logic for short positions
                elif use_trailing_stop and trailing_stop_pct:
                    if trailing_stop_price is None:
                        trailing_stop_price = current_price * (1 + trailing_stop_pct)
                    else:
                        # Update trailing stop if price moved favorably (downward)
                        new_trailing_stop = current_price * (1 + trailing_stop_pct)
                        if new_trailing_stop < trailing_stop_price:
                            trailing_stop_price = new_trailing_stop
                    
                    # Check if trailing stop was hit
                    if current_price >= trailing_stop_price:
                        should_exit = True
                        exit_reason = "TRAILING_STOP"
                        exit_price = trailing_stop_price
            
            # Execute risk management exit
            if should_exit:
                # Determine transaction price with spread adjustment
                if position_type == 'long':
                    # Selling long position
                    transaction_price = get_transaction_price(exit_price, 'SELL', spread_pct)
                    pnl = (transaction_price - position_entry_price) * shares
                    cash += shares * transaction_price
                elif position_type == 'short':
                    # Covering short position
                    transaction_price = get_transaction_price(exit_price, 'COVER', spread_pct)
                    pnl = (position_entry_price - transaction_price) * abs(shares)
                    cash += pnl  # Add the PnL to cash
                
                pnl_pct = pnl / (position_entry_price * abs(shares)) * 100
                
                action = f"{exit_reason}_{position_type.upper()}"
                if log_transactions:
                    transactions.append({
                        'Date': date,
                        'Action': action,
                        'Price': transaction_price,
                        'Shares': abs(shares),
                        'PnL': pnl,
                        'Return': pnl_pct,
                        'Portfolio_Value': cash
                    })
                record_transaction(action, date)
                
                shares = 0.0
                position_entry_price = None
                position_entry_date = None
                trailing_stop_price = None
                position_type = None
        
        # Regular signal-based trading
        if current_signal != prev_signal:
            if current_signal == 1.0 and shares == 0:  # Buy signal when not in position
                if cash > 0 and should_allow_transaction('BUY', date):
                    transaction_price = get_transaction_price(current_price, 'BUY', spread_pct)
                    new_shares = cash / transaction_price
                    
                    shares = new_shares
                    cash = 0.0
                    position_entry_price = transaction_price
                    position_entry_date = date
                    trailing_stop_price = None
                    position_type = 'long'
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'BUY',
                            'Price': transaction_price,
                            'Shares': new_shares,
                            'PnL': 0.0,
                            'Return': 0.0,
                            'Portfolio_Value': shares * current_price
                        })
                    record_transaction('BUY', date)
            
            elif current_signal == -1.0 and shares > 0:  # Sell signal when in long position
                if should_allow_transaction('SELL', date):
                    transaction_price = get_transaction_price(current_price, 'SELL', spread_pct)
                    pnl = (transaction_price - position_entry_price) * shares
                    pnl_pct = (transaction_price - position_entry_price) / position_entry_price * 100
                    
                    cash = shares * transaction_price
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'SELL',
                            'Price': transaction_price,
                            'Shares': shares,
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash
                        })
                    record_transaction('SELL', date)
                    
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                    
                    # If shorting is enabled, enter short position immediately
                    if enable_shorting and cash > 0 and should_allow_transaction('SHORT', date):
                        transaction_price = get_transaction_price(current_price, 'SHORT', spread_pct)
                        short_shares = cash / transaction_price
                        
                        shares = -short_shares  # Negative for short position
                        # For short positions, we keep the cash from the original sale
                        # and track the short position separately
                        position_entry_price = transaction_price
                        position_entry_date = date
                        trailing_stop_price = None
                        position_type = 'short'
                        
                        if log_transactions:
                            transactions.append({
                                'Date': date,
                                'Action': 'SHORT',
                                'Price': transaction_price,
                                'Shares': short_shares,
                                'PnL': 0.0,
                                'Return': 0.0,
                                'Portfolio_Value': cash
                            })
                        record_transaction('SHORT', date)
            
            elif current_signal == -1.0 and shares == 0 and enable_shorting:  # Short signal when not in position
                if cash > 0 and should_allow_transaction('SHORT', date):
                    transaction_price = get_transaction_price(current_price, 'SHORT', spread_pct)
                    short_shares = cash / transaction_price
                    
                    shares = -short_shares  # Negative for short position
                    # For short positions, we keep the original cash
                    position_entry_price = transaction_price
                    position_entry_date = date
                    trailing_stop_price = None
                    position_type = 'short'
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'SHORT',
                            'Price': transaction_price,
                            'Shares': short_shares,
                            'PnL': 0.0,
                            'Return': 0.0,
                            'Portfolio_Value': cash
                        })
                    record_transaction('SHORT', date)
            
            elif current_signal == 1.0 and shares < 0:  # Buy signal when in short position (cover)
                if should_allow_transaction('COVER', date):
                    transaction_price = get_transaction_price(current_price, 'COVER', spread_pct)
                    pnl = (position_entry_price - transaction_price) * abs(shares)
                    pnl_pct = (position_entry_price - transaction_price) / position_entry_price * 100
                    
                    # Cover short position: add PnL to cash
                    cash = cash + pnl
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'COVER',
                            'Price': transaction_price,
                            'Shares': abs(shares),
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash
                        })
                    record_transaction('COVER', date)
                    
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                    
                    # Enter long position immediately after covering
                    if cash > 0 and should_allow_transaction('BUY', date):
                        transaction_price = get_transaction_price(current_price, 'BUY', spread_pct)
                        new_shares = cash / transaction_price
                        
                        shares = new_shares
                        cash = 0.0
                        position_entry_price = transaction_price
                        position_entry_date = date
                        trailing_stop_price = None
                        position_type = 'long'
                        
                        if log_transactions:
                            transactions.append({
                                'Date': date,
                                'Action': 'BUY',
                                'Price': transaction_price,
                                'Shares': new_shares,
                                'PnL': 0.0,
                                'Return': 0.0,
                                'Portfolio_Value': shares * current_price
                            })
                        record_transaction('BUY', date)
            
            elif current_signal == 0.0 and shares > 0:  # Exit signal when in long position
                if should_allow_transaction('EXIT_LONG', date):
                    transaction_price = get_transaction_price(current_price, 'SELL', spread_pct)
                    pnl = (transaction_price - position_entry_price) * shares
                    pnl_pct = (transaction_price - position_entry_price) / position_entry_price * 100
                    
                    cash = shares * transaction_price
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'EXIT_LONG',
                            'Price': transaction_price,
                            'Shares': shares,
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash
                        })
                    record_transaction('EXIT_LONG', date)
                    
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                
            elif current_signal == 0.0 and shares < 0:  # Exit signal when in short position
                if should_allow_transaction('EXIT_SHORT', date):
                    transaction_price = get_transaction_price(current_price, 'COVER', spread_pct)
                    pnl = (position_entry_price - transaction_price) * abs(shares)
                    pnl_pct = (position_entry_price - transaction_price) / position_entry_price * 100
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'EXIT_SHORT',
                            'Price': transaction_price,
                            'Shares': abs(shares),
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash + pnl
                        })
                    record_transaction('EXIT_SHORT', date)
                    
                    # Update cash to reflect the PnL from the short position
                    cash = cash + pnl
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
        
        # Update portfolio tracking
        portfolio.loc[date, 'cash'] = float(cash)
        portfolio.loc[date, 'shares'] = float(shares)
        
        # Calculate total portfolio value
        if shares > 0:  # Long position
            portfolio.loc[date, 'total'] = float(cash + shares * current_price)
        elif shares < 0:  # Short position
            # For short positions: portfolio value = cash + unrealized P&L
            # Unrealized P&L = (entry_price - current_price) * number_of_shares
            if position_entry_price is not None:
                unrealized_pnl = (position_entry_price - current_price) * abs(shares)
                portfolio.loc[date, 'total'] = float(cash + unrealized_pnl)
            else:
                portfolio.loc[date, 'total'] = float(cash)
        else:  # No position
            portfolio.loc[date, 'total'] = float(cash)
    
    # Log transactions to file
    if log_transactions and transactions:
        with open('transactions.txt', 'w') as f:
            f.write("Date,Action,Price,Shares,PnL,Return%,Portfolio_Value\n")
            for t in transactions:
                f.write(f"{t['Date']:%Y-%m-%d %H:%M:%S},{t['Action']},{t['Price']:.2f},"
                       f"{t['Shares']:.6f},{t['PnL']:.2f},{t['Return']:.2f},{t['Portfolio_Value']:.2f}\n")
    
    return portfolio, transactions
