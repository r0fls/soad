#!/bin/bash
sed -i "s|\$REACT_API_URL|${REACT_API_URL}|g" src/axiosInstance.js 
nginx -g "daemon off;"
