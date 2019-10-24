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

echo "All done ✓, happy printing! "
