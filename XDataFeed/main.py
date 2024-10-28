import tweepy
import time

# Update with your tokens after server.py and ngrok are running
ACCESS_TOKEN = None  # We'll get this from the OAuth process


def setup_client(access_token):
    return tweepy.Client(bearer_token=access_token)


def get_trending_conversations(client, max_results=10):
    """Get trending conversations and their engagement"""
    try:
        # Search for engaging content
        tweets = client.search_recent_tweets(
            query="trending -is:retweet",
            max_results=max_results,
            tweet_fields=['public_metrics', 'conversation_id', 'created_at']
        )

        conversations = []
        for tweet in tweets.data:
            engagement = tweet.public_metrics
            conversations.append({
                'text': tweet.text,
                'created_at': tweet.created_at,
                'engagement': engagement,
                'conversation_id': tweet.conversation_id
            })

        return conversations
    except Exception as e:
        print(f"Error fetching conversations: {e}")
        return []


def poll_trending_content(client, interval_seconds=180):
    """Poll for new trending content every interval"""
    while True:
        print("\nFetching new trending content...")
        start_time = time.time()

        conversations = get_trending_conversations(client)

        if conversations:
            print(f"\nFound {len(conversations)} trending conversations:")
            for conv in conversations:
                print(f"\nTweet: {conv['text'][:100]}...")
                print(f"Engagement: {conv['engagement']}")
                print(f"Created at: {conv['created_at']}")

        # Calculate sleep time to maintain interval
        elapsed = time.time() - start_time
        sleep_time = max(0, interval_seconds - elapsed)
        if sleep_time > 0:
            print(f"\nWaiting {sleep_time:.2f} seconds until next update...")
            time.sleep(sleep_time)


if __name__ == "__main__":
    if not ACCESS_TOKEN:
        print("Please update ACCESS_TOKEN with the token received from OAuth process")
        exit(1)

    client = setup_client(ACCESS_TOKEN)
    poll_trending_content(client)
