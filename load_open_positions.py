from PyQt6.QtWidgets import QTableWidgetItem
from ib_insync import IB, util, Stock
import pandas as pd
from typing import List, Optional, Dict
import time


class OpenPositionsHandler:
    def __init__(self):
        pass

    def load_open_positions(self, positions_table, open_positions_table):
        """Handle the click event for the 'Otevřené pozice' button."""
        selected_rows = positions_table.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            ticker = positions_table.item(row, 0).text()
            print(ticker) # TODO.remove

            # Clear the open positions table
            open_positions_table.setRowCount(0)
            
            # Set up the table columns
            open_positions_table.setColumnCount(13)
            headers = ['Symbol', 'SecType', 'Position', 'AvgCost', 'CurrentPrice', 'MarketValue', 
                      'UnrealizedPNL', 'Exchange', 'Currency', 'Strike', 'Expiry', 'Right', 'Multiplier']
            open_positions_table.setHorizontalHeaderLabels(headers)
            
            # Add the ticker to the open positions table
            open_positions_table.setItem(0, 0, QTableWidgetItem(ticker))

            open_pos = self.get_filtered_positions(positions_table)
            
            # Clear and populate the open positions table
            open_positions_table.setRowCount(len(open_pos))
            for i, pos in enumerate(open_pos):
                # Add each value to the table
                open_positions_table.setItem(i, 0, QTableWidgetItem(str(pos['symbol'])))
                open_positions_table.setItem(i, 1, QTableWidgetItem(str(pos['secType'])))
                open_positions_table.setItem(i, 2, QTableWidgetItem(str(pos['position_size'])))
                open_positions_table.setItem(i, 3, QTableWidgetItem(str(pos['avg_cost'])))
                open_positions_table.setItem(i, 4, QTableWidgetItem(str(pos['current_price'])))
                open_positions_table.setItem(i, 5, QTableWidgetItem(str(pos['market_value'])))
                open_positions_table.setItem(i, 6, QTableWidgetItem(str(pos['unrealized_pnl'])))
                open_positions_table.setItem(i, 7, QTableWidgetItem(str(pos['exchange'])))
                open_positions_table.setItem(i, 8, QTableWidgetItem(str(pos['currency'])))
                
                # Add option-specific fields if they exist
                if pos['secType'] == 'OPT':
                    open_positions_table.setItem(i, 9, QTableWidgetItem(str(pos['strike'])))
                    open_positions_table.setItem(i, 10, QTableWidgetItem(str(pos['expiry'])))
                    open_positions_table.setItem(i, 11, QTableWidgetItem(str(pos['right'])))
                    open_positions_table.setItem(i, 12, QTableWidgetItem(str(pos['multiplier'])))

    def handler(self, positions_table, open_positions_table):
        """Handler function for the open positions button click."""
        self.load_open_positions(positions_table, open_positions_table) 

    def get_filtered_positions(self, positions_table, host: str = '127.0.0.1', port: int = 7496, client_id: int = 11) -> List[Dict]:
        """
        Download positions data from TWS API using ib_insync, filter by underlying symbol,
        and get current market prices with calculated market values.
        
        Parameters:
        -----------
        positions_table : QTableWidget
            The table widget containing the selected position
        host : str, optional
            TWS host address (default: '127.0.0.1')
        port : int, optional
            TWS port (default: 7496 for live trading, 7497 for paper)
        client_id : int, optional
            Client ID for the connection (default: 1)
        
        Returns:
        --------
        List[Dict]
            Filtered list of positions with current prices and market values
        """
        selected_rows = positions_table.selectedItems()
        
        if selected_rows:
            row = selected_rows[0].row()
            ticker = positions_table.item(row, 0).text()
            print(ticker) # TODO.remove

        # Initialize IB connection
        ib = IB()
            
        try:
            # Connect to TWS
            ib.connect(host, port, clientId=client_id)
            print(f"Connected to TWS on {host}:{port}")
            
            # Download all positions
            positions = ib.positions()
            print(f"Downloaded {len(positions)} total positions")
            
            # Store positions in variable
            all_positions = positions.copy()
            
            # Filter positions for the specified underlying symbol
            filtered_positions = []
            
            for position in all_positions:
                # Check if the contract symbol matches the underlying
                contract = position.contract
                
                # For stocks, check direct symbol match
                if hasattr(contract, 'symbol') and contract.symbol.upper() == ticker.upper():
                    filtered_positions.append(position)
                
                # For options, check underlying symbol
                elif hasattr(contract, 'symbol') and contract.secType == 'OPT':
                    if contract.symbol.upper() == ticker.upper():
                        filtered_positions.append(position)
                
                # For futures, check symbol match
                elif hasattr(contract, 'localSymbol') and contract.secType == 'FUT':
                    if ticker.upper() in contract.localSymbol.upper():
                        filtered_positions.append(position)
            
            print(f"Found {len(filtered_positions)} positions for underlying: {ticker}")
            # print (filtered_positions) # TODO.remove
            
            # Get current prices and calculate market values
            enriched_positions = []

            ### ib.reqMarketDataType(2)
                    
            for position in filtered_positions:
                try:
                    print(f"Getting market data for {position.contract.symbol} {position.contract.secType}...")
                    
                    # Ensure contract has exchange information
                    contract = position.contract
                    ### [ticker] = ib.reqTickers(contract)
                    
                    # For options without exchange, try to resolve it
                    if contract.secType == 'OPT' and not contract.exchange:
                        print(f"  Resolving contract details for option...")
                        try:
                            # Request contract details to get exchange
                            contract_details = ib.reqContractDetails(contract)
                            if contract_details:
                                contract = contract_details[0].contract
                                print(f"  Resolved exchange: {contract.exchange}")
                        except Exception as resolve_e:
                            print(f"  Could not resolve contract: {resolve_e}")
                            # Try setting common option exchanges
                            if contract.symbol in ['AAL', 'AAPL', 'SPY', 'QQQ']:  # Common US stocks
                                contract.exchange = 'SMART'
                                print(f"  Set exchange to SMART for {contract.symbol}")
                    
                    # For stocks without exchange, set to SMART
                    elif contract.secType == 'STK' and not contract.exchange:
                        contract.exchange = 'SMART'
                        print(f"  Set exchange to SMART for stock {contract.symbol}")
                    
                    # Request market data for current price
                    ib.reqMktData(contract, '233', True, False)
                    ## ib.reqMktData(contract, '', False, False)
                    
                    
                    # Wait longer for data to arrive
                    ib.sleep(3)
                    
                    # Get the ticker with current market data
                    ticker = ib.ticker(contract)
                    
                    # Determine current price (use different fields based on availability)
                    current_price = None
                    if ticker.marketPrice() and ticker.marketPrice() > 0:
                        current_price = ticker.marketPrice()
                    elif ticker.last and ticker.last > 0:
                        current_price = ticker.last
                    elif ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
                        current_price = (ticker.bid + ticker.ask) / 2
                    elif ticker.close and ticker.close > 0:
                        current_price = ticker.close
                    
                    print(f"  Live price attempt: {current_price}")
                    
                    # If no live price (market closed), get last available close price
                    if current_price is None or current_price <= 0:
                        print(f"  Market appears closed, getting last available close price...")
                        try:
                            # For stocks - get recent historical data
                            if contract.secType == 'STK':
                                bars = ib.reqHistoricalData(
                                    contract,
                                    endDateTime='',
                                    durationStr='10 D',  # Look back 10 days to ensure we get data
                                    barSizeSetting='1 day',
                                    whatToShow='TRADES',
                                    useRTH=True,
                                    formatDate=1
                                )
                                if bars and len(bars) > 0:
                                    current_price = bars[-1].close
                                    print(f"  Using last stock close price: {current_price}")
                            
                            # For options - use different approach since EOD data may not be available
                            elif contract.secType == 'OPT':
                                print(f"  Getting option data using snapshot...")
                                
                                # First try to get a market data snapshot
                                try:
                                    ib.reqMktData(contract, '106', True, False)  # Request snapshot with option volume
                                    ib.sleep(2)
                                    
                                    snapshot_ticker = ib.ticker(contract)
                                    if snapshot_ticker.close and snapshot_ticker.close > 0:
                                        current_price = snapshot_ticker.close
                                        print(f"  Using option snapshot close: {current_price}")
                                    elif snapshot_ticker.last and snapshot_ticker.last > 0:
                                        current_price = snapshot_ticker.last
                                        print(f"  Using option snapshot last: {current_price}")
                                    
                                    ib.cancelMktData(contract)
                                except Exception as snap_e:
                                    print(f"  Snapshot failed: {snap_e}")
                                
                                # If snapshot didn't work, try intraday historical data
                                if (current_price is None or current_price <= 0):
                                    print(f"  Trying intraday historical data for option...")
                                    try:
                                        bars = ib.reqHistoricalData(
                                            contract,
                                            endDateTime='',
                                            durationStr='2 D',  # Shorter duration
                                            barSizeSetting='1 hour',  # Hourly bars
                                            whatToShow='TRADES',
                                            useRTH=True,
                                            formatDate=1
                                        )
                                        if bars and len(bars) > 0:
                                            # Find the last bar with actual trades
                                            for bar in reversed(bars):
                                                if bar.close > 0 and bar.volume > 0:
                                                    current_price = bar.close
                                                    print(f"  Using last option trade price: {current_price}")
                                                    break
                                    except Exception as intra_e:
                                        print(f"  Intraday historical data error: {intra_e}")
                                
                                # Last resort for options: try to get underlying price and estimate
                                if (current_price is None or current_price <= 0):
                                    print(f"  Option price unavailable, getting underlying price for reference...")
                                    try:
                                        # Create underlying stock contract
                                        underlying_contract = Stock(contract.symbol, 'SMART', 'USD')
                                        
                                        underlying_bars = ib.reqHistoricalData(
                                            underlying_contract,
                                            endDateTime='',
                                            durationStr='5 D',
                                            barSizeSetting='1 day',
                                            whatToShow='TRADES',
                                            useRTH=True,
                                            formatDate=1
                                        )
                                        
                                        if underlying_bars and len(underlying_bars) > 0:
                                            underlying_price = underlying_bars[-1].close
                                            print(f"  Underlying {contract.symbol} price: {underlying_price}")
                                            
                                            # Simple intrinsic value calculation for reference
                                            if contract.right == 'C':  # Call option
                                                intrinsic = max(0, underlying_price - contract.strike)
                                            else:  # Put option
                                                intrinsic = max(0, contract.strike - underlying_price)
                                            
                                            if intrinsic > 0:
                                                current_price = intrinsic
                                                print(f"  Using intrinsic value as estimate: {current_price}")
                                            else:
                                                print(f"  Option is out-of-the-money, intrinsic value is 0")
                                                current_price = 0.01  # Minimal value for OTM options
                                    
                                    except Exception as underlying_e:
                                        print(f"  Underlying price lookup error: {underlying_e}")
                            
                            else:
                                print(f"  No historical data available for {contract.secType}")
                                
                        except Exception as hist_e:
                            print(f"  Historical data error: {hist_e}")
                            # Try one more approach - get the position's unrealized P&L to back-calculate price
                            if hasattr(position, 'unrealizedPNL') and position.unrealizedPNL is not None:
                                if position.position != 0:
                                    try:
                                        # Estimate current price from P&L: current_price = avg_cost + (unrealized_pnl / position_size)
                                        if contract.secType == 'OPT':
                                            estimated_price = position.avgCost + (position.unrealizedPNL / (position.position * 100))
                                        else:
                                            estimated_price = position.avgCost + (position.unrealizedPNL / position.position)
                                        
                                        if estimated_price > 0:
                                            current_price = estimated_price
                                            print(f"  Using P&L-derived price estimate: {current_price}")
                                    except:
                                        pass
                    
                    # Calculate market value
                    market_value = 0
                    if current_price and current_price > 0:
                        if contract.secType == 'OPT':
                            # Options: multiply by 100 (contract multiplier)
                            market_value = position.position * current_price * 100
                        else:
                            # Stocks and other securities
                            market_value = position.position * current_price
                    
                    # Create enriched position dictionary
                    enriched_position = {
                        'position_obj': position,
                        'contract': contract,  # Use the potentially updated contract
                        'symbol': contract.symbol,
                        'secType': contract.secType,
                        'exchange': contract.exchange,
                        'currency': contract.currency,
                        'position_size': position.position,
                        'avg_cost': position.avgCost,
                        'current_price': current_price if current_price else 0,
                        'market_value': market_value,
                        'unrealized_pnl': position.unrealizedPNL if hasattr(position, 'unrealizedPNL') else 0,
                        'ticker': ticker
                    }
                    
                    # Add option-specific details if applicable
                    if contract.secType == 'OPT':
                        enriched_position.update({
                            'strike': contract.strike,
                            'expiry': contract.lastTradeDateOrContractMonth,
                            'right': contract.right,  # 'C' for Call, 'P' for Put
                            'multiplier': contract.multiplier
                        })
                    
                    enriched_positions.append(enriched_position)
                    print(f"  Final - Current price: {current_price}, Market value: {market_value}")
                    
                    # Cancel market data subscription to avoid accumulating subscriptions
                    try:
                        ib.cancelMktData(contract)
                    except:
                        pass  # Ignore cancel errors
                    
                except Exception as e:
                    print(f"Error getting price for {position.contract.symbol}: {e}")
                    # Still add position even if price retrieval failed
                    enriched_position = {
                        'position_obj': position,
                        'contract': position.contract,
                        'symbol': position.contract.symbol,
                        'secType': position.contract.secType,
                        'exchange': position.contract.exchange,
                        'currency': position.contract.currency,
                        'position_size': position.position,
                        'avg_cost': position.avgCost,
                        'current_price': 0,
                        'market_value': 0,
                        'unrealized_pnl': position.unrealizedPNL if hasattr(position, 'unrealizedPNL') else 0,
                        'ticker': None
                    }
                    
                    if position.contract.secType == 'OPT':
                        enriched_position.update({
                            'strike': position.contract.strike,
                            'expiry': position.contract.lastTradeDateOrContractMonth,
                            'right': position.contract.right,
                            'multiplier': position.contract.multiplier
                        })
                    
                    enriched_positions.append(enriched_position)
            
            return enriched_positions
            
        except Exception as e:
            print(f"Error connecting to TWS or retrieving positions: {e}")
            return []
            
        finally:
            # Disconnect from TWS
            if ib.isConnected():
                ib.disconnect()
                print("Disconnected from TWS")


    def display_filtered_positions(positions: List[Dict]) -> pd.DataFrame:
        """
        Helper function to display filtered positions with current prices and market values.
        
        Parameters:
        -----------
        positions : List[Dict]
            List of enriched position dictionaries
        
        Returns:
        --------
        pd.DataFrame
            DataFrame containing position details with current prices and market values
        """
        
        if not positions:
            print("No positions found")
            return pd.DataFrame()
        
        position_data = []
        
        for pos in positions:
            row_data = {
                'Symbol': pos['symbol'],
                'SecType': pos['secType'],
                'Position': pos['position_size'],
                'AvgCost': round(pos['avg_cost'], 2),
                'CurrentPrice': round(pos['current_price'], 2) if pos['current_price'] else 'N/A',
                'MarketValue': round(pos['market_value'], 2) if pos['market_value'] else 'N/A',
                'UnrealizedPNL': round(pos['unrealized_pnl'], 2) if pos['unrealized_pnl'] else 'N/A',
                'Exchange': pos['exchange'],
                'Currency': pos['currency']
            }
            
            # Add option-specific columns if it's an option
            if pos['secType'] == 'OPT':
                row_data.update({
                    'Strike': pos.get('strike', 'N/A'),
                    'Expiry': pos.get('expiry', 'N/A'),
                    'Right': pos.get('right', 'N/A'),  # C or P
                    'Multiplier': pos.get('multiplier', 'N/A')
                })
            
            position_data.append(row_data)
        
        df = pd.DataFrame(position_data)
        return df


    def get_total_market_value(positions: List[Dict]) -> Dict[str, float]:
        """
        Calculate total market value by security type.
        
        Parameters:
        -----------
        positions : List[Dict]
            List of enriched position dictionaries
        
        Returns:
        --------
        Dict[str, float]
            Dictionary with totals by security type
        """
        
        totals = {'STK': 0, 'OPT': 0, 'TOTAL': 0}
        
        for pos in positions:
            if pos['market_value']:
                sec_type = pos['secType']
                if sec_type in totals:
                    totals[sec_type] += pos['market_value']
                totals['TOTAL'] += pos['market_value']
        
        return totals