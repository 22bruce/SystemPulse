import flask
from flask import request, render_template_string
import sqlite3
import datetime
import os

# Initialize Flask app
app = flask.Flask(__name__)

# Define database path (co-located with master_app.py)
DATABASE = os.path.join(os.path.dirname(__file__), 'clients.db')

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

def init_db():
    """Initializes the database and creates the known_clients table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS known_clients (
            hostname TEXT PRIMARY KEY,
            ip_address TEXT NOT NULL,
            last_seen TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print(f"{datetime.datetime.now()} - Database initialized successfully at {DATABASE}")

@app.route('/report_ip', methods=['POST'])
def report_ip():
    """API endpoint for clients to report their IP address."""
    data = request.get_json()

    if not data or 'hostname' not in data or 'ip_address' not in data:
        return flask.jsonify({'status': 'error', 'message': 'Missing hostname or ip_address'}), 400

    hostname = data['hostname']
    ip_address = data['ip_address']
    # Timestamp can be provided by client, or use server time if not.
    # For consistency, we'll use server time upon receipt.
    current_time = datetime.datetime.now()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO known_clients (hostname, ip_address, last_seen)
            VALUES (?, ?, ?)
        ''', (hostname, ip_address, current_time))
        conn.commit()
        conn.close()
        print(f"{datetime.datetime.now()} - Received IP report: Hostname={hostname}, IP={ip_address}")
        return flask.jsonify({'status': 'success', 'message': 'IP reported'}), 201
    except sqlite3.Error as e:
        print(f"{datetime.datetime.now()} - Database error: {e}")
        return flask.jsonify({'status': 'error', 'message': f'Database error: {e}'}), 500

@app.route('/')
def index():
    """Web UI endpoint to display known clients."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT hostname, ip_address, last_seen FROM known_clients ORDER BY last_seen DESC")
        clients = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"{datetime.datetime.now()} - Database error on index page: {e}")
        return "Error fetching client data from database.", 500

    # Simple HTML template string
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>IP Reporter - Known Clients</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            table { width: 80%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
        </style>
    </head>
    <body>
        <h1>Known Client Systems</h1>
        {% if clients %}
            <table>
                <thead>
                    <tr>
                        <th>Hostname</th>
                        <th>IP Address</th>
                        <th>Last Seen (UTC)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for client in clients %}
                    <tr>
                        <td>{{ client['hostname'] }}</td>
                        <td>{{ client['ip_address'] }}</td>
                        <td>{{ client['last_seen'].strftime('%Y-%m-%d %H:%M:%S') if client['last_seen'] is string else client['last_seen'] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p>No clients have reported yet.</p>
        {% endif %}
        <p><small>Page loaded at: {{ now_utc }} UTC</small></p>
    </body>
    </html>
    """
    # Ensure last_seen is formatted correctly if it's already a string from DB (depends on sqlite3 version/config)
    # Typically, SQLite stores TIMESTAMP as text, so strftime might not be needed if it's already text.
    # However, if it's retrieved as a datetime object by sqlite3.Row, strftime is good.
    # The template handles a string by just printing it.

    # Convert datetime objects in clients if they are not strings
    processed_clients = []
    for client_row in clients:
        client_dict = dict(client_row) # Convert sqlite3.Row to dict
        if isinstance(client_dict['last_seen'], datetime.datetime):
            client_dict['last_seen'] = client_dict['last_seen'].strftime('%Y-%m-%d %H:%M:%S')
        # If it's a string, assume it's already in 'YYYY-MM-DD HH:MM:SS.ffffff' format from DB
        # and take only the part before microseconds for cleaner display.
        elif isinstance(client_dict['last_seen'], str) and '.' in client_dict['last_seen']:
             client_dict['last_seen'] = client_dict['last_seen'].split('.')[0]

        processed_clients.append(client_dict)


    return render_template_string(html_template, clients=processed_clients, now_utc=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    # Ensure the script directory is the current working directory
    # This helps when running from different locations, ensuring DATABASE path is correct.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    init_db()  # Initialize the database and table on startup
    print(f"{datetime.datetime.now()} - Starting Flask server on host 0.0.0.0, port 5000")
    # When running Flask dev server directly, it's better not to use debug=True in "production" or shared dev.
    # For this task, debug=True is fine as requested.
    app.run(host='0.0.0.0', port=5000, debug=True)
