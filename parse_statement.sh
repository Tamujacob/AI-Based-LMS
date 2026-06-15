#!/bin/bash
# Parse an Equity Bank statement from Downloads

STATEMENT_FILE="$HOME/Downloads/statement(1).pdf"

echo "=================================================="
echo "  EQUITY BANK STATEMENT PARSER"
echo "=================================================="
echo ""

# Check if file exists
if [ ! -f "$STATEMENT_FILE" ]; then
    echo "❌ File not found: $STATEMENT_FILE"
    exit 1
fi

echo "✓ Found statement file: $STATEMENT_FILE"
echo ""

# Run the parser
cd /home/arjenzjacob/Desktop/AI-Based-LMS
python3 app/core/agents/statement_parser.py "$STATEMENT_FILE"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Parser completed successfully"
else
    echo ""
    echo "❌ Parser encountered an issue"
fi

exit $exit_code
