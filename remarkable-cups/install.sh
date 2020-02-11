#! /usr/bin/env bash

# Set bash to stop execution on failed commands. For sanity and safety
set -e

echo "Adding Unofficial remarkable printing driver"

# Compile ppd driver & copy to somewhere where CUPS can find it.
ppdc remarkable.drv; sudo cp ppd/remarkable.ppd /usr/share/cups/model/

# Copy & rename CUPS backend script
sudo cp remarkable.sh /usr/lib/cups/backend/remarkable

# Secure permissions
sudo chown root:root /usr/lib/cups/backend/remarkable
sudo chmod 700 /usr/lib/cups/backend/remarkable

# Add/Update "Remarkable" cups printer
sudo lpadmin -L 'Cloud Printer' -D 'my remarkable' -p "reMarkable" -E -v 'remarkable:/Print'

# Copy user credentials for printer driver user home
FILE=~/.rmapi
if [ -f "$FILE" ]; then
    echo "Installing credentials for cups user (root in debian)"
    sudo cp $FILE /root/
else
    echo "$FILE does not exist, please authenticate with .rmapi file"
fi

echo "Do you want to print a test page?"
read -p 'test page? (y/N): ' tp

if [ "$tp" = "y" ]; then
    cowsay "Howdy there! Hopefully this printer works! Cheers to RMS!" |pandoc -o /tmp/test.pdf
    lp -d reMarkable /tmp/test.pdf
fi

echo "All done ✓, happy printing! "
