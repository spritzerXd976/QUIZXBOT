# 🤖 Telegram MCQ Quiz Bot

A fully-featured Telegram quiz bot using **native Telegram Quiz Polls**, built with **aiogram 3**, **MongoDB (Motor async)**, and **Python**.

---

## ✨ Features

### Quiz Creation
- Create quizzes with unlimited MCQ questions
- **Native Telegram Quiz Polls** for question creation (correct answer selected inside Telegram)
- 4 options per question
- Per-question timer (5–300s)
- Question explanations
- Shuffle questions & options

### Quiz Settings
- ✅ Correct answer score (configurable)
- ❌ Negative marking / penalty (configurable)
- 🔒 Exam mode (hide results until end)
- 🔀 Shuffle questions & options
- ⏱ Default timer per question

### Quiz Play
- Start via share link: `t.me/YourBot?start=quiz_QUIZ_ID`
- Works in **private chat** and **Telegram groups**
- Multiplayer in groups — everyone answers the same poll
- Real-time answer tracking
- Auto-advance after timer
- Live leaderboard after each question (non-exam mode)
- Final result summary with rankings

### Auto-Pause
- If nobody answers within the timer, quiz pauses automatically
- Sends: *"⏸ Quiz paused due to no responses."*
- Buttons: **Resume Quiz** | **End Quiz**
- Any group member can resume; only admins/creator can end

### Results & Export
- Correct / Wrong / Missed tracking per user
- Score, percentage, time taken
- Live leaderboard during quiz
- Final ranking after quiz ends
- **PDF result export** (individual report with question-wise analysis)

### Admin / Permission Controls
- **Private chat**: Quiz creator controls everything
- **Groups**: Any member can participate; only admins/owner can End/Stop quiz; anyone can Resume paused quiz
- `/stopquiz` — stop running quiz (admins only in groups)

### Creator Controls
- Create, Edit, Delete, Duplicate, Preview quizzes
- Add/remove questions
- Configure all settings
- Share deep link

---

## 🛠 Tech Stack

| Component | Library |
|-----------|---------|
| Bot Framework | `aiogram 3.7` |
| Database | `MongoDB` via `motor` (async) |
| PDF Export | `reportlab` |
| Env Config | `python-dotenv` |
| Async Runtime | Python `asyncio` |

---

## 📁 Project Structure

```
telegram_quiz_bot/
├── main.py                     # Entry point
├── config.py                   # Config & constants
├── database.py                 # MongoDB connection
├── requirements.txt
├── .env.example
│
├── models/
│   ├── quiz.py                 # Quiz, Question, Option models
│   ├── session.py              # Session, Participant models
│   └── user.py                 # User model
│
├── services/
│   ├── user_service.py         # User CRUD
│   ├── quiz_service.py         # Quiz CRUD
│   ├── session_service.py      # Session management & scoring
│   └── quiz_engine.py          # Quiz orchestration (timers, flow)
│
├── handlers/
│   ├── start_handler.py        # /start, /help, deep links
│   ├── quiz_creation_handler.py # /create, /quizzes, quiz management
│   ├── quiz_play_handler.py    # Quiz play, poll answers, sessions
│   └── profile_handler.py      # /profile, /leaderboard
│
├── keyboards/
│   └── quiz_keyboards.py       # All inline & reply keyboards
│
└── utils/
    ├── helpers.py              # Formatting utilities
    └── pdf_generator.py        # PDF result generation
```

---

## ⚙️ Setup Guide

### 1. Prerequisites

- Python 3.10+
- MongoDB (local or cloud Atlas)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### 2. Create a Telegram Bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a name and username (e.g. `MyQuizBot`)
4. Copy the **API token**
5. Send `/setprivacy` → select your bot → `Disable` (needed to receive poll answers in groups)

### 3. Install Dependencies

```bash
# Clone or download the project
cd telegram_quiz_bot

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# OR
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy the example env file
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
MONGO_URI=mongodb://localhost:27017
DB_NAME=quiz_bot
BOT_USERNAME=MyQuizBot
```

> For **MongoDB Atlas** (cloud), use:
> ```
> MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
> ```

### 5. Start MongoDB

**Local:**
```bash
# Ubuntu/Debian
sudo systemctl start mongod

# macOS (Homebrew)
brew services start mongodb-community

# Windows
net start MongoDB
```

### 6. Run the Bot

```bash
python main.py
```

You should see:
```
✅ Connected to MongoDB: quiz_bot
🤖 Quiz Bot starting...
```

---

## 🎮 Usage Guide

### Creating a Quiz

1. Send `/create` to the bot
2. Enter a **title** for your quiz
3. Use the **📎 attachment button → Poll → Quiz** to add questions:
   - Write your question text
   - Add 2–4 answer options
   - Select the **correct answer** (Telegram highlights it)
   - Send the poll to the bot
4. The bot saves it automatically — add more or tap **✅ Done**
5. Configure settings (timer, scoring, shuffle, exam mode)
6. Share the link!

### Starting a Quiz

**Option 1: Share Link**
```
https://t.me/YourBot?start=quiz_QUIZ_ID
```
Share this in any group or DM — anyone who taps it starts the quiz.

**Option 2: From bot menu**
- Send `/quizzes` → select a quiz → tap **▶️ Start Quiz**

### During a Quiz

- A native Telegram quiz poll appears for each question
- Tap your answer — Telegram shows if you're correct (non-exam mode)
- Timer counts down automatically
- Quiz moves to next question after timer
- Live leaderboard shown after each question

### Commands Reference

| Command | Description |
|---------|-------------|
| `/start` | Welcome & main menu |
| `/create` | Create new quiz |
| `/quizzes` | View your quizzes |
| `/leaderboard` | Global leaderboard |
| `/profile` | Your stats |
| `/stopquiz` | Stop current quiz |
| `/help` | Help |
| `/cancel` | Cancel operation |

---

## 🗄️ MongoDB Collections

| Collection | Purpose |
|-----------|---------|
| `users` | User profiles & global stats |
| `quizzes` | Quiz definitions & settings |
| `sessions` | Active/completed quiz sessions |
| `attempts` | (Reserved for extended use) |
| `leaderboard` | Per-quiz best scores |

---

## 🔒 Permission Matrix

| Action | Private Chat | Group |
|--------|-------------|-------|
| Start quiz | Anyone | Anyone with link |
| Answer questions | Anyone | Any group member |
| Resume paused quiz | Creator | Any group member |
| End/Stop quiz | Creator | Group admin/owner |
| Create quiz | Anyone | Bot must be in group |

---

## 🐛 Troubleshooting

**Bot doesn't receive poll answers:**
- Ensure `/setprivacy` is set to **Disabled** in @BotFather for your bot
- Bot must be a member of the group

**MongoDB connection error:**
- Check `MONGO_URI` in `.env`
- Ensure MongoDB is running: `sudo systemctl status mongod`

**PDF not generating:**
- Ensure `reportlab` is installed: `pip install reportlab`

**Bot not responding in groups:**
- Add the bot as a member to the group
- Ensure bot privacy is disabled (see above)

---

## 📄 License

MIT License — free for personal and commercial use.
