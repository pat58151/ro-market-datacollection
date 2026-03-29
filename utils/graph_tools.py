import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import defaultdict
from .data_tools import normalize_item_name

def create_line_graph(item_data, item_name, server_name, days=90, ma_window=7, ma_type='EMA'):
    """Create a line chart from the item's price history with daily averages and trend analysis."""
    chart_filename = f'chart_{normalize_item_name(item_name, server_name)}.png'

    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        # Filter recent data
        recent_data = [
            entry for entry in item_data
            if 'timestamp' in entry and 'average' in entry
            and datetime.fromisoformat(entry['timestamp']).replace(tzinfo=None) >= cutoff_date
        ]

        if not recent_data:
            print("No recent data found.")
            return None

        # Organize data by day
        daily_data = defaultdict(list)
        for entry in recent_data:
            try:
                dt = datetime.fromisoformat(entry['timestamp']).replace(tzinfo=None)
                daily_data[dt.date()].append(entry['average'])
            except Exception:
                continue

        if not daily_data:
            print("No daily data to plot.")
            return None

        # Calculate daily averages
        daily_averages = []
        for date in sorted(daily_data.keys()):
            avg_price = sum(daily_data[date]) / len(daily_data[date])
            daily_averages.append({'date': date, 'price': avg_price})

        if not daily_averages:
            print("No daily averages available.")
            return None

        dates = [entry['date'] for entry in daily_averages]
        prices = [entry['price'] for entry in daily_averages]

        if not prices:
            print("Price list is empty.")
            return None

        # Plot setup
        fig, ax = plt.subplots(figsize=(14, 8))
        ax.plot(dates, prices, color='#2E86AB', linewidth=2.5, marker='o',
                markersize=5, markerfacecolor='#A23B72', markeredgecolor='white',
                markeredgewidth=1.5, label='Daily Average', zorder=3)
        ax.fill_between(dates, prices, alpha=0.2, color='#2E86AB')

        # Moving average
        if len(prices) >= ma_window:
            moving_avg = []
            if ma_type.upper() == 'EMA':
                multiplier = 2 / (ma_window + 1)
                sma = sum(prices[:ma_window]) / ma_window
                moving_avg.append(sma)
                for i in range(ma_window, len(prices)):
                    ema = (prices[i] * multiplier) + (moving_avg[-1] * (1 - multiplier))
                    moving_avg.append(ema)
                moving_avg = [None] * (ma_window - 1) + moving_avg
            else:  # SMA
                for i in range(len(prices)):
                    start_idx = max(0, i - ma_window + 1)
                    window_prices = prices[start_idx:i + 1]
                    moving_avg.append(sum(window_prices) / len(window_prices))

            valid_dates = [d for d, v in zip(dates, moving_avg) if v is not None]
            valid_ma = [v for v in moving_avg if v is not None]
            ax.plot(valid_dates, valid_ma, color='#F18F01', linewidth=2,
                    linestyle='--', label=f'{ma_window}-Day {ma_type.upper()}', alpha=0.8, zorder=2)

        # Overall average
        overall_avg = sum(prices) / len(prices)
        ax.axhline(y=overall_avg, color='gray', linestyle=':', linewidth=1.5,
                   label=f'Average: {int(overall_avg):,}', alpha=0.7)

        # Recent change
        if len(prices) > 1:
            price_change = prices[-1] - prices[-2]
            pct_change = (price_change / prices[-2]) * 100
            change_text = f"Recent Change: {price_change:+,.0f} ({pct_change:+.1f}%)"
            color = 'green' if price_change >= 0 else 'red'
            ax.text(0.98, 0.98, change_text, transform=ax.transAxes,
                    fontsize=11, fontweight='bold', color=color,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=color))

        # Axes settings
        price_range = max(prices) - min(prices)
        padding = price_range * 0.1 if price_range > 0 else max(prices) * 0.1
        ax.set_ylim(min(prices) - padding, max(prices) + padding)
        ax.set_xlabel('Date', fontsize=12, fontweight='bold')
        ax.set_ylabel('Average Price', fontsize=12, fontweight='bold')
        ax.set_title(f'{item_name.title()} - Price Trend (Last {days} Days)',
                     fontsize=14, fontweight='bold')
        ax.grid(axis='both', alpha=0.3, linestyle='--', zorder=1)

        if len(dates) == 1:
            single_date = dates[0]
            ax.set_xlim(single_date - timedelta(days=1), single_date + timedelta(days=1))
            ax.set_xticks([single_date])
        elif len(dates) == 2:
            ax.set_xlim(min(dates), max(dates))
            ax.set_xticks(dates)
        else:
            ax.set_xlim(min(dates), max(dates))
            interval = max(1, len(daily_averages) // 10)
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.xticks(rotation=45, ha='right')
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
        ax.legend(loc='upper left', framealpha=0.9, fontsize=10)
        plt.tight_layout()
        plt.savefig(chart_filename, dpi=150, bbox_inches='tight')
        plt.close(fig)

        return chart_filename

    except Exception as e:
        print(f"Error in create_line_graph: {e}")
        import traceback
        traceback.print_exc()
        return None
