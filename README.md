## Environmental Variables

The main.py will check the .env file for the following envs

```python
# LOGGER LEVEL
LOG_LEVEL = os.getenv("LOG_LEVEL", logging.INFO)
LOG_FILE = "/tmp/matrix_to_google_chat_hook.log"
# Matrix Home server
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER")
# Matrix User credentials
MATRIX_USER = os.getenv("MATRIX_USER")
MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD")
# Matrix Base URL
MATRIX_BASE_URL = os.getenv("MATRIX_BASE_URL")
# Environmental to force receiving all messages from any channel
MATRIX_GET_ALL_MESSAGES = os.getenv("MATRIX_GET_ALL_MESSAGES", False)
# Chat Room ID that we want specifically to listen to
MATRIX_FILTER_FOR_ROOM_ID = os.getenv("MATRIX_FILTER_FOR_ROOM_ID")
# E2E keys related to the user account and necessary
# for the bot to be trusted
MATRIX_E2E_KEYS_FILE = os.getenv("MATRIX_E2E_KEYS_FILE")
MATRIX_E2E_KEYS_FILE_PASS = os.getenv("MATRIX_E2E_KEYS_FILE_PASS")
# Location of where to save the NoSQL DB to
MATRIX_DB_LOCATION = os.getenv("MATRIX_DB_LOCATION")
# Google Chat webhook URL
GOOGLE_CHAT_WEBHOOK = os.getenv("GOOGLE_CHAT_WEBHOOK")
```

Be sure to have those in the .env file.
For the `MATRIX_E2E_KEYS_FILE` one, the user can get it's E2E keys, by going to the
Matrix UI, click on the user -> Security&Privacy -> Cryptography -> Export E2E room keys.
Add a password to the file and then set the location with that file and its pass using
the respective envs.

## Service Management

I am running the bot in MacOS, so I will be using Launchctl, but any other service
management should do theb job like systemd or some Yocto recipe.

The task definition in my case was created here:
/Users/andre/Library/LaunchAgents/com.matrix_to_google_chat_hook.plist

And these are the contents of the file:

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.matrix_to_google_chat_hook</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/andre/.virtualenvs/maubot_matrix/bin/python3</string>
        <string>/Users/andre/Devel/maubot_matrix/matrix_google_chat_hook/matrix_to_google_chat.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/matrix_to_google_chat_hook.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/matrix_to_google_chat_hook.log</string>

    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

As eviedent, the task points to the main script that starts the matrix bot, located in
case my at:
"/Users/andre/Devel/maubot_matrix/matrix_google_chat_hook/matrix_to_google_chat.py"

My .env file with the Environmental variables is present in the same location as the
script.

Ensure to also specify the path to the python interpreter that will run the script.
In my case it is a virtual env python interpreter.

The service also outputs the logs to a file in: "/tmp/matrix_to_google_chat_hook.log"
In main.py the logging library is configured to send the logs to both the regular stdout
but also to the specified file.

### Reload and start the script

`launchctl load ~/Library/LaunchAgents/com.matrix_to_google_chat_hook.plist`

### Stop the script

`launchctl unload ~/Library/LaunchAgents/com.matrix_to_google_chat_hook.plist`

### Check if the script is running

launchctl list | grep com.matrix_to_google_chat_hook

### Check the logs contents

```shell
> tail -f /tmp/matrix_to_google_chat_hook.log
2024-12-18 11:11:25,027 - INFO - Bot Logged into Matrix
2024-12-18 11:11:30,542 - INFO - Starting sync...
2024-12-18 11:11:31,269 - INFO - Initial sync completed. Listening for new messages...
```

## Solution for the issue with the installation of the e2e extra for the matrix-nio

Link to chatgpt: https://chatgpt.com/share/676189da-d1d4-8004-81bb-a49d427624b3

Solution: Use a Fixed Version of python-olm or Apply the Patch
We need to manually patch the source code before installation.

1. Download the Source Code of python-olm
   Manually download the python-olm 3.2.16 tarball and extract it:

```
wget https://pypi.org/packages/source/p/python-olm/python-olm-3.2.16.tar.gz
tar -xzvf python-olm-3.2.16.tar.gz
cd python-olm-3.2.16
```

2. Patch the Bug in list.hh
   Edit the libolm source code to fix the bug:

Open the file:

`nano libolm/include/olm/list.hh`
Find and Replace the problematic line.

Locate line 102:

`T * const other_pos = other._data;`
Replace it with:

`T *other_pos = other._data;` 3. Rebuild and Install Locally
Once the bug is patched, build and install python-olm using the local setup:

```
CFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib" python setup.py build
CFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib" python setup.py install
```

4. Verify the Installation
   Confirm that python-olm is installed:

`python -c "import olm; print(olm.__version__)"`
It should now display 3.2.16.
