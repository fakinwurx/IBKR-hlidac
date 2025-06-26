# database_manager.py
import sqlite3
from PyQt6.QtWidgets import QTableWidgetItem, QApplication
from PyQt6.QtGui import QColor
import os # For checking file existence

class DatabaseManager:
    def __init__(self, db_path, chat_output_widget):
        """
        Initializes the DatabaseManager.

        Args:
            db_path (str): The path to the SQLite database file.
            chat_output_widget (QTextEdit): Reference to the QTextEdit widget
                                            to display messages/errors.
        """
        self.db_path = db_path
        self.chat_output = chat_output_widget

        # Ensure the database file exists before trying to connect
        if not os.path.exists(self.db_path):
            self.chat_output.append(f"ERROR: Database file not found at '{self.db_path}'.")
            print(f"ERROR: Database file not found at '{self.db_path}'.")

    def load_dn_positions(self, positions_table):
        """
        Loads open positions from the 'DN' table in the database
        and displays them in the provided QTableWidget.

        Args:
            positions_table (QTableWidget): The table widget to populate.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Query to get open positions (where DateClose is NULL or empty)
            cursor.execute('''
                SELECT Ticker, DateOpen, DateClose
                FROM DN
                WHERE DateClose IS NULL OR DateClose = ''
            ''')
            
            positions = cursor.fetchall()
            
            # Populate the positions table
            positions_table.setRowCount(len(positions))
            for i, position in enumerate(positions):
                ticker, date_open, date_close = position
                
                # Add the row to the table
                positions_table.setItem(i, 0, QTableWidgetItem(str(ticker)))
                positions_table.setItem(i, 1, QTableWidgetItem(str(date_open)))
                positions_table.setItem(i, 2, QTableWidgetItem(str(date_close) if date_close else ''))

            conn.close()
        except sqlite3.Error as e:
            self.chat_output.setText(f"Chyba při načítání pozic z DB: {e}")
            print(f"Error loading positions from DB: {e}")
        except Exception as e:
            self.chat_output.setText(f"Neočekávaná chyba při načítání pozic z DB: {e}")
            print(f"Unexpected error loading positions from DB: {e}")

    def load_trade_history_and_summary(self, position, summary_table, trade_history_table):
        """
        Loads historical trades for a selected ticker and date range from the database,
        calculates PnL summaries, and populates the summary and history tables.

        Args:
            position (dict): Dictionary containing 'ticker', 'date_open', 'date_close'.
            summary_table (QTableWidget): The table widget for PnL summary.
            trade_history_table (QTableWidget): The table widget for detailed trade history.
        """
        ticker = position['ticker']
        raw_date_open = position['date_open']
        raw_date_close = position.get('date_close', '')

        date_open_int = None
        date_close_int = None

        try:
            date_open_int = int(raw_date_open)
        except ValueError:
            self.chat_output.append(f"Chyba konverze: 'Datum otevření' '{raw_date_open}' není platné číslo pro YYYYMMDD.")
            date_open_int = raw_date_open # Keep original if conversion fails

        if raw_date_close:
            try:
                date_close_int = int(raw_date_close)
            except ValueError:
                self.chat_output.append(f"Chyba konverze: 'Datum uzavření' '{raw_date_close}' není platné číslo pro YYYYMMDD.")
                date_close_int = raw_date_close # Keep original if conversion fails

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # SQL query to fetch trade details with new columns for options
            sql_query = '''
                SELECT
                    "tradeDate",
                    "underlyingSymbol",
                    "description",
                    "putCall",
                    "strike",
                    "averagePrice",
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

            if date_close_int is not None and date_close_int != '':
                sql_query += ' AND "tradeDate" <= ?'
                params.append(date_close_int)
            
            sql_query += ' GROUP BY "tradeDate", "description", "underlyingSymbol", "putCall", "strike", "averagePrice" ORDER BY "tradeDate"'

            cursor.execute(sql_query, tuple(params))
            
            trades = cursor.fetchall()

            # Calculate and populate summary table
            total_realized_pnl_trade_currency = 0.0
            total_net_cash_base_currency_sum = 0.0
            total_fx_pnl_summary = 0.0
            
            for trade in trades:
                # Ensure correct indices after adding putCall, strike, averagePrice
                total_realized_pnl_trade_currency += float(trade[10] if trade[10] is not None else 0.0)
                total_net_cash_base_currency_sum += float(trade[9] if trade[9] is not None else 0.0)
                total_fx_pnl_summary += float(trade[12] if trade[12] is not None else 0.0)

            summary_table.setRowCount(1)
            summary_table.setItem(0, 0, QTableWidgetItem(str(ticker)))
            summary_table.setItem(0, 1, QTableWidgetItem(f"{total_realized_pnl_trade_currency:.2f}"))
            summary_table.setItem(0, 2, QTableWidgetItem(f"{total_net_cash_base_currency_sum:.2f}"))
            summary_table.setItem(0, 3, QTableWidgetItem(f"{total_fx_pnl_summary:.2f}"))

            # Populate trade history table with highlighting
            trade_history_table.setColumnCount(7) # Update column count
            trade_history_table.setHorizontalHeaderLabels([
                "Datum", "Symbol", "C/P", "Strike", "Množství", "Realizovaný PnL", "Avg Price"
            ])
            trade_history_table.setRowCount(len(trades))
            
            yellow_color = QColor(255, 255, 150)
            green_color = QColor(190, 255, 190)

            for i, trade in enumerate(trades):
                trade_date = trade[0]
                symbol = trade[1]
                description = trade[2] # Used for highlighting logic
                put_call = trade[3]
                strike = trade[4]
                average_price = trade[5]
                quantity = trade[6]
                fifo_pnl = trade[10] # Realized PnL is at index 10

                date_item = QTableWidgetItem(str(trade_date if trade_date is not None else 'N/A'))
                symbol_item = QTableWidgetItem(str(symbol if symbol is not None else 'N/A'))
                put_call_item = QTableWidgetItem(str(put_call if put_call is not None else ''))
                strike_item = QTableWidgetItem(str(strike if strike is not None else ''))
                average_price_item = QTableWidgetItem(f"{average_price:.2f}" if isinstance(average_price, (float, int)) and average_price is not None else str(average_price if average_price is not None else 'N/A'))
                quantity_item = QTableWidgetItem(str(quantity if quantity is not None else 0))
                pnl_item = QTableWidgetItem(str(fifo_pnl if fifo_pnl is not None else 0.0))
                
                current_row_items = [
                    date_item, symbol_item, put_call_item, strike_item, quantity_item, pnl_item, average_price_item
                ]

                # Highlighting logic: Options and Positive PnL
                if "O" in description.upper() or "P" in description.upper(): # Check if it's an option trade
                    for item in current_row_items:
                        item.setBackground(yellow_color)
                
                if fifo_pnl is not None and fifo_pnl > 0:
                    for item in current_row_items:
                        item.setBackground(green_color)

                trade_history_table.setItem(i, 0, date_item)
                trade_history_table.setItem(i, 1, symbol_item)
                trade_history_table.setItem(i, 2, put_call_item)
                trade_history_table.setItem(i, 3, strike_item)
                trade_history_table.setItem(i, 4, quantity_item)
                trade_history_table.setItem(i, 5, pnl_item)
                trade_history_table.setItem(i, 6, average_price_item)

        except sqlite3.Error as e:
            self.chat_output.append(f"Chyba při načítání historie obchodů z DB: {e}")
            print(f"Error loading trade history from DB: {e}")
        except Exception as e:
            self.chat_output.append(f"Neočekávaná chyba při načítání historie obchodů: {e}")
            print(f"Unexpected error loading trade history: {e}")
        finally:
            if conn:
                conn.close()

