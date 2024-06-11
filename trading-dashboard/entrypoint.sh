#!/bin/sh

# Check if REACT_API_URL is set
if [ -z "${REACT_API_URL}" ]; then
  echo "Error: REACT_API_URL environment variable is not set."
  exit 1
fi

# Replace placeholders in JavaScript files
for file in /usr/share/nginx/html/static/js/*.js; do
  sed -i "s|\$REACT_API_URL|${REACT_API_URL}|g" "$file"
done

# Replace placeholders in the HTML file
sed -i "s|\$REACT_API_URL|${REACT_API_URL}|g" /usr/share/nginx/html/index.html

# Start nginx
nginx -g "daemon off;"
