# Step 1: Build the React application
FROM node:16 as build

# Set the working directory
WORKDIR /app

# Copy the package.json and yarn.lock files
COPY package.json yarn.lock ./

# Install the dependencies
RUN yarn install

# Copy the rest of the application code
COPY . ./
COPY .env ./

# Build the application
RUN yarn build

# Step 2: Serve the built application with Nginx
FROM nginx:alpine

# Copy the built files from the previous stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy the custom Nginx configuration
COPY nginx.conf.template /etc/nginx/nginx.conf.template

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port 80
EXPOSE 80

# Use the entrypoint script to start Nginx
ENTRYPOINT ["/entrypoint.sh"]
