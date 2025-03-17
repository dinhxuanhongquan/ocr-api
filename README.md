# Video Translation API

A FastAPI-based REST API for video translation services with user authentication and video upload capabilities.

## Features

- User Authentication (JWT)
- OAuth2 Integration (Google & Microsoft)
- Video Upload to S3
- Database Integration (SQLAlchemy)
- Session Management
- CORS Support

## Prerequisites

- Python 3.8+
- PostgreSQL
- AWS S3 Account
- Google OAuth2 Credentials
- Microsoft OAuth2 Credentials

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/OCR-API.git
cd OCR-API
```

2. Create and activate virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables:
   Create a `.env` file with the following variables:

```
DATABASE_URL=postgresql://user:password@localhost/dbname
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_BUCKET_NAME=your_bucket_name
SESSION_SECRET_KEY=your_session_secret
```

## Running the Application

1. Start the server:

```bash
uvicorn main:app --reload
```

2. Access the API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

- POST `/register` - Register a new user
- POST `/login` - Login with username/password
- GET `/login/google` - Google OAuth login
- GET `/login/microsoft` - Microsoft OAuth login
- POST `/logout` - Logout user
- POST `/videos/upload` - Upload a video file

## License

MIT License
