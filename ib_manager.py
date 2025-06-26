# ib_manager.py
import random
from ib_insync import IB, Stock, Option, Position
from PyQt6.QtWidgets import QApplication, QTableWidgetItem
from PyQt6.QtGui import QColor

class IBManager:
    def __init__(self, chat_output_widget):
        """
        Initializes the IBManager.

        Args:
            chat_output_widget (QTextEdit): Reference to the QTextEdit widget
                                            to display messages/errors.
        """
        self.ib = IB()
        self.chat_output = chat_output_widget

        # Attempt to connect to IB Gateway/TWS on startup
        self._connect_to_ib()

    def _connect_to_ib(self):
        """
        Attempts to connect to Interactive Brokers.
        Displays connection status in the chat_output.
        """
        try:
            client_id = random.randint(1, 1000) # Generate a random client ID
            self.ib.connect(host='127.0.0.1', port=7497, clientId=client_id, timeout=10)
            self.chat_output.setText(f"Connected to Interactive Brokers with Client ID: {client_id}.")
        except Exception as e:
            error_message = (
                f"ERROR: Could not connect to IB. Ensure TWS/Gateway is running on port 7497 "
                f"(or your configured port). Error: {e}"
            )
            self.chat_output.setText(error_message)
            print(error_message) # Also print to console for debugging

    def is_connected(self):
        """Checks if the IB connection is active."""
        return self.ib.isConnected()

    def get_market_price(self, contract):
        """
        Gets the market price for a given contract using reqMktData.
        Handles reconnection attempts if disconnected.

        Args:
            contract (Contract): The ib_insync Contract object.

        Returns:
            float or str: The last traded price if available, otherwise 'N/A'.
        """
        if not self.is_connected():
            self.chat_output.append("Attempting to reconnect to IB for market data...")
            self._connect_to_ib() # Try to reconnect
            if not self.is_connected():
                return 'N/A' # If still not connected after retry

        try:
            # Qualify the contract before requesting market data
            qualified_contract = self.ib.qualifyContracts(contract)[0]
            
            # Request market data for the contract. Use snapshot=True for one-time fetch.
            ticker_data = self.ib.reqMktData(qualified_contract, '', True, False)
            self.ib.sleep(0.5) # Give some time for the data to arrive

            price = 'N/A'
            if ticker_data.last is not None:
                price = ticker_data.last
            elif ticker_data.close is not None:
                price = ticker_data.close
            elif ticker_data.bid is not None and ticker_data.ask is not None:
                price = (ticker_data.bid + ticker_data.ask) / 2
            elif ticker_data.bid is not None:
                price = ticker_data.bid
            elif ticker_data.ask is not None:
                price = ticker_data.ask

            self.ib.cancelMktData(qualified_contract) # Crucial to cancel subscriptions
            return price
        except Exception as e:
            print(f"Failed to get market price for {contract.symbol}: {e}")
            return 'N/A'

    def load_live_positions(self, ticker, ib_live_positions_table, ib_live_positions_label):
        """
        Loads and displays live open positions from IB for a specific ticker.

        Args:
            ticker (str): The ticker symbol to filter positions by.
            ib_live_positions_table (QTableWidget): The table widget to populate.
            ib_live_positions_label (QLabel): The label to update with status.
        """
        if not self.is_connected():
            ib_live_positions_table.setRowCount(1)
            ib_live_positions_table.setItem(0, 0, QTableWidgetItem("IB není připojeno."))
            ib_live_positions_table.setSpan(0, 0, 1, ib_live_positions_table.columnCount())
            ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: IB odpojeno')
            return

        ib_live_positions_table.setRowCount(0) # Clear previous data
        ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: Načítám...')
        QApplication.processEvents() # Update UI immediately to show "Načítám..."

        try:
            ib_all_open_positions = self.ib.reqPositions()
            self.ib.sleep(0.1) # Give IB a moment to send the positions

            positions_for_ticker = [p for p in ib_all_open_positions if p.contract.symbol == ticker]

            if not positions_for_ticker:
                ib_live_positions_table.setRowCount(1)
                ib_live_positions_table.setItem(0, 0, QTableWidgetItem(f"Žádné živé pozice z IB pro {ticker}."))
                ib_live_positions_table.setSpan(0, 0, 1, ib_live_positions_table.columnCount())
                ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: (Žádné)')
                return

            ib_live_positions_table.setRowCount(len(positions_for_ticker))

            processed_positions_data = []

            for i, p in enumerate(positions_for_ticker):
                contract = p.contract
                
                # Calculate market value and unrealized PnL
                market_value = "N/A"
                unrealized_pnl = "N/A"
                
                current_price = self.get_market_price(contract)

                if isinstance(current_price, (float, int)) and p.position is not None:
                    market_value = current_price * p.position
                    if p.avgCost is not None:
                        unrealized_pnl = (current_price - p.avgCost) * p.position
                    else:
                        unrealized_pnl = "N/A (Missing Avg Cost)"

                processed_positions_data.append({
                    'contract': contract,
                    'position': p.position,
                    'avgCost': p.avgCost,
                    'marketValue': market_value,
                    'unrealizedPnl': unrealized_pnl
                })
            
            for i, data in enumerate(processed_positions_data):
                self._populate_live_position_row(i, data, ib_live_positions_table)

            ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}:') # Update label after loading
        except Exception as e:
            ib_live_positions_table.setRowCount(1)
            ib_live_positions_table.setItem(0, 0, QTableWidgetItem(f"Chyba při načítání živých pozic: {e}"))
            ib_live_positions_table.setSpan(0, 0, 1, ib_live_positions_table.columnCount())
            ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: Chyba')

    def _populate_live_position_row(self, row_index, data, ib_live_positions_table):
        """
        Helper to populate a single row in the live positions table.

        Args:
            row_index (int): The row index in the table.
            data (dict): Dictionary containing position data.
            ib_live_positions_table (QTableWidget): The table widget to populate.
        """
        contract = data['contract']
        position_qty = data['position']
        avg_cost = data['avgCost']
        market_value = data['marketValue']
        unrealized_pnl = data['unrealizedPnl']

        symbol_item = QTableWidgetItem(contract.symbol)
        sec_type_item = QTableWidgetItem(contract.secType)
        right_item = QTableWidgetItem(contract.right if contract.secType == "OPT" else "")
        strike_item = QTableWidgetItem(str(contract.strike) if contract.secType == "OPT" else "")
        position_item = QTableWidgetItem(str(position_qty))
        
        market_value_item = QTableWidgetItem(f"{market_value:.2f}" if isinstance(market_value, float) else str(market_value))
        avg_cost_item = QTableWidgetItem(f"{avg_cost:.2f}" if isinstance(avg_cost, float) else "N/A")
        unrealized_pnl_item = QTableWidgetItem(f"{unrealized_pnl:.2f}" if isinstance(unrealized_pnl, float) else str(unrealized_pnl))

        ib_live_positions_table.setItem(row_index, 0, symbol_item)
        ib_live_positions_table.setItem(row_index, 1, sec_type_item)
        ib_live_positions_table.setItem(row_index, 2, right_item)
        ib_live_positions_table.setItem(row_index, 3, strike_item)
        ib_live_positions_table.setItem(row_index, 4, position_item)
        ib_live_positions_table.setItem(row_index, 5, market_value_item)
        ib_live_positions_table.setItem(row_index, 6, avg_cost_item)
        ib_live_positions_table.setItem(row_index, 7, unrealized_pnl_item)

    def calculate_current_unrealized_pnl(self, ticker, current_pnl_label):
        """
        Calculates and updates the current unrealized PnL for a given ticker
        from live IB positions.

        Args:
            ticker (str): The ticker symbol.
            current_pnl_label (QLabel): The QLabel to update with the PnL.
        """
        current_unrealized_pnl_total = 0.0
        if not self.is_connected():
            current_pnl_label.setText('Aktuální PnL (Otevřené pozice): IB odpojeno')
            return

        current_pnl_label.setText(f'Aktuální PnL ({ticker}): Načítám...')
        QApplication.processEvents()

        try:
            ib_open_positions = self.ib.reqPositions()
            self.ib.sleep(0.1)

            positions_for_current_pnl = [p for p in ib_open_positions if p.contract.symbol == ticker]

            for p in positions_for_current_pnl:
                current_price = self.get_market_price(p.contract)
                if isinstance(current_price, (float, int)) and p.avgCost is not None and p.position is not None:
                    unrealized_pnl_val = (current_price - p.avgCost) * p.position
                    current_unrealized_pnl_total += unrealized_pnl_val
                else:
                    print(f"Cannot calculate PnL for {p.contract.symbol}: missing data (price, avg cost or quantity).")
        except Exception as e:
            print(f"Error calculating current unrealized PnL: {e}")
            current_unrealized_pnl_total = "Error"
        
        if isinstance(current_unrealized_pnl_total, float):
            current_pnl_label.setText(f'Aktuální PnL ({ticker}): {current_unrealized_pnl_total:.2f} USD')
        else:
            current_pnl_label.setText(f'Aktuální PnL ({ticker}): {current_unrealized_pnl_total}')

