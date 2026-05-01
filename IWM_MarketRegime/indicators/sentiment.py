#!/usr/bin/env python3
"""News sentiment module for IWM Market Regime."""

import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


def compute_sentiment_score(rss_feeds: List[str]) -> float:
    """Compute sentiment score (0-100) from RSS news headlines.

    Uses VADER sentiment analysis on headlines from configured RSS feeds.

    Args:
        rss_feeds: List of RSS feed URLs.

    Returns:
        Sentiment score between 0 and 100. Returns 50 if no news found.
    """
    try:
        import feedparser
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
    except ImportError as e:
        logger.error(f"Missing dependency: {e}. Install feedparser and nltk.")
        return 50.0

    # Ensure VADER lexicon is available
    try:
        import nltk
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        import nltk
        nltk.download("vader_lexicon", quiet=True)

    sia = SentimentIntensityAnalyzer()
    compound_scores: List[float] = []

    for feed_url in rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:  # Limit per feed
                title = entry.get("title", "")
                if not title:
                    continue
                sentiment = sia.polarity_scores(title)
                compound_scores.append(sentiment["compound"])
            logger.info(f"Parsed {len(feed.entries[:15])} entries from {feed_url}")
        except Exception as e:
            logger.warning(f"Failed to parse feed {feed_url}: {e}")

    if not compound_scores:
        logger.warning("No headlines found, returning neutral 50")
        return 50.0

    # VADER compound ranges from -1 to +1, normalize to 0-100
    avg_compound = float(np.mean(compound_scores))
    sentiment_score = (avg_compound + 1.0) / 2.0 * 100.0
    sentiment_score = float(np.clip(sentiment_score, 0, 100))

    logger.info(
        f"Sentiment: {len(compound_scores)} headlines, "
        f"avg compound={avg_compound:.3f}, score={sentiment_score:.1f}"
    )
    return sentiment_score
