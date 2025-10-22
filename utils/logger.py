# utils/logger.py

import sys
import os
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)


class Logger:
    def __init__(self, name: str = "Bot"):
        self.name = name
        self.log_dir = "logs"

        os.makedirs(self.log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = os.path.join(self.log_dir, f"{timestamp}.log")

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"=== Log started at {datetime.now()} ===\n")

    def _write_to_file(self, text: str):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def _log(self, level: str, color: str, *message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg_text = " ".join(str(m) for m in message)
        colored_output = f"{color}[{timestamp}] [{self.name}] [{level.upper()}]{Style.RESET_ALL} {msg_text}"
        plain_output = f"[{timestamp}] [{self.name}] [{level.upper()}] {msg_text}"

        print(colored_output, file=sys.stdout)

        self._write_to_file(plain_output)

    def info(self, *message):
        self._log("INFO", Fore.CYAN, *message)

    def success(self, *message):
        self._log("SUCCESS", Fore.GREEN, *message)

    def warning(self, *message):
        self._log("WARNING", Fore.YELLOW, *message)

    def error(self, *message):
        self._log("ERROR", Fore.RED, *message)

    def debug(self, *message):
        self._log("DEBUG", Fore.MAGENTA, *message)
