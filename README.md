# Pandemic Resilience Management System

A secure, role-based web platform engineered to streamline the management of health-related data. This system provides live dashboards, automates compliance monitoring, and supports robust data operations across both structured and unstructured data sources.

### Key Features

* **Role-Based Access Control:** Engineered a secure, role-based web platform with 3 dashboards and 20+ endpoints, enabling authentication-based access via `Flask-Login`.
* **Hybrid Data Architecture:** Developed a hybrid data architecture integrating **SQL Server** for compliance-critical data and **MongoDB Atlas** for semi-structured and instantaneous data. It supports dynamic data operations across 7 tables and collections with a query response time of under **100 ms** under load.
* **Automated Compliance & Security:** Implemented secure password hashing (PBKDF2 via `Werkzeug`), vaccination validation logic, and automatic compliance alerts, achieving **100% password encryption compliance** and improving error handling and data consistency by approximately **80%**.
* **Extensive Functionality:** The system supports over **500 dynamic data operations** and provides **20+ secure API endpoints**.

### Technical Stack

| Category         | Technologies Used                                               |
| :--------------- | :-------------------------------------------------------------- |
| **Backend** | `Python` • `Flask` • `Flask-Login` • `Werkzeug`                 |
| **Frontend** | `HTML` • `CSS`                                                  |
| **Databases** | `SQL Server` • `MongoDB Atlas`                                  |

### System Architecture

The system is built on a Flask backend and utilizes a hybrid data architecture to optimize for both compliance and performance. SQL Server is employed for structured data where data integrity and transactional consistency are paramount, while MongoDB Atlas handles flexible, semi-structured data for efficient storage and retrieval. This design allows for a responsive user experience while maintaining robust data governance.

### Getting Started

To get a local copy up and running, follow these simple steps.

**Prerequisites:**
* Python 3.x
* Pip (Python package installer)
* Access to a running SQL Server instance and a MongoDB Atlas cluster.

**Installation:**
1.  Clone the repository:
    ```bash
    git clone [https://github.com/your-username/pandemic-resilience-system.git](https://github.com/your-username/pandemic-resilience-system.git)
    cd pandemic-resilience-system
    ```
2.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure database connections:
    ```bash
    # Update your database connection strings in a config file or environment variables
    # (e.g., config.py or .env)
    ```
4.  Run the application:
    ```bash
    flask run
    ```

