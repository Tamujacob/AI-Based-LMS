"""
app/core/agents/whatsapp_quick.py
──────────────────────────────────────────────────────────────
Quick WhatsApp integration — NO EXTERNAL APPROVALS NEEDED

Two modes:
  1. "Open WhatsApp" — Opens WhatsApp Web with pre-filled message
     User clicks → browser opens wa.me link → message pre-filled
     → User clicks Send manually (requires internet but NO approval)
  
  2. "Copy Message" — Copies message to clipboard
     User clicks → message copied → paste into WhatsApp manually
     → Works completely offline

Author: Bingongold Credit
"""

import urllib.parse
import webbrowser


class QuickWhatsApp:
    """
    Utility for WhatsApp integration without external APIs.
    Safe for background threads. Never blocks UI.
    """
    # Track which phone chats we've opened during this app session so we
    # don't repeatedly open new browser tabs for the same contact.
    _opened_chats = set()
    # Whether the last call actually opened a browser tab (True) or only
    # copied the message to clipboard (False). Callers may read this to
    # decide which user-facing message to show.
    _last_opened = False

    @staticmethod
    def open_whatsapp_chat(phone: str, message: str) -> bool:
        """
        Open WhatsApp Web with pre-filled message.
        
        Flow:
          1. Clean phone number (handle various formats)
          2. Build wa.me URL with pre-filled message
          3. Open in default browser
          4. User sees WhatsApp Web with message ready to send
        
        Args:
            phone: Phone number (any format: 0701234567, +256701234567, 256701234567)
            message: Message text to pre-fill
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Normalize phone: remove spaces, +, dashes
            clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "")
            
            # Uganda format: 0701234567 → 256701234567
            if clean_phone.startswith("0"):
                clean_phone = "256" + clean_phone[1:]
            
            # If we've already opened a chat for this phone during this
            # session, don't call the browser again (that creates another
            # tab). Instead just copy the message to clipboard so the user
            # can paste into the existing WhatsApp tab.
            if clean_phone in QuickWhatsApp._opened_chats:
                QuickWhatsApp.copy_to_clipboard(message)
                QuickWhatsApp._last_opened = False
                return True

            # Build stable WhatsApp Web chat URL for the phone number.
            url = f"https://web.whatsapp.com/send?phone={clean_phone}"

            # Attempt to find an existing Chrome/Chromium instance with
            # remote debugging enabled and reuse an open WhatsApp Web tab
            # by instructing it to navigate to the chat URL. This avoids
            # creating a new tab each time. If this fails, fall back to
            # opening the URL in the default browser.
            try:
                # Import lazily so the feature is optional.
                import requests
                import json
                from websocket import create_connection

                devtools_url = "http://127.0.0.1:9222/json"
                resp = requests.get(devtools_url, timeout=0.6)
                targets = resp.json()
                # Prefer a tab that already has web.whatsapp.com open.
                for t in targets:
                    tu = t.get("url", "")
                    ws_url = t.get("webSocketDebuggerUrl")
                    if tu and "web.whatsapp.com" in tu and ws_url:
                        try:
                            ws = create_connection(ws_url, timeout=1)
                            # Send Page.navigate to the target to reuse the tab
                            msg = json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}})
                            ws.send(msg)
                            ws.close()
                            QuickWhatsApp.copy_to_clipboard(message)
                            QuickWhatsApp._opened_chats.add(clean_phone)
                            QuickWhatsApp._last_opened = True
                            return True
                        except Exception:
                            # If navigating this tab fails, try next target
                            continue
            except Exception:
                # Remote debugging not available or an error occurred —
                # we'll fall back to opening a new tab below.
                pass

            # Copy the message to clipboard and open the chat in browser
            # (fallback behavior).
            QuickWhatsApp.copy_to_clipboard(message)
            webbrowser.open(url, new=0, autoraise=True)
            QuickWhatsApp._opened_chats.add(clean_phone)
            QuickWhatsApp._last_opened = True
            return True
            
        except Exception as e:
            print(f"[WhatsApp] Error opening chat: {e}")
            return False

    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        """
        Copy text to system clipboard (works offline).
        
        Args:
            text: Text to copy
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Cross-platform clipboard using tkinter (no external deps)
            import tkinter as tk
            
            root = tk.Tk()
            root.withdraw()  # Hide window
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()  # Process clipboard write
            root.destroy()
            
            return True
            
        except Exception as e:
            print(f"[WhatsApp] Error copying to clipboard: {e}")
            return False

    @staticmethod
    def format_reminder_for_whatsapp(
        loan_number: str,
        client_name: str,
        amount_due: float,
        due_date: str,
        days_until: int,
        message: str,
    ) -> str:
        """
        Format a complete reminder message with metadata footer.
        
        Args:
            loan_number: Loan ID
            client_name: Borrower name
            amount_due: Payment amount
            due_date: Due date string
            days_until: Days until/past due
            message: Main reminder message
        
        Returns:
            Formatted message ready for WhatsApp
        """
        status = ""
        if days_until < 0:
            status = f"⚠️  {abs(days_until)} days OVERDUE"
        elif days_until == 0:
            status = "📌 DUE TODAY"
        else:
            status = f"📅 Due in {days_until} day(s)"
        
        footer = (
            f"\n\n"
            f"─────────────────────\n"
            f"Loan: {loan_number}\n"
            f"Amount: UGX {amount_due:,.0f}\n"
            f"Due Date: {due_date}\n"
            f"{status}\n"
            f"\nBingongold Credit — Together as One"
        )
        
        return message + footer
