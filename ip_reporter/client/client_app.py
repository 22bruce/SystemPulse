import socket
import time
import requests
import configparser
from datetime import datetime, timedelta
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'client_config.ini')

def get_hostname():
    """Returns the system's hostname."""
    try:
        return socket.gethostname()
    except socket.gaierror:
        print(f"{datetime.now()} - Error: Could not determine hostname.")
        return None

def get_ip_address():
    """
    Determines the primary non-loopback IP address.
    Connects to an external server (Google DNS) to find the outbound IP.
    """
    try:
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2) # Timeout for the connection attempt
        # Connect to an external server (doesn't actually send data)
        s.connect(("8.8.8.8", 53))
        # Get the socket's own address
        ip_address = s.getsockname()[0]
        return ip_address
    except socket.error as e:
        print(f"{datetime.now()} - Error: Could not determine IP address. Network may be down. Details: {e}")
        return None
    finally:
        if 's' in locals():
            s.close()

def load_config():
    """Reads client_config.ini and returns a config object."""
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        print(f"{datetime.now()} - Error: Configuration file {CONFIG_FILE} not found.")
        return None
    try:
        config.read(CONFIG_FILE)
        return config
    except configparser.Error as e:
        print(f"{datetime.now()} - Error reading configuration file: {e}")
        return None

def send_data(config, hostname, ip_address):
    """
    Sends the hostname and IP address to the master server.
    Returns True on success, False otherwise.
    """
    if not config:
        print(f"{datetime.now()} - Error: Configuration not loaded, cannot send data.")
        return False

    try:
        master_host = config.get('MasterServer', 'host')
        master_port = config.getint('MasterServer', 'port') # Ensure port is an integer
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"{datetime.now()} - Error: Missing master server configuration: {e}")
        return False

    url = f"http://{master_host}:{master_port}/report_ip"
    payload = {'hostname': hostname, 'ip_address': ip_address, 'timestamp': datetime.now().isoformat()}

    print(f"{datetime.now()} - Attempting to report IP: {ip_address} for hostname: {hostname} to {url}")
    try:
        response = requests.post(url, json=payload, timeout=10)
        if 200 <= response.status_code < 300:
            print(f"{datetime.now()} - Successfully reported. Server response: {response.text}")
            return True
        else:
            print(f"{datetime.now()} - Failed to report. Status code: {response.status_code}, Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"{datetime.now()} - Error sending data: {e}")
        return False

if __name__ == '__main__':
    config = load_config()
    if not config:
        print(f"{datetime.now()} - Exiting due to configuration error.")
        exit(1) # Use exit(1) to indicate an error exit

    try:
        reporting_interval = config.getint('ClientSettings', 'reporting_interval_seconds')
        retry_interval = config.getint('ClientSettings', 'retry_interval_seconds')
        max_retry_duration = timedelta(seconds=config.getint('ClientSettings', 'max_retry_duration_seconds'))
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        print(f"{datetime.now()} - Error: Invalid client settings in configuration: {e}")
        # Fallback to default values if config is malformed
        reporting_interval = 1800
        retry_interval = 300
        max_retry_duration = timedelta(seconds=86400)
        print(f"{datetime.now()} - Using default intervals: Report={reporting_interval}s, Retry={retry_interval}s, MaxRetryDuration={max_retry_duration.total_seconds()}s")


    first_failed_attempt_time = None
    last_known_hostname = None
    last_known_ip = None

    while True:
        current_hostname = get_hostname()
        current_ip = get_ip_address()

        if not current_hostname or not current_ip:
            print(f"{datetime.now()} - Could not get hostname or IP. Retrying in {retry_interval} seconds.")
            time.sleep(retry_interval)
            continue

        # Check if data has changed since last successful report or last attempt
        data_changed = (current_hostname != last_known_hostname) or (current_ip != last_known_ip)
        if data_changed:
            print(f"{datetime.now()} - Data changed. New Hostname: {current_hostname}, New IP: {current_ip}. Resetting retry state.")
            first_failed_attempt_time = None # Reset retry window if data is new
            last_known_hostname = current_hostname
            last_known_ip = current_ip

        success = send_data(config, current_hostname, current_ip)

        if success:
            print(f"{datetime.now()} - Reporting successful. Next report in {reporting_interval} seconds.")
            first_failed_attempt_time = None # Reset on success
            time.sleep(reporting_interval)
        else:
            print(f"{datetime.now()} - Reporting failed.")
            if first_failed_attempt_time is None:
                first_failed_attempt_time = datetime.now()
                print(f"{datetime.now()} - This is the first failure for this data. Starting retry window.")

            if datetime.now() - first_failed_attempt_time > max_retry_duration:
                print(f"{datetime.now()} - Maximum retry duration ({max_retry_duration.total_seconds()}s) exceeded for {last_known_hostname}/{last_known_ip}. Giving up on this data point.")
                print(f"{datetime.now()} - Will fetch fresh data and attempt reporting again in {reporting_interval} seconds.")
                first_failed_attempt_time = None # Reset retry state
                last_known_hostname = None # Force data refresh
                last_known_ip = None
                time.sleep(reporting_interval) # Sleep for the main reporting interval before fetching fresh data
            else:
                print(f"{datetime.now()} - Will retry in {retry_interval} seconds.")
                time.sleep(retry_interval)
