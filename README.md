# 🏙️ CityFix: Urban Infrastructure Management Platform

![Python](https://img.shields.io/badge/python-3.10-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.3.3-green.svg)
![MongoDB](https://img.shields.io/badge/mongodb-5.0-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**CityFix** is an enterprise-grade application that streamlines the reporting, tracking, and resolution of urban infrastructure issues. The platform creates a centralized ecosystem where citizens, maintenance personnel, and administrators collaborate efficiently to improve urban environments.

---

## 🚀 Key Features

### 👤 For Citizens
- 🔍 **Prioritized Issue Reporting**: Submit reports with customizable priority and severity levels
- 🗺️ **Geographic Precision**: Pin-point issue locations with interactive map integration
- 📸 **Visual Documentation**: Attach images to provide visual context for faster resolution
- 📊 **Progress Tracking**: Real-time status updates on submitted reports
- ⭐ **Quality Assurance**: Rate completed maintenance work to ensure accountability

### 🛠️ For Maintenance Staff
- 📋 **Task Management**: Organized dashboard of assigned issues
- 📷 **Documentation System**: Before/after photo uploads to verify completed work
- 🚨 **Problem Escalation**: Structured system to report complications with assignments
- 📱 **Mobile Compatibility**: Access reports and update statuses from any device

### 👨‍💼 For Administrators
- 📈 **Comprehensive Oversight**: Monitor all system activities from a centralized dashboard
- 📊 **Resource Allocation**: Assign tasks based on priority, location, and staff availability
- ✅ **Quality Control**: Review completed work before final approval
- 📉 **Analytics**: Generate insights on performance, resolution times, and issue patterns

---

## 🛠️ Technology Stack

### 🖥️ Backend
- 🐍 **Framework**: Python Flask 2.3.3
- 🗄️ **Database**: MongoDB 5.0
- 🔐 **Authentication**: Session-based with bcrypt password hashing
- 📧 **Email Service**: SMTP integration with HTML email templates

### 🎨 Frontend
- 🖌️ **UI Framework**: Bootstrap with custom responsive design
- ⚡ **Interactivity**: JavaScript with AJAX for asynchronous updates
- 🗺️ **Mapping**: Leaflet.js for interactive location selection

### ⚙️ DevOps
- 🐳 **Containerization**: Docker with multi-stage builds
- 🔄 **CI/CD**: Jenkins pipeline with automated testing
- 🧪 **Testing**: pytest with 80% code coverage
- 🚀 **Deployment**: Docker Compose for production and development environments

---

## 📋 Prerequisites

- 🐍 Python 3.10 or higher
- 🗃️ MongoDB 5.0 or higher
- 📨 SMTP server access for email notifications
- 🐳 Docker and Docker Compose (optional)

---

## 🔧 Installation

### 💻 Local Development Setup

#### 🪟 Windows

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If needed, set execution policy to run activation script
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

#### 🍎 macOS/Linux

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

### 🐳 Docker Deployment

```bash
# Build and start containers
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

---

## ⚙️ Configuration

Create a `.env` file in the root directory with the following variables:

```ini
# MongoDB credentials
raw_username = "your_mongodb_username"
raw_password = "your_mongodb_password"

# SMTP configuration
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=notifications@yourdomain.com
SMTP_PASSWORD=your_secure_password
MAIL_DEFAULT_SENDER=notifications@yourdomain.com
MAIL_DEFAULT_SENDER_NAME="City Fix Notifications"
```

---

## 🧪 Testing

The application includes comprehensive unit and integration testing with over 80% code coverage.

### 🖥️ Running Tests Locally

```bash
# Run all tests
python -m pytest

# Run tests with coverage report
python -m pytest --cov=. --cov-report=term --cov-report=html:coverage_report
```

### 🐳 Running Tests with Docker

```bash
# Run tests in Docker
./run_tests.sh docker

# Run tests with coverage in Docker
./run_tests.sh docker coverage
```

---

## 📁 Project Structure

```
cityfix/
├── 🔐 auth/               # Authentication modules
│   └── main.py            # Authentication logic
├── 🏛️ main/               # Core application modules
│   ├── main.py            # Main application routes
│   └── user_roles.py      # User role management
├── 📝 reports/            # Issue reporting modules
│   ├── reports.py         # Report management
│   ├── done_reports.py    # Completed reports
│   └── email_utils.py     # Email notification system
├── 🎨 static/             # Static assets
│   ├── css/               # Stylesheets
│   ├── js/                # JavaScript files
│   └── templates/         # HTML templates
├── 🧪 tests/              # Test suite
├── 🔧 .env                # Environment variables (create this)
├── ⚙️ config.py           # Configuration settings
├── 🐳 Dockerfile          # Docker configuration
├── 🐳 docker-compose.yml  # Docker Compose configuration
├── 📦 requirements.txt    # Python dependencies
└── 🚀 run.py              # Application entry point
```

---

## 🤝 Contributing

We welcome contributions to improve CityFix:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch: `git checkout -b feature/new-feature`
3. 💾 Make your changes and commit: `git commit -am 'Add new feature'`
4. 📤 Push to the branch: `git push origin feature/new-feature`
5. 📩 Submit a pull request

Please ensure your code passes all tests and follows our coding standards.

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🏢 About

**CityFix** was developed by **BS-PM-2025-TEAM25** as part of an initiative to modernize urban infrastructure management systems.

---

© 2025 BS-PM-2025-TEAM25. All Rights Reserved.