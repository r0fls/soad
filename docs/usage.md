# Usage Guide

## Getting Started
To really get started with trading live strategies, you will likely need to deploy the infrastructure to run your strategies. This can be done in a number of ways, but the most common is to use a cloud provider like AWS, GCP, Digital Ocean or Azure. See the [Deploying Infrastructure](deploying-infrastructure.md) section for an example.
## Writing Custom Strategies
To write a custom strategy, you will need to create a new Python file in the `strategies` directory. This file should contain a class that inherits from the `Strategy` class in `strategies/strategy.py`. The class should implement the `run` method, which is called every time the strategy is run. The `run` method should return a list of orders to be executed. See the [Writing Custom Strategies](writing-custom-strategies.md) section for more information.
## Running Strategies
To run a custom strategy, you can build a custom docker image that inherits from the soad base image. This image should contain your custom strategy file and any dependencies that are required. You can then deploy this image to a cloud provider and run it using a container orchestration tool like Kubernetes. See the [Deploying Infrastructure](deploying-infrastructure.md) section for an example.
