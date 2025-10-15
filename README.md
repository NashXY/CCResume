# CCResume

A resume management system built with Python, Flask, and SQLite.

## Project Structure

```
CCResume/
├── Source/              # Application source code
│   └── app.py          # Main Flask application
├── ThirdParty/         # Third-party dependencies
│   └── SQLite/         # SQLite database directory
│       └── ccresume.db # SQLite database file (generated at runtime)
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python Source/app.py
```

The application will:
- Create the `ThirdParty/SQLite` directory if it doesn't exist
- Initialize the SQLite database at `ThirdParty/SQLite/ccresume.db`
- Start the Flask development server on `http://localhost:5000`

## API Endpoints

### Home
- `GET /` - Welcome message with available endpoints

### Resumes
- `GET /resumes` - List all resumes
- `POST /resumes` - Create a new resume
  - Required fields: `name`, `email`
  - Optional fields: `phone`, `summary`
- `GET /resumes/<id>` - Get a specific resume by ID

## Example Usage

### Create a resume:
```bash
curl -X POST http://localhost:5000/resumes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "123-456-7890",
    "summary": "Experienced software developer"
  }'
```

### List all resumes:
```bash
curl http://localhost:5000/resumes
```

### Get a specific resume:
```bash
curl http://localhost:5000/resumes/1
```

## Technologies Used

- **Python 3.12+** - Programming language
- **Flask 3.0.0** - Web framework
- **SQLite** - Database (stored in `ThirdParty/SQLite/`)