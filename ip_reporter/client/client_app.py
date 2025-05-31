import socket
import time
import requests
import configparser
from datetime import datetime, timedelta
import json
import os
import logging

# Configure logging
logger = logging.getLogger("ip_reporter_client")
logger.setLevel(logging.INFO)
# Create a handler (e.g., StreamHandler to output to console)
# The systemd service file redirects stdout/stderr to syslog, so this will end up there.
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'client_config.ini')

def get_hostname():
    """Returns the system's hostname."""
    try:
        return socket.gethostname()
    except socket.gaierror:
        logger.error("Could not determine hostname.")
        return None

def get_ip_address():
    """
    Determines the primary non-loopback IP address.
    Connects to an external server (Google DNS) to find the outbound IP.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 53))
        ip_address = s.getsockname()[0]
        return ip_address
    except socket.error as e:
        logger.error(f"Could not determine IP address. Network may be down. Details: {e}")
        return None
    finally:
        if 's' in locals():
            s.close()

def load_config():
    """Reads client_config.ini and returns a config object."""
    logger.info(f"Loading configuration from {CONFIG_FILE}")
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Configuration file {CONFIG_FILE} not found.")
        return None
    try:
        config.read(CONFIG_FILE)
        logger.info("Configuration loaded successfully.")
        return config
    except configparser.Error as e:
        logger.critical(f"Error reading configuration file: {e}")
        return None

def send_data(config, hostname, ip_address):
    """
    Sends the hostname and IP address to the master server.
    Returns True on success, False otherwise.
    """
    if not config:
        logger.error("Configuration not loaded, cannot send data.")
        return False

    try:
        master_host = config.get('MasterServer', 'host')
        master_port = config.getint('MasterServer', 'port')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.error(f"Missing master server configuration: {e}")
        return False

    url = f"http://{master_host}:{master_port}/report_ip"
    # Including client-side timestamp in payload for more accurate 'event time' if needed by server
    payload = {'hostname': hostname, 'ip_address': ip_address, 'timestamp': datetime.now().isoformat()}

    logger.info(f"Attempting to report IP: {ip_address} for hostname: {hostname} to {url}")
    try:
        response = requests.post(url, json=payload, timeout=10)
        if 200 <= response.status_code < 300:
            # Assuming server sends back JSON, if it's plain text, response.text is better
            try:
                logger.info(f"Successfully reported. Server response: {response.json()}")
            except requests.exceptions.JSONDecodeError:
                logger.info(f"Successfully reported. Server response: {response.text}")
            return True
        else:
            logger.error(f"Failed to report. Status code: {response.status_code}, Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending data: {e}")
        return False

if __name__ == '__main__':
    logger.info("Starting IP Reporter Client...")
    config = load_config()
    if not config:
        logger.critical("Exiting due to configuration error.")
        exit(1)

    try:
        reporting_interval = config.getint('ClientSettings', 'reporting_interval_seconds')
        retry_interval = config.getint('ClientSettings', 'retry_interval_seconds')
        max_retry_duration = timedelta(seconds=config.getint('ClientSettings', 'max_retry_duration_seconds'))
        logger.info(f"Settings: ReportingInterval={reporting_interval}s, RetryInterval={retry_interval}s, MaxRetryDuration={max_retry_duration.total_seconds()}s")
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logger.error(f"Invalid client settings in configuration: {e}")
        reporting_interval = 1800
        retry_interval = 300
        max_retry_duration = timedelta(seconds=86400)
        logger.warning(f"Using default intervals: Report={reporting_interval}s, Retry={retry_interval}s, MaxRetryDuration={max_retry_duration.total_seconds()}s")

    first_failed_attempt_time = None
    last_known_hostname = None
    last_known_ip = None

    while True:
        current_hostname = get_hostname()
        current_ip = get_ip_address()

        if not current_hostname or not current_ip:
            logger.warning(f"Could not get hostname or IP. Retrying in {retry_interval} seconds.")
            time.sleep(retry_interval)
            continue

        data_changed = (current_hostname != last_known_hostname) or (current_ip != last_known_ip)
        if data_changed:
            logger.info(f"Data changed. New Hostname: {current_hostname}, New IP: {current_ip}. Resetting retry state.")
            first_failed_attempt_time = None
            last_known_hostname = current_hostname
            last_known_ip = current_ip

        success = send_data(config, current_hostname, current_ip)

        if success:
            logger.info(f"Reporting successful. Next report in {reporting_interval} seconds.")
            first_failed_attempt_time = None
            time.sleep(reporting_interval)
        else:
            logger.warning("Reporting failed.")
            if first_failed_attempt_time is None:
                first_failed_attempt_time = datetime.now()
                logger.info("This is the first failure for this data. Starting retry window.")

            elapsed_retry_time = datetime.now() - first_failed_attempt_time
            if elapsed_retry_time > max_retry_duration:
                logger.error(f"Maximum retry duration ({max_retry_duration.total_seconds()}s) exceeded for {last_known_hostname}/{last_known_ip}. Giving up on this data point.")
                logger.info(f"Will fetch fresh data and attempt reporting again in {reporting_interval} seconds.")
                first_failed_attempt_time = None
                last_known_hostname = None
                last_known_ip = None
                time.sleep(reporting_interval)
            else:
                logger.warning(f"Will retry in {retry_interval} seconds. Elapsed retry time: {elapsed_retry_time.total_seconds():.0f}s / {max_retry_duration.total_seconds()}s")
                time.sleep(retry_interval)
