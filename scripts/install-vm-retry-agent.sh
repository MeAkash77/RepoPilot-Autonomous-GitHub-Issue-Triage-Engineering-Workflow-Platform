#!/usr/bin/env bash
# Installs a user-level LaunchAgent that retries Oracle VM creation every 2 minutes.
# Auto-removes itself when VM is successfully created.
set -e

AGENT_LABEL="dev.repopilot.vm-retry"
PLIST="$HOME/Library/LaunchAgents/${AGENT_LABEL}.plist"
SCRIPT="$HOME/Library/LaunchAgents/repopilot-vm-retry.sh"
LOG="/tmp/repopilot-vm-retry.log"

# Write the retry script
cat > "$SCRIPT" << 'RETRY_SCRIPT'
#!/usr/bin/env bash
LOG="/tmp/repopilot-vm-retry.log"
AGENT_LABEL="dev.repopilot.vm-retry"
PLIST="$HOME/Library/LaunchAgents/${AGENT_LABEL}.plist"

echo "$(date '+%Y-%m-%d %H:%M:%S') — attempting Oracle VM creation..." >> "$LOG"

RESULT=$(/opt/homebrew/bin/oci compute instance launch \
  --compartment-id ocid1.tenancy.oc1..aaaaaaaakor3hcgn6zxjhahmnag3zsxroqjpfs7nyq2frvuzhooyc4vevt5q \
  --availability-domain "AD-1" \
  --shape "VM.Standard.A1.Flex" \
  --shape-config '{"ocpus": 2, "memoryInGBs": 12}' \
  --image-id "ocid1.image.oc1.ap-mumbai-1.aaaaaaaa2op2x2s5rnduo5osx6zojr526qxtrvhddkdhks5nllbwjzcylwya" \
  --subnet-id "ocid1.subnet.oc1.ap-mumbai-1.aaaaaaaawsrjvnyil4gltj3bkss5jhywz3nrele4jtpnjh3dphrwciomz4oq" \
  --assign-public-ip true \
  --display-name "repopilot-api" \
  --ssh-authorized-keys-file "$HOME/.oci/repopilot_oci_key_public.pem" \
  2>&1)

if echo "$RESULT" | grep -q "lifecycle-state"; then
  PUBLIC_IP=$(echo "$RESULT" | /opt/homebrew/bin/python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('public-ip','PROVISIONING'))" 2>/dev/null || echo "PROVISIONING")
  echo "$(date '+%Y-%m-%d %H:%M:%S') — VM CREATED. IP: $PUBLIC_IP" >> "$LOG"
  echo "$PUBLIC_IP" > /tmp/repopilot-api-vm-ip.txt
  # Self-remove
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST" "$0"
  echo "$(date '+%Y-%m-%d %H:%M:%S') — agent uninstalled." >> "$LOG"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') — capacity unavailable." >> "$LOG"
fi
RETRY_SCRIPT

chmod +x "$SCRIPT"

# Write the plist (runs every 120 seconds)
cat > "$PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>dev.repopilot.vm-retry</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${SCRIPT}</string>
  </array>
  <key>StartInterval</key>
  <integer>120</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG}</string>
  <key>StandardErrorPath</key>
  <string>${LOG}</string>
</dict>
</plist>
PLIST_EOF

# Load it
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "LaunchAgent installed. Retries every 2 minutes."
echo "Safe to close lid — runs on every wake."
echo ""
echo "Monitor: tail -f /tmp/repopilot-vm-retry.log"
echo "Uninstall manually: launchctl unload $PLIST && rm $PLIST"
