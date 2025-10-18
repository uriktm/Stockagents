# 📄 Technical Specification: Stockagents

**Version:** 1.1

## 1. Architecture

* **Paradigm:** Multi-Agent System (a single agent orchestrating multiple tools).
* **Platform:** OpenAI Assistants API (Agents SDK).
* **Development Language:** Python.

## 2. System Components

### 2.1. Core Agent: `AlphaSynthesizerAgent`

* **Description:** The orchestrating brain of the system, implemented as an `Agent` using the OpenAI SDK.
* **Prompt:** See `AGENTS.md`.

### 2.2. Assigned Tools

#### 2.2.1. `NewsAndBuzzTool`

* **Description (For Human):** A specialist tool for analyzing news, sentiment, and media buzz.
* **Docstring (For AI & Code):**
    ```
    Fetches recent news articles for a given stock symbol, analyzes their sentiment, and calculates the media buzz factor.
    ```
* **Technologies:** NewsAPI, OpenAI API.
* **Input:** `stock_symbol: str`
* **Output (dict):**
    ```json
    {
      "sentiment_score": 0.8,
      "narrative": "New product launch is receiving positive reviews",
      "buzz_factor": 2.5,
      "top_headlines": ["...", "..."]
    }
    ```

#### 2.2.2. `VolumeAndTechnicalsTool`

* **Description (For Human):** A technical analyst for trading volume and chart indicators.
* **Docstring (For AI & Code):**
    ```
    Analyzes the trading volume and key technical indicators (RSI, MACD) for a given stock symbol. Returns the volume spike ratio and technical signals.
    ```
* **Technology:** `yfinance` library.
* **Input:** `stock_symbol: str`
* **Output (dict):**
    ```json
    {
      "volume_spike_ratio": 1.8,
      "technical_signal": "Bullish Momentum (MACD Crossover)",
      "rsi": 65,
      "macd_signal_status": "Crossover"
    }
    ```

#### 2.2.3. `CorporateEventsTool`

* **Description (For Human):** Checks for upcoming corporate events.
* **Docstring (For AI & Code):**
    ```
    Checks for upcoming corporate events for a given stock symbol, such as earnings report dates. Returns the date of the next earnings report if available.
    ```
* **Technology:** `yfinance` library.
* **Input:** `stock_symbol: str`
* **Output (dict):**
    ```json
    {
      "upcoming_earnings_date": "2025-10-22",
      "has_upcoming_event": true
    }
    ```