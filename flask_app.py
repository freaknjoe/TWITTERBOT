from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "CryptoSocialBot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)
