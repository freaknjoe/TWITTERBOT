import os
import random
import time
import logging
import requests
import json
from flask import Flask
import threading
from openai import OpenAI
import tweepy

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

        # Allow the text to be slightly longer before truncating
        max_length = 270  # This allows room for an ellipsis or other additions
        
        if len(text) > max_length:
            logger.warning("Text exceeded 270 characters. Trimming gracefully.")
            
            # Find the last sentence or a natural breaking point
            last_period = text.rfind('.', 0, max_length)
            last_exclamation = text.rfind('!', 0, max_length)
            last_question = text.rfind('?', 0, max_length)
            
            # Find the last of any sentence-ending punctuation
            last_punctuation = max(last_period, last_exclamation, last_question)
            
            if last_punctuation != -1:
                # Use the furthest punctuation mark
                end = max(last_period, last_exclamation, last_question) + 1
                text = text[:end] + "..."
            else:
                # If no sentence-ending punctuation is found, find the last space
                last_space = text.rfind(' ', 0, max_length)
                if last_space != -1:
                    text = text[:last_space] + "..."
                else:
                    # If no spaces found, truncate at max_length
                    text = text[:max_length] + "..."
            
            logger.info(f"Final summarized text: {text}")
            logger.info(f"Length of summarized text: {len(text)}")
            
        logger.info(f"Length of original text: {len(text)}")
        return text

    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        return None

