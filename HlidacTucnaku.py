import sys
import math
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QComboBox
from ib_insync import IB, Stock, Option, Position
import openai
from datetime import datetime
import sqlite3
import load_open_positions

# OpenAI API klíč
# Zde vložte svůj OpenAI API klíč.
openai.api_key = 'YOUR API KEY!'

class DeltaNeutralApp(QWidget):
    def __init__(self):
        super().__init__()

        self.ib = IB()
        self.positions = []
        self.sold_options = []  # To store sold options data (symbol, premium, etc.)

        # Setup UI
        self.initUI()

    def initUI(self):
        # Window setup
        self.setWindowTitle('Delta Neutral Strategie a OpenAI Chat')
        self.setGeometry(100, 100, 1000, 600)

        # Main Layout
        main_layout = QHBoxLayout()

        # Left side layout for positions table and details
        left_layout = QVBoxLayout()

        # Upper window with open positions
        self.positions_label = QTextEdit()
        self.positions_label.setReadOnly(True)
        self.positions_label.setMaximumHeight(40)  # Set maximum height
        self.positions_label.setMinimumHeight(20)  # Set minimum height
        self.positions_label.setPlainText('Otevřené pozice:')
        self.positions_label.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-size: 12pt;
                font-weight: bold;
            }
        """)
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(3)  # Ticker, Quantity, Value
        self.positions_table.setHorizontalHeaderLabels(['Ticker', 'Datum Vstup', 'Datum Výstup'])
        self.positions_table.cellClicked.connect(self.on_position_click)

        # Bottom window with selected position details
        self.details_label = QLabel('Detaily pozice:')
        self.details_text = QLabel('Vyberte pozici pro zobrazení detailů.')
        
        # Add summary table for trader2 data
        self.summary_label = QLabel('Souhrn PnL uzavřených pozic:')
        self.summary_table = QTableWidget()
        self.summary_table.setMaximumHeight(60)  # Set maximum height to 60 pixels

        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels([
            'Symbol', 'Net Cash trade currency', 'Net Cash base currency', 'FX PnL'
        ])
        # Adjust column widths
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)  # Symbol
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)  # Net Cash
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)  # Net Cash In Base
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)  # FX PnL
        
        # Add open positions label
        self.open_positions_label = QLabel('Otevřené pozice:')
        self.open_positions_table = QTableWidget()
        self.open_positions_table.setColumnCount(1)  # Add one column for ticker
        self.open_positions_table.setHorizontalHeaderLabels(['Ticker'])  # Set column header
        ## self.open_positions_table.setMaximumHeight(60)  # Set maximum height to 60 pixels

        # Add trade history table
        self.trade_history_label = QLabel('Historie obchodů:')
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(10)  # Increased to 10 columns
        self.trade_history_table.setHorizontalHeaderLabels([
            'Datum', 'Symbol', 'Popis', 'Množství', 'Komise', 
            'Net Cash', 'Čistá hodnota', 'Realizovaný PnL', 'Kapitálový PnL', 'FX PnL'
        ])
        # Adjust column widths
        header = self.trade_history_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)  # Date
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)  # Symbol
        header.setSectionResizeMode(2, header.ResizeMode.Stretch)  # Description
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)  # Quantity
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)  # Commission
        header.setSectionResizeMode(5, header.ResizeMode.ResizeToContents)  # Net Cash
        header.setSectionResizeMode(6, header.ResizeMode.ResizeToContents)  # Net Cash In Base
        header.setSectionResizeMode(7, header.ResizeMode.ResizeToContents)  # Realized PnL
        header.setSectionResizeMode(8, header.ResizeMode.ResizeToContents)  # Capital Gains PnL
        header.setSectionResizeMode(9, header.ResizeMode.ResizeToContents)  # FX PnL

        # Layout for buttons
        button_layout = QHBoxLayout()

        # Load Button
        load_button = QPushButton('Načíst pozice')
        load_button.clicked.connect(self.load_positions)
        button_layout.addWidget(load_button)

        # Load Button open positions
        open_positions_button = QPushButton('Otevřené pozice')
        self.open_positions_handler = load_open_positions.OpenPositionsHandler()
        open_positions_button.clicked.connect(lambda: self.open_positions_handler.handler(self.positions_table, self.open_positions_table))
        button_layout.addWidget(open_positions_button)

        # Add all components to the left layout
        left_layout.addWidget(self.positions_label)
        left_layout.addWidget(self.positions_table)
        left_layout.addWidget(self.details_label)
        left_layout.addWidget(self.details_text)
        left_layout.addWidget(self.open_positions_label)
        left_layout.addWidget(self.open_positions_table)
        left_layout.addWidget(self.summary_label)
        left_layout.addWidget(self.summary_table)
        left_layout.addWidget(self.trade_history_label)
        left_layout.addWidget(self.trade_history_table)
        left_layout.addLayout(button_layout)

        # Right side layout for OpenAI Chat
        right_layout = QVBoxLayout()

        # Chat interface
        self.chat_input = QLineEdit(self)
        self.chat_input.setPlaceholderText("Zeptejte se...")

        self.chat_button = QPushButton('Zeptat se GPT')
        self.chat_button.clicked.connect(self.on_ask_gpt)

        self.chat_output = QTextEdit(self)
        self.chat_output.setPlaceholderText("Odpověď GPT se objeví zde.")
        self.chat_output.setReadOnly(True)

        # Add model selection
        self.model_label = QLabel("Vybrat model:")
        self.model_selector = QComboBox(self)
        self.model_selector.addItem("gpt-4o")  # Latest and most capable model
        self.model_selector.addItem("gpt-3.5-turbo")  # Faster and more cost-effective model
        self.model_selector.addItem("gpt-4.1-mini")
        self.model_selector.setCurrentText("gpt-4o")  # Default model

        # Add components to the right layout
        right_layout.addWidget(self.model_label)
        right_layout.addWidget(self.model_selector)
        right_layout.addWidget(self.chat_input)
        right_layout.addWidget(self.chat_button)
        right_layout.addWidget(self.chat_output)

        # Add both side layouts to the main layout
        main_layout.addLayout(left_layout, 70)
        main_layout.addLayout(right_layout, 30)

        self.setLayout(main_layout)

    def load_positions(self):
        """Load positions from IBFLEXQUERY.db database and display them."""
        try:
            # Connect to the database
            conn = sqlite3.connect('data/IBFlexQuery.db')
            cursor = conn.cursor()

            # Query to get open positions (where dateclose is empty)
            cursor.execute('''
                SELECT Ticker, DateOpen, DateClose 
                FROM DN 
                WHERE DateClose IS NULL OR DateClose = ''
            ''')
            
            positions = cursor.fetchall()
            
            # Populate the positions table
            self.positions_table.setRowCount(len(positions))
            for i, position in enumerate(positions):
                ticker, date_open, date_close = position
                
                # Add the row to the table
                self.positions_table.setItem(i, 0, QTableWidgetItem(str(ticker)))
                self.positions_table.setItem(i, 1, QTableWidgetItem(str(date_open)))
                self.positions_table.setItem(i, 2, QTableWidgetItem(str(date_close) if date_close else ''))

            conn.close()
            
        except Exception as e:
            self.chat_output.setText(f"Chyba při načítání pozic: {e}")

    # def load_open_positions(self):
    #     """Handle the click event for the 'Otevřené pozice' button."""
    #     print("ahoj")

    def get_market_price(self, contract):
        """Get the market price for the contract using reqMktData."""
        # Request market data for the contract
        market_data = self.ib.reqMktData(contract)
        self.ib.sleep(1)  # Give time for the data to update

        # Return the current price if available
        return market_data.last if market_data.last is not None else 'N/A'

    def on_position_click(self, row, column):
        """Handle the selection of a position and display its details."""
        ticker = self.positions_table.item(row, 0).text()
        date_open = self.positions_table.item(row, 1).text()
        
        # Create a simple position object with just the ticker
        position = {'ticker': ticker, 'date_open': date_open}
        
        # Display the details
        self.display_position_details(position)

    def display_position_details(self, position):
        """Display details for a selected position."""
        ticker = position['ticker']
        date_open = position['date_open']

        details_text = f"Ticker: {ticker}\n"
        details_text += f"Datum otevření: {date_open}\n"
        self.details_text.setText(details_text)

        conn = None
        try:
            # Add summary data from trader2
            conn = sqlite3.connect('data/IBFlexQuery.db')
            cursor = conn.cursor()
            
            # Debug print
            print(f"Querying trader2 for ticker: {ticker}, date: {date_open}")
            
            # First, let's check what data exists for this ticker
            cursor.execute('''
                SELECT 
                    "tradeDate",
                    "underlyingSymbol",
                    "Totalquantity",
                    "TotalNetCash",
                    "TotalNetCashInBase",
                    "TotalFxPnl"
                FROM trader2
                WHERE "tradeDate" >= ?
                AND "underlyingSymbol" = ?
                ORDER BY "tradeDate" DESC
                LIMIT 5
            ''', (date_open, ticker))
            
            debug_data = cursor.fetchall()
            print(f"Debug data from trader2: {debug_data}")
            
            # Now try the summary query
            cursor.execute('''
                SELECT
                    underlyingSymbol,
                    ROUND(SUM("TotalNetCash"), 2) AS TotalNetCash,
                    ROUND(SUM("TotalNetCashInBase"), 2) AS TotalNetCashInBase,
                    ROUND(SUM("TotalFxPnl"), 2) AS TotalFxPnl
                FROM trader2
                WHERE "tradeDate" >= ?
                AND "underlyingSymbol" = ?
                AND "Totalquantity" = 0
                GROUP BY "underlyingSymbol"
            ''', (date_open, ticker))
            
            summary = cursor.fetchone()
            print(f"Summary data: {summary}")  # Debug print
            
            # Clear and populate the summary table
            self.summary_table.setRowCount(1 if summary else 0)
            if summary:
                symbol, net_cash, net_cash_base, fx_pnl = summary
                self.summary_table.setItem(0, 0, QTableWidgetItem(str(symbol)))
                self.summary_table.setItem(0, 1, QTableWidgetItem(str(net_cash)))
                self.summary_table.setItem(0, 2, QTableWidgetItem(str(net_cash_base)))
                self.summary_table.setItem(0, 3, QTableWidgetItem(str(fx_pnl)))
            else:
                # If no data found, show a message
                self.summary_table.setRowCount(1)
                self.summary_table.setItem(0, 0, QTableWidgetItem("Žádná data k zobrazení"))
            
            # Add trade details from IBFlexQueryCZK
            cursor.execute('''
                SELECT
                    "tradeDate",
                    "underlyingSymbol",
                    "description",
                    SUM("quantity") as TotalQuantity,
                    ROUND(SUM("ibCommission"), 2) AS TotalIbCommission,
                    ROUND(SUM("netCash"), 2) AS TotalNetCash,
                    ROUND(SUM("netCashInBase"), 2) AS TotalNetCashInBase,
                    ROUND(SUM("fifoPnlRealized"), 2) AS TotalFifoPnlRealized,
                    ROUND(SUM("capitalGainsPnl"), 2) AS TotalCapitalGainsPnl,
                    ROUND(SUM("fxPnl"), 2) AS TotalFxPnl
                FROM "IBFlexQueryCZK"
                WHERE "tradeDate" >= ?
                AND "underlyingSymbol" = ?
                GROUP BY "description", "underlyingSymbol"
                ORDER BY "tradeDate"
            ''', (date_open, ticker))
            
            trades = cursor.fetchall()
            
            # Clear and populate the trade history table
            self.trade_history_table.setRowCount(len(trades))
            for i, trade in enumerate(trades):
                trade_date, symbol, description, quantity, commission, net_cash, net_cash_base, fifo_pnl, cap_gains_pnl, fx_pnl = trade
                
                # Add each value to the table
                self.trade_history_table.setItem(i, 0, QTableWidgetItem(str(trade_date)))
                self.trade_history_table.setItem(i, 1, QTableWidgetItem(str(symbol)))
                self.trade_history_table.setItem(i, 2, QTableWidgetItem(str(description)))
                self.trade_history_table.setItem(i, 3, QTableWidgetItem(str(quantity)))
                self.trade_history_table.setItem(i, 4, QTableWidgetItem(str(commission)))
                self.trade_history_table.setItem(i, 5, QTableWidgetItem(str(net_cash)))
                self.trade_history_table.setItem(i, 6, QTableWidgetItem(str(net_cash_base)))
                self.trade_history_table.setItem(i, 7, QTableWidgetItem(str(fifo_pnl)))
                self.trade_history_table.setItem(i, 8, QTableWidgetItem(str(cap_gains_pnl)))
                self.trade_history_table.setItem(i, 9, QTableWidgetItem(str(fx_pnl)))
                
        except Exception as e:
            print(f"Error: {e}")  # Debug print
            self.summary_table.setRowCount(1)
            self.summary_table.setItem(0, 0, QTableWidgetItem(f"Chyba při načítání dat: {e}"))
            self.trade_history_table.setRowCount(1)
            self.trade_history_table.setItem(0, 0, QTableWidgetItem(f"Chyba při načítání dat: {e}"))
        finally:
            if conn:
                conn.close()

    def black_scholes_call(self, S, K, T, r, sigma):
        """Calculates the Black-Scholes price of a call option."""
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        N_d1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2))) # Cumulative normal distribution
        N_d2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2))) # Cumulative normal distribution
        call_price = S * N_d1 - K * math.exp(-r * T) * N_d2
        return call_price

    def black_scholes_put(self, S, K, T, r, sigma):
        """Calculates the Black-Scholes price of a put option."""
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        N_d1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2))) # Cumulative normal distribution
        N_d2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2))) # Cumulative normal distribution
        put_price = K * math.exp(-r * T) * (1 - N_d2) - S * (1 - N_d1)
        return put_price

    def black_scholes_vega(self, S, K, T, r, sigma):
        """Calculates the Black-Scholes Vega (derivative of option price with respect to volatility)."""
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        # N'(d1) is the probability density function of the standard normal distribution
        # which is 1/sqrt(2*pi) * exp(-d1^2/2)
        pdf_d1 = (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * d1**2)
        vega = S * pdf_d1 * math.sqrt(T)
        return vega

    def calculate_IV(self, option_contract):
        """Calculate the implied volatility using the Newton-Raphson method."""
        # Request market data for the option
        market_data = self.ib.reqMktData(option_contract, genericTickList="100", snapshot=True)
        self.ib.sleep(1)  # Give time for data to update

        option_price = market_data.last
        strike = option_contract.strike
        underlying_price = market_data.underlyingLast if hasattr(market_data, 'underlyingLast') else None
        option_type = option_contract.right # 'C' for Call, 'P' for Put

        if option_price is None or underlying_price is None:
            return "N/A"  # Unable to calculate IV

        try:
            time_to_expiration = self.calculate_time_to_expiration(option_contract)  # in years
            interest_rate = 0.01  # Assume a 1% risk-free interest rate

            if time_to_expiration <= 0:
                return "N/A" # Option has expired or time to expiration is invalid

            # Newton-Raphson method for IV
            max_iterations = 100
            tolerance = 1e-6
            implied_volatility = 0.5 # Initial guess for IV

            for i in range(max_iterations):
                if option_type == 'C':
                    model_price = self.black_scholes_call(underlying_price, strike, time_to_expiration, interest_rate, implied_volatility)
                elif option_type == 'P':
                    model_price = self.black_scholes_put(underlying_price, strike, time_to_expiration, interest_rate, implied_volatility)
                else:
                    return "N/A" # Unknown option type

                vega = self.black_scholes_vega(underlying_price, strike, time_to_expiration, interest_rate, implied_volatility)

                if vega == 0: # Avoid division by zero
                    break

                # Newton-Raphson step
                implied_volatility_new = implied_volatility - (model_price - option_price) / vega

                if abs(implied_volatility_new - implied_volatility) < tolerance:
                    return round(implied_volatility_new * 100, 2) # Return in percentage

                implied_volatility = implied_volatility_new

                # Clamp volatility to reasonable bounds to prevent divergence
                if implied_volatility < 0.01:
                    implied_volatility = 0.01
                elif implied_volatility > 5.0: # Cap at 500%
                    implied_volatility = 5.0

            return "Convergence Error" # Did not converge within max iterations

        except Exception as e:
            print(f"Chyba při výpočtu IV: {e}")
            return "Chyba"

    def get_30_day_IV(self, option_contract):
        """Calculate the 30-day historical implied volatility."""
        # reqHistoricalData expects a Contract object
        historical_data = self.ib.reqHistoricalData(option_contract, endDateTime='', durationStr='30 D', barSizeSetting='1 day', whatToShow='TRADES', useRTH=True)
        
        if len(historical_data) < 30:
            return "N/A"  # Not enough data to calculate IV

        # Collect option prices for the last 30 days
        option_prices = [bar.close for bar in historical_data]

        if not option_prices or len(option_prices) < 2: # Need at least two prices for log returns
            return "N/A"

        # Calculate the 30-day standard deviation of option returns as a proxy for IV
        log_returns = [math.log(option_prices[i] / option_prices[i-1]) for i in range(1, len(option_prices))]
        std_dev = np.std(log_returns)  # Standard deviation of the log returns
        annualized_volatility = std_dev * math.sqrt(252)  # Annualize the volatility (assuming 252 trading days)

        return round(annualized_volatility * 100, 2)  # Return in percentage

    def calculate_time_to_expiration(self, option_contract):
        """Calculate the time to expiration in years."""
        # option_contract.lastTradeDate is a string in 'YYYYMMDD' format
        # current_time is a datetime object
        try:
            expiry_str = option_contract.lastTradeDate
            expiry_date = datetime.strptime(expiry_str, '%Y%m%d').date()
            
            current_time = self.ib.reqCurrentTime()
            current_date = current_time.date()
            
            time_to_expiration_days = (expiry_date - current_date).days
            
            if time_to_expiration_days < 0:
                return 0.0 # Option has already expired

            time_to_expiration_years = time_to_expiration_days / 365.25  # Convert days to years
            return time_to_expiration_years
        except Exception as e:
            print(f"Chyba při výpočtu času do expirace: {e}")
            return 0.0 # Return 0 or handle error appropriately

    def on_ask_gpt(self):
        """Handle the interaction with the OpenAI API using the new chat completions interface."""
        user_input = self.chat_input.text()

        if not user_input:
            self.chat_output.setText("Zadejte prosím otázku.")
            return

        try:
            # Get the selected model from the combo box
            selected_model = self.model_selector.currentText()

            # Send the user's question to OpenAI using the new chat completions API
            response = openai.chat.completions.create(
                model=selected_model,  # Use the selected model
                messages=[
                    {"role": "system", "content": "Jste užitečný asistent."},
                    {"role": "user", "content": user_input}
                ],
                max_tokens=150
            )

            # Extract the assistant's reply from the response
            # The structure for chat completions is response.choices[0].message.content
            gpt_output = response.choices[0].message.content.strip()

            # Display the response
            self.chat_output.setText(gpt_output)

        except Exception as e:
            self.chat_output.setText(f"Chyba: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DeltaNeutralApp()
    window.show()
    sys.exit(app.exec())
