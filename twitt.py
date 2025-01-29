import os
import random
import time
import logging
import requests
from flask import Flask
import tweepy
import threading
from openai import OpenAI

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CryptoSocialBot")

# Flask setup
app = Flask(__name__)

@app.route('/')
def home():
    return "CryptoSocialBot is running!"

def start_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Fetch credentials from environment variables
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY')

# Constants for $FEDJA
FEDJA_CONTRACT_ADDRESS = "9oDw3Q36a8mVHfPCSmxYBXE9iLeJjsCYu97JGpPwDvVZ"
FEDJA_TWITTER_TAG = "@Fedja_SOL"
IMAGES_FOLDER = "images"  # Folder containing images for $FEDJA tweets

# Validate API credentials
if not all([API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, OPENAI_API_KEY, CRYPTOPANIC_API_KEY]):
    logger.critical("API credentials are not properly set as environment variables.")
    raise ValueError("API credentials are missing.")

# Authenticate with Twitter API v1.1 (for media upload)
auth_v1 = tweepy.OAuth1UserHandler(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET_KEY,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)
api_v1 = tweepy.API(auth_v1)

# Authenticate with Twitter API v2 (for posting tweets)
client_v2 = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET_KEY,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_cryptopanic_topics():
    """Fetch trending topics from CryptoPanic, limited to 5 posts for efficiency."""
    try:
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&kind=news&filter=rising&limit=5"
        response = requests.get(url)
        response.raise_for_status()

        results = response.json().get("results", [])
        relevant_topics = [item["title"] for item in results][:5]  # Limit to 5 topics

        if not relevant_topics:
            logger.warning("No relevant trending topics found. Using fallback.")
            return ["Crypto is buzzing! Stay tuned for the latest updates. 🚀"]

        logger.info(f"Retrieved {len(relevant_topics)} topics from CryptoPanic.")
        return relevant_topics

    except Exception as e:
        logger.error(f"Error fetching topics from CryptoPanic: {e}")
        return ["Error fetching crypto news. Markets are wild! 🚀"]

def call_openai(prompt, model="gpt-3.5-turbo"):
    """Fetch a response from OpenAI API."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.7,
            top_p=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return None

def summarize_text(text):
    """Ensure the text remains under 280 characters and is suitable for Twitter."""
    try:
        if not text:
            logger.warning("Empty text provided for summarization.")
            return None

        if len(text) > 280:
            logger.warning("Text exceeded 280 characters. Trimming gracefully.")
            text = text[:277] + "..."

        logger.info(f"Final summarized text: {text}")
        return text

    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        return None

def select_random_image():
    """Select a random image from the images folder."""
    try:
        images = [os.path.join(IMAGES_FOLDER, img) for img in os.listdir(IMAGES_FOLDER) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if not images:
            logger.warning("No images found in the images folder.")
            return None
        return random.choice(images)
    except Exception as e:
        logger.error(f"Error selecting random image: {e}")
        return None

def post_tweet(text, image_path=None):
    """Post a tweet with optional media (image)."""
    try:
        logger.info(f"Posting tweet: {text}")

        if image_path:
            logger.info(f"Uploading image: {image_path}")
            media = api_v1.media_upload(filename=image_path)
            media_id = media.media_id_string

            response = client_v2.create_tweet(text=text, media_ids=[media_id])
        else:
            response = client_v2.create_tweet(text=text)

        logger.debug(f"Twitter API Response: {response}")

        if response and 'data' in response and 'id' in response['data']:
            tweet_id = response['data']['id']
            logger.info(f"Tweet posted successfully! Tweet ID: {tweet_id}")
            return tweet_id
        else:
            logger.error("Failed to get Tweet ID from Twitter API response.")
            return None

    except tweepy.TweepyException as e:
        logger.error(f"Error posting tweet: {e}")
        return None

def post_fedja_tweet():
    """Post a witty tweet about $FEDJA with a random image if available."""
    prompt = f"Create a short, engaging, and witty tweet about $FEDJA, a memecoin on Solana. Keep it under 250 characters. #FedjaMoon"
    text = summarize_text(call_openai(prompt))

    if not text:
        text = "FEDJA is mooning! 🚀🐕 #FedjaFren"

    fedja_reference = f"\n\n$FEDJA | {FEDJA_CONTRACT_ADDRESS} 🐕 #FedjaMoon"

    if len(text) + len(fedja_reference) <= 280:
        text += fedja_reference
    else:
        text = text[:280 - len(fedja_reference)] + fedja_reference

    # Select a random image for $FEDJA tweets
    image_path = select_random_image()
    
    post_tweet(text, image_path=image_path)

def run_bot():
    """Main bot loop."""
    logger.info("Starting the bot (Live Twitter posting enabled).")
    while True:
        action = "fedja_tweet" if random.random() < 0.2 else "regular_tweet"
        logger.info(f"Selected action: {action}")

        if action == "fedja_tweet":
            post_fedja_tweet()
        elif action == "regular_tweet":
            post_regular_tweet()

        time.sleep(1800)  # 30 min interval for live posting

if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    run_bot()
