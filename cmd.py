import subprocess


def run_command_realtime(command):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr with stdout
        text=True,
        bufsize=1,  # Line-buffered
        universal_newlines=True
    )

    try:
        if process.stdout:
            for line in process.stdout:
                print(line, end='')  # Process line immediately
    finally:
        process.wait()  # Ensure process cleanup


# Example usage
run_command_realtime(['ping', '-c', '4', 'google.com'])
