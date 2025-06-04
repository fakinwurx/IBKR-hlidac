import sys
import math
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QComboBox
from ib_insync import IB, Stock, Option, Position
import openai
from datetime import datetime

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
        self.positions_label = QLabel('Otevřené pozice:')
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(3)  # Ticker, Quantity, Value
        self.positions_table.setHorizontalHeaderLabels(['Ticker', 'Množství', 'Hodnota'])
        self.positions_table.cellClicked.connect(self.on_position_click)

        # Bottom window with selected position details
        self.details_label = QLabel('Detaily pozice:')
        self.details_text = QLabel('Vyberte pozici pro zobrazení detailů.')

        # Layout for buttons
        button_layout = QHBoxLayout()

        # Load Button
        load_button = QPushButton('Načíst pozice')
        load_button.clicked.connect(self.load_positions)
        button_layout.addWidget(load_button)

        # Add all components to the left layout
        left_layout.addWidget(self.positions_label)
        left_layout.addWidget(self.positions_table)
        left_layout.addWidget(self.details_label)
        left_layout.addWidget(self.details_text)
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
        """Load positions from IBKR account and display them."""
        try:
            # Connect to IBKR
            self.ib.connect('127.0.0.1', 7497, clientId=1)

            # Get open positions
            positions = self.ib.positions()
            
            # Qualify each contract to ensure all necessary fields are populated, like exchange
            qualified_positions = []
            for pos in positions:
                try:
                    # Attempt to qualify the contract. This can be blocking.
                    # For performance, consider doing this in a separate thread if many positions.
                    # For now, let's keep it synchronous.
                    self.ib.qualifyContracts(pos.contract)
                    qualified_positions.append(pos)
                except Exception as qc_e:
                    print(f"Varování: Nelze kvalifikovat kontrakt {pos.contract.symbol}: {qc_e}")
                    # If qualification fails, still add the original position, but it might cause issues later
                    qualified_positions.append(pos) 
            
            self.positions = qualified_positions

            # Populate the positions table
            self.positions_table.setRowCount(len(self.positions))
            for i, position in enumerate(self.positions):
                ticker = position.contract.symbol
                qty = position.position

                # Get the current market price using reqMktData
                market_price = self.get_market_price(position.contract)

                # Add the row to the table
                self.positions_table.setItem(i, 0, QTableWidgetItem(ticker))
                self.positions_table.setItem(i, 1, QTableWidgetItem(str(qty)))
                self.positions_table.setItem(i, 2, QTableWidgetItem(str(market_price)))
        except Exception as e:
            self.chat_output.setText(f"Chyba při načítání pozic: {e}")


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
        selected_position = None

        # Find the selected position
        for position in self.positions:
            if position.contract.symbol == ticker:
                selected_position = position
                break

        if selected_position:
            self.display_position_details(selected_position)

    def display_position_details(self, position):
        """Display details for a selected position."""
        ticker = position.contract.symbol
        contract = position.contract

        details_text = f"Ticker: {ticker}\n"
        details_text += f"Množství: {position.position}\n"

        # Collect PnL from sold options
        pnl = 0
        details_text += f"\nProdané opce a PnL:\n"
        for option in self.sold_options:
            if option['ticker'] == ticker:
                details_text += f"Symbol opce: {option['symbol']}\n"
                details_text += f"Vybraná prémie: {option['premium']}\n"
                pnl += option['premium']

        details_text += f"Celkové PnL z prodaných opcí: {pnl}\n"

        # Get the options details from IBKR
        # Note: reqContractDetails expects a Contract object, not an Option object directly.
        # This part might need refinement based on how you intend to get option details
        # related to the underlying stock position.
        # For now, let's assume 'contract' here refers to the underlying stock.
        # To get option details for the underlying, you'd typically search for options
        # associated with that underlying. This part of the original code might need
        # a more robust implementation if you want to list *all* options for the underlying.
        
        try:
            # If position.contract is an Option, this will work.
            # If position.contract is a Stock, it will return details for the stock.
            contract_details = self.ib.reqContractDetails(contract)
            
            if contract_details and isinstance(contract_details[0].contract, Option):
                details_text += f"\nInformace o opcích (pro tuto konkrétní pozici opce):\n"
                for detail in contract_details:
                    option_contract = detail.contract
                    details_text += f"Symbol opce: {option_contract.symbol}\n"
                    details_text += f"Strike: {option_contract.strike}\n"
                    details_text += f"Expirace: {option_contract.lastTradeDate if hasattr(option_contract, 'lastTradeDate') else 'Data nejsou k dispozici'}\n"
                    details_text += f"IV při nákupu: {self.calculate_IV(option_contract)}\n"
                    details_text += f"30denní IV: {self.get_30_day_IV(option_contract)}\n"
            elif isinstance(contract, Stock):
                details_text += f"\nInformace o opcích pro podkladovou akcii ({ticker}):\n"
                # Example of how to get option chain for a stock:
                # This section demonstrates fetching option parameters and then details for a few options.
                # In a real application, you might filter these more precisely.
                contracts_params = self.ib.reqSecDefOptParams(underlyingSymbol=ticker, futFopExchange='',
                                                      underlyingConId=contract.conId, genericTickList='')
                if contracts_params:
                    # For simplicity, let's just pick the first expiration and a few strikes
                    first_contract_param = contracts_params[0]
                    expirations = first_contract_param.expirations
                    strikes = first_contract_param.strikes

                    if expirations and strikes:
                        # Limit to a few options for display purposes to avoid too much data
                        for i, strike in enumerate(strikes[:3]): # Take first 3 strikes
                            for right in ['C', 'P']: # Calls and Puts
                                try:
                                    # Explicitly set exchange to 'SMART' when creating the Option contract
                                    option_contract = Option(ticker, expirations[0], strike, right, 'SMART', exchange='SMART')
                                    self.ib.qualifyContracts(option_contract) # Qualify the newly created contract
                                    details_text += f"  Symbol opce: {option_contract.symbol}\n"
                                    details_text += f"  Strike: {option_contract.strike}\n"
                                    details_text += f"  Expirace: {option_contract.lastTradeDate if hasattr(option_contract, 'lastTradeDate') else 'N/A'}\n"
                                    details_text += f"  IV při nákupu: {self.calculate_IV(option_contract)}\n"
                                    details_text += f"  30denní IV: {self.get_30_day_IV(option_contract)}\n"
                                except Exception as e:
                                    details_text += f"  Chyba při získávání detailů opce {ticker} {expirations[0]} {strike} {right}: {e}\n"
                    else:
                        details_text += "  Žádné dostupné expirace nebo strike ceny pro opce.\n"
                else:
                    details_text += "  Žádné parametry opcí nalezeny pro tuto akcii.\n"
            else:
                details_text += f"\nPro tuto pozici nejsou k dispozici žádné konkrétní detaily opcí (může se jednat o jiný typ kontraktu než akcie nebo opce).\n"

        except Exception as e:
            details_text += f"\nChyba při načítání detailů kontraktu: {e}\n"
        
        # Update details in the UI
        self.details_text.setText(details_text)

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
