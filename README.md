# Delta Neutral Strategy and OpenAI Chat

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![IB-Insync](https://img.shields.io/badge/BrokerAPI-IB--Insync-orange.svg)
![OpenAI](https://img.shields.io/badge/AI-OpenAI-purple.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

A comprehensive Python desktop application for managing delta-neutral options strategies with live data from Interactive Brokers (IB) and an integrated AI chat (OpenAI GPT). The project aims to provide traders with a tool for monitoring positions, analyzing implied volatility, and getting quick insights from AI.

## Table of Contents

- [Project Goals](#project-goals)
- [Key Features](#key-features)
- [Planned Future Enhancements](#planned-future-enhancements)
- [Installation and Setup](#installation-and-setup)
- [Usage](#usage)
- [API Key Configuration](#api-key-configuration)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Project Goals

The main objective of this project is to create a robust and user-friendly application that enables options traders to effectively manage and analyze their delta-neutral strategies. Specific goals include:

1.  **Clear Position Monitoring:** Displaying only underlying assets in the main overview and a detailed breakdown of all associated options upon selection.
2.  **Detailed Volatility Analysis:** Providing current implied volatility (IV), 30-day historical IV, and IV at the time of trade entry for options.
3.  **Comprehensive PnL Reporting:** Displaying profit and loss (PnL) for the underlying asset, individual options, and the entire grouped position.
4.  **Dynamic Break-Even Points:** Calculating and displaying break-even points that dynamically adjust based on collected premium.
5.  **Trading System Integration:** Reliable connection to Interactive Brokers for retrieving live position and market data.
6.  **Intelligent Assistance:** Utilizing OpenAI GPT to answer questions related to trading, market analysis, or general inquiries.
7.  **Historical Data and Analysis:** Building a robust database for storing historical transactions and IB Flex Reports for deeper PnL analysis and backtesting.

## Key Features

* **Open Positions Overview:** Displays only underlying assets (stocks/futures) with their quantity and current value.
* **Detailed Position View:** Clicking on an underlying asset shows comprehensive position information, including:
    * Quantity of the underlying stock.
    * Delta of the underlying stock and individual options.
    * Total delta of the entire position.
    * Current option price, current implied volatility (IV), 30-day historical IV.
    * (Planned: IV at the time of option purchase/sale).
    * Profit and Loss (PnL) for the underlying, individual options, and the entire strategy.
    * (Planned: Dynamic Break-Even points).
* **Interactive Brokers Integration:** Connects to IB TWS/Gateway for retrieving live position and market data.
* **OpenAI GPT Chat:** Integrated chat module for quick questions and answers, with the ability to select different GPT models (gpt-4o, gpt-3.5-turbo, etc.).
* **User Interface:** Intuitive GUI built with PyQt6.
* **Flex Report:** Donwloading YTD actual info and updating database by click of a button !

## Planned Future Enhancements

The project is under active development, and the following key features are planned:

* **Historical Transactions and PnL:**
    * Implement downloading and parsing of Flex Reports from Interactive Brokers.
    * Create an SQL database (e.g., SQLite) to store all transactional data (purchase prices, premiums, commissions, IV at trade time).
    * Calculate and display PnL (realized and unrealized) for all position components based on historical data.
* **Dynamic Break-Even Points:** Calculate and visualize break-even points that dynamically adjust based on collected premiums and market movements.
* **IV at Purchase Time:** Store and display the implied volatility at the moment a trade was executed.
* **Asynchronous Data Processing:** Transition to `asyncio` for asynchronous communication with the IB API to prevent UI freezing during data loading.
* **Improved Filtering and Grouping:** More advanced options for filtering and grouping positions (e.g., by strategy, expiration).
* **Charts and Visualizations:** Basic charts for IV evolution, PnL, or position risk profiles.
* **Alerts:** Configurable alerts based on predefined rules (e.g., reaching a certain IV level, underlying price).
* **Strategy Management:** Ability to define and save complex options strategies.

## Installation and Setup

### Prerequisites

* Python 3.9+
* Interactive Brokers TWS (Trader Workstation) or IB Gateway running and connected to your account.
* An OpenAI account with a valid API key.
* For Report Downloading and full funtionality IBKR FLEX QUERY TOKEN AND ID is required

### Installation Steps

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/your-project.git](https://github.com/your-username/your-project.git)
    cd your-project
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # or
    .\venv\Scripts\activate   # On Windows
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    (You will need to create a `requirements.txt` file with the following content:
    ```
    PyQt6
    ib_insync
    openai
    numpy
    ```)

### Configuration

1.  **IB TWS/Gateway:** Ensure your TWS or IB Gateway is running and enabled for API connections (Edit -> Global Configuration -> API -> Settings -> Enable ActiveX and Socket Clients).
2.  **OpenAI API Key:** Open the `main.py` file and replace the placeholder `YOUR API KEY!` with your actual OpenAI API key:
    ```python
    openai.api_key = 'sk-YourActualOpenAIAPIKeyHere'
    ```

### Running the Application

```bash
python main.py
