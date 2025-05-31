# IP Reporter

This project helps track the IP addresses of remote systems. A client application runs on remote systems and reports their IP address and hostname to a master server. The master server collects this information and displays it on a simple web UI.

## Features
*   Client application automatically reports its public/primary IP address and system hostname.
*   Master server with a web UI to view a list of all reported client systems, their last known IP, and the timestamp of their last report.
*   Client application includes retry logic for temporary network issues.
*   Client configuration is managed via an `.ini` file.
*   Master server stores data in a local SQLite database (`clients.db`).
*   Client can be run as a systemd service on Linux for automatic startup and background operation.
*   Configurable reporting intervals, retry intervals, and maximum retry duration for the client.

## Directory Structure
*   `ip_reporter/`
    *   `client/`
        *   `client_app.py`: The client application script.
        *   `client_config.ini`: Configuration file for the client.
        *   `requirements.txt`: Python dependencies for the client.
        *   `ip_reporter_client.service`: A template systemd service file for running the client on Linux.
    *   `master/`
        *   `master_app.py`: The master server Flask application.
        *   `requirements.txt`: Python dependencies for the master server.
        *   `clients.db`: (Created automatically) SQLite database for storing client data.
    *   `README.md`: This file.
    *   `.gitignore`: Standard Python git ignore file.

## Master Server Setup

The master server listens for reports from clients and displays the collected data.

1.  **Prerequisites:**
    *   Python 3 (python3)
    *   pip (Python package installer)
    *   Access to the server's terminal.

2.  **Clone or Copy Files:**
    *   Transfer the `ip_reporter/master/` directory (containing `master_app.py` and `requirements.txt`) to your chosen server. For example, you might place it in `/opt/ip_reporter/master/`.

3.  **Install Dependencies:**
    Navigate to the master application directory and install the required Python packages:
    ```bash
    cd /path/to/ip_reporter/master
    pip install -r requirements.txt
    ```

4.  **Running the Server:**
    Execute the `master_app.py` script:
    ```bash
    python3 master_app.py
    ```
    *   The server will start by default on `0.0.0.0:5000`. This means it will be accessible on all network interfaces of the server at port 5000.
    *   A `clients.db` SQLite database file will be automatically created in the `ip_reporter/master/` directory when the first client reports, or when the server starts (as `init_db` is called).
    *   You can access the web UI by navigating to `http://<master_server_ip>:5000` in a web browser.

5.  **Firewall Configuration:**
    Ensure that port 5000 (or your chosen port) is open for incoming TCP connections on the master server's firewall.

6.  **IMPORTANT (Dynamic IP for Master Server):**
    If the master server is on a network with a dynamic public IP address (common for home internet connections), its IP can change. For reliable client reporting:
    *   **Use a Dynamic DNS (DDNS) service:** Sign up for a free or paid DDNS service (e.g., No-IP, Dynu, DuckDNS).
    *   **Configure DDNS:**
        *   Set up a DDNS client on your master server or router. This client will automatically update the DDNS service whenever your public IP changes.
        *   You will get a stable hostname (e.g., `yourmaster.ddns.org`) from the DDNS provider.
    *   **Use the DDNS hostname:** In the `client_config.ini` file on all client machines, set the `host` parameter under `[MasterServer]` to this DDNS hostname instead of an IP address.

7.  **Running as a Service (Optional, Advanced):**
    For production, you might want to run the Flask master server using a more robust setup like Gunicorn behind an Nginx reverse proxy, and manage it with systemd. This is beyond this basic setup guide.

## Client Application Setup

The client application reports its IP and hostname to the master server.

1.  **Prerequisites:**
    *   Python 3 (python3)
    *   pip (Python package installer)
    *   Access to the client machine's terminal.

2.  **Clone or Copy Files:**
    *   Transfer the `ip_reporter/client/` directory (containing `client_app.py`, `client_config.ini`, `requirements.txt`, and `ip_reporter_client.service`) to each client machine.
    *   A common location for such applications is `/opt/ip_reporter/client` or `/usr/local/ip_reporter/client`. If you copy the whole project, it might be `/opt/ip_reporter/`.

