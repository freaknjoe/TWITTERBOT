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

def load_prompts(file_path):
    """Load prompts from a specified file into a list."""
    try:
        with open(file_path, 'r') as file:
            prompts = [line.strip() for line in file if line.strip()]
        return prompts
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return []

# Load prompts from text files
FEDJA_PROMPTS = load_prompts('fedja_prompts.txt')
GENERAL_CRYPTO_PROMPTS = load_prompts('general_crypto_prompts.txt')

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
            return GENERAL_CRYPTO_PROMPTS if GENERAL_CRYPTO_PROMPTS else ["Crypto is buzzing! 🚀"]

        logger.info(f"Retrieved {len(relevant_topics)} topics from CryptoPanic.")
        return relevant_topics

    except Exception as e:
        logger.error(f"Error fetching topics from CryptoPanic: {e}")
        return GENERAL_CRYPTO_PROMPTS if GENERAL_CRYPTO_PROMPTS else ["Crypto is buzzing! 🚀"]

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
    if not text:
        return None

    if len(text) > 280:
        text = text[:277] + "..."

    return text

def select_random_image():
    """Select a random image from the images folder."""
    try:
        images = [os.path.join(IMAGES_FOLDER, img) for img in os.listdir(IMAGES_FOLDER) if img.endswith(('.png', '.jpg', '.jpeg'))]
        return random.choice(images) if images else None
    except Exception as e:
        logger.error(f"Error selecting random image: {e}")
        return None

def post_tweet(text, image_path=None):
    """Post a tweet with optional media (image)."""
    try:
        logger.info(f"Posting tweet: {text}")

        if image_path:
            media = api_v1.media_upload(filename=image_path)
            response = client_v2.create_tweet(text=text, media_ids=[media.media_id_string])
        else:
            response = client_v2.create_tweet(text=text)

        if response and 'data' in response and 'id' in response['data']:
            logger.info(f"Tweet posted successfully! Tweet ID: {response['data']['id']}")
    except tweepy.TweepyException as e:
        logger.error(f"Error posting tweet: {e}")

def post_fedja_tweet():
    """Post a $FEDJA tweet with an image if available."""
    prompt = f"Write a fun, engaging $FEDJA tweet under 250 characters. #FedjaMoon"
    text = summarize_text(call_openai(prompt))

    if not text:
        text = random.choice(FEDJA_PROMPTS) if FEDJA_PROMPTS else "FEDJA is mooning! 🚀🐕 #FedjaFren"

    fedja_reference = f"\n\n$FEDJA | {FEDJA_CONTRACT_ADDRESS} 🐕 #FedjaMoon"
    text = text[:280 - len(fedja_reference)] + fedja_reference if len(text) + len(fedja_reference) > 280 else text + fedja_reference

    post_tweet(text, image_path=select_random_image())

def post_regular_tweet():
    """Post a general crypto tweet from CryptoPanic or fallback prompts."""
    topics = fetch_cryptopanic_topics()
    selected_topic = random.choice(topics)

    prompt = f"Write a short, engaging tweet under 250 characters about:\n\n{selected_topic}"
    text = summarize_text(call_openai(prompt))

    if not text:
        text = random.choice(GENERAL_CRYPTO_PROMPTS) if GENERAL_CRYPTO_PROMPTS else "Crypto is wild today! 🚀 #CryptoChat"

    post_tweet(text)

def run_bot():
    """Main bot loop."""
    while True:
        action = "fedja_tweet" if random.random() < 0.2 else "regular_tweet"
        post_fedja_tweet() if action == "fedja_tweet" else post_regular_tweet()
        time.sleep(10800)  # 3 hours interval

if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    run_bot()
