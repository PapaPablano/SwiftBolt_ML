#!/bin/bash

# Setup script to ensure correct Supabase configuration for SwiftBolt ML
echo "Setting up Supabase configuration for SwiftBolt ML..."

# Copy the environment file to the correct location if needed
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
fi

# Validate Supabase URL in .env
if grep -q "SUPABASE_URL.*iwwdxshzrxilpzehymeu" .env; then
    echo "Warning: Found incorrect Supabase URL in .env. Updating to correct URL..."
    sed -i '' 's/iwwdxshzrxilpzehymeu/cygflaemtmwiwaviclks/g' .env
fi

echo "Supabase configuration is ready. Make sure to restart the app."