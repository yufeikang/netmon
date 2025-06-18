#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "dnspython==2.6.1",
#     "pythonping==1.1.4",
#     "requests==2.32.3",
#     "speedtest-cli==2.1.3",
#     "psutil",
#     "prometheus_client==0.20.0",
#     "PyYAML==6.0.1",
# ]
# ///
# -*- coding: utf-8 -*-
"""
Company Network Monitor
"""

import asyncio
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from typing import Dict, List

import dns.resolver
import psutil
import requests
import yaml
from prometheus_client import Counter, Gauge, Summary, start_http_server
from pythonping import ping

# ------------------------- Configuration ------------------------- #
DEFAULT_CONF = {
    "interval_sec": 30,  # Sampling interval
    "dns": {
        "targets": ["www.google.com", "www.cloudflare.com"],
        "server": None,  # None=system default / or specify "8.8.8.8"
        "timeout": 3,
    },
    "icmp": {"targets": ["1.1.1.1", "8.8.8.8"], "count": 4, "timeout": 2},
    "http": {"targets": ["https://www.google.com/generate_204"], "timeout": 5},
    "speedtest": {
        "enabled": True,
        "interval_runs": 60,
    },  # Run speed test every n cycles
    "wifi": {"enabled": True, "interface": "wlan0"},
    "prometheus": {"port": 9105},
    "log_dir": "./logs",  # Log directory
    "log_level": "INFO",
}


def load_config(path="config.yaml") -> Dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            user_conf = yaml.safe_load(f)
    else:
        user_conf = {}
    conf = DEFAULT_CONF.copy()
    for k, v in user_conf.items():
        if isinstance(v, dict):
            conf[k].update(v)
        else:
            conf[k] = v
    return conf


CONF = load_config()

# ------------------------- Logging ------------------------- #
os.makedirs(CONF["log_dir"], exist_ok=True)
log_path = os.path.join(CONF["log_dir"], "netmon.log")

handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(fmt)
logger = logging.getLogger("netmon")
logger.setLevel(CONF["log_level"])
logger.addHandler(handler)

# ------------------------- Prometheus Metrics ------------------------- #
DNS_LATENCY = Summary("dns_lookup_seconds", "DNS resolution time", ["domain"])
DNS_FAILS = Counter("dns_lookup_fail_total", "DNS resolution failure count", ["domain"])

PING_LATENCY = Summary("icmp_ping_seconds", "ICMP round-trip time", ["target"])
PING_LOSS = Gauge("icmp_ping_loss_ratio", "ICMP packet loss rate", ["target"])

HTTP_LATENCY = Summary("http_latency_seconds", "HTTP response time", ["url"])
HTTP_FAILS = Counter("http_fail_total", "HTTP failure count", ["url"])
HTTP_STATUS = Gauge("http_status_code", "HTTP status code", ["url"])

SPEED_DOWN = Gauge("speedtest_download_mbps", "Download bandwidth (Mbps)")
SPEED_UP = Gauge("speedtest_upload_mbps", "Upload bandwidth (Mbps)")
SPEED_PING = Gauge("speedtest_ping_ms", "Speed test server ping (ms)")

WIFI_SIGNAL = Gauge("wifi_signal_dbm", "Wi‑Fi signal strength (dBm)")
WIFI_TX = Gauge("wifi_tx_rate_mbps", "Wi‑Fi transmission rate (Mbps)")
WIFI_RX = Gauge("wifi_rx_rate_mbps", "Wi‑Fi reception rate (Mbps)")

NET_SENT = Gauge("sys_net_sent_bytes", "System sent bytes")
NET_RECV = Gauge("sys_net_recv_bytes", "System received bytes")


# ------------------------- Monitoring Tasks ------------------------- #
async def check_dns():
    resolver = dns.resolver.Resolver()
    if CONF["dns"]["server"]:
        resolver.nameservers = [CONF["dns"]["server"]]
    for domain in CONF["dns"]["targets"]:
        start = time.time()
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                resolver.resolve,
                domain,
                "A",
                dns.rdatatype.A,
                CONF["dns"]["timeout"],
            )
            dt = time.time() - start
            DNS_LATENCY.labels(domain).observe(dt)
            logger.info(f"DNS {domain} OK {dt:.3f}s")
        except Exception as e:
            DNS_FAILS.labels(domain).inc()
            logger.warning(f"DNS {domain} FAIL {e}")


