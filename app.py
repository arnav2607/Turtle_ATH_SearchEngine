import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Turtle Wealth Screener", layout="wide")

st.title("🐢 Turtle Wealth - ATH Research Engine")

# ==========================================
# LOAD STOCK UNIVERSE
# ==========================================
@st.cache_data
def load_data():
    return pd.read_csv("nse_tickers.csv")

df = load_data()

st.write("Total Stocks in Universe:", len(df))

# ==========================================
# FUNCTION 1: Check Fresh ATH
# ==========================================
# def check_fresh_ath_today(stock_list):

#     results = []

#     progress = st.progress(0)
#     total = len(stock_list)

#     for i, ticker in enumerate(stock_list):

#         try:
#             stock = yf.Ticker(ticker)
#             hist = stock.history(period="max", auto_adjust=False)

#             if hist.empty or len(hist) < 2:
#                 continue

#             today_high = hist['High'].iloc[-1]
#             previous_ath = hist['High'].iloc[:-1].max()

#             if today_high > previous_ath:
#                 st.write(f"Fresh ATH Found: {ticker} - Today's High: {today_high:.2f}, Previous ATH: {previous_ath:.2f}")
#                 results.append(ticker)

#         except:
#             continue

#         progress.progress((i + 1) / total)

#     return results
def check_fresh_ath_today(stock_list):

    results = []

    progress = st.progress(0)
    total = len(stock_list)

    # 🔥 Download ALL stocks together
    data = yf.download(
        tickers=stock_list,
        period="max",        # change to 5y if needed
        group_by="ticker",
        auto_adjust=False,
        threads=True
    )

    for i, ticker in enumerate(stock_list):

        try:
            if ticker not in data:
                continue

            df = data[ticker]

            if df.empty or len(df) < 2:
                continue

            today_high = df["High"].iloc[-1]
            previous_ath = df["High"].iloc[:-1].max()

            if today_high > previous_ath:
                st.write(f"🔥 Fresh ATH: {ticker}")
                results.append(ticker)

        except:
            continue

        progress.progress((i + 1) / total)

    return results

# ==========================================
# FUNCTION 2: Get Net Profit
# ==========================================
def get_net_profit_screener(ticker):

    url = f"https://www.screener.in/company/{ticker}/#profit-loss"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except:
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    pl_section = soup.find('section', id='profit-loss')
    if not pl_section:
        return None

    table = pl_section.find('table', class_='data-table')
    if not table:
        return None

    net_profit_row = None
    for row in table.find('tbody').find_all('tr'):
        first_col = row.find('td')
        if first_col and "Net Profit" in first_col.text:
            net_profit_row = row
            break

    if not net_profit_row:
        return None

    years = [th.text.strip() for th in table.find('thead').find_all('th')[1:]]
    values = [td.text.strip() for td in net_profit_row.find_all('td')[1:]]

    return dict(zip(years, values))


# ==========================================
# FUNCTION 3: Get 1Y Return
# ==========================================
def get_1y_return(ticker):

    try:
        data = yf.Ticker(ticker).history(period="1y")

        if data.empty:
            return None

        start_price = data["Close"].iloc[0]
        end_price = data["Close"].iloc[-1]

        return ((end_price / start_price) - 1) * 100

    except:
        return None


# ==========================================
# MAIN BUTTON
# ==========================================

if st.button("🚀 Run Screener"):

    stock_list = df['Ticker'].tolist()

    st.subheader("Checking Fresh ATH Stocks...")
    fresh_ath_stocks = check_fresh_ath_today(stock_list)

    if not fresh_ath_stocks:
        st.warning("No Fresh ATH Stocks Found")
    else:

        scoredf = pd.DataFrame()
        scoredf['Ticker'] = fresh_ath_stocks
        scoredf['ATH price'] = 1
        scoredf['ATH profit'] = 0
        scoredf['Outperformance'] = 0

        # -----------------------------------
        # ATH PROFIT CHECK
        # -----------------------------------
        st.subheader("Checking ATH Profit...")

        for index, row in scoredf.iterrows():

            screener_ticker = row['Ticker'].replace('.NS', '')

            net_profit = get_net_profit_screener(screener_ticker)

            if not net_profit:
                continue

            def clean_number(value):
                value = value.replace(",", "").strip()
                if value in ["", "-", "—"]:
                    return None
                try:
                    return float(value)
                except:
                    return None

            numeric_values = {
                k: clean_number(v)
                for k, v in net_profit.items()
                if clean_number(v) is not None
            }

            if 'TTM' in numeric_values:
                if numeric_values['TTM'] == max(numeric_values.values()):
                    st.write(f"ATH Profit Found: {row['Ticker']} - TTM Net Profit: {numeric_values['TTM']}")
                    scoredf.loc[index, 'ATH profit'] = 1

        # -----------------------------------
        # OUTPERFORMANCE CHECK
        # -----------------------------------
        st.subheader("Checking Outperformance vs BSE 500...")

        benchmark_return = get_1y_return("BSE-500.BO")

        for index, row in scoredf.iterrows():

            stock_return = get_1y_return(row['Ticker'])

            if stock_return and benchmark_return:
                if stock_return > benchmark_return:
                    st.write(f"Outperformance Found: {row['Ticker']} - 1Y Return: {stock_return:.2f}%, Benchmark Return: {benchmark_return:.2f}%")
                    scoredf.loc[index, 'Outperformance'] = 1

        # -----------------------------------
        # FINAL SCORE
        # -----------------------------------
        scoredf['Score'] = (
            scoredf['ATH price'] +
            scoredf['ATH profit'] +
            scoredf['Outperformance']
        )

        scoredf = scoredf.sort_values(by='Score', ascending=False)

        st.subheader("🔥 Final Scored Stocks")
        st.dataframe(scoredf)
