"""
Azure Function - Fear & Greed Signal Generator
Triggered by timer schedule: Pre-market (8AM ET) and Post-market (5PM ET)
"""

import logging
import azure.functions as func
from combined_signal_generator import CombinedSignalGenerator


def main(mytimer: func.TimerRequest) -> None:
    """
    Azure Function entry point

    Runs on schedule:
    - Pre-market: 8:00 AM ET (1:00 PM UTC)
    - Post-market: 5:00 PM ET (10:00 PM UTC)
    """
    logging.info('Fear & Greed Signal Generator starting...')

    if mytimer.past_due:
        logging.info('The timer is past due!')

    try:
        generator = CombinedSignalGenerator()
        results = generator.run()

        logging.info(f'Successfully generated signals for {len(results["stocks"])} stocks and {len(results["crypto"])} crypto')

    except Exception as e:
        logging.error(f'Error generating signals: {str(e)}')
        raise

    logging.info('Fear & Greed Signal Generator completed!')
