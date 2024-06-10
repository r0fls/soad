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

# Expose port 3000
EXPOSE 3000

# Serve the app
CMD ["yarn", "start"]
