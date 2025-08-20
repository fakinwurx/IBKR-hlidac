import smtplib
import ib_insync
import pandas as pd
import sqlite3 as sq
import sys
from datetime import datetime
import os
# Ujistěte se, že váš konfigurační soubor se jmenuje config.py
import config 

if __name__ == '__main__':
    print("Spouštím stahování a ukládání FlexReportu...")
    try:
        # Získání hodnot z konfiguračního souboru
        token = config.TOKEN
        queryid = config.QUERY_ID
        database_path = config.DATABASE_PATH

        # Krok 1: Připojení k databázi SQLite
        # Používáme sqlite3 a cestu z konfiguračního souboru
        conn = sq.connect(database_path)
        cur = conn.cursor()
        print(f"Úspěšně připojeno k databázi na cestě: {database_path}")

        # Krok 2: Smazání všech stávajících dat z hlavní tabulky
        cur.execute('''DELETE FROM IBFlexQueryCZK''')
        conn.commit()
        print("Všechna data z tabulky 'IBFlexQueryCZK' byla smazána.")

        # Krok 3: Stažení nových dat z FlexReportu
        fr = ib_insync.FlexReport(token, queryid)
        pdtrades = fr.df('Trade')
        print(f"Úspěšně staženo {len(pdtrades)} záznamů z FlexReportu.")

        # Krok 4: Vložení nových dat do dočasné tabulky
        pdtrades.to_sql('IBFlexQueryCZK_Temp', conn, if_exists='replace', index=False)

        # Krok 5: Přesunutí dat z dočasné tabulky do hlavní tabulky
        cur.execute('''INSERT INTO IBFlexQueryCZK SELECT * FROM IBFlexQueryCZK_Temp''')
        conn.commit()
        print("Nová data byla úspěšně vložena do tabulky 'IBFlexQueryCZK'.")

        # Krok 6: Smazání dočasné tabulky
        cur.execute('''DROP TABLE IF EXISTS IBFlexQueryCZK_Temp''')
        conn.commit()
        
    except Exception as e:
        print(f"Chyba při spouštění FlexReport skriptu: {e}")
    finally:
        if conn:
            conn.close()
            print("Připojení k databázi uzavřeno.")

