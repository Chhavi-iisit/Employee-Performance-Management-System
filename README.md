\# Employee Performance Management System



A role-based web application for managing employee performance appraisals, document verification, appeals, and administrative workflows.



\## Overview



The Employee Performance Management System provides separate workflows for employees, managers, and administrators. It helps manage employee documents and performance appraisals while maintaining records of reviews, appeals, and system activities.



\## Features



\- Role-based employee, manager, and administrator workflows

\- User registration and login

\- Employee document submission

\- Document verification and rejection

\- Document resubmission workflow

\- Employee performance appraisal management

\- Manager review and comments

\- Employee appeal workflow

\- Escalation workflow for appraisal-related issues

\- Notifications

\- Audit log for tracking system activities

\- MySQL database integration

\- Flask-based web application



\## Technology Stack



\- \*\*Backend:\*\* Python, Flask

\- \*\*Database:\*\* MySQL

\- \*\*Frontend:\*\* HTML, CSS

\- \*\*Database Connector:\*\* MySQL Connector/Python

\- \*\*Authentication:\*\* Flask sessions

\- \*\*Version Control:\*\* Git, GitHub



\## Project Structure



```text

Employee-Performance-Management-System/

│

├── app.py

├── main.py

├── requirements.txt

├── .gitignore

│

├── static/

│   └── css/

│       ├── app.css

│       └── dashboard.css

│

└── templates/

&#x20;   ├── login.html

&#x20;   ├── register.html

&#x20;   ├── dashboard.html

&#x20;   ├── manager\_dashboard.html

&#x20;   └── admin\_dashboard.html

