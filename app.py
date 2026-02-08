from flask import Flask, render_template, request, redirect, url_for
from langchain_groq import  ChatGroq
from dotenv import load_dotenv
import os, sqlite3, datetime

app = Flask(__name__)

# ---- Configuration ----
load_dotenv()
llm =  ChatGroq(model='llama-3.1-8b-instant', groq_api_key=os.getenv('GROQ_API_KEY'))
DB_FILE = "chatbot.db"

# ---- DB SETUP ----
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Chats table
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at TEXT
                )''')
    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    sender TEXT,
                    text TEXT,
                    created_at TEXT,
                    FOREIGN KEY(chat_id) REFERENCES chats(id)
                )''')
    conn.commit()
    conn.close()
     
init_db()

# ---- ROUTES ----

@app.route("/")
def home():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats ORDER BY created_at DESC")
    chats = c.fetchall()
    conn.close()

    if chats:
        return redirect(url_for("view_chat", chat_id=chats[0][0]))
    else:
        return redirect(url_for("new_chat"))

@app.route("/chat/<int:chat_id>")
def view_chat(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # All chats for sidebar
    c.execute("SELECT id, title FROM chats ORDER BY created_at DESC")
    all_chats = c.fetchall()
    # Messages for this chat
    c.execute("SELECT sender, text FROM messages WHERE chat_id=? ORDER BY created_at ASC", (chat_id,))
    chat_history = [{"sender": row[0], "text": row[1]} for row in c.fetchall()]
    conn.close()

    return render_template("index.html", chats=all_chats, chat_history=chat_history, current_chat=chat_id)

@app.route("/new_chat")
def new_chat():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Create new chat
    c.execute("INSERT INTO chats (title, created_at) VALUES (?, ?)", (f"Chat {now}", now))
    chat_id = c.lastrowid
    # Initial AI message
    c.execute("INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
              (chat_id, "ai", "Assalam O alaikum Dear! How can I help you today?", now))
    conn.commit()
    conn.close()
    return redirect(url_for("view_chat", chat_id=chat_id))

@app.route("/send/<int:chat_id>", methods=["POST"])
def send_message(chat_id):
    user_message = request.form.get("message", "").strip()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_message:
        # 1️⃣ Store user message
        with sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, "user", user_message, now)
            )
            conn.commit()

        # 2️⃣ Fetch last 10 messages for memory (token-safe)
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT sender, text FROM messages
                WHERE chat_id=?
                ORDER BY created_at DESC
                LIMIT 10
            """, (chat_id,))
            rows = c.fetchall()

        # Reverse to maintain correct order
        rows = list(reversed(rows))

        # 3️⃣ Build conversation string
        conversation = ""
        for sender, text in rows:
            role = "User" if sender == "user" else "AI"
            conversation += f"{role}: {text}\n"


        # 4️⃣ Prepare AI prompt   
        prompt = f"""
You are a friendly AI assistant.
Always reply in short, direct sentences.
Do NOT give extra explanations.

Conversation so far:
{conversation}

User: {user_message}
"""
        # 5️⃣ Call AI
        ai_response = llm.invoke(prompt)
        ai_reply = ai_response.content.strip()

        # 6️⃣ Store AI response
        with sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, "ai", ai_reply, now)
            )
            conn.commit()

    return redirect(url_for("view_chat", chat_id=chat_id))

# ---- RUN APP ----
if __name__ == "__main__":
    app.run(debug=True)






