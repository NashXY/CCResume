from flask import Flask, jsonify, request
import sqlite3
import os

app = Flask(__name__)

# Database path in ThirdParty/SQLite directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ThirdParty', 'SQLite', 'ccresume.db')

def init_db():
    """Initialize the database with a sample table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create a sample resumes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Home route."""
    return jsonify({
        'message': 'Welcome to CCResume API',
        'endpoints': {
            '/resumes': 'GET - List all resumes, POST - Create a resume',
            '/resumes/<id>': 'GET - Get a specific resume'
        }
    })

@app.route('/resumes', methods=['GET', 'POST'])
def resumes():
    """Handle resume list and creation."""
    if request.method == 'GET':
        conn = get_db_connection()
        resumes = conn.execute('SELECT * FROM resumes').fetchall()
        conn.close()
        return jsonify([dict(row) for row in resumes])
    
    elif request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone', '')
        summary = data.get('summary', '')
        
        if not name or not email:
            return jsonify({'error': 'Name and email are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO resumes (name, email, phone, summary) VALUES (?, ?, ?, ?)',
            (name, email, phone, summary)
        )
        conn.commit()
        resume_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'id': resume_id, 'message': 'Resume created successfully'}), 201

@app.route('/resumes/<int:resume_id>', methods=['GET'])
def get_resume(resume_id):
    """Get a specific resume by ID."""
    conn = get_db_connection()
    resume = conn.execute('SELECT * FROM resumes WHERE id = ?', (resume_id,)).fetchone()
    conn.close()
    
    if resume is None:
        return jsonify({'error': 'Resume not found'}), 404
    
    return jsonify(dict(resume))

if __name__ == '__main__':
    # Ensure the database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    # Initialize the database
    init_db()
    print(f"Database initialized at: {DB_PATH}")
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
