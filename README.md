# Telegram MCQ Quiz Bot

A fully functional Telegram MCQ Quiz Bot built with Python, aiogram 3, and MongoDB.

## Features
- Create unlimited quizzes using native Telegram Quiz Polls.
- Multiplayer quiz mode.
- Auto-pause if no responses.
- Leaderboards and PDF result exports.
- A built-in web app for creation instructions.

## Prerequisites
- Python 3.12+
- MongoDB instance running

## Setup Instructions

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory based on `.env.example`:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   MONGODB_URI=mongodb://localhost:27017
   DB_NAME=quiz_bot_db
   WEB_HOST=0.0.0.0
   WEB_PORT=8080
   BASE_URL=http://your_domain_or_ip:8080
   ```
4. Run the bot:
   ```bash
   python quiz_bot/main.py
   ```
