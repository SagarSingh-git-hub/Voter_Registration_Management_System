# Voter Registration Management System (VRMS)

A secure, full-stack Flask application for voter registration and management.

## 🔒 Privacy & Security Notice

**This repository contains DUMMY DATA only.**
- All voter names, addresses, ID numbers (Aadhaar, EPIC), and phone numbers are randomly generated or placeholders.
- **No real personal data** is included in this codebase.
- Do NOT use real personal data for testing or development in a public fork.
- This project is configured to use **Environment Variables** for all sensitive credentials. Never commit your `.env` file.

## Features

- **Role-Based Access Control**: Admin and Voter roles.
- **Secure Authentication**: 
  - Dual-mode Login (Citizen/Admin).
  - Firebase Auth Integration.
  - OTP Email Verification.
- **Voter Application**:
  - Full application form (Form 6) with validation.
  - Secure Document Upload (PDF/JPG) with photo standardization.
  - Application Status Tracking (Real-time).
  - Voter Slip PDF Generation.
- **Admin Dashboard**:
  - Statistics & Analytics.
  - Review applications with document viewer.
  - Approve/Reject workflow with email notifications.
  - Export Approved Voter List.
- **Modern UI**:
  - Tailwind CSS with Glassmorphism design.
  - GSAP Animations (3D Tilt, Parallax).
  - Responsive & Accessible.
- **Integration**:
  - **EmailJS**: For client-side email notifications.
  - **Supabase**: For secondary data sync/storage.
  - **n8n**: For AI Chatbot integration.

## Setup & Installation

### 1. Clone and Install Dependencies
```bash
git clone https://github.com/yourusername/vrms.git
cd vrms
pip install -r requirements.txt
```

### 2. Configuration
Copy the example environment file to create your local config:
```bash
cp .env.example .env
```
Open `.env` and fill in your credentials:
- **Flask**: `SECRET_KEY`, `MONGO_URI`
- **EmailJS**: Keys for email service.
- **Supabase**: URL and Anon Key.
- **Firebase**: Project config keys.
- **n8n**: Webhook URL for the chatbot.
- **Mail**: SMTP settings (optional).

### 3. Database Setup
Ensure MongoDB is running locally or provide a remote URI.
To seed the database with dummy data for testing:
```bash
python seed_voters.py
```
To create an admin user (admin/admin123):
```bash
python create_admin.py
```

### 4. Run Application
```bash
python run.py
```
Access at `http://127.0.0.1:5000`

## Tech Stack
- **Backend**: Python, Flask, Flask-Login, Flask-Mail, PyMongo
- **Database**: MongoDB, Supabase (Sync), Redis (Rate Limiting)
- **Frontend**: Tailwind CSS, Jinja2, GSAP, FontAwesome
- **Services**: Firebase Auth, EmailJS, n8n (Chatbot)
