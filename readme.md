# City Scraper

Comprehensive city website scraper with intelligent fallback strategy and LLM-powered content structuring.

## Features

- Smart Fallback Strategy: Firecrawl → Playwright → PDF processing
- Form & Signup Detection: Automatically finds and processes registration forms
- PDF Processing: Extracts text from city documents and PDFs
- Dynamic Content: Handles JavaScript-heavy pages, calendars, events
- LLM Enhancement: Claude structures all content into JSON
- Comprehensive Data: Meetings, contacts, services, permits, forms

## Quick Start

### Installation

```bash
# Create project directory
mkdir city_scraper && cd city_scraper

# Save all the provided files in this directory

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Optional: Install Tesseract for PDF OCR
# Ubuntu/Debian: sudo apt-get install tesseract-ocr
# macOS: brew install tesseract
# Windows: Download from GitHub releases
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

**Required in .env:**
```bash
FIRECRAWL_API_KEY_V2=your_firecrawl_api_key_here
AWS_REGION=us-east-2
BEDROCK_MODEL_ID=your_bedrock_model_arn
```

**Optional in .env:**
```bash
AWS_S3_BUCKET=your-bucket-name
```

### Add Your Cities

Edit `config.py` to add your target city websites:

```python
TARGET_URLS = [
    "https://www.elsegundo.org/",
    "https://311.sanantonio.gov/",
    "https://www.sanantonio.gov/",
    # Add more city websites as needed
]
```

### Run the Scraper

```bash
# Normal scraping
python main.py

# See all available commands
python main.py help
```

## Usage Examples

### Basic Scraping
```bash
# Scrape all configured city websites
python main.py
```

### Resume a Job
```bash
# If Firecrawl job gets interrupted, resume it
python main.py resume abc123-def456-ghi789
```

### Forms-Only Mode
```bash
# Focus on finding signup and registration forms
python main.py forms
```

## Data Extraction

### Main Content
- **City Information**: Departments, services, contact details
- **Meetings**: City council, planning commission, public hearings
- **Events**: Community events, public meetings, deadlines
- **Documents**: Ordinances, reports, agendas, permits
- **News**: Announcements, press releases, alerts

### Forms & Signups
- **Registration Forms**: Resident portals, service signups
- **Application Forms**: Permits, licenses, requests
- **Contact Forms**: Feedback, inquiries, complaints
- **Subscription Forms**: Newsletters, alerts, notifications

### Structured Output
```json
{
  "overview": "Official website for San Antonio, Texas",
  "city_name": "San Antonio",
  "departments": ["Public Works", "Development Services", "Fire Department"],
  "services": ["311 Services", "Building Permits", "Business Licenses"],
  "contacts": [{
    "name": "Erik Walsh",
    "title": "City Manager", 
    "phone": "210-207-7080",
    "email": "erik.walsh@sanantonio.gov"
  }],
  "meetings": [{
    "title": "City Council Meeting",
    "date": "2024-01-18",
    "time": "9:00 AM",
    "location": "Municipal Plaza Building"
  }],
  "forms": [{
    "name": "SA311 Service Request",
    "type": "application",
    "purpose": "Request city services",
    "fields": ["address", "issue_type", "description"],
    "requirements": ["Valid San Antonio address"]
  }],
  "signup_info": {
    "available": true,
    "description": "Create account for SA311 and online services",
    "benefits": ["Service requests", "Status tracking", "Notifications"]
  }
}
```

## Output Structure

```
city_scraper/
├── output/
│   ├── raw/                    # Raw scraped content
│   │   ├── abc123.json
│   │   └── def456.json
│   └── structured/             # LLM-processed data
│       ├── abc123.json
│       └── def456.json
├── city_data_raw.tar.gz        # Compressed raw data
├── city_data_structured.tar.gz # Compressed structured data
└── scraper.log                 # Execution log
```

## Configuration Options

### In `config.py`:

```python
# Target websites
TARGET_URLS = [
    "https://www.elsegundo.org/",
    "https://311.sanantonio.gov/", 
    "https://www.sanantonio.gov/"
]

# Scraping limits
MAX_DEPTH = 5        # How deep to crawl
TIMEOUT = 30         # Timeout in seconds
RETRY_ATTEMPTS = 3   # Retry failed requests

# Output directories  
OUTPUT_RAW = "output/raw"
OUTPUT_STRUCTURED = "output/structured"
```

### In `.env`:

```bash
# Required
FIRECRAWL_API_KEY_V2=your_key
AWS_REGION=us-east-2
BEDROCK_MODEL_ID=your_model_arn

# Optional
AWS_S3_BUCKET=your_bucket
LOG_LEVEL=INFO
```

## How It Works

### Fallback Strategy
1. **Firecrawl First**: Handles most static content efficiently
2. **Playwright Fallback**: For dynamic JS content, forms, calendars  
3. **PDF Processing**: Downloads and extracts text from documents
4. **LLM Enhancement**: Claude cleans and structures all content

### Smart Content Detection
- Automatically detects pages with forms
- Identifies signup/registration pages
- Finds PDF documents for processing
- Extracts calendar events and meeting schedules

### Form Classification
- **Signup**: Registration, account creation
- **Login**: Authentication pages
- **Application**: Permits, licenses, requests  
- **Contact**: Feedback, inquiries
- **Subscription**: Newsletters, alerts