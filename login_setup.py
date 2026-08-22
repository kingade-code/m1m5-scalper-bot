"""Login setup helper for Kingade Scalper Bot.
Prompts for MT5 credentials on first run and saves to config.py.
"""
import os
import config

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")


def setup_login():
    """Prompt for MT5 login if not configured. Returns True if credentials set."""
    if config.MT5_LOGIN and config.MT5_PASSWORD and config.MT5_SERVER:
        return True

    print("\n" + "=" * 60)
    print("  MT5 LOGIN SETUP")
    print("=" * 60)
    print("No credentials found in config.py.")
    print("Enter your MT5 login details below:")
    print("(Press Enter to skip and use default terminal)\n")

    login = input("  Login (account number): ").strip()
    password = input("  Password: ").strip()
    server = input("  Server (e.g., Exness-MT5Trial9): ").strip()

    if login and password and server:
        config.MT5_LOGIN = int(login)
        config.MT5_PASSWORD = password
        config.MT5_SERVER = server

        # Save to config.py for next time
        try:
            with open(CONFIG_PATH, "r") as f:
                lines = f.readlines()

            new_lines = []
            for line in lines:
                if line.startswith("MT5_LOGIN = None"):
                    new_lines.append(f"MT5_LOGIN = {login}\n")
                elif line.startswith("MT5_PASSWORD = None"):
                    new_lines.append(f"MT5_PASSWORD = \"{password}\"\n")
                elif line.startswith("MT5_SERVER = None"):
                    new_lines.append(f"MT5_SERVER = \"{server}\"\n")
                else:
                    new_lines.append(line)

            with open(CONFIG_PATH, "w") as f:
                f.writelines(new_lines)

            print(f"\n  Credentials saved to config.py!")
            print(f"  Login: {login}")
            print(f"  Server: {server}")
        except Exception as e:
            print(f"\n  Warning: Could not save to config.py: {e}")
            print(f"  Credentials set for this session only.")

        print("=" * 60 + "\n")
        return True
    else:
        print("\n  Skipping — will use default MT5 terminal.\n")
        return False
