# Custom Range Plotting Guide

## Overview
The backtesting system now supports flexible custom range plotting, allowing you to zoom into specific periods of your data for detailed analysis.

## Available Range Types

### 1. Custom Day Ranges
Plot specific day ranges from your dataset (e.g., day 21 to day 34).

**Configuration in main.py:**
```python
GENERATE_CUSTOM_RANGE = True    # Enable custom day range plots
CUSTOM_RANGES = [
    (21, 34),   # Day 21 to Day 34 - your requested range
    (10, 25),   # Day 10 to Day 25 - early period focus
    (40, 55),   # Day 40 to Day 55 - later period analysis
    (5, 15),    # Day 5 to Day 15 - very early period
]
```

### 2. Hour-Based Ranges (for High-Frequency Data)
Plot specific hour ranges for 1m, 2m, or 5m interval data.

**Configuration in main.py:**
```python
GENERATE_HOUR_RANGES = True     # Enable hour-based custom ranges
CUSTOM_HOUR_RANGES = [
    (2, 4),    # First 2 hours of trading
    (8, 12),   # Mid-day trading (4 hours)
    (20, 24),  # End-of-day trading
]
```

### 3. Auto-Suggested Ranges
Let the system automatically suggest optimal ranges based on your data length.

**Configuration in main.py:**
```python
AUTO_SUGGEST_RANGES = True      # Auto-suggest optimal ranges
CUSTOM_RANGES = []              # Leave empty to use auto-suggestions
```

### 4. Regular Zoom Plots
Standard zoom functionality for last N days.

**Configuration in main.py:**
```python
GENERATE_ZOOM_PLOTS = True      # Enable 7d and 14d zoom plots
```

## Usage Examples

### Example 1: Focus on Day 21-34 (Your Request)
```python
CUSTOM_RANGES = [(21, 34)]
```
This creates a plot showing only days 21 through 34 of your dataset.

### Example 2: Multiple Custom Ranges
```python
CUSTOM_RANGES = [
    (21, 34),   # Mid-period analysis
    (50, 65),   # Later period analysis
    (5, 20),    # Early period analysis
]
```

### Example 3: High-Frequency Hour Analysis
```python
PERIOD = "7d"
INTERVAL = "1m"
GENERATE_HOUR_RANGES = True
CUSTOM_HOUR_RANGES = [(2, 6), (10, 14), (20, 24)]
```

## Data Limitations
- **1m, 2m data**: Limited to last 7 days
- **5m-90m data**: Limited to last 60 days
- **1h+ data**: Available for longer periods

## Generated Files
The system generates PNG files with descriptive names:
- `portfolio_vs_spy.png` - Full period
- `portfolio_vs_spy_zoom_7d.png` - Last 7 days
- `portfolio_vs_spy_custom_21_to_34.png` - Day 21 to 34
- `portfolio_vs_spy_custom_h2_to_h4.png` - Hour 2 to 4

## Features
- **Buy/Sell Markers**: Visible only on the orange benchmark line
- **Performance Metrics**: CAGR, Sharpe Ratio, Max Drawdown for each plot
- **Transaction Logging**: All trades logged to `transactions.txt`
- **Validation**: Automatic range validation and adjustment
- **Multiple Strategies**: Works with both mean reversion and moving average

## Tips
1. Start with auto-suggested ranges to understand your data structure
2. Use day ranges for longer-term analysis (5m+ intervals)
3. Use hour ranges for intraday analysis (1m, 2m intervals)
4. Combine multiple ranges to capture different market conditions
5. Check the console output for actual date/time ranges of your custom plots
