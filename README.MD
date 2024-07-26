# Sentinel  Bot

This bot provides a full suite  of complex action for telegram and discord simultaneuosly, it allows admins to protect and safeguard their communities all from the comfort of a few keyboard strokes, the code is fully modular and can be utilized across several platforms simultanueosly utlizing a central dtatabse to protect users


# Project Title

## Installation


### Install the required dependencies

\```bash
pip install -r requirements.txt
\```

### Set up the MySQL database

1. Create a MySQL database and a user with the necessary privileges.
2. Import the provided SQL schema to set up the required tables.

### Set up YARA rules

Ensure you have a valid `malware_rules.yar` file in the same directory as the script.

## Configuration

### Configure the bot

Update the following variables in the script with your own credentials:

\```python
api_id = 'your_api_id'
api_hash = 'your_api_hash'
bot_token = 'your_bot_token'
admin_user_id = your_admin_user_id
\```

## Usage

### Run the bot

\```bash
python bot.py
\```

### Commands

- `/escrow <sender_id> <receiver_id>`: Initiate an escrow transaction between two users in a group.
- `/addsub <user_id> <days>`: Add or update a subscription for a user.
- `/checksub <user_id>`: Check a user's subscription status.
- `/user @username`: Get the user ID of a username.
- `/commands`: Show the list of available commands.
- `/addbannedword <word>`: Add a word to the banned list.
- `/removebannedword <word>`: Remove a word from the banned list.
- `/listbannedwords`: List all banned words.

### Inline Buttons

- **Sent**: Confirm that funds have been sent to the escrow wallet.
- **Cancel Escrow**: Cancel the escrow transaction.
- **Yes**: Confirm satisfaction with the escrow contract.
- **No**: Deny satisfaction with the escrow contract.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Contact

For any questions or support, please open an issue on GitHub or contact me at [sylvesterdivine@outlook.com].

