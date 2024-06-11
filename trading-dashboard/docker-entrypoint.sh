#!/bin/bash

# Debug logging
echo "Starting entrypoint script..."
echo "REACT_API_URL is set to: ${REACT_API_URL}"

# Check if REACT_API_URL is set
if [ -z "${REACT_API_URL}" ]; then
  echo "Error: REACT_API_URL environment variable is not set."
  exit 1
fi

# Check if the file exists
if [ ! -f "src/axiosInstance.js" ]; then
  echo "Error: src/axiosInstance.js file not found."
  exit 1
fi

# Replace the variable in the file
sed -i "s|\$REACT_API_URL|${REACT_API_URL}|g" src/axiosInstance.js

# Check the sed command success
if [ $? -ne 0 ]; then
  echo "Error: sed command failed."
  exit 1
fi

# Start nginx
echo "Starting nginx..."
nginx -g "daemon off;"

# Check the nginx command success
if [ $? -ne 0 ]; then
  echo "Error: nginx failed to start."
  exit 1
fi

# Keep the script running to avoid container restart
tail -f /dev/null
