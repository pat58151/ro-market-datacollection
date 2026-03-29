import json
import os
from datetime import datetime, timezone

REMINDERS_FILE = 'price_reminders.json'


def load_reminders():
    """Load price reminders from file"""
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {REMINDERS_FILE} corrupted. Creating a new one.")
            return {}
    return {}


def save_reminders(reminders):
    """Save price reminders to file"""
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, indent=2, ensure_ascii=False)


def add_reminder(user_id, item_name, server_name, target_price, alert_type='lower'):
    """
    Add or update a price reminder for a user
    alert_type: 'lower' or 'higher'
    """
    reminders = load_reminders()
    # Key now includes alert_type to allow both lower and higher for same item
    key = f"{item_name.lower()}||{server_name.lower()}||{alert_type}"

    if key not in reminders:
        reminders[key] = []

    for reminder in reminders[key]:
        if reminder['user_id'] == str(user_id):
            reminder['target_price'] = target_price
            reminder['timestamp'] = datetime.now(timezone.utc).isoformat()
            save_reminders(reminders)
            return False

    reminders[key].append({
        'user_id': str(user_id),
        'target_price': target_price,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

    save_reminders(reminders)
    return True  # Created new


def remove_reminder(user_id, item_name, server_name, alert_type=None):
    """
    Remove a price reminder for a user
    If alert_type is None, removes both lower and higher alerts
    """
    reminders = load_reminders()
    removed = False

    if alert_type:
        # Remove specific alert type
        key = f"{item_name.lower()}||{server_name.lower()}||{alert_type}"
        if key in reminders:
            original_len = len(reminders[key])
            reminders[key] = [r for r in reminders[key] if r['user_id'] != str(user_id)]
            removed = len(reminders[key]) < original_len

            if not reminders[key]:
                del reminders[key]
    else:
        # Remove both lower and higher alerts
        for alert_t in ['lower', 'higher']:
            key = f"{item_name.lower()}||{server_name.lower()}||{alert_t}"
            if key in reminders:
                original_len = len(reminders[key])
                reminders[key] = [r for r in reminders[key] if r['user_id'] != str(user_id)]
                if len(reminders[key]) < original_len:
                    removed = True

                if not reminders[key]:
                    del reminders[key]

    save_reminders(reminders)
    return removed


def get_user_reminders(user_id):
    """Return all reminders belonging to a given user"""
    reminders = load_reminders()
    user_reminders = []

    for key, reminder_list in reminders.items():
        try:
            item_name, server_name, alert_type = key.rsplit('||', 2)
        except ValueError:
            continue

        for r in reminder_list:
            if r['user_id'] == str(user_id):
                user_reminders.append({
                    'item_name': item_name,
                    'server_name': server_name,
                    'target_price': r['target_price'],
                    'alert_type': alert_type
                })
    return user_reminders

def get_all_reminders():
    """Return a flat list of all reminders from all users"""
    reminders = load_reminders()
    all_reminders = []

    for key, reminder_list in reminders.items():
        try:
            item_name, server_name, alert_type = key.rsplit('||', 2)
        except ValueError:
            continue

        for r in reminder_list:
            all_reminders.append({
                'user_id': r['user_id'],
                'item_name': item_name,
                'server_name': server_name,
                'target_price': r['target_price'],
                'alert_type': alert_type
            })
    return all_reminders


def parse_reminder_args(args: str):
    """
    Parse '!remindme <lower|higher> <item> <server> <price>'
    Returns: (item_name, server_name, target_price, alert_type)
    """
    parts = args.split()
    if len(parts) < 4:
        return None, None, None, None

    # First part should be 'lower' or 'higher'
    alert_type = parts[0].lower()
    if alert_type not in ['lower', 'higher']:
        return None, None, None, None

    try:
        # The price is the last part
        target_price = float(parts[-1].replace(',', ''))
    except ValueError:
        return None, None, None, None

    # The server name is the second to last part
    server_name = parts[-2]
    # The item name is everything between alert_type and server name
    item_name = ' '.join(parts[1:-2])

    return item_name.strip(), server_name.strip(), target_price, alert_type


def parse_forget_args(args: str):
    """
    Parse '!forgetme <item> <server> [lower|higher]'
    If alert_type is not specified, both will be removed
    """
    parts = args.split()
    if len(parts) < 2:
        return None, None, None

    # Check if last part is an alert type
    if parts[-1].lower() in ['lower', 'higher']:
        alert_type = parts[-1].lower()
        server_name = parts[-2]
        item_name = ' '.join(parts[:-2])
    else:
        alert_type = None  # Remove both
        server_name = parts[-1]
        item_name = ' '.join(parts[:-1])

    return item_name.strip(), server_name.strip(), alert_type


def should_trigger_alert(current_price, target_price, alert_type):
    """
    Check if an alert should be triggered based on alert type
    alert_type: 'lower' or 'higher'
    """
    if alert_type == 'lower':
        return current_price <= target_price
    elif alert_type == 'higher':
        return current_price >= target_price
    return False