3.  **Install Dependencies:**
    Navigate to the client application directory and install the required Python packages:
    ```bash
    cd /path/to/ip_reporter/client
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    Edit the `client_config.ini` file:
    *   `[MasterServer]`
        *   `host`: Set this to the hostname or IP address of your master server. **Using a DDNS hostname is highly recommended if the master server's IP can change.** (e.g., `yourmaster.ddns.org`).
        *   `port`: The port on which the master server is listening (default is `5000`).
    *   `[ClientSettings]`
        *   `reporting_interval_seconds`: How often (in seconds) the client should report its IP (e.g., `1800` for 30 minutes).
        *   `retry_interval_seconds`: How long (in seconds) to wait before retrying if a report fails (e.g., `300` for 5 minutes).
        *   `max_retry_duration_seconds`: Maximum total time (in seconds) to keep retrying for a single data point if reporting continuously fails (e.g., `86400` for 24 hours). After this, it will wait for the normal `reporting_interval_seconds` and try with fresh data.

5.  **Manual Run (for Testing):**
    You can run the client directly from the terminal to test its operation:
    ```bash
    cd /path/to/ip_reporter/client
    python3 client_app.py
    ```
    Log messages will be printed to the standard output.

6.  **Systemd Service Installation (Linux - Recommended for Auto-start and Background Operation):**
    This allows the client to run automatically on boot and restart on failure.
    *   **Ensure Project is in a Stable Location:** The client application files (especially `client_app.py` and `client_config.ini`) should be in their final, stable location (e.g., `/opt/ip_reporter/client/`).
    *   **Edit the Service File:**
        Open the `ip_reporter_client.service` template file with a text editor. You will need to customize the paths:
        *   `WorkingDirectory=`: Set this to the absolute path of your `ip_reporter/client/` directory.
            *   Example: `WorkingDirectory=/opt/ip_reporter/client/`
        *   `ExecStart=`: Set this to the absolute path of your `python3` interpreter followed by the absolute path to `client_app.py`.
            *   Example: `ExecStart=/usr/bin/python3 /opt/ip_reporter/client/client_app.py`
            *   If you are using a Python virtual environment, the path to python3 would be different, e.g., `/opt/ip_reporter/venv/bin/python3`.
        *   `User=` / `Group=`: By default, the service might run as root. For better security, you can create a dedicated user and group to run the client service, then specify them here (e.g., `User=ipreporter`, `Group=ipreporter`). Ensure this user has read access to the client files and write access if the script needs to create local logs (though current script logs to syslog via systemd).
    *   **Install and Enable the Service:**
        ```bash
        # Copy your edited service file to the systemd directory
        sudo cp /path/to/your/edited/ip_reporter_client.service /etc/systemd/system/ip_reporter_client.service

        # Reload the systemd daemon to recognize the new service
        sudo systemctl daemon-reload

        # Enable the service to start on boot
        sudo systemctl enable ip_reporter_client.service

        # Start the service immediately
        sudo systemctl start ip_reporter_client.service
        ```
    *   **Check Status and Logs:**
        ```bash
        # Check the status of the service
        sudo systemctl status ip_reporter_client.service

            # View live logs (follow mode)
        sudo journalctl -u ip_reporter_client.service -f

        # View all logs for the service
        sudo journalctl -u ip_reporter_client.service
        ```
            The client application uses Python's built-in logging. Timestamps and log levels are part of the log messages. Journald captures these logs, and they will typically look like this (the `ip-reporter-client[PID]` part is added by systemd/journald):
            ```
            -- Logs begin at ... --
            May 31 18:00:00 yourclienthostname ip-reporter-client[12345]: 2025-05-31 18:00:00,123 - ip_reporter_client - INFO - Starting IP Reporter Client...
            May 31 18:00:00 yourclienthostname ip-reporter-client[12345]: 2025-05-31 18:00:00,125 - ip_reporter_client - INFO - Loading configuration from /path/to/ip_reporter/client/client_config.ini
            May 31 18:00:01 yourclienthostname ip-reporter-client[12345]: 2025-05-31 18:00:01,300 - ip_reporter_client - INFO - Attempting to report IP: 192.168.1.10 for hostname: yourclient to http://masterhost:5000/report_ip
            May 31 18:00:01 yourclienthostname ip-reporter-client[12345]: 2025-05-31 18:00:01,500 - ip_reporter_client - INFO - Successfully reported. Server response: {'status': 'success', 'message': 'IP reported'}
            May 31 18:00:01 yourclienthostname ip-reporter-client[12345]: 2025-05-31 18:00:01,502 - ip_reporter_client - INFO - Reporting successful. Next report in 1800 seconds.
            ```

## Troubleshooting

*   **Client Not Reporting:**
    *   **Client Logs:** If running as a service, use `journalctl -u ip_reporter_client.service` to check for errors. If running manually, check terminal output.
    *   **Configuration:** Double-check `client_config.ini`. Is the master `host` and `port` correct?
    *   **Network:** Can the client machine reach the master server and port? Use `ping <master_host>` (if ICMP is allowed) or `curl http://<master_host>:<master_port>` from the client. Check firewalls on both client and master, and any network firewalls in between.
    *   **Dependencies:** Ensure `requests` is installed in the Python environment the client is using.
    *   **IP Address Detection:** The `get_ip_address()` function in `client_app.py` tries to connect to `8.8.8.8:53` to determine the outbound IP. If this is blocked or the client has no internet, it might fail.

*   **Master Server Issues:**
    *   **Server Logs:** Check the terminal output where `master_app.py` is running for error messages.
    *   **Accessibility:** Is the master server running? Is the port (e.g., 5000) accessible from the client machines? Check server firewall.
    *   **Dependencies:** Ensure `Flask` is installed.
    *   **Database:** Check if `clients.db` is created in the `master/` directory. Check its permissions if there are database errors in the logs.

*   **Data Not Appearing in Web UI:**
    *   Ensure clients are successfully reporting (check client logs).
    *   Ensure the master server is receiving reports (check master logs).
    *   The web UI shows data from `clients.db`. If this database is deleted or inaccessible, no data will appear.

*   **Systemd Service Fails to Start:**
    *   Use `sudo systemctl status ip_reporter_client.service` and `sudo journalctl -xeu ip_reporter_client.service` for detailed error messages.
    *   **Path Errors:** Most common issue. Double-check `ExecStart=` and `WorkingDirectory=` paths in your `.service` file. They must be absolute and correct.
    *   **Permissions:** Ensure the user running the service (root or a dedicated user) has execute permissions for `client_app.py` and the Python interpreter, and read access to all necessary files.
    *   **Python Environment:** If you installed dependencies into a virtual environment, ensure `ExecStart` points to the python executable *inside* that venv.
```
