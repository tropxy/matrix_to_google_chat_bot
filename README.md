# Service Management

The bot is runnig in a Launchctl task
The task definition is defined here:
/Users/andre/Library/LaunchAgents/com.matrix_to_google_chat_hook.plist

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
    <string>/tmp/matrix_to_google_chat_hook_error.log</string>

    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

As eviedent, the task points to the main script that starts the matrix bot, located at:
"/Users/andre/Devel/maubot_matrix/matrix_google_chat_hook/matrix_to_google_chat.py"

It also outputs the logs to a file in: "/tmp/matrix_to_google_chat_hook.log"

## Reload and start the script

`launchctl load ~/Library/LaunchAgents/com.matrix_to_google_chat_hook.plist`

## Stop the script

`launchctl unload ~/Library/LaunchAgents/com.matrix_to_google_chat_hook.plist`

## Check if the script is running

launchctl list | grep com.matrix_to_google_chat_hook

## Check the logs contents

1. log file
   `tail -f /tmp/matrix_to_google_chat_hook.log`

2. Error log file
   `tail -f /tmp/matrix_to_google_chat_hook_error.log`

# Solution for the issue with the installation of the e2e extra for the matrix-nio

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