def select_random_image(image_folder):
    """Select a random image from the specified image folder."""
    try:
        if not image_folder:
            logger.warning("No image folder specified.")
            return None

        images = [os.path.join(image_folder, img) for img in os.listdir(image_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if not images:
            logger.warning("No images found in the folder.")
            return None
        return random.choice(images)
    except Exception as e:
        logger.error(f"Error selecting random image: {e}")
        return None

def load_fallback_prompts(file_path):
    """Load fallback prompts from a specified file."""
    try:
        with open(file_path, 'r') as file:
            prompts = [line.strip() for line in file if line.strip()]
        return prompts
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return []

def get_fallback_prompt(topic):
    """Get a random fallback prompt from the specified topic."""
    fallback_file = topic.get("fallback_file", "")
    if fallback_file:
        fallback_prompts = load_fallback_prompts(fallback_file)
        if fallback_prompts:
            return random.choice(fallback_prompts)
    return "Default fallback prompt."

def simulate_post_tweet(text, image_path=None):
    """Simulate posting a tweet."""
    try:
        logger.info(f"Simulating tweet post: {text}")
        if image_path:
            logger.info(f"Selected image: {image_path}")
        logger.info("Tweet simulation successful.")
    except Exception as e:
        logger.error(f"Error simulating tweet post: {e}")

def post_tweet(text, image_path=None, max_retries=5, initial_delay=300, simulate_posting=False):
    """Post a tweet using Twitter API v2 with rate limiting and error handling."""
    if simulate_posting:
        simulate_post_tweet(text, image_path)
        return True

    retry_count = 0
    base_delay = initial_delay  # Initial delay in seconds (5 minutes)

    while retry_count < max_retries:
        try:
            logger.info(f"Posting tweet: {text}")

            if image_path:
                # Upload media using Twitter API v1.1
                media = api_v1.media_upload(filename=image_path)
                response = client_v2.create_tweet(text=text, media_ids=[media.media_id_string])
            else:
                # Post text-only tweet using Twitter API v2
                response = client_v2.create_tweet(text=text)

            # Log the full response for debugging
            logger.debug(f"Twitter API Response: {response}")

            if response and 'data' in response and 'id' in response['data']:
                tweet_id = response['data']['id']
                logger.info(f"Tweet posted successfully! Tweet ID: {tweet_id}")
                return tweet_id
            else:
                logger.error("Failed to get Tweet ID from Twitter API response.")
                logger.error(f"Response data: {response.get('data', {})}")
                logger.error(f"Response errors: {response.get('errors', [])}")
                retry_count += 1

        except tweepy.TweepyException as e:
            logger.error(f"Error posting tweet: {e}")
            retry_count += 1

            # Check if error is due to rate limits
            if "429" in str(e) or "Too Many Requests" in str(e):
                logger.warning("Rate limit exceeded. Waiting longer before retrying.")
                # Calculate exponential backoff with jitter
                delay = base_delay * (2 ** retry_count)
                jitter = random.uniform(0, delay)
                total_delay = delay + jitter
                logger.info(f"Waiting {total_delay:.2f} seconds before retry {retry_count + 1}/{max_retries}")
                time.sleep(total_delay)
            elif "403" in str(e) and "content" in str(e).lower():
                logger.error("Tweet failed due to content policy violation. Will not retry.")
                return None
            else:
                # For other errors, use a shorter delay
                delay = 60  # 1 minute
                jitter = random.uniform(0, delay)
                total_delay = delay + jitter
                logger.info(f"Waiting {total_delay:.2f} seconds before retry {retry_count + 1}/{max_retries}")
                time.sleep(total_delay)

            # Break the loop if max retries are reached
            if retry_count >= max_retries:
                logger.error(f"Max retries ({max_retries}) reached. Giving up.")
                return None

    # If we've exhausted all retries, return None
    logger.error(f"Failed to post tweet after {max_retries} retries.")
    return None

def generate_and_post_tweet(topic, simulate_posting=False):
    """Generate a detailed text, summarize it to 280 characters or less, and post as a tweet."""
    try:
        prompt_template = topic.get("prompt_template", "")
        image_folder = topic.get("image_folder", None)

        if topic["name"] == "general_crypto":
            topics = fetch_cryptopanic_topics()
            if not topics:
                logger.warning("No trending topics found. Using fallback.")
                topics = ["The crypto market is full of surprises! 🚀"]
            selected_topic = random.choice(topics)
            prompt = prompt_template.replace("{TRENDING_TOPIC}", selected_topic)
            logger.info(f"Selected topic for tweet: {selected_topic}")
        else:
            prompt = prompt_template

        response_text = call_openai(prompt)

        if not response_text:
            logger.warning("OpenAI response failed. Using fallback.")
            response_text = get_fallback_prompt(topic)

        summarized_text = summarize_text(response_text)

        if not summarized_text:
            logger.warning("Summarization failed. Using fallback.")
            summarized_text = get_fallback_prompt(topic)

        image_path = select_random_image(image_folder)

        # Append reference if applicable
        reference = topic.get("reference", None)
        if reference:
            reference_type = random.choice(["contract", "twitter"])
            reference_text = reference.get(reference_type, "")
            if len(summarized_text) + len(reference_text) <= 280:
                summarized_text += reference_text
                logger.info(f"Updated tweet with reference: {summarized_text}")
            else:
                max_length = 280 - len(reference_text)
                summarized_text = summarized_text[:max_length] + reference_text
                logger.info(f"Adjusted tweet to include reference: {summarized_text}")

        post_tweet(summarized_text, image_path, simulate_posting=simulate_posting)

    except Exception as e:
        logger.error(f"Error in generate_and_post_tweet: {e}")

def run_bot():
    """Main bot loop."""
    logger.info("Starting the bot (Live Twitter posting enabled).")

    # Load configuration
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    topics = config.get("topics", [])
    simulate_posting = config.get("simulate_posting", False)

    while True:
        # Randomly select a topic based on probabilities
        selected_topic = random.choices([topic for topic in topics], weights=[topic["probability"] for topic in topics])[0]
        logger.info(f"Selected topic: {selected_topic['name']}")

        generate_and_post_tweet(selected_topic, simulate_posting=simulate_posting)

        # Sleep for the specified interval
        time.sleep(1800)  # 30 min interval for live posting

if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    run_bot()