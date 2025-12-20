import subprocess
import sys
import time

# Auto restart when script gets killed

while True:
    try:
        subprocess.run([sys.executable, "-m", "on9wordchainbot"])
        time.sleep(0.2)
    except KeyboardInterrupt:
        break
