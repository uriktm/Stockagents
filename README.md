# Stockagents 📈

**Stockagents** is an AI-powered stock analysis tool that provides on-demand insights for a given list of stocks. It uses a multi-agent architecture powered by the OpenAI Assistants API to analyze news sentiment, media buzz, technical indicators, and corporate events to identify stocks with the potential for abnormal positive activity.

## ✨ Features

- **On-Demand Analysis:** Get fresh insights whenever you need them.
- **Multi-Source Intelligence:** Gathers data from news APIs, financial data providers, and technical analysis libraries.
- **AI-Powered Synthesis:** Uses a sophisticated AI agent to weigh different factors and provide a holistic view.
- **Confidence Scoring:** Each forecast is given a confidence score to help prioritize focus.
- **Causal Explanations (XAI):** Clearly explains *why* a stock is flagged, citing the specific data points that led to the conclusion.

---

## 🚀 Getting Started

Follow these instructions to get a local copy up and running.

### Prerequisites

- Python 3.9+
- Pip package manager

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/uriktm/Stockagents.git
    cd Stockagents
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required packages:**
    ```sh
    pip install -r requirements.txt
    ```

---

## ⚙️ Configuration

The project requires API keys to function.

1.  Create a file named `.env` in the root directory of the project.
2.  Copy the contents of `.env.example` into `.env`.
3.  Add your secret API keys to the `.env` file:
    ```ini
    OPENAI_API_KEY="sk-..."
    NEWS_API_KEY="your-news-api-key"
    ```

---

## Usage

### Web Interface (Recommended)

Run the Streamlit web interface for a beautiful, interactive experience:

```sh
py -m streamlit run streamlit_app.py
```

The interface features:
- Hebrew RTL (right-to-left) support
- Card-based layout sorted by confidence score
- Interactive legend explaining all metrics
- Direct links to news sources
- Expandable detailed analysis

### Command Line Interface

Run the main script from the command line and provide a comma-separated list of stock symbols using the `--stocks` argument.

**Example:**
```sh
python main.py --stocks "NVDA,TSLA,LLY,GOOG,QQQ,TQQQ"
```

## תרשים השיקולים בניתוח

- **חדשות וסנטימנט**
  - ציון סנטימנט: חיובי/שלילי, עם הסבר טקסטואלי.
  - חשיפה תקשורתית (`buzz_factor`): כמה כתבות לעומת הממוצע.
  - קישורים ישירים לכתבות לחיזוק הנרטיב.
- **ניתוח טכני**
  - RSI: טווח כוח יחסי כולל פרשנות "מכירה יתר" / "קנייה יתר".
  - MACD וחצייה: מגמה ומומנטום (Bullish / Bearish crossover).
  - יחס נפח מול ממוצע: מצביע על עניין חריג.
- **אירועים קרובים**
  - בודק האם יש דוח רווחים קרוב או אירוע תאגידי שיכול לשמש קטליזטור.
- **תחזית הסוכן**
  - הסוכן משלב את הנתונים (חדשות + טכני + אירועים) כדי לנסח תחזית בעברית עם הסיבה המרכזית.
  - מצרף ציון ביטחון (1–10) בהתאם לעוצמת הסימנים והקונסיסטנטיות ביניהם.
- **ממשק המשתמש (UI)**
  - תג צבעוני ואייקון (`_forecast_tone`) משקפים אם המגמה חיובית, שלילית או ניטרלית.
  - רשימות חדשות/טכני/אירועים מציגות את המספרים ביחד עם פרשנות קצרה (למשל `ציון סנטימנט: 0.2 (חיובי קל)`).

### סיכום
- **המערכת** מחברת בין נתוני חדשות בזמן אמת, אינדיקטורים טכניים ואירועי חברה.
- **הסוכן** מסכם את הכול בעברית, מעניק תחזית + ציון ביטחון.
- **הממשק** מציג את המידע בצורה גרפית ומוסבר, כך שניתן להבין במהירות את תמונת המצב של כל מניה.