# ib_manager.py
import random
from ib_insync import IB, Stock, Option, Position
from PyQt6.QtWidgets import QApplication, QTableWidgetItem
from PyQt6.QtGui import QColor
import math # Importujeme modul math pro práci s NaN

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
            # Use a short timeout for the initial connection attempt
            self.ib.connect(host='127.0.0.1', port=7497, clientId=client_id, timeout=5)
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

    def get_market_data_for_contract(self, contract):
        """
        Gets comprehensive market data (last, bid, ask, close) for a given contract.
        Handles reconnection attempts if disconnected.

        Args:
            contract (Contract): The ib_insync Contract object.

        Returns:
            dict: A dictionary containing 'last', 'bid', 'ask', 'close' (float or None),
                  'best_market_price' (float or 'N/A' for general market value),
                  and 'multiplier' (float, defaults to 1.0).
        """
        if not self.is_connected():
            self.chat_output.append("Attempting to reconnect to IB for market data...")
            self._connect_to_ib() # Try to reconnect
            if not self.is_connected():
                print("DEBUG: Still not connected after reconnect attempt.")
                return {'last': None, 'bid': None, 'ask': None, 'close': None, 'best_market_price': 'N/A', 'multiplier': 1.0}

        try:
            # IMPORTANT: Qualify the contract to ensure multiplier is populated for options
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                print(f"DEBUG: Failed to qualify contract {contract.symbol}. No qualified contracts returned.")
                return {'last': None, 'bid': None, 'ask': None, 'close': None, 'best_market_price': 'N/A', 'multiplier': 1.0}
            qualified_contract = qualified_contracts[0]
            
            ticker_data = self.ib.reqMktData(qualified_contract, '', True, False)
            self.ib.sleep(1.0) # Increased sleep time to give more opportunity for market data to arrive.

            # Extract all relevant prices and handle NaN explicitly
            last_price = ticker_data.last if ticker_data.last is not None and not math.isnan(ticker_data.last) else None
            bid_price = ticker_data.bid if ticker_data.bid is not None and not math.isnan(ticker_data.bid) else None
            ask_price = ticker_data.ask if ticker_data.ask is not None and not math.isnan(ticker_data.ask) else None
            close_price = ticker_data.close if ticker_data.close is not None and not math.isnan(ticker_data.close) else None

            # Determine the 'best_market_price' for general display/market value
            # Prioritizing Last -> Mid -> Bid -> Ask -> Close
            best_market_price = 'N/A'
            if last_price is not None and last_price != 0.0:
                best_market_price = last_price
            elif bid_price is not None and ask_price is not None and bid_price != 0.0 and ask_price != 0.0:
                best_market_price = (bid_price + ask_price) / 2
            elif bid_price is not None and bid_price != 0.0:
                best_market_price = bid_price
            elif ask_price is not None and ask_price != 0.0:
                best_market_price = ask_price
            elif close_price is not None and close_price != 0.0:
                best_market_price = close_price
            
            print(f"DEBUG: {contract.symbol} - Fetched market data: Last={last_price}, Bid={bid_price}, Ask={ask_price}, Close={close_price}, Best={best_market_price}")

            self.ib.cancelMktData(qualified_contract) # Crucial to cancel subscriptions

            # Explicitly convert multiplier to float to prevent TypeError
            multiplier = 1.0 # Default to 1.0 (float)
            if hasattr(qualified_contract, 'multiplier') and qualified_contract.multiplier is not None:
                try:
                    multiplier = float(qualified_contract.multiplier)
                except ValueError:
                    print(f"WARNING: Multiplier for {contract.symbol} is not a valid number: {qualified_contract.multiplier}. Defaulting to 1.0.")
                    multiplier = 1.0
            print(f"DEBUG: {contract.symbol} - Final Multiplier (type {type(multiplier)}): {multiplier}")

            return {
                'last': last_price,
                'bid': bid_price,
                'ask': ask_price,
                'close': close_price,
                'best_market_price': best_market_price,
                'multiplier': multiplier
            }
        except Exception as e:
            print(f"Failed to get market data for {contract.symbol}: {e}")
            self.chat_output.append(f"Chyba při získávání tržních dat pro {contract.symbol}: {e}")
            return {'last': None, 'bid': None, 'ask': None, 'close': None, 'best_market_price': 'N/A', 'multiplier': 1.0}

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
            print("DEBUG: load_live_positions: IB not connected.")
            return

        ib_live_positions_table.setRowCount(0) # Clear previous data
        ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: Načítám...')
        QApplication.processEvents() # Update UI immediately to show "Načítám..."

        try:
            ib_all_open_positions = self.ib.reqPositions()
            self.ib.sleep(0.1) # Give IB a moment to send the positions

            positions_for_ticker = [p for p in ib_all_open_positions if p.contract.symbol == ticker]
            print(f"DEBUG: load_live_positions: Found {len(positions_for_ticker)} IB positions for ticker {ticker}.")

            if not positions_for_ticker:
                ib_live_positions_table.setRowCount(1)
                ib_live_positions_table.setItem(0, 0, QTableWidgetItem(f"Žádné živé pozice z IB pro {ticker}."))
                ib_live_positions_table.setSpan(0, 0, 1, ib_live_positions_table.columnCount())
                ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: (Žádné)')
                print(f"DEBUG: load_live_positions: No live IB positions found for {ticker}.")
                return

            ib_live_positions_table.setRowCount(len(positions_for_ticker))

            processed_positions_data = []

            for i, p in enumerate(positions_for_ticker):
                contract = p.contract
                print(f"\nDEBUG: Processing IB position {i+1}/{len(positions_for_ticker)}:")
                print(f"  Contract: {contract.symbol} ({contract.secType}) - {contract.right} {contract.strike}")
                print(f"  Raw Position: {p.position}, Raw AvgCost: {p.avgCost}")
                
                market_value = "N/A"
                unrealized_pnl = "N/A"
                
                # Get comprehensive market data
                market_data = self.get_market_data_for_contract(contract)
                # Define current_market_price here for use in this function
                current_market_price = market_data['best_market_price'] 
                print(f"  DEBUG: Market data for {contract.symbol}: {market_data}") # Updated print
                
                # Get multiplier for options, default to 1.0 for stocks/futures
                multiplier = market_data['multiplier'] # Now guaranteed to be a float
                print(f"  Contract Multiplier (from market_data): {multiplier}")


                # Ensure avgCost is a number for calculation
                avg_cost_for_calc = p.avgCost if p.avgCost is not None else 0.0
                if not isinstance(avg_cost_for_calc, (float, int)):
                    print(f"  WARNING: p.avgCost is not a number for {contract.symbol} ({p.avgCost}). Using 0.0 for calculation.")
                    avg_cost_for_calc = 0.0

                # Ensure position is a number for calculation
                position_qty_for_calc = p.position if p.position is not None else 0.0
                if not isinstance(position_qty_for_calc, (float, int)):
                    print(f"  WARNING: p.position is not a number for {contract.symbol} ({p.position}). Using 0.0 for calculation.")
                    position_qty_for_calc = 0.0


                # Determine the 'closing price' per share for PnL calculation
                pnl_calculation_price_per_share = None
                
                # Prioritize Mid -> Last -> Best_market_price for PnL calculation
                if market_data['bid'] is not None and market_data['ask'] is not None and \
                   market_data['bid'] != 0.0 and market_data['ask'] != 0.0:
                    pnl_calculation_price_per_share = (market_data['bid'] + market_data['ask']) / 2
                    print(f"  DEBUG: PnL Price per share (preferring Mid): {pnl_calculation_price_per_share}")
                elif market_data['last'] is not None and market_data['last'] != 0.0:
                    pnl_calculation_price_per_share = market_data['last']
                    print(f"  DEBUG: PnL Price per share (Mid not available, falling back to Last): {pnl_calculation_price_per_share}")
                elif isinstance(market_data['best_market_price'], (float, int)):
                    pnl_calculation_price_per_share = market_data['best_market_price']
                    print(f"  DEBUG: PnL Price per share (Last not available, falling back to Best Market Price): {pnl_calculation_price_per_share}")
                else:
                    print(f"  DEBUG: No valid PnL calculation price found for {contract.symbol}. All fallbacks failed.")
                
                
                if position_qty_for_calc > 0: # Long position (bought asset)
                    if isinstance(pnl_calculation_price_per_share, (float, int)):
                        # PnL for long position: (Current Value per contract - Initial Cost per contract) * number of contracts
                        unrealized_pnl = ((pnl_calculation_price_per_share * multiplier) - avg_cost_for_calc) * position_qty_for_calc
                        print(f"  Calculated Unrealized PnL (Long): {unrealized_pnl:.2f}")
                    else:
                        print(f"  WARNING: PnL calculation price per share for Long {contract.symbol} is not a number: {pnl_calculation_price_per_share}")

                elif position_qty_for_calc < 0: # Short position (sold asset)
                    if isinstance(pnl_calculation_price_per_share, (float, int)):
                        # PnL for short position: (Initial Credit per contract - Current Cost to Close per contract) * number of contracts
                        # Opraveno: Multiplikátor se aplikuje na celý rozdíl, nikoli jen na aktuální cenu
                        unrealized_pnl = (avg_cost_for_calc - pnl_calculation_price_per_share) * abs(position_qty_for_calc) * multiplier
                        print(f"  Calculated Unrealized PnL (Short): {unrealized_pnl:.2f}")
                    else:
                        print(f"  WARNING: PnL calculation price per share for Short {contract.symbol} is not a number: {pnl_calculation_price_per_share}")
                else: # Position is 0
                    unrealized_pnl = 0.0
                
                # --- Market Value Calculation ---
                if isinstance(current_market_price, (float, int)) and position_qty_for_calc is not None:
                    market_value = current_market_price * position_qty_for_calc * multiplier # Apply multiplier to market value too
                    print(f"  Calculated Market Value: {market_value:.2f}")
                else:
                    print(f"  Skipping Market Value calculation: current_market_price ({current_market_price}) not float/int or position ({position_qty_for_calc}) is None.")
                    market_value = "N/A" # Ensure it remains N/A if not calculable


                processed_positions_data.append({
                    'contract': contract,
                    'position': p.position, # Keep original p.position for table display
                    'avgCost': p.avgCost, # Keep original avgCost for table display
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
            self.chat_output.append(f"Chyba v IBManager.load_live_positions: {e}")
            print(f"DEBUG: Exception in load_live_positions: {e}")


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
        
        # Format numerical values to 2 decimal places, keep "N/A" for others
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
            print("DEBUG: calculate_current_unrealized_pnl: IB not connected.")
            return

        current_pnl_label.setText(f'Aktuální PnL ({ticker}): Načítám...')
        QApplication.processEvents()

        try:
            ib_open_positions = self.ib.reqPositions()
            self.ib.sleep(0.1)

            positions_for_current_pnl = [p for p in ib_open_positions if p.contract.symbol == ticker]
            print(f"DEBUG: calculate_current_unrealized_pnl: Found {len(positions_for_current_pnl)} IB positions for PnL for ticker {ticker}.")

            for i, p in enumerate(positions_for_current_pnl):
                print(f"  DEBUG: Calculating PnL for: {p.contract.symbol} - Position: {p.position}, AvgCost: {p.avgCost}")
                
                market_data = self.get_market_data_for_contract(p.contract)
                # Define current_market_price here for use in this function
                current_market_price = market_data['best_market_price'] 
                print(f"  DEBUG: Market data for PnL {p.contract.symbol}: {market_data}")

                # Get multiplier for options, default to 1.0 for stocks/futures
                multiplier = market_data['multiplier'] # Now guaranteed to be a float
                print(f"  Contract Multiplier: {multiplier}")


                # Ensure avgCost is a number for calculation
                # For options, p.avgCost often comes as the total cost per contract (Avg Price * Multiplier)
                avg_cost_for_calc = p.avgCost if p.avgCost is not None else 0.0
                if not isinstance(avg_cost_for_calc, (float, int)):
                    print(f"  WARNING: p.avgCost is not a number for {p.contract.symbol} ({p.avgCost}). Using 0.0 for calculation.")
                    avg_cost_for_calc = 0.0

                # Ensure position is a number for calculation
                position_qty_for_calc = p.position if p.position is not None else 0.0
                if not isinstance(position_qty_for_calc, (float, int)):
                    print(f"  WARNING: p.position is not a number for {p.contract.symbol} ({p.position}). Using 0.0 for calculation.")
                    position_qty_for_calc = 0.0

                # Determine the 'closing price' per share for PnL calculation based on position direction
                pnl_calculation_price_per_share = None
                unrealized_pnl_val = 0.0 # Default to 0
                
                # Prioritize Mid -> Last -> Best_market_price for PnL calculation
                if market_data['bid'] is not None and market_data['ask'] is not None and \
                   market_data['bid'] != 0.0 and market_data['ask'] != 0.0:
                    pnl_calculation_price_per_share = (market_data['bid'] + market_data['ask']) / 2
                    print(f"  DEBUG: PnL Price per share (preferring Mid): {pnl_calculation_price_per_share}")
                elif market_data['last'] is not None and market_data['last'] != 0.0:
                    pnl_calculation_price_per_share = market_data['last']
                    print(f"  DEBUG: PnL Price per share (Mid not available, falling back to Last): {pnl_calculation_price_per_share}")
                elif isinstance(current_market_price, (float, int)): # Fallback to best_market_price
                     pnl_calculation_price_per_share = current_market_price
                     print(f"  DEBUG: PnL Price per share (Last not available, falling back to Best Market Price): {pnl_calculation_price_per_share}")
                else:
                    print(f"  DEBUG: No valid PnL calculation price found for {p.contract.symbol}. All fallbacks failed.")
                
                
                if position_qty_for_calc > 0: # Long position (bought asset)
                    if isinstance(pnl_calculation_price_per_share, (float, int)):
                        # PnL for long position: (Current Value per contract - Initial Cost per contract) * number of contracts
                        unrealized_pnl_val = ((pnl_calculation_price_per_share * multiplier) - avg_cost_for_calc) * position_qty_for_calc
                        print(f"  Calculated PnL (Long): {unrealized_pnl_val:.2f}")
                    else:
                        print(f"  WARNING: PnL calculation price per share for Long {p.contract.symbol} is not a number: {pnl_calculation_price_per_share}")

                elif position_qty_for_calc < 0: # Short position (sold asset)
                    if isinstance(pnl_calculation_price_per_share, (float, int)):
                        # PnL for short position: (Initial Credit per contract - Current Cost to Close per contract) * number of contracts
                        # Opraveno: Multiplikátor se aplikuje na celý rozdíl, nikoli jen na aktuální cenu
                        unrealized_pnl_val = (avg_cost_for_calc - pnl_calculation_price_per_share) * abs(position_qty_for_calc) * multiplier
                        print(f"  Calculated PnL (Short): {unrealized_pnl_val:.2f}")
                    else:
                        print(f"  WARNING: PnL calculation price per share for Short {p.contract.symbol} is not a number: {pnl_calculation_price_per_share}")
                else: # Position is 0
                    unrealized_pnl_val = 0.0
                
                current_unrealized_pnl_total += (unrealized_pnl_val if isinstance(unrealized_pnl_val, float) else 0.0)
                print(f"  DEBUG: PnL component for {p.contract.symbol}: {unrealized_pnl_val:.2f}")

        except Exception as e:
            print(f"Chyba při získávání tržních dat pro PnL {p.contract.symbol}: {e}")
            self.chat_output.append(f"Chyba v IBManager.calculate_current_unrealized_pnl: {e}")
            current_unrealized_pnl_total = "Chyba" # Indicate error to user
            print(f"DEBUG: Exception in calculate_current_unrealized_pnl: {e}")

        if isinstance(current_unrealized_pnl_total, float):
            current_pnl_label.setText(f'Aktuální PnL ({ticker}): {current_unrealized_pnl_total:.2f} USD')
        else:
            current_pnl_label.setText(f'Aktuální PnL ({ticker}): {current_unrealized_pnl_total}') # Display "Chyba"