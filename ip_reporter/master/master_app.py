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
        clients_rows = cursor.fetchall() # Renamed to avoid confusion with template variable name
        conn.close()
    except sqlite3.Error as e:
        print(f"{datetime.datetime.now()} - Database error on index page: {e}")
        return "Error fetching client data from database.", 500

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="60">
        <title>IP Reporter - Monitored Systems</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
                margin: 0;
                padding: 20px;
                background-color: #f4f7f6;
                color: #333;
                line-height: 1.6;
            }
            .container {
                max-width: 900px;
                margin: 20px auto;
                padding: 20px;
                background-color: #fff;
                box-shadow: 0 0 15px rgba(0,0,0,0.1);
                border-radius: 8px;
            }
            h1 {
                color: #2c3e50;
                text-align: center;
                margin-bottom: 10px;
            }
            .last-updated {
                text-align: center;
                font-size: 0.9em;
                color: #7f8c8d;
                margin-bottom: 25px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            th, td {
                padding: 12px 15px;
                border: 1px solid #ddd;
                text-align: left;
            }
            th {
                background-color: #3498db;
                color: #ffffff;
                font-weight: bold;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            tr:hover {
                background-color: #e8f4f8;
            }
            .no-clients {
                text-align: center;
                font-style: italic;
                color: #777;
                padding: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Monitored Systems</h1>
            <p class="last-updated">Last Updated: {{ now_utc }} UTC</p>
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
                        <td>{{ client['last_seen'].strftime('%Y-%m-%d %H:%M:%S') if client['last_seen'].strftime else client['last_seen'] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p class="no-clients">No client systems have reported yet.</p>
            {% endif %}
        </div>
    </body>
    </html>
    """

    processed_clients = []
    for client_row in clients_rows: # Iterate over fetched rows
        client_dict = dict(client_row)
        last_seen_str = client_dict['last_seen']
        try:
            last_seen_dt = datetime.datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            try:
                last_seen_dt = datetime.datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S')
            except ValueError as e_parse:
                print(f"{datetime.datetime.now()} - Error parsing timestamp '{last_seen_str}': {e_parse}")
                last_seen_dt = last_seen_str

        client_dict['last_seen'] = last_seen_dt
        processed_clients.append(client_dict)

    return render_template_string(html_template, clients=processed_clients, now_utc=datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    init_db()
    print(f"{datetime.datetime.now()} - Starting Flask server on host 0.0.0.0, port 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
