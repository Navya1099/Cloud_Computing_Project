# ✈️ Travel Expense Optimizer

A Flask-based web application that helps users find the best travel deals by searching for flights, hotels, and activities, combining them into optimized packages.

**🌐 Live Demo:** [https://travel-expense-optimizer-463884911750.europe-west2.run.app](https://travel-expense-optimizer-463884911750.europe-west2.run.app)

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [File Structure](#file-structure)
6. [Database Schema](#database-schema)
7. [API Integration](#api-integration)
8. [CRUD Operations](#crud-operations)
9. [Deployment](#deployment)
10. [Local Development](#local-development)

---

## 🎯 Project Overview

The Travel Expense Optimizer is a cloud-native application deployed on Google Cloud Platform. It integrates with the Amadeus Travel API to provide real-time travel data and recommendations.

### Key Features

- 🔐 User authentication (register/login/profile management)
- ✈️ Flight search with airline names
- 🏨 Hotel search with per-night pricing
- 🎭 Activity/tour recommendations
- 📦 Best package deals calculation
- 📜 Search history tracking with delete capability
- 📱 Responsive web interface

---

## 🏗️ Architecture

```
+------------------+         +------------------+         +------------------+
|   User Browser   | <-----> |  Google Cloud    | <-----> |   Amadeus API    |
|                  |         |    Cloud Run     |         | (Travel Data)    |
+------------------+         +------------------+         +------------------+
                                     |
                                     v
                    +--------------------------------+
                    |        Google Cloud            |
                    |   +------------------------+   |
                    |   |   Firestore Database   |   |
                    |   |   (User Accounts &     |   |
                    |   |    Search History)     |   |
                    |   +------------------------+   |
                    |                                |
                    |   +------------------------+   |
                    |   |    Secret Manager      |   |
                    |   |   (API Keys & Secrets) |   |
                    |   +------------------------+   |
                    +--------------------------------+
```

### Cloud Services Used

| Service | Purpose |
|---------|---------|
| **Cloud Run** | Serverless container hosting (auto-scales, pay-per-use) |
| **Firestore** | NoSQL database for users and search history |
| **Secret Manager** | Secure storage for API keys and secrets |
| **Cloud Build** | CI/CD pipeline for automated deployments |
| **Container Registry** | Docker image storage |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.11, Flask 3.0
- **Frontend:** HTML5, CSS3, JavaScript
- **Database:** Google Cloud Firestore
- **API:** Amadeus Travel API
- **Deployment:** Docker, Google Cloud Run
- **CI/CD:** Google Cloud Build

---

## 📁 File Structure

```
TravelExpenseOptimizer/
│
├── app.py                  # Main Flask application
├── auth.py                 # Authentication & database functions
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container configuration
├── cloudbuild.yaml         # CI/CD deployment config
├── .gitignore              # Git ignore rules
├── .gcloudignore           # Cloud deployment ignore rules
│
└── templates/
    ├── index.html          # Main search page
    ├── login.html          # Login page
    ├── register.html       # Registration page
    ├── history.html        # Search history page
    └── profile.html        # User profile settings
```

---

## 🗄️ Database Schema

### Firestore Structure

```
users (Collection)
│
└── {username} (Document)
    ├── email: "user@example.com"
    ├── password: "hashed_password"
    │
    └── history (Subcollection)
        └── {auto-id} (Document)
            ├── origin: "LON"
            ├── destination: "PAR"
            ├── departure_date: "2025-02-01"
            ├── return_date: "2025-02-05"
            ├── adults: 1
            ├── searched_at: "2025-12-14T10:30:00"
            └── best_package: { flight: {...}, hotel: {...} }
```

---

## 🔌 API Integration

### Amadeus Travel API

The application uses OAuth2 authentication to access Amadeus endpoints:

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/security/oauth2/token` | Get access token |
| `GET /v2/shopping/flight-offers` | Search flights |
| `GET /v1/reference-data/locations/hotels/by-city` | List hotels |
| `GET /v3/shopping/hotel-offers` | Get hotel prices |
| `GET /v1/shopping/activities` | Get tours/activities |

---

## 📝 CRUD Operations

### Users

| Operation | Function | Description |
|-----------|----------|-------------|
| **CREATE** | `create_user()` | Register new user |
| **READ** | `get_user()` | Login / get user data |
| **UPDATE** | `update_user()` | Change email/password |
| **DELETE** | - | Not implemented |

### Search History

| Operation | Function | Description |
|-----------|----------|-------------|
| **CREATE** | `save_search_history()` | Save search with best deal |
| **READ** | `get_search_history()` | Display history page |
| **UPDATE** | - | N/A for history |
| **DELETE** | `delete_history_item()` | Remove history entry |

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Search for travel deals |
| `/api/history/<id>` | DELETE | Delete history item |
| `/api/test` | GET | API health check |
| `/login` | GET/POST | User login |
| `/register` | GET/POST | User registration |
| `/history` | GET | View search history |
| `/profile` | GET/POST | User profile settings |

---

## 🚀 Deployment

### Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and configured
- Docker (for local testing)

### Deploy to Cloud Run

```bash
# Deploy using Cloud Build
gcloud builds submit --config=cloudbuild.yaml
```

### What Happens

1. Code uploaded to Cloud Storage
2. Cloud Build creates Docker image
3. Image pushed to Container Registry
4. Cloud Run pulls new image
5. New revision created and traffic shifted

---

## 💻 Local Development

### Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd TravelExpenseOptimizer
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create `.env` file**
   ```env
   AMADEUS_API_KEY=your_api_key
   AMADEUS_API_SECRET=your_api_secret
   SECRET_KEY=your_secret_key
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open in browser**
   ```
   http://localhost:5000
   ```

---

## 🔐 Environment Variables

| Variable | Purpose | Set Where |
|----------|---------|-----------|
| `AMADEUS_API_KEY` | Amadeus API authentication | Secret Manager |
| `AMADEUS_API_SECRET` | Amadeus API authentication | Secret Manager |
| `SECRET_KEY` | Flask session encryption | Secret Manager |
| `USE_FIRESTORE` | Enable Firestore database | Cloud Run env |
| `PASSWORD_SALT` | Password hashing salt | Cloud Run env |

---

## 📚 Project Summary

This project demonstrates:

- ☁️ **Cloud Computing** - Serverless deployment, managed database, secret management, CI/CD
- 🌐 **Web Development** - Flask backend, responsive frontend, REST API design
- 🔗 **API Integration** - OAuth2 authentication, external API consumption
- 🗄️ **Database Operations** - NoSQL document structure, CRUD operations
- 🔒 **Security** - Password hashing, secret management, protected routes

---

## 📄 License

This project is for educational purposes - Cloud Computing Course Project.

---

## 👤 Author

Cloud Computing Project - December 2025
