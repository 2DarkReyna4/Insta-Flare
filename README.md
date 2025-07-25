# InstaFlare

A full-featured Instagram-style social media application built with Flask and SQLite.

## 🚀 Features

- User registration and login
- Profile pages with avatar and cover photo
- Post images, captions, and videos
- Like, comment, save and follow functionality
- Direct messages between users
- Notifications for likes and comments
- View count tracking for posts
- AI-powered caption suggestions (OpenAI/GPT)
- Admin dashboard (optional)
- Scheduled posts (optional)
- Responsive design and dark mode
- Dockerized for deployment

## 📁 Project Structure

```
insta_flare/
├── app.py
├── run.py
├── caption_ai.py
├── scheduler.py
├── brobook.db
├── schema.sql
├── .env
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
├── README.md
├── templates/
├── static/
└── migrations/
```

## 🐳 Docker Usage

```bash
docker build -t insta-app .
docker run -p 5000:5000 insta-app
```

## 🧪 Local Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

## 🧠 AI Caption Suggestion

To enable AI caption suggestions, set your OpenAI API key in `.env`:

```
OPENAI_API_KEY=your_key_here
```

## 🛠️ License

MIT License. Feel free to build on top of this!
