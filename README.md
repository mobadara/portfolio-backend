# Portfolio Chat Backend

An AI-powered chat application with real-time human handoff capability. Built with FastAPI, WebSockets, and Groq LLM.

## Features

- **AI Chat**: Intelligent responses powered by Groq's Llama 3 model
- **Real-time Communication**: WebSocket-based bidirectional communication
- **Human Handoff**: Seamless transition from AI to human agents
- **Lead Capture**: Automatic email notifications for lead generation
- **Session Management**: Persistent chat history with MongoDB
- **Admin Dashboard**: Real-time admin monitoring and chat takeover

## Tech Stack

- **Framework**: FastAPI
- **Database**: MongoDB with Beanie ODM
- **Real-time**: WebSockets
- **LLM**: Groq API (Llama 3)
- **Email**: FastAPI-Mail
- **Validation**: Pydantic v2
- **Server**: Uvicorn

## Prerequisites

- Python 3.9+
- MongoDB (local or Atlas)
- Groq API key
- Gmail account (for email notifications)

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd backend
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
- `MONGODB_URL`: Your MongoDB connection string
- `GROQ_API_KEY`: Your Groq API key
- `MAIL_USERNAME`: Your Gmail address
- `MAIL_PASSWORD`: Your Gmail app password
- `ADMIN_AUTH_TOKEN`: A secure random token for admin access

## Running the Application

### Development
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### WebSocket Endpoints

#### User Chat
- **URL**: `ws://localhost:8000/chat/{session_id}`
- **Description**: Establish chat session with AI
- **Message Format**: Plain text

#### Admin Monitor
- **URL**: `ws://localhost:8000/ws/admin/{session_id}?token=YOUR_ADMIN_TOKEN`
- **Description**: Monitor and take over chat sessions
- **Security**: Requires `ADMIN_AUTH_TOKEN` query parameter

### HTTP Endpoints

#### Health Check
- **GET** `/health`
- **Response**: `{"status": "healthy"}`

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization
│   ├── models/
│   │   └── chat.py          # Pydantic & Beanie models
│   ├── routers/
│   │   └── chat.py          # WebSocket endpoints
│   └── services/
│       ├── email.py         # Email notifications
│       ├── llm.py           # LLM service (placeholder)
│       ├── prompts.py       # System prompts
│       └── websocket_manager.py  # Connection management
├── requirements.txt
├── .env.example
└── README.md
```

## Data Models

### Message
```python
{
  "role": "user" | "assistant" | "system",
  "content": "Message text",
  "timestamp": "2024-01-01T12:00:00"
}
```

### ChatSession
- `session_id`: Unique identifier
- `messages`: List of messages
- `user_name`: Optional user name
- `user_email`: Optional user email
- `user_phone`: Optional user phone
- `is_active`: Session status
- `human_mode`: AI or human mode
- `human_agent_assigned`: Agent assignment status

## Key Improvements Made

✅ **Pydantic Validation**
- Added `MessageRole` enum for type safety
- Proper field validation with constraints
- Email validation using `EmailStr`

✅ **Error Handling**
- Specific exception handling instead of bare `except`
- Comprehensive logging throughout
- Graceful error recovery

✅ **Security**
- Admin authentication via token
- CORS middleware configuration
- Input validation

✅ **Code Quality**
- Type hints throughout
- Proper docstrings
- Logging for debugging
- Industry-standard structure

✅ **Database**
- Beanie ODM integration
- Proper startup initialization
- MongoDB support

✅ **Configuration**
- Environment variable management
- `.env.example` template
- Configurable CORS origins

## Environment Variables

```env
# Database
MONGODB_URL=mongodb://localhost:27017
DB_NAME=portfolio_chat

# API Keys
GROQ_API_KEY=your_key_here
ADMIN_AUTH_TOKEN=your_secure_token

# Email (Gmail)
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

## Troubleshooting

### MongoDB Connection Issues
- Ensure MongoDB is running locally or Atlas connection string is correct
- Check `MONGODB_URL` in `.env`

### Groq API Errors
- Verify `GROQ_API_KEY` is valid
- Check API rate limits

### Email Not Sending
- Enable "Less secure app access" or use App Password in Gmail
- Verify `MAIL_USERNAME` and `MAIL_PASSWORD` are correct
- Check firewall/antivirus blocking port 587

### WebSocket Connection Refused
- Ensure FastAPI server is running
- Check port 8000 is available
- Verify CORS origins are configured

## Contributing

1. Create a feature branch
2. Make changes with proper type hints
3. Add/update docstrings
4. Test thoroughly
5. Submit pull request

## License

See LICENSE file for details.