async def check_ping():
    for target in CONF["icmp"]["targets"]:
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                ping,
                target,
                CONF["icmp"]["count"],
                CONF["icmp"]["timeout"],
                True,  # verbose False
            )
            loss = resp.packet_loss
            avg = resp.rtt_avg_ms / 1000  # convert to seconds
            PING_LATENCY.labels(target).observe(avg)
            PING_LOSS.labels(target).set(loss)
            logger.info(f"PING {target} loss={loss:.2%} avg={avg:.3f}s")
        except Exception as e:
            logger.warning(f"PING {target} FAIL {e}")


async def check_http():
    for url in CONF["http"]["targets"]:
        start = time.time()
        try:
            r = requests.get(url, timeout=CONF["http"]["timeout"])
            dt = time.time() - start
            HTTP_LATENCY.labels(url).observe(dt)
            HTTP_STATUS.labels(url).set(r.status_code)
            logger.info(f"HTTP {url} {r.status_code} {dt:.3f}s")
        except Exception as e:
            HTTP_FAILS.labels(url).inc()
            logger.warning(f"HTTP {url} FAIL {e}")


async def check_speedtest(counter: int):
    """
    Run speedtest every interval_runs cycles
    """
    if not CONF["speedtest"]["enabled"]:
        return
    if counter % CONF["speedtest"]["interval_runs"] != 0:
        return
    try:
        import json
        import shutil
        import subprocess
        import tempfile

        # Ookla official CLI recommends using --accept-license
        result = subprocess.check_output(
            ["speedtest-cli", "--json"], text=True, timeout=120
        )
        data = json.loads(result)
        SPEED_DOWN.set(round(data["download"] / 1e6, 2))
        SPEED_UP.set(round(data["upload"] / 1e6, 2))
        SPEED_PING.set(round(data["ping"], 2))
        logger.info(
            f"SPEEDTEST ↓{SPEED_DOWN._value.get()}Mb/s ↑{SPEED_UP._value.get()}Mb/s ping={SPEED_PING._value.get()}ms"
        )
    except Exception as e:
        logger.warning(f"SPEEDTEST FAIL {e}")


async def check_wifi():
    if not CONF["wifi"]["enabled"]:
        return
    iface = CONF["wifi"]["interface"]
    # Read iw output
    try:
        import re
        import subprocess

        out = subprocess.check_output(["iw", "dev", iface, "link"], text=True)
        rssi = int(re.search(r"signal:\s*(-\d+)", out).group(1))
        tx = float(re.search(r"tx bitrate:\s*([\d\.]+)", out).group(1))
        rx = float(re.search(r"rx bitrate:\s*([\d\.]+)", out).group(1))

        WIFI_SIGNAL.set(rssi)
        WIFI_TX.set(tx)
        WIFI_RX.set(rx)
        logger.info(f"WIFI {iface} RSSI={rssi}dBm tx={tx}Mb/s rx={rx}Mb/s")
    except Exception as e:
        logger.debug(f"WIFI INFO FAIL {e}")


def check_sys_net():
    # psutil counters
    io = psutil.net_io_counters()
    NET_SENT.set(io.bytes_sent)
    NET_RECV.set(io.bytes_recv)


# ------------------------- Main Loop ------------------------- #
async def main():
    start_http_server(CONF["prometheus"]["port"])
    logger.info(f"Prometheus metrics on :{CONF['prometheus']['port']}/metrics")
    counter = 0
    while True:
        await asyncio.gather(
            check_dns(),
            check_ping(),
            check_http(),
            check_wifi(),
        )
        await check_speedtest(counter)
        check_sys_net()
        counter += 1
        await asyncio.sleep(CONF["interval_sec"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
