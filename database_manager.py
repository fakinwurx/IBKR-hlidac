# database_manager.py
import sqlite3 as sq
from datetime import datetime
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class DatabaseManager:
    """
    Spravuje interakci s databází SQLite.
    """
    def __init__(self, db_path, log_output):
        self.db_path = db_path
        self.log_output = log_output
        self.conn = self.get_connection()
        self.cursor = self.conn.cursor()
        self.init_db()

    def get_connection(self):
        try:
            return sq.connect(self.db_path)
        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba databáze: {e}</span>")
            return None

    def init_db(self):
        """
        Inicializuje databázové tabulky.
        """
        if self.conn:
            try:
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS DeltaNeutralStrategies (
                        date_open TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        date_close TEXT,
                        PRIMARY KEY (date_open, ticker)
                    )
                ''')
                self.conn.commit()
                self.log_output.append("<span style='color:green;'>Tabulka 'DeltaNeutralStrategies' připravena.</span>")
                
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS IBFlexQueryCZK (
                        tradeDate TEXT,
                        symbol TEXT,
                        conid INTEGER,
                        assetCategory TEXT,
                        strike REAL,
                        fifoPnlRealized REAL, 
                        realizedPnL_Ccy TEXT,
                        netCash REAL,
                        netCash_Ccy TEXT,
                        fxPnL REAL,
                        fxPnL_Ccy TEXT,
                        tradeId REAL,
                        multiplier REAL,
                        code TEXT,
                        underlyingSymbol TEXT,
                        buySell TEXT,
                        putCall TEXT,
                        openClose TEXT,
                        tradePrice REAL,
                        quantity INTEGER,
                        PRIMARY KEY (tradeId)
                    )
                ''')
                self.conn.commit()
                self.log_output.append("<span style='color:green;'>Tabulka 'IBFlexQueryCZK' připravena.</span>")
            
            except sq.Error as e:
                self.log_output.append(f"<span style='color:red;'>Chyba při inicializaci DB: {e}</span>")
                self.conn.close()
                self.conn = None

    def add_dn_entry(self, ticker, date_open):
        """Přidá nový záznam Delta Neutral strategie do databáze."""
        if not self.conn:
            self.log_output.append("<span style='color:red;'>Chyba: Databázové spojení není aktivní.</span>")
            return
        
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO DeltaNeutralStrategies (ticker, date_open, date_close)
                VALUES (?, ?, '')
            ''', (ticker, date_open))
            self.conn.commit()
        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba při přidávání záznamu: {e}</span>")

    def get_all_dn_entries(self,):
        """Získává všechny záznamy z tabulky DeltaNeutralStrategies."""
        if not self.conn:
            self.log_output.append("<span style='color:red;'>Chyba: Databázové spojení není aktivní.</span>")
            return []
        
        try:
            self.cursor.execute('''
                SELECT date_open, ticker, date_close FROM DeltaNeutralStrategies
            ''')
            return self.cursor.fetchall()
        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba při načítání strategií: {e}</span>")
            return []

    def update_dn_strategy(self, ticker, date_open, old_date_close, column_name, new_value):
        """
        Aktualizuje záznam v tabulce DeltaNeutralStrategies na základě tickeru a původního data otevření.
        """
        if not self.conn:
            self.log_output.append("<span style='color:red;'>Chyba: Databázové spojení není aktivní.</span>")
            return

        try:
            sql = f"UPDATE DeltaNeutralStrategies SET {column_name} = ? WHERE ticker = ? AND date_open = ?"
            self.cursor.execute(sql, (new_value, ticker, date_open))
            self.conn.commit()
            self.log_output.append(f"<span style='color:green;'>Úspěšně aktualizováno {column_name} pro {ticker} ({date_open}).</span>")
        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba při aktualizaci záznamu: {e}</span>")

    def delete_dn_entry(self, ticker, date_open):
        """Smaže záznam Delta Neutral strategie z databáze."""
        if not self.conn:
            self.log_output.append("<span style='color:red;'>Chyba: Databázové spojení není aktivní.</span>")
            return
        try:
            self.cursor.execute('''
                DELETE FROM DeltaNeutralStrategies
                WHERE ticker = ? AND date_open = ?
            ''', (ticker, date_open))
            self.conn.commit()
            self.log_output.append(f"<span style='color:green;'>Záznam pro {ticker} s datem {date_open} úspěšně smazán.</span>")
        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba při mazání záznamu: {e}</span>")

    def load_trade_history_and_summary(self, position_data, summary_table, trade_history_table):
        """
        Načte a zobrazí historii obchodů a souhrn PnL pro danou strategii.
        """
        if not self.conn:
            self.log_output.append("<span style='color:red;'>Chyba: Databázové spojení není aktivní.</span>")
            return

        ticker = position_data.get('ticker')
        date_open_str = position_data.get('date_open')
        date_close_str = position_data.get('date_close')
        
        if not ticker or not date_open_str:
            self.log_output.append("<span style='color:red;'>Chyba: Ticker a datum otevření jsou povinné pro načtení historie.</span>")
            return
        
        # Určení koncového data pro dotaz.
        # Pokud je strategie otevřená, použije se dnešní datum.
        end_date = date_close_str if date_close_str else datetime.now().strftime('%Y-%m-%d')
        
        self.log_output.append(f"Načítám historii obchodů pro ticker: {ticker} v rozmezí {date_open_str} až {end_date}.")
        
        # Načtení historie obchodů
        try:
            # ZMĚNA: Používáme 'underlyingSymbol' místo 'symbol'
            # NOVINKA: Přidáno řazení podle tradeDate
            query = """
                SELECT tradeDate, symbol, putCall, strike, quantity, fifoPnlRealized, tradePrice, tradeId
                FROM IBFlexQueryCZK
                WHERE underlyingSymbol = ? AND tradeDate BETWEEN ? AND ?
                ORDER BY tradeDate
            """
            self.cursor.execute(query, (ticker, date_open_str, end_date))
            trades = self.cursor.fetchall()
            
            trade_history_table.setRowCount(len(trades))
            for i, trade in enumerate(trades):
                trade_date, symbol, put_call, strike, quantity, realized_pnl, trade_price, trade_id = trade
                
                trade_history_table.setItem(i, 0, QTableWidgetItem(str(trade_date)))
                trade_history_table.setItem(i, 1, QTableWidgetItem(str(symbol)))
                trade_history_table.setItem(i, 2, QTableWidgetItem(str(put_call)))
                trade_history_table.setItem(i, 3, QTableWidgetItem(str(strike)))
                trade_history_table.setItem(i, 4, QTableWidgetItem(str(quantity)))
                
                realized_pnl_item = QTableWidgetItem(f"{realized_pnl:.2f}" if realized_pnl is not None else "0.00")
                if realized_pnl is not None:
                    color = QColor('red') if realized_pnl < 0 else QColor('green')
                    realized_pnl_item.setForeground(color)
                trade_history_table.setItem(i, 5, realized_pnl_item)
                
                trade_history_table.setItem(i, 6, QTableWidgetItem(f"{trade_price:.2f}" if trade_price is not None else "0.00"))
                trade_id_item = QTableWidgetItem(str(trade_id))
                trade_history_table.setItem(i, 7, trade_id_item)

            self.log_output.append(f"<span style='color:green;'>Historie obchodů načtena.</span>")

        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba při načítání historie obchodů: {e}</span>")
            return

        # Načtení souhrnu PnL
        try:
            # Souhrn se nyní počítá vždy, ať je strategie otevřená, nebo uzavřená
            # ZMĚNA: Používáme 'underlyingSymbol' místo 'symbol'
            query = """
                SELECT underlyingSymbol, SUM(fifoPnlRealized), SUM(netCash), SUM(fxPnL)
                FROM IBFlexQueryCZK
                WHERE underlyingSymbol = ? AND tradeDate BETWEEN ? AND ?
                GROUP BY underlyingSymbol
            """
            self.cursor.execute(query, (ticker, date_open_str, end_date))
            summary = self.cursor.fetchone()
            
            summary_table.setRowCount(1)
            if summary:
                symbol, realized_pnl, net_cash, fx_pnl = summary
                summary_table.setItem(0, 0, QTableWidgetItem(str(symbol)))
                summary_table.setItem(0, 1, QTableWidgetItem(f"{realized_pnl:.2f}" if realized_pnl is not None else "0.00"))
                summary_table.setItem(0, 2, QTableWidgetItem(f"{net_cash:.2f}" if net_cash is not None else "0.00"))
                summary_table.setItem(0, 3, QTableWidgetItem(f"{fx_pnl:.2f}" if fx_pnl is not None else "0.00"))
            else:
                summary_table.clearContents()

            if date_close_str:
                self.log_output.append(f"<span style='color:green;'>Souhrn PnL pro uzavřenou strategii načten.</span>")
            else:
                self.log_output.append(f"<span style='color:orange;'>Zobrazen průběžný souhrn PnL pro otevřenou strategii.</span>")

        except sq.Error as e:
            self.log_output.append(f"<span style='color:red;'>Chyba při načítání souhrnu PnL: {e}</span>")
