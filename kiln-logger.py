#!/usr/bin/env python

import websocket
import json
import time
import csv
import argparse
import sys

# Define standard and PID headers for CSV file
STD_HEADER = [
    'stamp',
    'runtime',
    'temperature',
    'target',
    'state',
    'heat',
    'total_time',
    'profile',
]

PID_HEADER = [
    'pid_time',
    'pid_timeDelta',
    'pid_setpoint',
    'pid_ispoint',
    'pid_err',
    'pid_errDelta',
    'pid_p',
    'pid_i',
    'pid_d',
    'pid_kp',
    'pid_ki',
    'pid_kd',
    'pid_pid',
    'pid_out',
]

def logger(hostname, csv_file, profile_stats, pid_stats, stdout):
    status_ws = websocket.WebSocket()

    # Determine CSV fields based on flags
    csv_fields = STD_HEADER if profile_stats else []
    csv_fields += PID_HEADER if pid_stats else []

    # Setup CSV writer for file output
    with open(csv_file, 'w', newline='') as output_file:
        csv_writer = csv.DictWriter(output_file, csv_fields, extrasaction='ignore')
        csv_writer.writeheader()

        # Setup CSV writer for standard output if required
        csv_stdout = csv.DictWriter(sys.stdout, csv_fields, extrasaction='ignore', delimiter='\t') if stdout else None
        if stdout:
            csv_stdout.writeheader()

        # Main data logging loop
        while True:
            try:
                msg = json.loads(status_ws.recv())
            except websocket.WebSocketException:
                try:
                    status_ws.connect(f'ws://{hostname}/status')
                except Exception:
                    time.sleep(5)
                continue

            # Skip backlog messages
            if msg.get('type') == 'backlog':
                continue

            # Process message for CSV and stdout output
            if profile_stats:
                msg['stamp'] = time.time()
            if pid_stats and 'pid_stats' in msg:
                msg.update({f"pid_{k}": v for k, v in msg['pid_stats'].items()})

            formatted_msg = {k: '{:5.3f}'.format(v) if isinstance(v, float) else v for k, v in msg.items()}

            # Write formatted message to CSV file and flush
            csv_writer.writerow(formatted_msg)
            output_file.flush()

            # Write the same formatted message to stdout (if enabled) and flush
            if stdout:
                csv_stdout.writerow(formatted_msg)
                sys.stdout.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Log kiln data for analysis.')
    parser.add_argument('--hostname', type=str, default="localhost:8081", help="The kiln-controller hostname:port")
    parser.add_argument('--csv_file', type=str, default="/tmp/kiln_stats.csv", help="Where to write the kiln stats to")
    parser.add_argument('--pid_stats', action='store_false', help="Include PID stats")
    parser.add_argument('--profile_stats', action='store_false', help="store profile stats (default is to store them)")
    parser.add_argument('--stdout', action='store_false', help="Also print to stdout")
    args = parser.parse_args()

    logger(args.hostname, args.csv_file, args.profile_stats, args.pid_stats, args.stdout)
