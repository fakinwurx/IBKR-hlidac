import sys
import math
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QComboBox, QHeaderView, QMessageBox
from PyQt6.QtGui import QColor # Import QColor for highlighting
from ib_insync import IB, Stock, Option, Position
import openai
from datetime import datetime
import sqlite3
import random # Import random for client ID

# Ensure load_open_positions.py exists if you still need its functionality.
# For this updated code, the "Otevřené pozice" button's functionality
# has been moved to directly query IB for live positions.
# import load_open_positions

# OpenAI API klíč
# Zde vložte svůj OpenAI API klíč.
openai.api_key = 'YOUR API KEY!' # Remember to replace this with your actual key!

class DeltaNeutralApp(QWidget):
    def __init__(self):
        super().__init__()

        self.ib = IB()
        self.positions = []
        self.sold_options = []  # To store sold options data (symbol, premium, etc.)

        # --- Initialize chat_output early for error messages ---
        # This part of the UI (chat_output) needs to be initialized before
        # attempting the IB connection, so it can display connection errors.
        self.chat_output = QTextEdit(self)
        self.chat_output.setPlaceholderText("Odpověď GPT se objeví zde.")
        self.chat_output.setReadOnly(True)
        # --------------------------------------------------------

        # Ensure IB connection is established when the app starts.
        # This is critical for fetching real-time data.
        try:
            # Connect to IB Gateway/TWS. Replace host/port if different.
            # Use a random client ID to avoid conflicts from previous sessions
            client_id = random.randint(1, 1000) # Generate a random client ID
            self.ib.connect('127.0.0.1', 7497, clientId=client_id)
            self.chat_output.setText(f"Connected to Interactive Brokers with Client ID: {client_id}.") # Success message
        except Exception as e:
            error_message = f"ERROR: Could not connect to IB. Ensure TWS/Gateway is running on port 7497 (or your configured port). Error: {e}"
            self.chat_output.setText(error_message)
            print(error_message) # Also print to console for debugging


        # Setup UI (the rest of initUI will now follow)
        self.initUI()

    def initUI(self):
        # Window setup
        self.setWindowTitle('Delta Neutral Strategie a OpenAI Chat')
        self.setGeometry(100, 100, 1000, 600)

        # Main Layout
        main_layout = QHBoxLayout()

        # Left side layout for positions table and details
        left_layout = QVBoxLayout()

        # Upper window with open positions (from DN database - strategy entries)
        self.positions_label = QTextEdit()
        self.positions_label.setReadOnly(True)
        self.positions_label.setMaximumHeight(40)  # Set maximum height
        self.positions_label.setMinimumHeight(20)  # Set minimum height
        self.positions_label.setPlainText('Otevřené Pozice (Strategie):')
        self.positions_label.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-size: 12pt;
                font-weight: bold;
            }
        """)
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(3)  # Ticker, Datum Vstup, Datum Výstup
        self.positions_table.setHorizontalHeaderLabels(['Ticker', 'Datum Vstup', 'Datum Výstup'])
        self.positions_table.cellClicked.connect(self.on_position_click)

        # Bottom window with selected position details
        self.details_label = QLabel('Detaily vybrané pozice:')
        self.details_text = QLabel('Vyberte pozici pro zobrazení detailů.')
        
        # Add summary table for closed positions
        self.summary_label = QLabel('Souhrn PnL uzavřených pozic (z historie obchodů):')
        self.summary_table = QTableWidget()
        self.summary_table.setMaximumHeight(120)  # **INCREASED HEIGHT HERE**

        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels([
            'Symbol', 'Celk. realizovaný PnL', 'Celk. čistá hotovost (Báze Ccy)', 'Celk. FX PnL' # Adjusted headers for clarity
        ])
        # Adjust column widths
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Symbol
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Realized PnL (Trade Ccy)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Net Cash (Base Ccy)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # FX PnL
        
        # Add break-even and current PnL labels ABOVE new live positions table
        self.delta_breakeven_label = QLabel('Break-even (Při otevření strategie): N/A')
        self.current_pnl_label = QLabel('Aktuální PnL (Otevřené pozice z IB): N/A')

        # New table for LIVE IB Open Positions details
        self.ib_live_positions_label = QLabel('Detailní živé pozice z IB:')
        self.ib_live_positions_table = QTableWidget()
        self.ib_live_positions_table.setColumnCount(8)
        self.ib_live_positions_table.setHorizontalHeaderLabels([
            'Symbol', 'Typ', 'Právo', 'Strike', 'Množství', 'Tržní hodnota', 'Prům. cena', 'Nerealizovaný PnL'
        ])
        # Adjust column widths for live positions
        live_header = self.ib_live_positions_table.horizontalHeader()
        live_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Symbol (narrowed)
        live_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # SecType
        live_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Right
        live_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Strike
        live_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Position
        live_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Market Value
        live_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Avg Cost
        live_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # Unrealized PnL


        # Add trade history table
        self.trade_history_label = QLabel('Historie obchodů pro vybraný Ticker:')
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(5) # Reduced to 5 columns as requested
        self.trade_history_table.setHorizontalHeaderLabels([
            'Datum', 'Symbol', 'Množství', 'Realizovaný PnL', 'Čistá Hotovost' # Renamed/simplified headers
        ])
        # Adjust column widths for trade history
        history_header = self.trade_history_table.horizontalHeader()
        history_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Datum
        history_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Symbol
        history_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Množství
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Realizovaný PnL
        history_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Net Cash (Trade Ccy)


        # Layout for buttons
        button_layout = QHBoxLayout()

        # Load Button (for DN positions from DB)
        load_dn_strategies_button = QPushButton('Načíst strategie (DB)')
        load_dn_strategies_button.clicked.connect(self.load_positions)
        button_layout.addWidget(load_dn_strategies_button)

        # New button to explicitly load live IB positions for the selected ticker
        load_live_ib_positions_button = QPushButton('Zobrazit živé pozice IB')
        load_live_ib_positions_button.clicked.connect(self.on_show_live_ib_positions_button_click)
        button_layout.addWidget(load_live_ib_positions_button)

        # Add all components to the left layout
        left_layout.addWidget(self.positions_label)
        left_layout.addWidget(self.positions_table)
        left_layout.addWidget(self.details_label)
        left_layout.addWidget(self.details_text)
        
        # Add new PnL/Breakeven labels
        left_layout.addWidget(self.delta_breakeven_label)
        left_layout.addWidget(self.current_pnl_label)
        
        # Add the new live IB positions table
        left_layout.addWidget(self.ib_live_positions_label)
        left_layout.addWidget(self.ib_live_positions_table)

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

        # self.chat_output is already initialized in __init__
        # self.chat_output = QTextEdit(self)
        # self.chat_output.setPlaceholderText("Odpověď GPT se objeví zde.")
        # self.chat_output.setReadOnly(True)

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
        right_layout.addWidget(self.chat_output) # Add the already initialized chat_output here

        # Add both side layouts to the main layout
        main_layout.addLayout(left_layout, 70)
        main_layout.addLayout(right_layout, 30)

        self.setLayout(main_layout)

    def load_positions(self):
        """Load open positions from IBFLEXQUERY.db database (DN table) and display them."""
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

    def on_show_live_ib_positions_button_click(self):
        """Handle click on 'Zobrazit živé pozice IB' button."""
        selected_rows = self.positions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Výběr pozice", "Prosím, vyberte strategii z tabulky 'Otevřené Pozice (Strategie)', abyste viděli její živé pozice z IB.")
            return
        
        # Assuming only one row can be selected for this action
        row = selected_rows[0].row()
        ticker = self.positions_table.item(row, 0).text()
        self.load_ib_live_positions(ticker)


    def get_market_price(self, contract):
        """Get the market price for the contract using reqMktData."""
        # Ensure IB connection is active before requesting market data
        if not self.ib.isConnected():
            try:
                # Use a random client ID for reconnect attempts too
                client_id = random.randint(1, 1000)
                self.ib.connect('127.0.0.1', 7497, clientId=client_id)
            except Exception as e:
                print(f"Failed to reconnect to IB: {e}")
                return 'N/A'
        
        # Qualify the contract before requesting market data
        # This is important for IB to recognize the contract fully
        try:
            self.ib.qualifyContracts(contract)
        except Exception as e:
            print(f"Failed to qualify contract {contract.symbol}: {e}")
            return 'N/A'

        ticker_data = self.ib.reqMktData(contract)
        self.ib.sleep(1)  # Give time for the data to update

        # Cancel market data subscription to avoid hitting limits
        self.ib.cancelMktData(contract) # Cancel using the contract object directly

        # Return the current price if available
        return ticker_data.last if ticker_data.last is not None else 'N/A'

    

    def load_ib_live_positions(self, ticker):
        """Loads and displays live open positions from IB for a specific ticker."""
        if not self.ib.isConnected():
            self.ib_live_positions_table.setRowCount(1)
            self.ib_live_positions_table.setItem(0, 0, QTableWidgetItem("IB není připojeno."))
            self.ib_live_positions_table.setSpan(0, 0, 1, self.ib_live_positions_table.columnCount())
            self.ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: IB odpojeno')
            return

        self.ib_live_positions_table.setRowCount(0) # Clear previous data
        self.ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: Načítám...')
        QApplication.processEvents() # Update UI immediately to show "Načítám..."

        try:
            # Request all open positions from IB
            ib_all_open_positions = self.ib.reqPositions()
            self.ib.sleep(0.1) # Give IB a moment to send the positions

            # Filter positions for the selected ticker
            positions_for_ticker = [p for p in ib_all_open_positions if p.contract.symbol == ticker]

            if not positions_for_ticker:
                self.ib_live_positions_table.setRowCount(1)
                self.ib_live_positions_table.setItem(0, 0, QTableWidgetItem(f"Žádné živé pozice z IB pro {ticker}."))
                self.ib_live_positions_table.setSpan(0, 0, 1, self.ib_live_positions_table.columnCount())
                self.ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: (Žádné)')
                return

            self.ib_live_positions_table.setRowCount(len(positions_for_ticker))

            processed_positions_data = []

            for i, p in enumerate(positions_for_ticker):
                contract = p.contract
                
                # Always attempt to qualify the contract and request market data
                # to ensure we get the latest prices for calculation.
                market_value = "N/A"
                unrealized_pnl = "N/A"
                avg_cost_display = "N/A" # For display, use None for calculation

                # Ensure avgCost is available for PnL calculation
                avg_cost_for_calc = p.avgCost

                try:
                    # Qualify the contract to ensure it's fully defined for market data
                    qualified_contract = self.ib.qualifyContracts(contract)[0]

                    # Request market data for the contract. Use snapshot=True for one-time fetch.
                    # 'genericTickList' can be empty for basic price data.
                    ticker_data = self.ib.reqMktData(qualified_contract, '', True, False)
                    self.ib.sleep(0.5) # Give some time for the data to arrive

                    if ticker_data.last is not None and p.position is not None:
                        market_value = ticker_data.last * p.position
                        if avg_cost_for_calc is not None:
                            unrealized_pnl = (ticker_data.last - avg_cost_for_calc) * p.position
                        else:
                            unrealized_pnl = "N/A (Chybí prům. cena)" # Can't calculate PnL without avgCost
                    
                    self.ib.cancelMktData(qualified_contract) # Crucial to cancel subscriptions

                except Exception as md_e:
                    print(f"Chyba při získávání tržních dat pro {contract.symbol}: {md_e}")
                    # Keep market_value/unrealized_pnl as N/A if data fetching fails

                # Store the data (using the original position object, but augmenting it for display)
                processed_positions_data.append({
                    'contract': contract,
                    'position': p.position,
                    'avgCost': p.avgCost, # Keep original avgCost
                    'marketValue': market_value,
                    'unrealizedPnl': unrealized_pnl
                })
            
            # Now, populate the table with the processed data
            for i, data in enumerate(processed_positions_data):
                self._populate_live_position_row(i, data)

            self.ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}:') # Update label after loading
        except Exception as e:
            self.ib_live_positions_table.setRowCount(1)
            self.ib_live_positions_table.setItem(0, 0, QTableWidgetItem(f"Chyba při načítání živých pozic: {e}"))
            self.ib_live_positions_table.setSpan(0, 0, 1, self.ib_live_positions_table.columnCount())
            self.ib_live_positions_label.setText(f'Detailní živé pozice z IB pro {ticker}: Chyba')

    def _populate_live_position_row(self, row_index, data):
        """Helper to populate a single row in the live positions table."""
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

        self.ib_live_positions_table.setItem(row_index, 0, symbol_item)
        self.ib_live_positions_table.setItem(row_index, 1, sec_type_item)
        self.ib_live_positions_table.setItem(row_index, 2, right_item)
        self.ib_live_positions_table.setItem(row_index, 3, strike_item)
        self.ib_live_positions_table.setItem(row_index, 4, position_item)
        self.ib_live_positions_table.setItem(row_index, 5, market_value_item)
        self.ib_live_positions_table.setItem(row_index, 6, avg_cost_item)
        self.ib_live_positions_table.setItem(row_index, 7, unrealized_pnl_item)

    def on_position_click(self, row, column):
        """Handle the selection of a position and display its details."""
        ticker = self.positions_table.item(row, 0).text()
        date_open = self.positions_table.item(row, 1).text()
        
        # Bezpečně získáme date_close. Pokud klíč (položka tabulky) neexistuje nebo je prázdný, použijeme prázdný řetězec.
        date_close_item = self.positions_table.item(row, 2)
        date_close = date_close_item.text() if date_close_item and date_close_item.text() else '' 

        # Vytvoříme slovník 'position' s tickerem, datem otevření a datem uzavření (pokud existuje)
        position = {'ticker': ticker, 'date_open': date_open, 'date_close': date_close}
        
        self.display_position_details(position)
        self.load_ib_live_positions(ticker)

    def display_position_details(self, position):
        """Display details for a selected strategy position and calculate summaries.
        
        This version uses 'YYYYMMDD' date format directly and converts to integer for SQL.
        Now includes 'C/P' (from putCall), 'Strike', and 'Avg Price' (from averagePrice)
        replacing 'Čistá Hotovost' in the historical trades table.
        """
        ticker = position['ticker']
        raw_date_open = position['date_open'] 
        raw_date_close = position.get('date_close', '') 

        date_open_int = None
        date_close_int = None

        try:
            date_open_int = int(raw_date_open)
        except ValueError:
            print(f"Chyba konverze: 'Datum otevření' '{raw_date_open}' není platné číslo pro YYYYMMDD.")
            date_open_int = raw_date_open

        if raw_date_close: 
            try:
                date_close_int = int(raw_date_close)
            except ValueError:
                print(f"Chyba konverze: 'Datum uzavření' '{raw_date_close}' není platné číslo pro YYYYMMDD.")
                date_close_int = raw_date_close

        details_text = f"Ticker: {ticker}\n"
        details_text += f"Datum otevření strategie: {raw_date_open}\n" 
        if raw_date_close: 
            details_text += f"Datum uzavření strategie: {raw_date_close}\n"
        self.details_text.setText(details_text)

        conn = None
        try:
            conn = sqlite3.connect('data/IBFlexQuery.db')
            cursor = conn.cursor()
            
            # --- Calculate and Display Current Unrealized PnL (from live IB positions) ---
            current_unrealized_pnl_total = 0.0
            
            if self.ib.isConnected():
                self.delta_breakeven_label.setText(f'Break-even (Při otevření pro {ticker}): Načítám...')
                self.current_pnl_label.setText(f'Aktuální PnL ({ticker}): Načítám...')
                QApplication.processEvents() 

                ib_open_positions = self.ib.reqPositions()
                self.ib.sleep(0.1) 

                positions_for_current_pnl = [p for p in ib_open_positions if p.contract.symbol == ticker]

                for p in positions_for_current_pnl:
                    current_price = None
                    try:
                        qualified_contract = self.ib.qualifyContracts(p.contract)[0]
                        ticker_data = self.ib.reqMktData(qualified_contract, '', True, False) 
                        self.ib.sleep(0.5) 

                        if ticker_data.last is not None:
                            current_price = ticker_data.last
                        elif ticker_data.close is not None:
                            current_price = ticker_data.close
                        elif ticker_data.bid is not None and ticker_data.ask is not None:
                            current_price = (ticker_data.bid + ticker_data.ask) / 2
                        elif ticker_data.bid is not None:
                            current_price = ticker_data.bid
                        elif ticker_data.ask is not None:
                            current_price = ticker_data.ask

                        if current_price is not None and p.avgCost is not None and p.position is not None:
                            unrealized_pnl_val = (current_price - p.avgCost) * p.position
                            current_unrealized_pnl_total += unrealized_pnl_val
                        else:
                            print(f"Nelze vypočítat PnL pro {p.contract.symbol}: chybí data (cena, průměrná cena nebo množství).")
                        
                        self.ib.cancelMktData(qualified_contract) 

                    except Exception as md_e:
                        print(f"Chyba při získávání tržních dat pro PnL {p.contract.symbol}: {md_e}")
                            
            else:
                self.delta_breakeven_label.setText('Break-even (Při otevření): IB odpojeno')
                self.current_pnl_label.setText('Aktuální PnL (Otevřené pozice): IB odpojeno')
            
            self.current_pnl_label.setText(f'Aktuální PnL ({ticker}): {current_unrealized_pnl_total:.2f} USD')

            self.delta_breakeven_label.setText(f'Break-even (Při otevření pro {ticker}): N/A (Vyžaduje detailní data o legách strategie)')

            # --- Načtení a filtrování detailů obchodů z IBFlexQueryCZK (historické obchody) ---
            # DŮLEŽITÉ: Nyní vybíráme "putCall", "strike" a "averagePrice"
            sql_query = '''
                SELECT
                    "tradeDate",
                    "underlyingSymbol",
                    "description",
                    "putCall",         -- NOVÝ SLOUPEC (index 3 v `trade`)
                    "strike",            -- NOVÝ SLOUPEC (index 4 v `trade`)
                    "averagePrice",      -- NOVÝ SLOUPEC (index 5 v `trade`)
                    SUM("quantity") as TotalQuantity,
                    ROUND(SUM("ibCommission"), 2) AS TotalIbCommission,
                    ROUND(SUM("netCash"), 2) AS TotalNetCash,
                    ROUND(SUM("netCashInBase"), 2) AS TotalNetCashInBase,
                    ROUND(SUM("fifoPnlRealized"), 2) AS TotalFifoPnlRealized,
                    ROUND(SUM("capitalGainsPnl"), 2) AS TotalCapitalGainsPnl,
                    ROUND(SUM("fxPnl"), 2) AS TotalFxPnl
                FROM "IBFlexQueryCZK"
                WHERE "underlyingSymbol" = ? AND "tradeDate" >= ?
            '''
            params = [ticker, date_open_int]

            if date_close_int is not None: 
                sql_query += ' AND "tradeDate" <= ?'
                params.append(date_close_int)
            
            # DŮLEŽITÉ: Do GROUP BY musíme přidat nové sloupce, které vybíráme
            sql_query += ' GROUP BY "tradeDate", "description", "underlyingSymbol", "putCall", "strike", "averagePrice" ORDER BY "tradeDate"'

            # --- LADÍCÍ VÝPISY ---
            print(f"DEBUG: FINAL SQL Query for historical trades:\n{sql_query}")
            print(f"DEBUG: FINAL SQL Params for historical trades: {params}")
            # --- KONEC LADÍCÍCH VÝPISŮ ---

            cursor.execute(sql_query, tuple(params))
            
            trades = cursor.fetchall()

            # --- LADÍCÍ VÝPISY ---
            print(f"DEBUG: Number of historical trades fetched: {len(trades)}")
            if len(trades) == 0:
                print("DEBUG: Nebyly nalezeny žádné obchody pro daná kritéria. Znovu zkontrolujte data v DB a rozsahy dat.")
            # --- KONEC LADÍCÍCH VÝPISŮ ---

            # --- Výpočet souhrnného PnL z načtených obchodů (zaměřeno na realizované PnL) ---
            # Indexy se posunou kvůli novým sloupcům v SELECTu (putCall, strike, averagePrice)
            # Tyto summary se nemění, jen jejich zdrojové indexy
            # fifoPnlRealized je nyní na indexu 10 (původně 7)
            # netCashInBase je nyní na indexu 9 (původně 6)
            # fxPnl je nyní na indexu 12 (původně 9)
            total_realized_pnl_trade_currency = 0.0
            total_net_cash_base_currency_sum = 0.0
            total_fx_pnl_summary = 0.0
            
            for trade in trades:
                total_realized_pnl_trade_currency += float(trade[10] if trade[10] is not None else 0.0) 
                total_net_cash_base_currency_sum += float(trade[9] if trade[9] is not None else 0.0) 
                total_fx_pnl_summary += float(trade[12] if trade[12] is not None else 0.0) 

            self.summary_table.setRowCount(1)
            self.summary_table.setItem(0, 0, QTableWidgetItem(str(ticker)))
            self.summary_table.setItem(0, 1, QTableWidgetItem(f"{total_realized_pnl_trade_currency:.2f}"))
            self.summary_table.setItem(0, 2, QTableWidgetItem(f"{total_net_cash_base_currency_sum:.2f}"))
            self.summary_table.setItem(0, 3, QTableWidgetItem(f"{total_fx_pnl_summary:.2f}"))


            # --- Naplnění tabulky historie obchodů s zvýrazněním ---
            # NOVÝ POČET HLAVIČEK TABULKY: 7
            # Datum, Symbol, C/P, Strike, Množství, Realizovaný PnL, Avg Price
            self.trade_history_table.setColumnCount(7) 
            # Nastavení hlaviček (pokud je nemáte nastaveny jinde)
            self.trade_history_table.setHorizontalHeaderLabels([
                "Datum", "Symbol", "C/P", "Strike", "Množství", "Realizovaný PnL", "Avg Price"
            ])

            self.trade_history_table.setRowCount(len(trades))
            yellow_color = QColor(255, 255, 150) 
            green_color = QColor(190, 255, 190) 

            for i, trade in enumerate(trades):
                # DŮLEŽITÉ: Změnily se indexy, protože jsme přidali 3 sloupce na začátek SELECTu
                trade_date = trade[0]
                symbol = trade[1]
                description = trade[2] # Popis (pro highlighting)
                put_call = trade[3]       # NOVÝ INDEX (původně description byl index 2)
                strike = trade[4]            # NOVÝ INDEX
                average_price = trade[5]     # NOVÝ INDEX
                quantity = trade[6]          # Posunutý (původně 3)
                commission = trade[7]        # Posunutý (původně 4)
                net_cash = trade[8]          # Posunutý (původně 5) - Ponechán pro případ, že ho budeme chtít použít jinde
                net_cash_base = trade[9]     # Posunutý (původně 6)
                fifo_pnl = trade[10]         # Posunutý (původně 7)
                cap_gains_pnl = trade[11]    # Posunutý (původně 8)
                fx_pnl = trade[12]           # Posunutý (původně 9)
                
                # Vytvoření QTableWidgetItem pro každou buňku, ošetření None hodnot
                date_item = QTableWidgetItem(str(trade_date if trade_date is not None else 'N/A'))
                symbol_item = QTableWidgetItem(str(symbol if symbol is not None else 'N/A'))
                
                # Nové položky pro C/P, Strike, Avg Price
                # put_call bude buď 'C' nebo 'P' nebo None
                put_call_item = QTableWidgetItem(str(put_call if put_call is not None else ''))
                strike_item = QTableWidgetItem(str(strike if strike is not None else ''))
                # Formátování average_price na 2 desetinná místa
                average_price_item = QTableWidgetItem(f"{average_price:.2f}" if isinstance(average_price, (float, int)) and average_price is not None else str(average_price if average_price is not None else 'N/A'))

                quantity_item = QTableWidgetItem(str(quantity if quantity is not None else 0))
                pnl_item = QTableWidgetItem(str(fifo_pnl if fifo_pnl is not None else 0.0))
                
                # Uložení všech položek pro aktuální řádek pro aplikaci barvy
                current_row_items = [
                    date_item, symbol_item, put_call_item, strike_item, quantity_item, pnl_item, average_price_item
                ]

                # Logika zvýraznění: Opce a pozitivní PnL
                # Používáme put_call pro detekci opce místo description
                is_option_trade = (put_call in ("C", "P") if put_call is not None else False)
                
                realized_pnl_val = float(fifo_pnl) if fifo_pnl is not None else 0.0

                if is_option_trade:
                    # Žlutá pro put s téměř nulovým PnL (potenciální přiřazení)
                    if put_call == "P" and abs(realized_pnl_val) < 0.01:
                        for item in current_row_items:
                            item.setBackground(yellow_color)
                    # Zelená pro ostatní opce s pozitivním PnL
                    elif realized_pnl_val > 0:
                        for item in current_row_items:
                            item.setBackground(green_color)
                # Pro ne-opční obchody nebo opce nesplňující kritéria pro žlutou, použij zelenou, pokud je PnL pozitivní
                elif realized_pnl_val > 0:
                    for item in current_row_items:
                        item.setBackground(green_color)
                # Pokud je PnL negativní nebo nulové (a není to žlutě zvýrazněná opce), žádná specifická barva
                else:
                    for item in current_row_items:
                        item.setBackground(QColor(255, 255, 255)) # Bílé nebo výchozí pozadí

                # Nastavení položek do tabulky historie obchodů (POŘADÍ SE ZMĚNILO A PŘIDALY SE NOVÉ SLUPCE!)
                self.trade_history_table.setItem(i, 0, date_item)
                self.trade_history_table.setItem(i, 1, symbol_item)
                self.trade_history_table.setItem(i, 2, put_call_item)        # C/P
                self.trade_history_table.setItem(i, 3, strike_item)          # Strike
                self.trade_history_table.setItem(i, 4, quantity_item)        # Množství
                self.trade_history_table.setItem(i, 5, pnl_item)             # Realizovaný PnL
                self.trade_history_table.setItem(i, 6, average_price_item)   # Avg Price
                
        except Exception as e:
            print(f"Error in display_position_details: {e}")
            self.summary_table.setRowCount(1)
            self.summary_table.setItem(0, 0, QTableWidgetItem(f"Chyba při načítání dat: {e}"))
            self.trade_history_table.setRowCount(1)
            self.trade_history_table.setItem(0, 0, QTableWidgetItem(f"Chyba při načítání dat: {e}"))
            self.delta_breakeven_label.setText('Break-even (Při otevření): Chyba')
            self.current_pnl_label.setText('Aktuální PnL (Otevřené pozice): Chyba')
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
        # Ensure IB connection is active
        if not self.ib.isConnected():
            try:
                # Use a random client ID for reconnect attempts too
                client_id = random.randint(1, 1000)
                self.ib.connect('127.0.0.1', 7497, clientId=client_id)
            except Exception as e:
                print(f"Failed to reconnect to IB for IV: {e}")
                return "N/A"

        # Qualify the contract
        try:
            self.ib.qualifyContracts(option_contract)
        except Exception as e:
            print(f"Failed to qualify option contract {option_contract.symbol}: {e}")
            return 'N/A'

        # Request market data for the option
        ticker_data = self.ib.reqMktData(option_contract, genericTickList="100", snapshot=True)
        self.ib.sleep(1)  # Give time for data to update

        # Cancel market data subscription
        self.ib.cancelMktData(option_contract)

        option_price = ticker_data.last
        strike = option_contract.strike
        underlying_price = ticker_data.underlyingLast if hasattr(ticker_data, 'underlyingLast') else None
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
        # Ensure IB connection is active
        if not self.ib.isConnected():
            try:
                # Use a random client ID for reconnect attempts too
                client_id = random.randint(1, 1000)
                self.ib.connect('127.0.0.1', 7497, clientId=client_id)
            except Exception as e:
                print(f"Failed to reconnect to IB for 30-day IV: {e}")
                return "N/A"

        # Qualify the contract
        try:
            self.ib.qualifyContracts(option_contract)
        except Exception as e:
            print(f"Failed to qualify option contract for 30-day IV: {e}")
            return 'N/A'

        historical_data = self.ib.reqHistoricalData(option_contract, endDateTime='', durationStr='30 D', barSizeSetting='1 day', whatToShow='TRADES', useRTH=True)
        self.ib.sleep(0.5) # Give time for data

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
            
            # Ensure IB connection is active before getting current time
            if not self.ib.isConnected():
                try:
                    # Use a random client ID for reconnect attempts too
                    client_id = random.randint(1, 1000)
                    self.ib.connect('127.0.0.1', 7497, clientId=client_id)
                except Exception as e:
                    print(f"Failed to reconnect to IB for current time: {e}")
                    return 0.0 # Return 0 or handle error appropriately

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
    # It's good practice to disconnect from IB when the app closes
    def cleanup():
        if window.ib.isConnected():
            window.ib.disconnect()
            print("Disconnected from Interactive Brokers.")
    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())
