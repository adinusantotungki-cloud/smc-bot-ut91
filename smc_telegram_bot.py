import ccxt
import pandas as pd
import numpy as np
import telebot
from datetime import datetime

# =========================================================
# KONFIGURASI BOT & TELEGRAM (MASUKKAN DATA KAMU DI SINI)
# =========================================================
TELEGRAM_BOT_TOKEN = "8653442759:AAHWybcQGcPw7MF0-fwbWTWDjbrHrbmEpQ8"
MY_CHAT_ID = "1786601771"  # Angka Chat ID dari userinfobot

SYMBOL = 'BTC/USDT'
ACCOUNT_BALANCE = 10000  # Simulasi Balance ($)
RISK_PER_TRADE = 0.01    # Risiko 1% per transaksi

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
exchange = ccxt.binance()

# =========================================================
# FUNGSI PENGAMBILAN DATA MARKET (VIA CCXT / BINANCE API)
# =========================================================
def get_market_data(timeframe, limit=200):
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['time_dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error Fetch Data {timeframe}: {e}")
        return None

def find_swings(df, left=3, right=3):
    df['swing_high'] = False
    df['swing_low'] = False
    for i in range(left, len(df) - right):
        if df['high'].iloc[i] == df['high'].iloc[i - left:i + right + 1].max():
            df.loc[df.index[i], 'swing_high'] = True
        if df['low'].iloc[i] == df['low'].iloc[i - left:i + right + 1].min():
            df.loc[df.index[i], 'swing_low'] = True
    return df

# =========================================================
# ENGINE ANALISIS INSTITUSIONAL SMC
# =========================================================
def analyze_smc():
    # 1. FASE 1: MAKRO-KONTEKSTUAL (H4)
    df_h4 = get_market_data('4h', 200)
    if df_h4 is None: return "❌ Gagal mengambil data market dari server."
    df_h4 = find_swings(df_h4)
    
    sh_h4 = df_h4[df_h4['swing_high']]['high'].iloc[-1] if not df_h4[df_h4['swing_high']].empty else df_h4['high'].max()
    sl_h4 = df_h4[df_h4['swing_low']]['low'].iloc[-1] if not df_h4[df_h4['swing_low']].empty else df_h4['low'].min()
    current_price = df_h4.iloc[-1]['close']
    
    macro_bias = "BULLISH" if current_price > (sh_h4 + sl_h4)/2 else "BEARISH"
    
    # Dealing Range & Discount/Premium Zone
    highest_h4, lowest_h4 = df_h4.tail(60)['high'].max(), df_h4.tail(60)['low'].min()
    range_total = highest_h4 - lowest_h4
    eq_level = lowest_h4 + (range_total / 2)
    
    is_discount = current_price < eq_level
    is_premium = current_price > eq_level

    # 2. FASE 2: FILTER LIKUIDITAS (M15)
    df_m15 = get_market_data('15m', 100)
    df_m15 = find_swings(df_m15, 2, 2)
    sh_m15 = df_m15[df_m15['swing_high']]['high'].iloc[-1]
    sl_m15 = df_m15[df_m15['swing_low']]['low'].iloc[-1]
    curr_m15 = df_m15.iloc[-1]
    
    sweep_bull = curr_m15['low'] < sl_m15 and curr_m15['close'] > sl_m15
    sweep_bear = curr_m15['high'] > sh_m15 and curr_m15['close'] < sh_m15
    liquidity_swept = sweep_bull or sweep_bear

    # 3. FASE 3: EKSEKUSI MIKRO (M5)
    df_m5 = get_market_data('5m', 100)
    df_m5 = find_swings(df_m5, 2, 2)
    sh_m5 = df_m5[df_m5['swing_high']]['high'].iloc[-1]
    sl_m5 = df_m5[df_m5['swing_low']]['low'].iloc[-1]
    curr_m5 = df_m5.iloc[-1]
    
    choch_bull = curr_m5['close'] > sh_m5
    choch_bear = curr_m5['close'] < sl_m5
    choch_valid = choch_bull or choch_bear
    
    # Micro Stop Loss Calculation
    entry_price = current_price
    if macro_bias == "BULLISH":
        sl_price = curr_m5['low'] - 15.0
        risk_points = entry_price - sl_price
        tp1 = entry_price + (risk_points * 2)
        tp2 = entry_price + (risk_points * 4)
    else:
        sl_price = curr_m5['high'] + 15.0
        risk_points = sl_price - entry_price
        tp1 = entry_price - (risk_points * 2)
        tp2 = entry_price - (risk_points * 4)

    if risk_points <= 0: risk_points = 10.0

    # CHECKLIST MATRIKS (1-5)
    score = 1 # Bias Makro selalu 1
    c1 = f"✅ Bias Makro H4 ({macro_bias})"
    
    zone_valid = (macro_bias == "BULLISH" and is_discount) or (macro_bias == "BEARISH" and is_premium)
    if zone_valid: score += 1
    c2 = f"{'✅' if zone_valid else '❌'} Zona Harga ({'Discount' if is_discount else 'Premium'})"
    
    if liquidity_swept: score += 1
    c3 = f"{'✅' if liquidity_swept else '❌'} Liquidity Sweep M15"
    
    if choch_valid: score += 1
    c4 = f"{'✅' if choch_valid else '❌'} CHoCH Confirmation M5"
    
    c5 = "⚠️ Waktu & News (Cek Manual Red Folder)"

    # POSITION SIZING (1% RISK)
    risk_amount = ACCOUNT_BALANCE * RISK_PER_TRADE
    lot_size = risk_amount / risk_points

    # FORMAT PESAN TELEGRAM
    status_icon = "🚀" if score >= 4 else ("⚠️" if score == 3 else "⏸️")
    status_title = "HIGH PROBABILITY SETUP" if score >= 4 else ("MEDIUM PROBABILITY" if score == 3 else "NO TRADE ZONE (WAIT)")
    
    msg = f"🏛️ *SMC INSTITUTIONAL ANALYZER (BTC/USDT)*\n"
    msg += f"⏰ *Waktu:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB`\n"
    msg += f"💰 *Harga Saat Ini:* `${current_price:,.2f}`\n\n"
    
    msg += f"📋 *CHECKLIST KONFLUENSI ({score}/5):*\n"
    msg += f"1. {c1}\n2. {c2}\n3. {c3}\n4. {c4}\n5. {c5}\n\n"
    
    msg += f"-----------------------------------------\n"
    msg += f"{status_icon} *STATUS: {status_title}*\n"
    msg += f"-----------------------------------------\n"
    
    if score >= 3:
        msg += f"🎯 *Arah Posisi:* `{macro_bias}`\n"
        msg += f"📍 *Entry Limit:* `${entry_price:,.2f}`\n"
        msg += f"🛑 *Stop Loss:* `${sl_price:,.2f}` (Micro SL M5)\n"
        msg += f"🎯 *TP 1 (RR 1:2):* `${tp1:,.2f}` (Close 50% + BEP)\n"
        msg += f"🎯 *TP 2 (RR 1:4+):* `${tp2:,.2f}` (Runner Target)\n"
        msg += f"⚖️ *Rekomendasi Lot:* `{lot_size:.3f} Lot` (Max Risk 1% = ${risk_amount})\n"
    else:
        msg += "💡 *Saran:* Fase institusi belum terbentuk sempurna. Algoritma menolak entry berkualitas rendah untuk melindungi modal Anda.\n"

    return msg

# =========================================================
# BOT TELEGRAM COMMAND HANDLERS
# =========================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 *Selamat Datang di SMC Institutional Bot!*\n\n"
        "Ketik /analisa dari HP kamu kapan saja untuk mendapatkan analisis "
        "BTC/USDT multi-timeframe berbasis algoritma Smart Money Concepts."
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['analisa'])
def handle_analisa(message):
    bot.reply_to(message, "⏳ *Sedang memproses analisis SMC multi-timeframe... Mohon tunggu 3-5 detik.*", parse_mode='Markdown')
    result_msg = analyze_smc()
    bot.send_message(message.chat.id, result_msg, parse_mode='Markdown')

if __name__ == "__main__":
    print("Bot SMC Telegram aktif dan siap menerima perintah...")
    bot.infinity_polling()
