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
            
            # URL-encode message
            encoded_msg = urllib.parse.quote(message)
            
            # Build WhatsApp Web URL
            url = f"https://wa.me/{clean_phone}?text={encoded_msg}"
            
            # Open in browser
            webbrowser.open(url)
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
