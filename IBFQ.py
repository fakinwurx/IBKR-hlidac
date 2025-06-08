import smtplib
import ib_insync
from config.settings import *
import pandas as pd
import sqlite3 as sq
import sys
from datetime import datetime
import os

if __name__ == '__main__':
    fr = ib_insync.FlexReport(token, queryid)
    pdtrades = fr.df('Trade')

    conn = sq.connect(setsql['sqldata'])
    cur = conn.cursor()

    pdtrades.to_sql('IBFlexQueryCZK_Temp', conn, if_exists='append', index=False)

    cur.execute(
        '''INSERT INTO IBFlexQueryCZK SELECT * FROM IBFlexQueryCZK_Temp t1 WHERE NOT EXISTS(SELECT * FROM IBFlexQueryCZK t2 WHERE t2.tradeID = t1.tradeID )''')
    conn.commit()
    cur.execute('''DELETE FROM IBFlexQueryCZK_Temp''')
    conn.commit()
    conn.close()