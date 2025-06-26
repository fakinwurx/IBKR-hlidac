# main_app.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QTextEdit, QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
# from ib_insync import util # Odstraněno, jelikož patch_loop již není k dispozici
import config
from ib_manager import IBManager
from database_manager import DatabaseManager 
from news_window import NewsWindow # Importujeme nové okno pro novinky

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IBKR Hlídač & Autotrader")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # Inicializace chat_output dříve, aby bylo dostupné pro manažery
        self.chat_output = QTextEdit()
        self.chat_output.setReadOnly(True)
        self.chat_output.setText("Systém spuštěn.")

        # Inicializace manažerů
        self.ib_manager = IBManager(self.chat_output)
        self.db_manager = DatabaseManager(config.DATABASE_PATH, self.chat_output) 

        # Nastavení UI (nyní by měly být všechny metody, na které se odkazuje, definovány)
        self.setup_ui()
        
        # Načtení dat DN při startu
        self.load_dn_data()

    def load_dn_data(self):
        """Načte data z tabulky DN a naplní jimi dn_table."""
        data = self.db_manager.get_all_dn_entries()
        self.dn_table.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            self.dn_table.setItem(row_idx, 0, QTableWidgetItem(str(row_data[0]))) # DateOpen
            self.dn_table.setItem(row_idx, 1, QTableWidgetItem(row_data[1]))      # Ticker
            self.dn_table.setItem(row_idx, 2, QTableWidgetItem(str(row_data[2]) if row_data[2] else "NULL")) # DateClose
        self.chat_output.append("Data DN načtena.")

    def on_dn_selected(self):
        """Zpracuje výběr řádku v DN tabulce a aktualizuje detailní pozice."""
        selected_items = self.dn_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            date_open = self.dn_table.item(row, 0).text()
            ticker = self.dn_table.item(row, 1).text()
            date_close = self.dn_table.item(row, 2).text() if self.dn_table.item(row, 2).text() != "NULL" else None

            self.selected_position_label.setText(f'Datum strategie: {date_open} {ticker}')
            self.chat_output.append(f'Vybrána pozice: {date_open} {ticker}')
            
            # Aktualizace živých pozic z IB pro vybraný ticker
            self.ib_manager.load_live_positions(ticker, self.ib_live_positions_table, self.ib_live_positions_label)
            # Aktualizace celkového PnL pro vybraný ticker
            self.ib_manager.calculate_current_unrealized_pnl(ticker, self.current_pnl_label)

            # Načtení historických obchodů a souhrnu pro vybranou pozici
            position_data = {
                'ticker': ticker,
                'date_open': date_open,
                'date_close': date_close # Posíláme i date_close
            }
            self.db_manager.load_trade_history_and_summary(
                position_data, 
                self.historical_summary_table, 
                self.trade_history_table
            )
            # Aktivovat tlačítko pro novinky
            self.show_news_button.setEnabled(True)
        else:
            self.selected_position_label.setText('Datum strategie: N/A')
            self.ib_live_positions_table.setRowCount(0)
            self.ib_live_positions_label.setText('Detailní živé pozice z IB pro :')
            self.current_pnl_label.setText("Aktuální PnL (Otevřené pozice z IB): N/A")
            # Vyprázdnění tabulek historie a souhrnu, pokud není nic vybráno
            self.historical_summary_table.setRowCount(0)
            self.trade_history_table.setRowCount(0)
            # Deaktivovat tlačítko pro novinky
            self.show_news_button.setEnabled(False)

    def add_dn_entry_to_db(self):
        """Přidá nový záznam DN do databáze."""
        ticker = self.ticker_input.text().strip().upper()
        date_open = self.date_open_input.text().strip()

        if not ticker or not date_open:
            self.chat_output.append("<span style='color:red;'>CHYBA: Ticker a Datum vstupu nesmí být prázdné.</span>")
            return

        # Základní validace formátu YYYYMMDD
        if not (len(date_open) == 8 and date_open.isdigit()):
            self.chat_output.append("<span style='color:red;'>CHYBA: Datum vstupu musí být ve formátu YYYYMMDD (např. 20230101).</span>")
            return
        
        try:
            # Pokus o přidání do databáze
            self.db_manager.add_dn_entry(date_open, ticker)
            self.chat_output.append(f"<span style='color:green;'>Záznam '{ticker}' s datem '{date_open}' úspěšně přidán do DB DN.</span>")
            
            # Po přidání znovu načíst data, aby se tabulka aktualizovala
            self.load_dn_data()
            # Vyprázdnění vstupních polí
            self.ticker_input.clear()
            self.date_open_input.clear()
        except ValueError as ve: # Chytáme specifickou chybu pro existující záznam
            self.chat_output.append(f"<span style='color:orange;'>Upozornění: {ve}</span>")
        except Exception as e:
            self.chat_output.append(f"<span style='color:red;'>CHYBA při přidávání záznamu do DB: {e}</span>")
            print(f"ERROR: Exception in add_dn_entry_to_db: {e}") # Pro debug v konzoli

    def show_news_for_selected_ticker(self):
        """Otevře okno s novinkami pro vybraný ticker."""
        selected_items = self.dn_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            ticker = self.dn_table.item(row, 1).text()
            self.chat_output.append(f"Otevírám okno s novinkami pro ticker: {ticker}")
            # Vytvoření a zobrazení nového okna s novinkami
            # Předáme self jako parent, aby okno bylo modální a chat_output pro logování
            self.news_window = NewsWindow(ticker, self.chat_output, self) 
            self.news_window.show()
        else:
            self.chat_output.append("<span style='color:orange;'>Prosím, vyberte ticker z tabulky DN, abyste zobrazili novinky.</span>")


    def setup_ui(self):
        # Levý panel (vertikální)
        self.left_panel = QVBoxLayout()
        self.main_layout.addLayout(self.left_panel)

        # Sekce pro výběr DN (první tabulka)
        self.dn_selection_label = QLabel("Vyberte DN:")
        self.left_panel.addWidget(self.dn_selection_label)

        self.dn_table = QTableWidget()
        self.dn_table.setColumnCount(3)
        self.dn_table.setHorizontalHeaderLabels(["DateOpen", "Ticker", "DateClose"])
        self.dn_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dn_table.verticalHeader().setVisible(False)
        self.dn_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dn_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.dn_table.itemSelectionChanged.connect(self.on_dn_selected)
        self.left_panel.addWidget(self.dn_table)

        # Sekce pro přidání DN do DB (NOVÁ - pod první tabulkou)
        self.add_dn_group_box = QVBoxLayout()
        self.add_dn_label = QLabel("Přidat nový záznam DN:")
        self.add_dn_group_box.addWidget(self.add_dn_label)

        self.ticker_input_layout = QHBoxLayout()
        self.ticker_label = QLabel("Ticker:")
        self.ticker_input_layout.addWidget(self.ticker_label)
        self.ticker_input = QLineEdit()
        self.ticker_input_layout.addWidget(self.ticker_input)
        self.add_dn_group_box.addLayout(self.ticker_input_layout)

        self.date_open_input_layout = QHBoxLayout()
        self.date_open_label = QLabel("Datum vstupu (YYYYMMDD):")
        self.date_open_input_layout.addWidget(self.date_open_label)
        self.date_open_input = QLineEdit()
        self.date_open_input.setPlaceholderText("např. 20230101")
        self.date_open_input_layout.addWidget(self.date_open_input)
        self.add_dn_group_box.addLayout(self.date_open_input_layout)

        self.add_dn_button = QPushButton("Přidat DN do DB")
        self.add_dn_button.clicked.connect(self.add_dn_entry_to_db)
        self.add_dn_group_box.addWidget(self.add_dn_button)
        
        # NOVÉ: Tlačítko pro znovunačtení databáze
        self.reload_db_button = QPushButton("Znovu načíst DN databázi")
        self.reload_db_button.clicked.connect(self.load_dn_data)
        self.add_dn_group_box.addWidget(self.reload_db_button) 
        
        # NOVÉ: Tlačítko pro zobrazení novinek
        self.show_news_button = QPushButton("Zobrazit novinky pro vybraný ticker")
        self.show_news_button.clicked.connect(self.show_news_for_selected_ticker)
        self.show_news_button.setEnabled(False) # Zpočátku neaktivní, aktivuje se po výběru tickeru
        self.add_dn_group_box.addWidget(self.show_news_button)


        # Přidáme celou skupinu pro přidání DN do levého panelu
        # Zajistíme, že add_dn_group_box je správně přidán k left_panel
        self.left_panel.addLayout(self.add_dn_group_box)


        # Detailní vybrané pozice (druhá tabulka) - PŮVODNÍ UMÍSTĚNÍ A POPIS
        self.detail_label = QLabel("Detaily vybrané pozice:")
        self.left_panel.addWidget(self.detail_label)

        self.selected_position_label = QLabel("Datum strategie: N/A")
        self.left_panel.addWidget(self.selected_position_label)

        self.ib_live_positions_label = QLabel("Detailní živé pozice z IB pro :")
        self.left_panel.addWidget(self.ib_live_positions_label)
        self.ib_live_positions_table = QTableWidget()
        self.ib_live_positions_table.setColumnCount(8)
        self.ib_live_positions_table.setHorizontalHeaderLabels([
            "Symbol", "Typ", "Právo", "Strike", "Množství", "Tržní hodnota", "Prům. cena", "Nerealizovaný PnL"
        ])
        self.ib_live_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ib_live_positions_table.verticalHeader().setVisible(False)
        self.left_panel.addWidget(self.ib_live_positions_table)

        self.current_pnl_label = QLabel("Aktuální PnL (Otevřené pozice z IB): N/A")
        self.left_panel.addWidget(self.current_pnl_label)

        # Historické obchody a souhrn (PŮVODNÍ ČÁST, KTERÁ BYLA MOŽNÁ ODSTRANĚNA)
        self.historical_summary_label = QLabel("Souhrn realizovaného PnL:")
        self.left_panel.addWidget(self.historical_summary_label)
        self.historical_summary_table = QTableWidget()
        self.historical_summary_table.setColumnCount(4)
        self.historical_summary_table.setHorizontalHeaderLabels(["Ticker", "Realizovaný PnL", "Čistá hotovost", "FX PnL"])
        self.historical_summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.historical_summary_table.verticalHeader().setVisible(False)
        self.left_panel.addWidget(self.historical_summary_table)

        self.trade_history_label = QLabel("Historie obchodů:")
        self.left_panel.addWidget(self.trade_history_label)
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(7) # Aktualizován počet sloupců na základě databázového manažera
        self.trade_history_table.setHorizontalHeaderLabels([
            "Datum", "Symbol", "C/P", "Strike", "Množství", "Realizovaný PnL", "Avg Price"
        ])
        self.trade_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.trade_history_table.verticalHeader().setVisible(False)
        self.left_panel.addWidget(self.trade_history_table)


        # Pravý panel (chat output)
        self.right_panel = QVBoxLayout()
        self.main_layout.addLayout(self.right_panel)

        self.chat_label = QLabel("Chat/Log:")
        self.right_panel.addWidget(self.chat_label)
        self.right_panel.addWidget(self.chat_output) # Přenese chat_output do UI


if __name__ == "__main__":
    # util.patch_loop() # Tato řádka byla odstraněna, protože způsobuje AttributeError
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
