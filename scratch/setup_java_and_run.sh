#!/bin/bash
set -e

# Directory where we will extract JDK
JAVA_DIR="$HOME/java"

if [ ! -d "$JAVA_DIR/Contents/Home" ]; then
    echo "Downloading Java OpenJDK 17 for macOS Apple Silicon..."
    curl -L -o openjdk.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse"
    echo "Extracting OpenJDK 17..."
    mkdir -p "$JAVA_DIR"
    tar -xzf openjdk.tar.gz -C "$JAVA_DIR" --strip-components=1
    rm -f openjdk.tar.gz
    echo "Java OpenJDK 17 installed locally."
fi

# Set Java variables
export JAVA_HOME="$JAVA_DIR/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"

echo "Checking local Java version..."
java -version

# Terminate existing Firestore and Auth emulators if running
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
lsof -ti:9099 | xargs kill -9 2>/dev/null || true
lsof -ti:4000 | xargs kill -9 2>/dev/null || true
sleep 1

echo "Starting Firebase Emulators (Firestore & Auth) in background..."
npx firebase emulators:start --only firestore,auth > firestore_emulator.log 2>&1 &
EMULATOR_PID=$!
echo "Firestore Emulator started with PID $EMULATOR_PID."

# Wait for Firestore emulator port 8080 to be active
echo "Waiting for Firestore emulator to listen on port 8080..."
for i in {1..30}; do
    if lsof -i :8080 > /dev/null; then
        echo "Firestore Emulator is online on port 8080."
        break
    fi
    sleep 1
done

# Start Flask server with Firestore configuration
export DATABASE_TYPE=firestore
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
export FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
export GOOGLE_CLOUD_PROJECT=focusguard-ai
export GCLOUD_PROJECT=focusguard-ai
export GRPC_ENABLE_FORK_SUPPORT=0

echo "Starting Flask web server on port 5001..."
# Terminate existing Flask server on port 5001
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
sleep 2

source venv/bin/activate
python -u app.py
