# Stage 1: Build the react application
FROM node:16 as build

# Set working directory
WORKDIR /app

# Copy package.json and yarn.lock to leverage Docker cache
COPY package.json yarn.lock ./

# Install dependencies
RUN yarn install

# Copy the rest of the source code
COPY . ./

# Build the application
RUN yarn build

# Stage 2: Serve the react application
FROM node:16

# Install serve globally
RUN npm install -g serve

# Copy built files from the previous stage
COPY --from=build /app/build /app/build

# Copy serve.json
COPY trading-dashboard/serve.json /app/serve.json

# Expose port 3000
EXPOSE 3000

# Serve the app
CMD ["serve", "-s", "build", "-c", "serve.json", "-l", "3000"]
