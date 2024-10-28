from datetime import datetime
import tweepy
from config import X_CREDENTIALS


def setup_x_clients():
    """Initialize and return both v2 and v1.1 Twitter API clients"""
    try:
        # Initialize v2 client
        v2_client = tweepy.Client(
            bearer_token=X_CREDENTIALS["BEARER_TOKEN"],
            consumer_key=X_CREDENTIALS["API_KEY"],
            consumer_secret=X_CREDENTIALS["API_SECRET"],
            access_token=X_CREDENTIALS["ACCESS_TOKEN"],
            access_token_secret=X_CREDENTIALS["ACCESS_TOKEN_SECRET"]
        )

        # Initialize v1.1 client for trends
        auth = tweepy.OAuth1UserHandler(
            consumer_key=X_CREDENTIALS["API_KEY"],
            consumer_secret=X_CREDENTIALS["API_SECRET"],
            access_token=X_CREDENTIALS["ACCESS_TOKEN"],
            access_token_secret=X_CREDENTIALS["ACCESS_TOKEN_SECRET"]
        )
        v1_api = tweepy.API(auth)

        return v2_client, v1_api
    except Exception as e:
        print(f"Error setting up clients: {e}")
        return None, None


def get_controversial_trending_topics(v1_api, top_n=5):
    """Get and score trending topics based on controversy and relevance"""
    try:
        trends = v1_api.get_place_trends(1)  # Worldwide trends

        scored_trends = []
        for trend in trends[0]['trends']:
            score = 0
            volume = trend['tweet_volume'] or 0

            # Volume score (0-50 points)
            score += min(50, (volume / 10000)) if volume else 0

            # Keyword scoring (0-50 points)
            controversial_keywords = ['controversy', 'breaking', 'conflict', 'debate',
                                      'protest', 'politics', 'dispute', 'scandal']
            keyword_score = sum(10 for keyword in controversial_keywords
                                if keyword.lower() in trend['name'].lower())
            score += min(50, keyword_score)

            scored_trends.append({
                'name': trend['name'],
                'query': trend['query'],
                'volume': volume,
                'score': score
            })

        return sorted(scored_trends, key=lambda x: x['score'], reverse=True)[:top_n]

    except Exception as e:
        print(f"Error getting trends: {e}")
        return []


def get_conversation_data(v2_client, trend, max_tweets=20):
    """Get relevant tweets and replies for a trend"""
    try:
        tweets = v2_client.search_recent_tweets(
            query=trend['query'],
            max_results=max_tweets,
            tweet_fields=['created_at', 'public_metrics', 'conversation_id'],
            sort_order='relevancy'
        )

        if not tweets.data:
            return None

        conversations = []
        for tweet in tweets.data:
            # Score tweet relevance/quality
            engagement_score = (
                tweet.public_metrics['like_count'] * 1 +
                tweet.public_metrics['retweet_count'] * 2 +
                tweet.public_metrics['reply_count'] * 1.5
            )

            if engagement_score > 100:  # Minimum engagement threshold
                conversations.append({
                    'text': tweet.text,
                    'created_at': tweet.created_at,
                    'engagement_score': engagement_score,
                    'metrics': tweet.public_metrics,
                    'conversation_id': tweet.conversation_id
                })

        return conversations

    except Exception as e:
        print(f"Error getting conversation: {e}")
        return None
