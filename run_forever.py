import subprocess

# Auto restart when script gets killed

while True:
    try:
        subprocess.run(["python3.9", "-m", "on9wordchainbot"])
    except KeyboardInterrupt:
        break
