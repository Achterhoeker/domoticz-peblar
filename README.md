# Domoticz Peblar Plugin

This is a Domoticz plugin for Peblar devices, allowing you to integrate and manage your Peblar devices within the Domoticz home automation system.

## Installation Instructions

Follow these steps to install the Peblar plugin in your Domoticz setup:

### Prerequisites

1. **Domoticz**: Ensure that you have Domoticz installed on your device. You can find the installation instructions [here](https://www.domoticz.com/).

2. **Python**: The plugin requires Python 3.x. Make sure Python is installed and accessible on your system.

### Steps to Install the Plugin

1. **Clone the Repository Directly into the Plugins Directory**:
   - Open a terminal and navigate to the Domoticz plugins directory. Replace `/path/to/domoticz/plugins/` with your actual path:

     ```bash
     cd /path/to/domoticz/plugins/
     ```

   - Run the following command to clone the repository directly into the plugins directory:

     ```bash
     git clone https://github.com/Achterhoeker/domoticz-peblar.git peblar
     ```

2. **Restart Domoticz**:
   - Restart the Domoticz service to load the new plugin. You can do this with the following command (the command may vary based on your setup):

     ```bash
     sudo systemctl restart domoticz
     ```

3. **Configure the Plugin**:
   - After restarting, go to the Domoticz web interface.
   - In Domoticz -> Hardware select the Wallbox plugin.

### Connecting to the Peblar REST API

Once you have successfully connected to the Peblar REST API, multiple devices will be created automatically within Domoticz. 

To connect to the API, you need to generate an API key. Follow these steps:

1. **Generate an API Key**:
   - Visit the [Peblar Developer API documentation](https://developer.peblar.com/local-rest-api) for instructions on generating an API key.
   - Ensure that you have **write access** enabled, as this is required for load balancing.

### Load Balancing Configuration

For proper load balancing, you will need to provide the following information during the configuration:

- **IDX of the Main Meter (P1 Meter)**: This is the identifier for your main meter in Domoticz.
- **Maximum Current in Amperes**: Specify the maximum current of your home connection in amperes.

### Updating the Plugin

To update the Peblar plugin to the latest version, follow these steps:

1. **Navigate to the Plugin Directory**:
   - Open a terminal and go to the directory where the plugin was cloned:

     ```bash
     cd /path/to/domoticz/plugins/peblar
     ```

2. **Pull the Latest Changes**:
   - Run the following command to fetch and merge the latest changes from the repository:

     ```bash
     git pull origin main
     ```

   - Replace `main` with the appropriate branch name if necessary.

3. **Restart Domoticz**:
   - After updating, restart the Domoticz service:

     ```bash
     sudo systemctl restart domoticz
     ```

### Troubleshooting

If you encounter issues during installation or setup, check the following:

- Ensure all dependencies are installed.
- Review the Domoticz log files for any error messages.
- Visit the [Domoticz community forums](https://www.domoticz.com/forum/) for additional support.

### Contribution

If you'd like to contribute to the development of the Peblar plugin, feel free to fork the repository and submit a pull request.

### License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for more details.
