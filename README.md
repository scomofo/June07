# BRIDeal Application

BRIDeal is a comprehensive desktop application designed to streamline sales and operational workflows. It provides tools for managing deals, customer interactions, quotes (with John Deere API integration), inventory, and related business data.

## Key Features

*   **Dashboard:** Provides a home screen overview.
*   **Deal Management:** Create, view, and manage sales deals.
*   **John Deere Integration:**
    *   Retrieve and manage John Deere quotes.
    *   John Deere API authentication.
*   **Inventory Management:** Track used inventory and manage receiving processes.
*   **Price Book:** Access and manage product pricing information.
*   **Data Editors:** Built-in CSV editors for managing:
    *   Customers
    *   Parts
    *   Products
    *   Salesmen
*   **Invoice Module:** Generate and manage invoices.
*   **Application Settings:** Configure application preferences, including themes.
*   **Async Operations:** Utilizes asynchronous programming for improved performance and responsiveness.
*   **Comprehensive Logging & Error Handling:** Robust logging for diagnostics and user-friendly error reporting.

## Technical Stack

*   **Programming Language:** Python (3.8+)
*   **Graphical User Interface (GUI):** PyQt6
*   **Key Libraries & Frameworks:**
    *   `asyncio` for asynchronous programming
    *   `requests` & `httpx` for HTTP requests
    *   `aiohttp` for asynchronous HTTP requests
    *   `pandas` for data manipulation (especially with CSVs)
    *   `openpyxl` for Excel file interactions (likely for SharePoint)
    *   `msal` (Microsoft Authentication Library) for authentication with Microsoft services (e.g., SharePoint)
    *   `python-dotenv` for environment variable management
    *   `cryptography` for security-related operations
    *   `ReportLab` for PDF generation (likely for invoices/reports)
    *   `PyQtWebEngine` (though `requirements.txt` might list the PyQt5 version, PyQt6's equivalent is `QtWebEngineWidgets` if used directly, or often bundled)
    *   `pyperclip` for clipboard operations
    *   `pyautogui` for GUI automation tasks (potentially for integrations or testing)

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create and Activate a Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**

    The primary GUI framework used in this application is **PyQt6**. However, the `requirements.txt` file currently lists `PyQt5`.

    **Important:** You should install PyQt6. It's recommended to either:
    *   Manually install PyQt6: `pip install PyQt6 PyQt6-sip PyQt6-Qt6Designer` (and other PyQt6 specific tools if needed, like `pyqt6-tools`)
    *   Or, modify `requirements.txt` to replace `PyQt5` and `PyQtWebEngine` (for PyQt5) with their PyQt6 equivalents before running `pip install -r requirements.txt`. A direct replacement for `PyQtWebEngine` in `pip` for PyQt6 is less common as it's often included or handled differently; ensure `PyQt6` itself is installed. `QtWebEngineWidgets` is the module.

    After addressing the PyQt6 requirement, install other dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    If you didn't modify `requirements.txt` for PyQt6, ensure you install it separately as mentioned above.

4.  **Configure Environment Variables:**
    *   This application uses a `.env` file for environment-specific configurations (e.g., API keys, paths, secrets).
    *   Create a `.env` file in the root of the project.
    *   You may need to get necessary API keys or configuration details from your administrator or development team.
    *   A `config.json` file might also be used for less sensitive configurations. Check `app/core/config.py` for details on what configurations are expected.
    *   Example structure for `.env` (actual variables may differ):
        ```env
        BRIDEAL_LOG_LEVEL=INFO
        SHAREPOINT_SITE_URL=your_sharepoint_site_url
        JD_API_CLIENT_ID=your_jd_client_id
        # ... other necessary configurations
        ```

5.  **Resource Files:**
    *   Ensure that the `resources/` directory and its contents (icons, themes) are present.
    *   The `data/` directory might need to be populated with initial CSV files or will be created/managed by the application.

## Running the Application

Once the setup is complete:

1.  **Ensure your virtual environment is activated.**
2.  **Navigate to the project's root directory.**
3.  **Run the application using the main script:**
    ```bash
    python run_brideal.py
    ```

### Diagnostic Mode

The application includes a diagnostic script that can help check for common issues:
```bash
python run_brideal.py --diagnostics
```
This will print information about your Python version, project root, dependency status, file structure, and configuration files.

## Project Structure

A brief overview of the main directories and files:

```
.
├── app/                  # Core application module
│   ├── main.py           # Main application window and logic (PyQt6 based)
│   ├── core/             # Core components (config, logging, services, etc.)
│   ├── models/           # Data models and database interactions
│   ├── services/         # Business logic, API clients, integrations
│   ├── utils/            # Utility functions and handlers
│   ├── views/            # UI components (windows, dialogs, modules, widgets)
│   └── static/           # Static assets like CSS for theming
├── data/                 # Default location for CSV data files, JSON caches, etc.
├── resources/            # Icons, themes, images, and other static resources
│   ├── icons/
│   ├── themes/
│   └── images/
├── tests/                # Unit and integration tests (structure mirrors `app/`)
├── .env                  # Environment variables (needs to be created locally)
├── config.json           # General application configuration
├── jd_quote_config.json  # Configuration specific to John Deere quotes
├── requirements.txt      # Python package dependencies
├── run_brideal.py        # Main executable script to launch the application
└── README.md             # This file
```

## Running Tests

The application includes tests located in the `app/tests/` directory (older tests might be in `tests/`).

Further instructions on how to run these tests (e.g., specific commands or test runners to use) should be added here. If you are familiar with Python testing frameworks, you might be able to run them using standard tools like `pytest` or `unittest`:

```bash
# Example using pytest (if applicable)
# pip install pytest
# pytest
```

```bash
# Example using unittest (if applicable)
# python -m unittest discover -s app/tests
```

## Contributing

Contributions to the BRIDeal application are welcome. If you'd like to contribute, please consider the following:

*   **Reporting Issues:** Use the issue tracker to report bugs or suggest features.
*   **Code Contributions:**
    1.  Fork the repository.
    2.  Create a new branch for your feature or bug fix.
    3.  Make your changes, adhering to the existing code style.
    4.  Add or update tests as appropriate.
    5.  Submit a pull request for review.

(More detailed contribution guidelines can be added here if the project grows.)

## License

A `LICENSE` file detailing the terms of use for this software should be included in the root of the project. If one is not present, please consult with the project maintainers regarding licensing information.

(Consider adding a standard open-source license like MIT, Apache 2.0, or GPLv3 if applicable.)
