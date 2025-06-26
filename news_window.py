# news_window.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTextBrowser
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QColor # Pro otevírání URL v prohlížeči a barvy
from my_news_api_manager import NewsAPIManager # Importujeme NewsAPIManager (přejmenovaný modul)

class NewsWindow(QDialog):
    def __init__(self, ticker, chat_output_widget, parent=None):
        """
        Inicializuje okno pro zobrazení novinek.

        Args:
            ticker (str): Ticker pro, který se mají zobrazit novinky.
            chat_output_widget (QTextEdit): Odkaz na hlavní chatovací výstup pro logování.
            parent (QWidget): Nadřazený widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Novinky pro {ticker}")
        self.setGeometry(200, 200, 1000, 600) # Rozšíříme okno pro nový sloupec a lepší viditelnost

        self.ticker = ticker
        self.chat_output = chat_output_widget # Pro logování do hlavního okna
        self.news_manager = NewsAPIManager(self.chat_output) # Inicializace NewsAPIManageru

        self.setup_ui()
        # Zde načítáme novinky za POSLEDNÍCH 7 DNÍ
        self.load_news(days_ahead=7) 

    def setup_ui(self):
        """Nastaví prvky uživatelského rozhraní pro okno novinek."""
        self.main_layout = QVBoxLayout(self)

        self.title_label = QLabel(f"Nadcházející novinky pro: <b>{self.ticker}</b>")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 16pt; margin-bottom: 10px;")
        self.main_layout.addWidget(self.title_label)

        self.news_table = QTableWidget()
        self.news_table.setColumnCount(5) # Zvýšíme počet sloupců na 5 (Datum, Nadpis, Zdroj, URL, Sentiment)
        self.news_table.setHorizontalHeaderLabels(["Datum", "Nadpis", "Zdroj", "URL", "Sentiment"])
        
        # Nastavení šířky sloupců pro lepší čitelnost sentimentu a URL
        # Nastavení sekcí musí být provedeno po nastavení počtu sloupců a hlaviček
        self.news_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Datum - automatická šířka podle obsahu
        self.news_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)         # Nadpis - roztáhne se, aby vyplnil místo
        self.news_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Zdroj - automatická šířka podle obsahu
        self.news_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)         # URL - roztáhne se, aby vyplnil místo
        self.news_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)           # Sentiment - pevná šířka
        self.news_table.setColumnWidth(4, 80) # Nastavíme pevnou šířku pro sloupec Sentiment


        self.news_table.verticalHeader().setVisible(False)
        self.news_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.news_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.news_table.itemDoubleClicked.connect(self.open_news_url) # Dvojklik otevře URL
        self.main_layout.addWidget(self.news_table)

        self.info_label = QLabel("Dvojklikem na řádek otevřete odkaz. Sentiment: -1 (negativní) až +1 (pozitivní).")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.info_label)

    def load_news(self, days_ahead):
        """Načte novinky a naplní jimi tabulku."""
        self.chat_output.append(f"Načítám novinky pro {self.ticker} za posledních {days_ahead} dnů...")
        news_data = self.news_manager.get_upcoming_news(self.ticker, days_ahead=days_ahead)

        self.news_table.setRowCount(len(news_data))
        if not news_data:
            self.chat_output.append(f"<span style='color:orange;'>Pro {self.ticker} nebyly nalezeny žádné novinky nebo došlo k chybě.</span>")
            self.news_table.setRowCount(1)
            # Nastavíme text do první buňky a roztáhneme přes všechny sloupce
            no_news_item = QTableWidgetItem("Žádné novinky k zobrazení.")
            no_news_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # Zarovnání na střed
            self.news_table.setItem(0, 0, no_news_item)
            self.news_table.setSpan(0, 0, 1, self.news_table.columnCount())
            return

        for row_idx, news_item in enumerate(news_data):
            date_item = QTableWidgetItem(news_item.get('date', 'N/A'))
            title_item = QTableWidgetItem(news_item.get('title', 'N/A'))
            source_item = QTableWidgetItem(news_item.get('source', 'N/A'))
            url_item = QTableWidgetItem(news_item.get('url', '')) 
            sentiment_item = QTableWidgetItem(f"{news_item.get('sentiment', 0.0):.2f}") # Zobrazení skóre na 2 desetinná místa

            # Barevné odlišení sentimentu
            sentiment_score = news_item.get('sentiment', 0.0)
            if sentiment_score >= 0.05: # Pozitivní
                sentiment_item.setBackground(QColor(190, 255, 190)) # Světle zelená
            elif sentiment_score <= -0.05: # Negativní
                sentiment_item.setBackground(QColor(255, 190, 190)) # Světle červená
            else: # Neutrální
                sentiment_item.setBackground(QColor(255, 255, 220)) # Světle žlutá


            self.news_table.setItem(row_idx, 0, date_item)
            self.news_table.setItem(row_idx, 1, title_item)
            self.news_table.setItem(row_idx, 2, source_item)
            self.news_table.setItem(row_idx, 3, url_item)
            self.news_table.setItem(row_idx, 4, sentiment_item) # Nový sloupec pro sentiment
        
        self.chat_output.append(f"Novinky pro {self.ticker} načteny a zobrazeny.")


    def open_news_url(self, item):
        """Otevře URL novinky v systémovém prohlížeči po dvojkliku na řádek."""
        row = item.row()
        url_item = self.news_table.item(row, 3) # URL je ve 4. sloupci (index 3)
        if url_item and url_item.text():
            url = url_item.text()
            if url.startswith("http://") or url.startswith("https://"):
                QDesktopServices.openUrl(QUrl(url))
                self.chat_output.append(f"Otevírám odkaz: {url}")
            else:
                self.chat_output.append(f"<span style='color:red;'>CHYBA: Neplatný URL formát: {url}</span>")
        else:
            self.chat_output.append("<span style='color:orange;'>Upozornění: Pro vybranou novinku není k dispozici žádný odkaz.</span>")

