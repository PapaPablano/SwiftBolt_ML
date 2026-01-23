#!/bin/bash
# Start ngrok and extract the public URL

echo "Starting ngrok tunnel to port 8000..."
ngrok http 8000 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "Waiting for ngrok to start..."
sleep 5

# Try to get URL from API
for i in {1..10}; do
    URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    if tunnels:
        print(tunnels[0]['public_url'])
except:
    pass
" 2>/dev/null)
    
    if [ -n "$URL" ]; then
        echo ""
        echo "✅ ngrok is running!"
        echo "🌐 Public URL: $URL"
        echo ""
        echo "Set this in Supabase with:"
        echo "supabase secrets set FASTAPI_URL=$URL --project-ref cygflaemtmwiwaviclks"
        echo ""
        echo "Press Ctrl+C to stop ngrok"
        wait $NGROK_PID
        exit 0
    fi
    sleep 1
done

echo "❌ Could not get ngrok URL. Check /tmp/ngrok.log"
kill $NGROK_PID 2>/dev/null
exit 1
