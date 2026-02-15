import socket
import requests

import os
import psutil
import subprocess

import time
from datetime import datetime

import json


def check_cpu_usage(cnf: dict):
    warn = cnf['warn']
    crit = cnf['crit']
    cpu_used= psutil.cpu_percent(interval=1)
    if cpu_used >= crit:
        status = 'CRITICAL'
    elif cpu_used >= warn:
        status = 'WARNING'
    else: status = 'OK'

    return {'Value': cpu_used, 'status': status}



def check_memory_usage(cnf: dict):
        warn = cnf['warn']
        crit = cnf['crit']

        memory_used = psutil.virtual_memory().percent
        if memory_used >= crit:
            status = 'CRITICAL'
        elif memory_used >= warn:
            status = 'WARNING'
        else:
            status = 'OK'
        return {'Value': memory_used, 'status': status}

def check_disk_usage(cnf: dict):
        warn = cnf['warn']
        crit = cnf['crit']
        path = cnf['path']

        disk_used= psutil.disk_usage(path).percent
        free = psutil.disk_usage(path).free / 1024 / 1024 / 8

        if disk_used >= crit:
            status = 'CRITICAL'
        elif disk_used >= warn:
            status = 'WARNING'
        else:
            status = 'OK'
        return {'free_percent mb': free, 'status': status}


def check_logs(cnf: dict):
        file = cnf['file']
        error_count = 0
        max_mb = cnf['max_mb']

        try:
            size = os.path.getsize(file)
            size_mb = size / 1024 / 1024
            with open(file, 'r') as f:
                for line in f:
                    if 'ERROR' in line:
                        error_count += 1
                    if size_mb > max_mb:
                        status = 'WARNING'
                    else: status = 'OK'
                    return {'Errors': error_count,'size mb': size_mb, 'status': status}
        except FileNotFoundError as e:
            status = f'ERROR - {e}'
            return {'Errors': error_count, 'status': status}



def check_http(cnf: dict, retry: int = 3):
        url = cnf['url']
        timeout = cnf['timeout']
        warn = cnf['warn_ms']
        status = None
        ms = 0
        status_ms = None
        for times in range(1,retry + 1):
            try:
                t0 = time.perf_counter()
                conn = requests.get(url, timeout=timeout)
                ms = round((time.perf_counter() - t0) * 1000, 2)
                if conn.status_code == 200:
                    status = 'OK'
                if ms > warn:
                    status_ms = 'WARNING'
                return {'time_ms': ms, 'status_ms': status_ms, 'status': status}
            except (OSError, requests.exceptions.ConnectionError) as e:
                status = f'ERROR - - - {e}'
        return {'time_ms': ms, 'status_ms': status_ms, 'status': status}


def check_tcp(cnf: dict):
    host = cnf["host"]
    port = cnf["port"]
    timeout = cnf.get("timeout", 1)
    restart_cmd = cnf.get("restart_cmd")

    def tcp_once():
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return {"status": "OK"}
        except OSError as e:
            return {"status": "DOWN", "error": str(e)}

    initial = tcp_once()
    action = "NONE"
    restart = None

    if initial["status"] != "OK" and restart_cmd:
        action = "RESTART"
        r = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)
        restart = {
            "ok": (r.returncode == 0),
            "return code": r.returncode,
            "output": (r.stdout + "\n" + r.stderr).strip()
        }
        time.sleep(2)

    final = tcp_once()

    overall = "OK" if final["status"] == "OK" else "CRITICAL"
    return {"initial": initial, "action": action, "restart": restart, "final": final, "status": overall}


def over_all(parts: list[str]) -> str:

    if 'CRITICAL' in parts:
        status = 'CRITICAL'
    elif 'WARNING' in parts:
        status = 'WARNING'
    elif "ERROR" in parts:
        status = 'ERROR'
    else:
        status = 'OK'
    return status


def exit_codes(parts: list[str]):
    exit_code = None
    for part in parts:
        if "OK" in part:
            exit_code = exit(0)
        elif "WARNING" in part:
            exit_code = exit(1)
        else: exit_code = exit(2)
    return exit_code

def main():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cnf = json.load(f)
    except FileNotFoundError:
        print("Error: config_1.json not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing config_1.json: {e}")
        return


    cpu = check_cpu_usage(cnf["cpu"])
    memory = check_memory_usage(cnf["memory"])
    disk = check_disk_usage(cnf["disk"])
    logs = check_logs(cnf["logs"])
    http = check_http(cnf["http"])
    tcp = check_tcp(cnf["tcp"])


    alls = over_all([cpu['status'], memory['status'], disk['status'], logs['status'], http['status'], tcp['status']])
    all_results = []
    report = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'cpu': cpu,
        'memory': memory,
        'disk': disk,
        'logs': logs,
        'http': http,
        'tcp': tcp,
        'alls': alls
    }
    all_results.append(report)
    try:
        with open('report.json', 'w', encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=4)
            print('Report saved to report_2.json')
    except FileNotFoundError as e:
        print("Error: report.json not found")

if __name__ == '__main__':
    main()