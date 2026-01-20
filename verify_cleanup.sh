#!/bin/bash
# Check for "firebase" strings (case insensitive) in the app directory, creating the file if it doesn't exist
# We exclude the .antigravityignore file itself if it matches, and .git directories
# This is a verification script for the user

echo "Searching for 'firebase' in app directory..."
if grep -rni "firebase" E:/DH2OCOL/python/sst-app/sst-backend/app; then
    echo "WARNING: Potential Firebase references found!"
else
    echo "SUCCESS: No 'firebase' references found in app directory."
fi
