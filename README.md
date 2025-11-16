# Rutabaga QA Review Website

Flask-based web application for human review and quality assurance of Rutabaga's answer service responses.

## Features

- **Google OAuth Authentication**: Secure login with pre-approved reviewer list
- **Multi-Intent Support**: Review responses for all intents (interaction, dosing, etc.)
- **Segment Scoring**: Rate each response segment (S1-S4) on a 0-5 scale
- **Draft & Flag System**: Save work in progress or flag problematic responses
- **Production Updates**: Approved reviews automatically update the production database
- **Admin Dashboard**: Global statistics and reviewer management (admin only)
- **Audit Trail**: Complete history of all reviews and changes

## Tech Stack

- **Backend**: Flask 3.0, SQLAlchemy 2.0
- **Database**: PostgreSQL (shared with Rutabaga app backend)
- **Authentication**: Google OAuth 2.0 (via Authlib)
- **Frontend**: Tailwind CSS, HTMX, Alpine.js
- **Deployment**: Railway

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (shared with Rutabaga backend)
- Google OAuth credentials

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Rutabaga_QA_Website.git
   cd Rutabaga_QA_Website
   ```

2. **Install dependencies with hatch + uv**
   ```bash
   # Hatch will automatically use uv to install dependencies
   hatch env create
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run database migration** (from Rutabaga_Backend directory)
   ```bash
   cd ../Rutabaga_Backend
   PGPASSWORD=rutabaga_dev_password psql -h localhost -U rutabaga_user -d rutabaga \
     -f infrastructure/database/migrations/013_qa_reviews_schema.sql
   ```

5. **Run the application**
   ```bash
   cd ../Rutabaga_QA_Website
   hatch run dev
   # Or for production: hatch run serve
   ```

6. **Access the website**
   ```
   http://localhost:6000
   ```

> **Note**: This project uses [hatch](https://hatch.pypa.io/) for environment management and [uv](https://github.com/astral-sh/uv) for fast dependency installation. Install them with:
> ```bash
> pip install hatch uv
> ```

## Configuration

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI: `http://localhost:6000/login/callback`
4. Copy Client ID and Secret to `.env`

### Pre-Approved Reviewers

Reviewers must be added to the database before they can log in:

```sql
INSERT INTO qa_reviews.reviewers (google_id, email, full_name, specialization, role, is_active)
VALUES ('pending', 'user@example.com', 'User Name', 'Pharmacy', 'reviewer', TRUE);
```

The `google_id` will be updated on first login.

## Deployment (Railway)

### Environment Variables

Set these in Railway dashboard:

```
FLASK_ENV=production
SECRET_KEY=<generate-strong-secret>
DATABASE_URL=<railway-postgres-url>
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=https://qa.rutabaga.app/login/callback
ANSWER_SERVICE_URL=https://api.rutabaga.app/v2/answer
```

### Deploy

```bash
# Link to Railway project
railway link

# Deploy
railway up
```

## Development Roadmap

### Phase 1: Database & Authentication ✅
- [x] PostgreSQL schema (qa_reviews)
- [x] Google OAuth login/logout
- [x] Login page with Tailwind CSS
- [x] Session tracking

### Phase 2: Review Workflow (In Progress)
- [ ] Get next unreviewed response
- [ ] Segment scoring interface
- [ ] Skip/Flag/Draft/Submit actions
- [ ] Scoring guide popover
- [ ] Counters (session + all-time)

### Phase 3: Response Generation & Source Data
- [ ] Call /v2/answer endpoint
- [ ] Pre-populate response queue
- [ ] View source data modal
- [ ] Single-record re-ingestion
- [ ] Empty state handling

### Phase 4: My Reviews & Re-review
- [ ] My reviews page with tables
- [ ] Re-review request flow
- [ ] Show original + submitted versions
- [ ] Filters (Submitted, Drafts, Flagged)

### Phase 5: Production Updates
- [ ] Update production tables on submit
- [ ] Intent-to-table mapping
- [ ] Segment-to-field mapping
- [ ] Audit logging

### Phase 6: Admin Dashboard
- [ ] Global statistics
- [ ] Flagged items view
- [ ] Reviewer statistics
- [ ] CSV export
- [ ] Reviewer activation/deactivation

### Phase 7: Testing & Polish
- [ ] Unit tests
- [ ] Integration tests
- [ ] UI/UX polish
- [ ] Error handling

### Phase 8: Deployment & Documentation
- [ ] Railway deployment
- [ ] Custom domain setup
- [ ] User guide for reviewers
- [ ] Admin guide

## Project Structure

```
Rutabaga_QA_Website/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── auth.py               # Google OAuth routes
│   ├── models.py             # SQLAlchemy models
│   ├── routes/
│   │   ├── review.py         # Review routes
│   │   ├── admin.py          # Admin routes
│   │   └── api.py            # API endpoints
│   ├── services/             # Business logic (future)
│   ├── templates/
│   │   ├── base.html         # Base template
│   │   ├── login.html        # Login page
│   │   ├── review.html       # Review page
│   │   ├── my_reviews.html   # My reviews page
│   │   └── admin/
│   │       └── dashboard.html
│   └── static/
│       ├── css/
│       └── js/
├── app.py                    # Entry point
├── config.py                 # Flask configuration
├── requirements.txt
├── Procfile                  # Railway deployment
├── .env.example
└── README.md
```

## Database Schema

All tables live in the `qa_reviews` schema:

- **reviewers**: Authorized users (Google OAuth)
- **response_queue**: Responses waiting for review
- **reviews**: Review records with scores/suggestions
- **review_audit_log**: Audit trail of all actions
- **production_updates**: Log of production DB changes
- **rereview_requests**: Re-review workflow
- **review_sessions**: Session tracking for counters

See `/dev_docs/QA_Website_Dev_Plan.md` in Rutabaga_Backend for complete schema.

## Contributing

This is an internal tool for Rutabaga QA. Contact an administrator for access.

## License

Proprietary - Rutabaga, Inc.
