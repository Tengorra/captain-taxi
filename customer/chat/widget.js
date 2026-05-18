/**
 * Captain Taxi — Live Chat Widget
 *
 * Usage: Add to any page on the Captain Taxi website:
 *
 *   <script>
 *     window.CaptainTaxiChat = { apiUrl: "https://customer.captain.taxi" };
 *   </script>
 *   <script src="https://customer.captain.taxi/chat/widget.js" defer></script>
 *
 * The widget self-initialises after the page loads.
 */

(function () {
  "use strict";

  const cfg = window.CaptainTaxiChat || {};
  const API_URL   = (cfg.apiUrl  || "https://customer.captain.taxi").replace(/\/$/, "");
  const USE_WS    = cfg.websocket !== false;   // Set to false to force polling
  const BRAND     = cfg.brandColor || "#F7B731";
  const FONT      = "'Segoe UI', Arial, sans-serif";

  // ── Session ID (persisted in localStorage) ──────────────────────────────
  function getSessionId() {
    let id = localStorage.getItem("ct_chat_session");
    if (!id) {
      id = "web-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem("ct_chat_session", id);
    }
    return id;
  }

  const SESSION_ID = getSessionId();

  // ── Styles ───────────────────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    #ct-chat-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      width: 60px; height: 60px; border-radius: 50%;
      background: ${BRAND}; border: none; cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,.25);
      display: flex; align-items: center; justify-content: center;
      transition: transform .2s;
    }
    #ct-chat-btn:hover { transform: scale(1.08); }
    #ct-chat-btn svg { width: 28px; height: 28px; fill: #fff; }

    #ct-chat-window {
      position: fixed; bottom: 96px; right: 24px; z-index: 9998;
      width: 340px; max-width: calc(100vw - 48px);
      border-radius: 16px; overflow: hidden;
      box-shadow: 0 8px 32px rgba(0,0,0,.22);
      font-family: ${FONT}; font-size: 14px;
      display: none; flex-direction: column;
      background: #fff;
    }
    #ct-chat-window.open { display: flex; }

    #ct-chat-header {
      background: ${BRAND}; color: #fff; padding: 14px 16px;
      display: flex; align-items: center; gap: 10px;
    }
    #ct-chat-header img { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; }
    #ct-chat-header .ct-title { font-weight: 700; font-size: 15px; flex: 1; }
    #ct-chat-header .ct-sub  { font-size: 11px; opacity: .85; }
    #ct-chat-close { background: none; border: none; color: #fff; cursor: pointer; font-size: 20px; padding: 0 4px; line-height: 1; }

    #ct-chat-messages {
      flex: 1; overflow-y: auto; padding: 14px 12px;
      max-height: 340px; min-height: 180px;
      display: flex; flex-direction: column; gap: 8px;
      background: #f9f9f9;
    }

    .ct-msg {
      max-width: 82%; padding: 9px 13px; border-radius: 14px;
      line-height: 1.45; word-break: break-word;
    }
    .ct-msg.bot  { background: #fff; border: 1px solid #e8e8e8; align-self: flex-start; color: #222; }
    .ct-msg.user { background: ${BRAND}; color: #fff; align-self: flex-end; }
    .ct-typing   { align-self: flex-start; font-style: italic; color: #999; font-size: 13px; }

    #ct-chat-input-row {
      display: flex; padding: 10px 12px; gap: 8px; border-top: 1px solid #eee; background: #fff;
    }
    #ct-chat-input {
      flex: 1; border: 1px solid #ddd; border-radius: 20px;
      padding: 8px 14px; font-size: 14px; font-family: ${FONT};
      outline: none; resize: none;
    }
    #ct-chat-input:focus { border-color: ${BRAND}; }
    #ct-chat-send {
      background: ${BRAND}; color: #fff; border: none; border-radius: 50%;
      width: 38px; height: 38px; cursor: pointer; font-size: 18px; display: flex;
      align-items: center; justify-content: center; flex-shrink: 0;
    }
    #ct-chat-send:hover { opacity: .88; }
  `;
  document.head.appendChild(style);

  // ── DOM ──────────────────────────────────────────────────────────────────
  document.body.insertAdjacentHTML("beforeend", `
    <button id="ct-chat-btn" aria-label="Chat with Captain Taxi">
      <svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>
    </button>

    <div id="ct-chat-window" role="dialog" aria-label="Captain Taxi Chat">
      <div id="ct-chat-header">
        <div>
          <div class="ct-title">Captain Taxi</div>
          <div class="ct-sub">Typically replies instantly</div>
        </div>
        <button id="ct-chat-close" aria-label="Close chat">&times;</button>
      </div>
      <div id="ct-chat-messages"></div>
      <div id="ct-chat-input-row">
        <input id="ct-chat-input" type="text" placeholder="Type a message…" autocomplete="off" maxlength="500" />
        <button id="ct-chat-send" aria-label="Send">&#9658;</button>
      </div>
    </div>
  `);

  const win     = document.getElementById("ct-chat-window");
  const btn     = document.getElementById("ct-chat-btn");
  const closeBtn= document.getElementById("ct-chat-close");
  const msgs    = document.getElementById("ct-chat-messages");
  const input   = document.getElementById("ct-chat-input");
  const sendBtn = document.getElementById("ct-chat-send");

  let ws       = null;
  let isOpen   = false;
  let greeted  = false;

  function addMsg(text, role) {
    const el = document.createElement("div");
    el.className = "ct-msg " + (role === "user" ? "user" : "bot");
    el.textContent = text;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
    return el;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "ct-typing";
    el.id = "ct-typing-indicator";
    el.textContent = "Captain Taxi is typing…";
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById("ct-typing-indicator");
    if (el) el.remove();
  }

  // ── WebSocket transport ───────────────────────────────────────────────────
  function connectWS() {
    const wsUrl = API_URL.replace(/^http/, "ws") + "/chat/ws/" + SESSION_ID;
    ws = new WebSocket(wsUrl);

    ws.onmessage = function (e) {
      const data = JSON.parse(e.data);
      if (data.type === "typing") {
        showTyping();
      } else if (data.type === "message" && data.role === "assistant") {
        hideTyping();
        addMsg(data.content, "bot");
      }
    };

    ws.onclose = function () {
      ws = null;
      // Reconnect after 3s if window is open
      if (isOpen) setTimeout(connectWS, 3000);
    };

    ws.onerror = function () {
      ws && ws.close();
    };
  }

  // ── Polling transport ─────────────────────────────────────────────────────
  async function sendPoll(text) {
    showTyping();
    try {
      const resp = await fetch(API_URL + "/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID, message: text }),
      });
      const data = await resp.json();
      hideTyping();
      addMsg(data.reply, "bot");
    } catch {
      hideTyping();
      addMsg("Sorry, I couldn't connect. Please call 306-242-0000.", "bot");
    }
  }

  // ── Send message ──────────────────────────────────────────────────────────
  function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    addMsg(text, "user");
    input.value = "";

    if (USE_WS && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ content: text }));
    } else {
      sendPoll(text);
    }
  }

  // ── Open / close ──────────────────────────────────────────────────────────
  function openChat() {
    isOpen = true;
    win.classList.add("open");
    btn.style.display = "none";
    input.focus();

    if (USE_WS && !ws) connectWS();

    if (!greeted) {
      greeted = true;
      // If WS, greeting comes from server on connect; for polling show client-side greeting
      if (!USE_WS) {
        addMsg(
          "Hi! Welcome to Captain Taxi. I can book a ride, give ETAs, cancel bookings, or answer questions. How can I help?",
          "bot"
        );
      }
    }
  }

  function closeChat() {
    isOpen = false;
    win.classList.remove("open");
    btn.style.display = "";
  }

  btn.addEventListener("click", openChat);
  closeBtn.addEventListener("click", closeChat);
  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
})();
