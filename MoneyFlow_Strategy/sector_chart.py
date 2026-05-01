"""
Sector Rankings Chart Visualization
Creates and updates a cumulative line chart showing sector performance over time
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path
import glob

from config import DAILY_REPORTS_DIR, CHART_ROLLING_DAYS


class SectorChartVisualizer:
    """Create and update sector ranking charts"""

    def __init__(self, chart_filename='sector_rankings_chart.png', days_to_show=None):
        self.chart_path = DAILY_REPORTS_DIR / chart_filename
        self.days_to_show = days_to_show or CHART_ROLLING_DAYS  # Use config default if not specified

    def load_all_sector_data(self):
        """
        Load all historical sector ranking CSV files and combine them

        Returns:
            pd.DataFrame: Combined data with Date, Ticker, Sector_Name, Sector_Score
        """
        # Find all sector ranking files
        pattern = str(DAILY_REPORTS_DIR / "sector_rankings_*.csv")
        files = glob.glob(pattern)

        if not files:
            print("[WARNING] No sector ranking files found")
            return None

        # Load and combine all files
        dfs = []
        for file in files:
            try:
                df = pd.read_csv(file)
                # Only keep necessary columns
                df = df[['Date', 'Ticker', 'Sector_Name', 'Sector_Score']]
                dfs.append(df)
            except Exception as e:
                print(f"[WARNING] Could not load {file}: {e}")

        if not dfs:
            return None

        # Combine all data
        combined_df = pd.concat(dfs, ignore_index=True)

        # Convert Date to datetime
        combined_df['Date'] = pd.to_datetime(combined_df['Date'])

        # Sort by date
        combined_df = combined_df.sort_values('Date')

        # Remove duplicates (in case same date appears multiple times)
        combined_df = combined_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')

        return combined_df

    def create_chart(self):
        """
        Create/update the sector rankings chart

        Returns:
            Path: Path to the saved chart, or None if failed
        """
        from datetime import datetime, timedelta

        # Load all data
        df = self.load_all_sector_data()

        if df is None or len(df) == 0:
            print("[ERROR] No data available to create chart")
            return None

        # Filter to show only last N days from today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = today - timedelta(days=self.days_to_show - 1)  # -1 to include today

        df = df[df['Date'] >= cutoff_date]

        if len(df) == 0:
            print(f"[WARNING] No data in the last {self.days_to_show} days")
            return None

        date_range = f"{df['Date'].min().strftime('%b %d')} - {df['Date'].max().strftime('%b %d, %Y')}"
        print(f"[INFO] Chart showing data from {date_range} ({len(df['Date'].unique())} days)")

        # Create figure
        plt.figure(figsize=(14, 8))

        # Get unique sectors and assign colors
        sectors = df['Sector_Name'].unique()
        colors = plt.cm.tab20(range(len(sectors)))
        color_map = dict(zip(sectors, colors))

        # Plot each sector
        for sector in sectors:
            sector_data = df[df['Sector_Name'] == sector].copy()
            sector_data = sector_data.sort_values('Date')

            plt.plot(
                sector_data['Date'],
                sector_data['Sector_Score'],
                marker='o',
                linewidth=2,
                markersize=4,
                label=sector,
                color=color_map[sector],
                alpha=0.8
            )

        # Formatting
        plt.title(f'Sector Rankings - Last {self.days_to_show} Days\nMoney Flow Strategy',
                  fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('Date', fontsize=12, fontweight='bold')
        plt.ylabel('Sector Score', fontsize=12, fontweight='bold')
        plt.grid(True, alpha=0.3, linestyle='--')

        # Legend
        plt.legend(
            loc='center left',
            bbox_to_anchor=(1, 0.5),
            fontsize=10,
            framealpha=0.9,
            title='Sectors',
            title_fontsize=11
        )

        # Format x-axis dates
        ax = plt.gca()
        num_days = len(df['Date'].unique())

        if num_days <= 7:
            # Show all dates if 7 days or less
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        elif num_days <= 14:
            # Show every other day for 8-14 days
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        else:
            # Show weekly intervals for more than 14 days
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))

        plt.xticks(rotation=45, ha='right')

        # Add horizontal line at 50 (neutral score)
        plt.axhline(y=50, color='gray', linestyle=':', alpha=0.5, linewidth=1.5, label='Neutral (50)')

        # Tight layout to prevent label cutoff
        plt.tight_layout()

        # Save chart
        try:
            plt.savefig(self.chart_path, dpi=150, bbox_inches='tight')
            print(f"[OK] Sector chart saved: {self.chart_path.name}")
            plt.close()
            return self.chart_path
        except Exception as e:
            print(f"[ERROR] Failed to save chart: {e}")
            plt.close()
            return None

    def get_chart_path(self):
        """Get the path to the chart file"""
        return self.chart_path if self.chart_path.exists() else None


def update_sector_chart():
    """
    Convenience function to update the sector chart

    Returns:
        Path: Path to updated chart, or None if failed
    """
    visualizer = SectorChartVisualizer()
    return visualizer.create_chart()


if __name__ == "__main__":
    # Test the chart creation
    print("Creating sector rankings chart...")
    chart_path = update_sector_chart()

    if chart_path:
        print(f"\n[OK] Chart created successfully: {chart_path}")
    else:
        print("\n[ERROR] Failed to create chart")
