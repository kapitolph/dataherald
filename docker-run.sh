#!/bin/bash

# Function to bring up services
start_services() {
    # Create Docker network
    docker network create dataherald_network

    # Bring up services with Docker Compose
    docker-compose -p dataherald -f services/engine/docker-compose.yml up --build -d
    docker-compose -p dataherald -f services/enterprise/docker-compose.yml up --build -d
    docker-compose -p dataherald -f services/slackbot/docker-compose.yml up --build -d
    docker-compose -p dataherald -f services/admin-console/docker-compose.yml up --build -d
    docker-compose -p dataherald -f services/streamlit/docker-compose.yml up --build -d
}

# Function to take down services
stop_services() {
    # Take down services with Docker Compose
    docker-compose -p dataherald -f services/admin-console/docker-compose.yml down
    docker-compose -p dataherald -f services/slackbot/docker-compose.yml down
    docker-compose -p dataherald -f services/enterprise/docker-compose.yml down
    docker-compose -p dataherald -f services/engine/docker-compose.yml down
    docker-compose -p dataherald -f services/streamlit/docker-compose.yml down

    # Remove Docker network
    docker network rm dataherald_network
}

# Check command-line argument
if [ "$1" = "up" ]; then
    start_services
elif [ "$1" = "down" ]; then
    stop_services
else
    echo "Usage: $0 [up|down]"
    exit 1
fi
