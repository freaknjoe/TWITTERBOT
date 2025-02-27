import os
import random
import time
import logging
import requests
import json
from flask import Flask, jsonify
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

@app.route('/run-bot', methods=['GET'])
def run_bot_endpoint():
    try:
        bot.run_bot_once()
        return "Bot executed successfully.", 200
    except Exception as e:
        logger.error(f"Error executing bot via endpoint: {e}")
        return "Failed to execute bot.", 500

@app.route('/health')
def health_check():
    return jsonify(status="OK"), 200

def start_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

# Fetch credentials from environment variables
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('ACCESS_TOKEN_SECRET')
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
    """Select a random image from the specified image folder or subfolder."""
    try:
        if not image_folder:
            logger.warning("No image folder specified.")
            return None

        # Check if image_folder is a subfolder within the 'images' directory
        base_images_dir = 'images'
        full_image_folder = os.path.join(base_images_dir, image_folder)

        if not os.path.isdir(full_image_folder):
            logger.warning(f"Image folder {full_image_folder} does not exist.")
            return None

        images = [os.path.join(full_image_folder, img) for img in os.listdir(full_image_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if not images:
            logger.warning(f"No images found in the folder: {full_image_folder}.")
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
            logger.info(f"Full Twitter API Response: {response}")

            if response and hasattr(response, "data") and "id" in response.data:
                tweet_id = response.data["id"]
                logger.info(f"Tweet posted successfully! Tweet ID: {tweet_id}")
                return tweet_id
            else:
                logger.error("Failed to get Tweet ID from Twitter API response.")
                logger.error(f"Response data: {getattr(response, 'data', 'No response')}")
                logger.error(f"Response errors: {getattr(response, 'errors', 'No errors')}")
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

class CryptoBot:
    def __init__(self, config, twitter_api_v1, twitter_api_v2, openai_client):
        self.config = config
        self.twitter_api_v1 = twitter_api_v1
        self.twitter_api_v2 = twitter_api_v2
        self.openai_client = openai_client
        self.topics = config.get("topics", [])
        self.simulate_posting = config.get("simulate_posting", False)

    def generate_and_post_tweet(self, topic):
        """Generate a detailed text, summarize it to 280 characters or less, and post as a tweet."""
        try:
            prompt_template = topic.get("prompt_template", "")
            image_folder = topic.get("image_folder", None)

            if topic["name"] == "general_crypto":
                topics = fetch_cryptopanic_topics()
                if not topics:
                    logger.warning("No trending topics found. Using fallback.")
                    topics = ["Crypto is buzzing! Stay tuned for the latest updates. 🚀"]
                selected_topic = random.choice(topics)
                prompt = prompt_template.replace("{TRENDING_TOPIC}", selected_topic)
                logger.info(f"Selected topic for tweet: {selected_topic}")
                # Do NOT include images for general crypto tweets
                image_path = None
            else:
                prompt = prompt_template
                # Only include images for Fedja tweets
                if topic["name"] == "fedja_tweet":
                    image_path = select_random_image(image_folder)
                    if not image_path:
                        logger.warning("No images found for Fedja tweet.")
                        image_path = None
                else:
                    image_path = None

            response_text = call_openai(prompt)

            if not response_text:
                logger.warning("OpenAI response failed. Using fallback.")
                response_text = get_fallback_prompt(topic)

            summarized_text = summarize_text(response_text)

            if not summarized_text:
                logger.warning("Summarization failed. Using fallback.")
                summarized_text = get_fallback_prompt(topic)

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

            post_tweet(summarized_text, image_path, simulate_posting=self.simulate_posting)

        except Exception as e:
            logger.error(f"Error in generate_and_post_tweet: {e}")

    def run_bot_once(self):
        """Execute one iteration of the bot's tasks."""
        try:
            logger.info("Starting the bot for one iteration.")
            # Randomly select a topic based on probabilities
            selected_topic = random.choices(
                [topic for topic in self.topics],
                weights=[topic["probability"] for topic in self.topics]
            )[0]
            logger.info(f"Selected topic: {selected_topic['name']}")

            self.generate_and_post_tweet(selected_topic)
            logger.info("Bot iteration completed successfully.")
        except Exception as e:
            logger.error(f"Error in run_bot_once: {e}")

    def run_bot_periodically(self):
        """Run the bot periodically."""
        while True:
            try:
                self.run_bot_once()
                sleep_interval = random.randint(10800, 14400)
                logger.info(f"Sleeping for {sleep_interval} seconds ({sleep_interval / 3600:.2f} hours)")
                time.sleep(sleep_interval)
            except Exception as e:
                logger.error(f"Error in run_bot_periodically: {e}")

def main():
    try:
        # Load configuration
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)
        
        # Initialize bot
        global bot
        bot = CryptoBot(config, api_v1, client_v2, client)
        
        # Check if running in Cloud Run or Railway
        is_cloud = os.getenv('K_SERVICE') or os.getenv('RAILWAY_SERVICE_NAME')
        
        if is_cloud:
            # For Cloud Run/Railway, run the Flask server as the main process
            port = int(os.getenv("PORT", 8080))
            app.run(host='0.0.0.0', port=port, debug=False)
        else:
            # For local development, start Flask server and bot threads
            flask_thread = threading.Thread(target=start_flask, daemon=True)
            flask_thread.start()
            
            bot_thread = threading.Thread(target=bot.run_bot_periodically, daemon=True)
            bot_thread.start()
            
            logger.info("Running locally. Waiting for HTTP requests or background execution...")
            while True:
                time.sleep(60)  # Keep the main thread alive locally

    except Exception as e:
        logger.critical(f"Fatal error in main: {e}")
        raise

if __name__ == "__main__":
    main()