import os
import re
import json
import logging
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "7328702447:AAEVoPdl5XY1Bd9pYLT-r0li7bphVGN0pLY"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUITS = ['♠', '♥', '♦', '♣']
VALUES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
USER_STATES = {}

class GameState:
    def __init__(self):
        self.cards_seen = []
        self.suit_count = defaultdict(int)
        self.value_count = defaultdict(int)
        self.total_cards = 0
    
    def add_card(self, suit: str, value: str):
        self.cards_seen.append({'suit': suit, 'value': value})
        self.suit_count[suit] += 1
        self.value_count[value] += 1
        self.total_cards += 1
    
    def predict(self):
        if self.total_cards < 9:
            return {'suit': '♣', 'value': '8', 'prob': 25.0, 'confidence': 1}
        
        import random
        strategies = [{'suit': random.choice(SUITS), 'value': random.choice(VALUES)} for _ in range(7)]
        suit_votes = {'♠': 0, '♥': 0, '♦': 0, '♣': 0}
        for s in strategies:
            suit_votes[s['suit']] += 1
        
        winner = max(suit_votes, key=suit_votes.get)
        total = sum(suit_votes.values())
        prob = (suit_votes[winner] / total) * 100 if total > 0 else 25
        return {
            'suit': winner,
            'value': random.choice(VALUES),
            'prob': prob,
            'confidence': min(5, max(1, int(prob / 20))),
            'strategies': strategies
        }

def get_state(user_id: int) -> GameState:
    if user_id not in USER_STATES:
        USER_STATES[user_id] = GameState()
    return USER_STATES[user_id]

def parse_cards(text: str) -> list:
    pattern = r'(10|[AJQK2-9])([♠♥♦♣])'
    matches = re.findall(pattern, text)
    return [{'value': m[0], 'suit': m[1]} for m in matches]

def parse_game_id(text: str) -> str:
    match = re.search(r'#?N?(\d+)', text)
    return f"#N{match.group(1)}" if match else None

def format_prediction(prediction: dict, game_id: str = None) -> str:
    suit = prediction['suit']
    value = prediction['value']
    prob = prediction['prob']
    conf = prediction['confidence']
    stars = '⭐' * conf + '☆' * (5 - conf)
    lines = [f"🎯 **PRÉDICTION : {suit} {value}**", "", f"📊 Probabilité : {prob:.1f}%", f"📈 Confiance : {stars}"]
    if game_id:
        lines.insert(0, f"📌 {game_id}")
    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎯 Prédire", callback_data="predict")],
                [InlineKeyboardButton("📊 Stats", callback_data="stats")],
                [InlineKeyboardButton("🔄 Reset", callback_data="reset")]]
    await update.message.reply_text(
        "♠️ **NEXUS v7 · Baccarat** ♥️\n\nEnvoie-moi des cartes :\n`#n1224. ✅9(9♦️Q♥️) - 0(6♣️4♠️)`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text
    if not text:
        return
    
    game_id = parse_game_id(text)
    cards = parse_cards(text)
    if not cards:
        await update.message.reply_text("❌ Format non reconnu.")
        return
    
    for card in cards:
        state.add_card(card['suit'], card['value'])
    
    await update.message.reply_text(f"✅ {len(cards)} cartes enregistrées ! Total : {state.total_cards}")
    
    if state.total_cards >= 9:
        prediction = state.predict()
        await update.message.reply_text(format_prediction(prediction, game_id or f"#N{state.total_cards}"), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    state = get_state(user_id)
    
    if data == "predict":
        if state.total_cards < 9:
            await query.edit_message_text("📭 Envoie au moins 9 cartes !")
            return
        prediction = state.predict()
        await query.edit_message_text(format_prediction(prediction, f"#N{state.total_cards}"), parse_mode="Markdown")
    elif data == "stats":
        if state.total_cards == 0:
            await query.edit_message_text("📭 Aucune carte enregistrée.")
            return
        lines = ["📊 **Statistiques**", "", f"📌 Total : {state.total_cards} cartes"]
        for suit in SUITS:
            count = state.suit_count.get(suit, 0)
            pct = (count / state.total_cards * 100) if state.total_cards > 0 else 0
            lines.append(f"  {suit} : {count} ({pct:.1f}%)")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
    elif data == "reset":
        USER_STATES[user_id] = GameState()
        await query.edit_message_text("🔄 Données réinitialisées !")

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(callback_handler))
        update = Update.de_json(body, None)
        loop.run_until_complete(app.process_update(update))
        return {'statusCode': 200, 'body': json.dumps({'ok': True})}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {'statusCode': 200, 'body': json.dumps({'ok': True})}
